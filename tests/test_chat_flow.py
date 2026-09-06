"""Six focused private-chat recommendation/privacy integration scenarios."""

from unittest.mock import AsyncMock, patch

from aiogram import Bot
from aiogram.types import Message, Update
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import SendMessage
from sqlalchemy import delete, func, select, update

from music_bot import messages as M
from music_bot.chat_service import ChatService
from music_bot.chat_ui import safe_url
from music_bot.models import AudioAnalysis, ChatControl, IdentificationFlow, Rating, RecommendationHistory, SongSubmission, Track, User, utc_now
from music_bot.recommendations import RecommendationService
from music_bot.submissions import Submitter
from tests.support import ServiceTestCase, dispatcher
from tests.recommendation_fixture import TELEGRAM_ID, populate


class ChatFlowTests(ServiceTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.tracks = await populate(self.database)
        self.chat = ChatService(self.database, RecommendationService(self.database, self.providers))
        self.bot = Bot('123456:TEST_ONLY_FAKE_TOKEN')
        self.outgoing = []
        self.serial = 100
        async def answer(text, **kwargs):
            self.serial += 1
            message = self.message(self.serial, text=text)
            self.outgoing.append((message, text, kwargs))
            return message
        self.patches = [patch('aiogram.types.Message.answer', side_effect=answer),
                        patch('aiogram.types.Message.edit_reply_markup', new_callable=AsyncMock),
                        patch('aiogram.types.CallbackQuery.answer', new_callable=AsyncMock)]
        self.answer, self.edit, self.ack = [p.start() for p in self.patches]

    async def asyncTearDown(self):
        for p in self.patches:
            p.stop()
        await self.bot.session.close()
        await super().asyncTearDown()

    def message(self, message_id=1, user=TELEGRAM_ID, **fields):
        return Message.model_validate({'message_id': message_id, 'date': 1700000000,
            'chat': {'id': user, 'type': 'private'},
            'from': {'id': user, 'is_bot': False, 'first_name': 'Test'}, **fields})

    async def feed(self, **fields):
        await dispatcher.feed_update(self.bot, Update(update_id=self.serial, **fields),
            chat_service=self.chat, submissions=self.submissions, workflow=self.workflow, enrichment=AsyncMock())

    async def click(self, outgoing, row=0, column=0, user=TELEGRAM_ID):
        message, _, fields = outgoing
        data = fields['reply_markup'].inline_keyboard[row][column].callback_data
        update = Update.model_validate({'update_id': self.serial, 'callback_query': {
            'id': str(self.serial), 'from': {'id': user, 'is_bot': False, 'first_name': 'Test'},
            'chat_instance': 'fixture', 'data': data, 'message': message.model_dump(mode='json')}})
        await self.feed(callback_query=update.callback_query)

    async def count(self, model):
        async with self.database.sessions() as session:
            return await session.scalar(select(func.count()).select_from(model))

    async def test_recommend_insufficient_sufficient_and_failed_delivery(self):
        async with self.database.write() as session:
            await session.execute(update(Rating).where(Rating.value.in_(['love', 'like'])).values(value='neutral'))
        await self.feed(message=self.message(text='/recommend'))
        self.assertEqual(self.outgoing[-1][1], M.PREFERENCES_NEEDED)
        self.assertEqual(await self.count(RecommendationHistory), 0)
        async with self.database.write() as session:
            await session.execute(update(Rating).where(Rating.track_id == self.tracks['metal_seed']).values(value='love'))
        await self.feed(message=self.message(text='/recommend'))
        self.assertEqual(await self.count(RecommendationHistory), 5)
        self.assertNotIn('score=', self.outgoing[-1][1])
        self.assertTrue(self.outgoing[-1][1].startswith(M.FOR_YOU_TITLE))
        async with self.database.write() as session:
            await session.execute(delete(RecommendationHistory))
        from music_bot.chat_ui import show_recommendations
        with patch('aiogram.types.Message.answer', side_effect=TelegramBadRequest(
                method=SendMessage(chat_id=TELEGRAM_ID, text='test'), message='failed')):
            with self.assertRaises(TelegramBadRequest):
                await show_recommendations(self.message(), self.chat, TELEGRAM_ID)
        self.assertEqual(await self.count(RecommendationHistory), 0)

    async def test_list_dedup_plain_text_and_safe_links(self):
        from dataclasses import replace
        from music_bot.recommendations.types import RecommendationResult
        result = await self.chat.recommendations.recommend_for_user(TELEGRAM_ID, random_seed=42)
        row = replace(result.recommendations[0], artist='<b>Artist</b>', title='Unsafe & title',
                      artwork_url='https://127.0.0.1/private', external_ids={'lastfm': 'javascript:alert(1)'})
        self.chat.recommendations = AsyncMock()
        self.chat.recommendations.recommend_for_user.return_value = RecommendationResult('ok', (row, row))
        await self.feed(message=self.message(text='/recommend'))
        self.assertEqual(await self.count(RecommendationHistory), 1)
        _, text, options = self.outgoing[-1]
        self.assertEqual(text.count('<b>Artist</b>'), 1)
        self.assertIsNone(options['parse_mode'])
        self.assertFalse(any(b.url for r in options['reply_markup'].inline_keyboard for b in r))
        self.assertIsNone(safe_url('https://www.last.fm@evil.example/music'))
        self.assertEqual(safe_url('https://www.last.fm/music/A/_/B'), 'https://www.last.fm/music/A/_/B')

    async def test_more_like_selected_seed_without_rating_change(self):
        await self.feed(message=self.message(text='/recommend'))
        listing = self.outgoing[-1]
        async with self.database.sessions() as session:
            before = (await session.execute(select(Rating.track_id, Rating.value).order_by(Rating.id))).all()
            control = await session.scalar(select(ChatControl).where(ChatControl.message_id == listing[0].message_id))
        seed = control.payload['tracks'][0]
        engine = self.chat.recommendations
        with patch.object(engine, 'recommend_similar_to_track', wraps=engine.recommend_similar_to_track) as similar:
            await self.click(listing, 0, 1)
            similar.assert_awaited_once_with(TELEGRAM_ID, seed, limit=5)
        self.assertIn('More Like This', self.outgoing[-1][1])
        async with self.database.sessions() as session:
            after = (await session.execute(select(Rating.track_id, Rating.value).order_by(Rating.id))).all()
        self.assertEqual(before, after)
        self.ack.assert_awaited()

    async def test_rating_recommendation_owner_repeat_and_change(self):
        await self.feed(message=self.message(text='/recommend'))
        await self.click(self.outgoing[-1])
        card = self.outgoing[-1]
        await self.click(card, user=999)
        self.ack.assert_called_with(M.STALE)
        self.assertEqual(await self.count(Rating), 4)
        await self.click(card)
        await self.click(card)
        await self.click(card, column=3)
        self.assertEqual(await self.count(Rating), 5)
        self.assertTrue(self.edit.call_args.kwargs['reply_markup'].inline_keyboard[0][3].text.startswith('✓'))
        await self.feed(message=self.message(text='/profile'))
        self.assertIn('Disliked: 2', self.outgoing[-1][1])
        self.assertIn('Recommendations shown: 5', self.outgoing[-1][1])

    async def test_another_list_is_navigation_and_repeated_click_safe(self):
        await self.feed(message=self.message(text='/recommend'))
        listing = self.outgoing[-1]
        async with self.database.sessions() as session:
            before = set((await session.scalars(select(RecommendationHistory.track_id))).all())
        await self.click(listing, row=5)
        self.assertEqual(await self.count(Rating), 4)
        self.assertEqual(await self.count(RecommendationHistory), 10)
        async with self.database.sessions() as session:
            after = (await session.scalars(select(RecommendationHistory.track_id))).all()
        self.assertEqual(len(set(after)), 10)
        await self.click(listing, row=5)
        self.ack.assert_called_with(M.STALE)
        self.assertEqual(await self.count(RecommendationHistory), 10)

    async def test_forget_confirmation_removes_only_owner(self):
        own = await self.submissions.submit_text(Submitter(TELEGRAM_ID), 'Forge - Loved Metal')
        other = await self.submissions.submit_text(Submitter(999), 'Forge - Loved Metal')
        async with self.database.write() as session:
            session.add(IdentificationFlow(submission_id=own.id, state='confirmed', expires_at=utc_now()))
            for submission, key in ((own, 'metal_seed'), (other, 'piano_seed')):
                session.add(AudioAnalysis(track_id=self.tracks[key], submission_id=submission.id, requested_by=submission.user_id,
                    analyzer_name='fixture', analyzer_version='1', status='succeeded', features={'sample_rate': 22050, 'bpm': 120}))
                session.add(RecommendationHistory(user_id=submission.user_id, track_id=self.tracks[key]))
            session.add(Rating(user_id=other.user_id, track_id=self.tracks['metal_seed'], value='love'))
        track_count = await self.count(Track)
        await self.feed(message=self.message(text='/forgetme'))
        await self.click(self.outgoing[-1], column=1)
        self.assertEqual(await self.count(User), 2)
        await self.feed(message=self.message(text='/forgetme'))
        confirmation = self.outgoing[-1]
        await self.click(confirmation, user=999)
        self.assertEqual(await self.count(User), 2)
        await self.click(confirmation)
        self.assertEqual(self.outgoing[-1][1], M.FORGET_DONE)
        for model in (User, SongSubmission, Rating, RecommendationHistory, AudioAnalysis):
            self.assertEqual(await self.count(model), 1)
        self.assertEqual(await self.count(IdentificationFlow), 0)
        self.assertEqual(await self.count(ChatControl), 0)
        self.assertEqual(await self.count(Track), track_count)
        await self.click(confirmation)
        self.assertEqual(await self.count(User), 1)
        self.ack.assert_called_with(M.STALE)
