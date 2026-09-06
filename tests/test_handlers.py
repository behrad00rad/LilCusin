import unittest
from unittest.mock import AsyncMock, patch

from aiogram import Bot
from aiogram.types import Update

from music_bot import messages
from music_bot.submissions import InvalidSubmission
from tests.support import dispatcher


class HandlerTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.dispatcher = dispatcher

    async def asyncSetUp(self):
        self.bot = Bot("123456:TEST_ONLY_FAKE_TOKEN")
        self.service = AsyncMock()
        self.answer_patch = patch("aiogram.types.Message.answer", new_callable=AsyncMock)
        self.answer = self.answer_patch.start()
        self.present_patch = patch("music_bot.handlers.present", new_callable=AsyncMock)
        self.present_patch.start()

    async def asyncTearDown(self):
        self.answer_patch.stop()
        self.present_patch.stop()
        await self.bot.session.close()

    async def send(self, **fields):
        update = Update.model_validate({"update_id": 1, "message": {
            "message_id": 1, "date": 1700000000,
            "chat": {"id": 123, "type": "private"},
            "from": {"id": 123, "is_bot": False, "first_name": "Test"},
            **fields,
        }})
        await self.dispatcher.feed_update(self.bot, update, submissions=self.service,
                                          workflow=AsyncMock(), enrichment=AsyncMock())

    async def test_commands_preserved_and_not_saved(self):
        for command, response in [("/start", messages.START), ("/help", messages.HELP)]:
            await self.send(text=command)
            self.answer.assert_called_with(response)
        await self.send(text="/unknown - song")
        self.service.submit_text.assert_not_called()

    async def test_text_dispatches_and_responds(self):
        self.service.submit_text.return_value.parsed_artist = "گوگوش"
        self.service.submit_text.return_value.parsed_title = "Song"
        await self.send(text="گوگوش — Song")
        self.service.submit_text.assert_awaited_once()
        self.assertIn("گوگوش", self.answer.call_args.args[0])
        self.assertIn("Received", self.answer.call_args.args[0])

    async def test_bad_text_explains_format(self):
        self.service.submit_text.side_effect = InvalidSubmission()
        await self.send(text="invalid")
        self.answer.assert_called_with(messages.INVALID_TEXT)

    async def test_forwarded_audio_without_metadata(self):
        await self.send(
            audio={"file_id": "f", "file_unique_id": "u", "duration": 50},
            forward_origin={"type": "hidden_user", "sender_user_name": "Other", "date": 1700000000},
        )
        user, audio = self.service.submit_audio.call_args.args
        self.assertEqual(user.telegram_user_id, 123)
        self.assertIsNone(audio.performer)
        self.assertIsNone(audio.title)
        self.assertIn(messages.UNKNOWN, self.answer.call_args.args[0])

    async def test_voice_not_saved(self):
        await self.send(voice={"file_id": "f", "file_unique_id": "u", "duration": 10})
        self.service.submit_audio.assert_not_called()
        self.answer.assert_called_with(messages.UNSUPPORTED)
