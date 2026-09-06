from dataclasses import replace
import asyncio
from unittest.mock import AsyncMock, patch

from aiogram import Bot
from aiogram.types import Message, Update
from sqlalchemy import func, select

from music_bot import messages
from music_bot.enrichment import Enrichment
from music_bot.interactions import parse_callback
from music_bot.models import Rating, SongSubmission
from music_bot.providers.common import Failure, ProviderError
from tests.support import ServiceTestCase, dispatcher
from tests.test_workflow import EXACT


class FlowHandlerTests(ServiceTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.bot = Bot("123456:TEST_ONLY_FAKE_TOKEN")
        self.outgoing = []
        self.enrichment = Enrichment(self.database, self.providers)

        async def answer(text, **kwargs):
            self.outgoing.append((text, kwargs))
            return self.message(1000 + len(self.outgoing), text=text)

        self.patches = [patch("aiogram.types.Message.answer", side_effect=answer),
                        patch("aiogram.types.Message.edit_reply_markup", new_callable=AsyncMock),
                        patch("aiogram.types.CallbackQuery.answer", new_callable=AsyncMock)]
        self.answer, self.edit, self.ack = [p.start() for p in self.patches]

    async def asyncTearDown(self):
        await self.enrichment.close()
        for p in self.patches:
            p.stop()
        await self.bot.session.close()
        await super().asyncTearDown()

    def message(self, message_id=1, user=123, **fields):
        return Message.model_validate({"message_id": message_id, "date": 1700000000,
                                       "chat": {"id": user, "type": "private"},
                                       "from": {"id": user, "is_bot": False, "first_name": "Test"}, **fields})

    async def feed(self, **fields):
        await dispatcher.feed_update(self.bot, Update(update_id=1, **fields),
                                     submissions=self.submissions, workflow=self.workflow,
                                     enrichment=self.enrichment,
                                     audio_analysis=getattr(self, "audio_analysis", None))

    async def callback(self, data, user=123):
        update = Update.model_validate({"update_id": 2, "callback_query": {
            "id": "callback", "from": {"id": user, "is_bot": False, "first_name": "Test"},
            "chat_instance": "test", "data": data,
            "message": self.message(1000, user=user, text="buttons").model_dump(mode="json"),
        }})
        await self.feed(callback_query=update.callback_query)

    async def test_text_identify_rate_and_change(self):
        async def call(provider, method, *args):
            if method == "search_tracks":
                return [EXACT]
            raise ProviderError(Failure.NETWORK)  # Ratings still work.

        self.providers.call.side_effect = call
        await self.feed(message=self.message(text="Artist - Song"))
        keyboard = self.outgoing[-1][1]["reply_markup"]
        data = keyboard.inline_keyboard[0][0].callback_data
        self.assertIn(messages.RATING_QUESTION, self.outgoing[-1][0])
        await self.callback(data)
        await self.callback(data)
        await self.callback(data.replace("love", "dislike"))
        self.assertEqual(self.ack.await_count, 3)
        selected = self.edit.call_args.kwargs["reply_markup"].inline_keyboard[0][-1].text
        self.assertTrue(selected.startswith("✓"))
        async with self.database.sessions() as session:
            self.assertEqual(await session.scalar(select(Rating.value)), "dislike")
            self.assertEqual(await session.scalar(select(func.count()).select_from(Rating)), 1)

    async def test_audio_with_metadata_and_confirmation(self):
        self.providers.call.return_value = [replace(EXACT, title="Songs", external_ids={})]
        await self.feed(message=self.message(audio={"file_id": "f", "file_unique_id": "u", "duration": 100,
                                                   "performer": "Artist", "title": "Song"}))
        data = self.outgoing[-1][1]["reply_markup"].inline_keyboard[0][0].callback_data
        self.assertLessEqual(len(data.encode()), 64)
        await self.callback(data, user=456)
        self.ack.assert_called_with(messages.STALE)
        await self.callback(data)
        self.assertIn(messages.RATING_QUESTION, self.outgoing[-1][0])

    async def test_audio_missing_metadata_correction(self):
        await self.feed(message=self.message(audio={"file_id": "f", "file_unique_id": "u", "duration": 10}))
        self.assertEqual(self.outgoing[-1][0], messages.MISSING)
        prompt = self.message(1000 + len(self.outgoing), text=messages.MISSING)
        self.providers.call.return_value = [EXACT]
        await self.feed(message=self.message(2, text="Artist — Song", reply_to_message=prompt))
        self.assertIn(messages.RATING_QUESTION, self.outgoing[-1][0])
        async with self.database.sessions() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(SongSubmission)), 1)

    async def test_none_and_cancel_stale_reply(self):
        self.providers.call.return_value = [replace(EXACT, title="Songs", external_ids={})]
        await self.feed(message=self.message(text="Artist - Song"))
        data = self.outgoing[-1][1]["reply_markup"].inline_keyboard[-1][0].callback_data
        await self.callback(data)
        prompt = self.message(1000 + len(self.outgoing), text=messages.CORRECTION)
        await self.feed(message=self.message(3, text="/cancel"))
        await self.feed(message=self.message(4, text="Artist - Song", reply_to_message=prompt))
        self.assertEqual(self.outgoing[-1][0], messages.STALE)

    async def test_malformed_and_stale_callbacks_answered(self):
        for data in ("", "r:1:skip", "r:999:love", "c:1:-1:0", "c:1:0:9", "user text" * 20):
            if data != "r:999:love":
                self.assertIsNone(parse_callback(data))
            await self.callback(data)
            self.ack.assert_called_with(messages.STALE)
        self.assertEqual(self.ack.await_count, 6)

    async def test_private_chats_only(self):
        message = self.message(text="Artist - Song", chat={"id": -100, "type": "group"})
        await self.feed(message=message)
        self.assertEqual(self.outgoing[-1][0], messages.PRIVATE_ONLY)
        async with self.database.sessions() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(SongSubmission)), 0)

    async def test_rating_responsive_while_audio_analysis_runs(self):
        from music_bot.audio.service import AudioAnalysisService
        from music_bot.config import Config
        from music_bot.models import AudioAnalysis
        from tests.audio_fixture import feature_result

        self.audio_analysis = AudioAnalysisService(self.database, self.bot, Config("fake", "fake"))
        started, release = asyncio.Event(), asyncio.Event()
        async def slow(path):
            started.set()
            await release.wait()
            return feature_result()
        async def provider(provider, method, *args):
            if method == "search_tracks":
                return [EXACT]
            raise ProviderError(Failure.NETWORK)
        self.providers.call.side_effect = provider
        with patch("music_bot.audio.service.available", return_value=True), \
             patch("music_bot.audio.service.download_audio", new_callable=AsyncMock), \
             patch("music_bot.audio.service.convert_audio", new_callable=AsyncMock), \
             patch("music_bot.audio.service.analyse_audio", side_effect=slow), \
             patch("aiogram.Bot.send_message", new_callable=AsyncMock):
            try:
                await self.feed(message=self.message(audio={"file_id": "f", "file_unique_id": "u", "duration": 12,
                                                           "performer": "Artist", "title": "Song"}))
                data = self.outgoing[-1][1]["reply_markup"].inline_keyboard[0][0].callback_data
                await asyncio.wait_for(started.wait(), 2)
                await asyncio.wait_for(self.callback(data), 1)
                async with self.database.sessions() as session:
                    self.assertEqual(await session.scalar(select(Rating.value)), "love")
                    self.assertEqual(await session.scalar(select(AudioAnalysis.status)), "processing")
                release.set()
                await asyncio.gather(*list(self.audio_analysis.tasks.values()))
            finally:
                await self.audio_analysis.close()
