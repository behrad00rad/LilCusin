import asyncio
from dataclasses import replace
from datetime import datetime, UTC
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from aiogram.methods import SendAudio
from sqlalchemy import select

from tests.support import ServiceTestCase
from music_bot.chat_service import ChatService
from music_bot.daily_pick import DailyPicks, DailyPickState, setting, daily_command
from music_bot.models import User, Track, Rating, ChatControl, RecommendationHistory
from music_bot.preferences import preferences
from music_bot.recommendations.types import Recommendation, RecommendationResult
from music_bot.submissions import Submitter
from music_bot.get_song import GetSong, FetchSettings
from music_bot.taste_learning import TasteRequest, TrackPreference
from music_bot.fetch_models import AudioRequest, FetchJob

NOW = datetime(2026, 10, 28, 14, 30, tzinfo=UTC)


class DailyPickTests(ServiceTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.clock = patch('music_bot.daily_pick.utc_now', return_value=NOW)
        self.clock.start()
        self.addCleanup(self.clock.stop)
        self.recs = NS(queue=NS(reserve=AsyncMock(), release=AsyncMock()))
        self.chat = ChatService(self.database, self.recs)
        await self.chat.ensure_user(Submitter(123))
        async with self.database.write() as session:
            self.internal = await session.scalar(select(User.id))
            from music_bot.taste_setup import TasteSetup
            session.add(TasteSetup(user_id=self.internal,artist='Artist',completed=True))
            track = Track(artist='Artist', title='Fresh song', metadata_source='fixture')
            session.add(track)
            await session.flush()
            self.track = track
        self.pick = Recommendation(self.track.id, 'Artist', 'Fresh song', None, None, {}, 1, 'For you', ('fixture',))
        self.recs.queue.reserve.return_value = RecommendationResult('ok', (self.pick,), 'batch')
        self.bot = NS(send_message=AsyncMock(return_value=NS(message_id=41)),
            send_audio=AsyncMock(return_value=NS(message_id=42, audio=NS(file_id='cached-audio'))),
            me=AsyncMock(return_value=NS(username='LilCusinBot')))
        self.delivery = GetSong(self.database, self.bot, FetchSettings(enabled=True), fetcher=NS())
        self.daily = DailyPicks(self.chat, self.bot, self.delivery)

    async def request(self):
        await self.daily.send(123, '2026-10-28')
        async with self.database.sessions() as session:
            req = await session.scalar(select(AudioRequest).where(AudioRequest.user_id == self.internal).order_by(AudioRequest.created_at.desc()))
            job = await session.get(FetchJob, req.job_id) if req else None
            if job:
                job.video_id = 'abcdefghijk'
            return req, job

    async def deliver(self, audio='cached-audio'):
        req, job = await self.request()
        await self.delivery.send(req, 123, job, self.track, audio)
        return req, job

    async def test_queue_is_silent_and_claim_survives_concurrent_restart(self):
        await asyncio.gather(self.daily.send(123, '2026-10-28'), self.daily.send(123, '2026-10-28'))
        await DailyPicks(self.chat, self.bot, self.delivery).send(123, '2026-10-28')
        self.bot.send_message.assert_not_awaited()
        self.bot.send_audio.assert_not_awaited()
        async with self.database.sessions() as session:
            self.assertEqual(len(list(await session.scalars(select(AudioRequest)))), 1)
            self.assertIsNone(await session.scalar(select(RecommendationHistory)))
            self.assertIsNone(await session.scalar(select(TasteRequest)))
            self.assertIsNone(await session.scalar(select(Rating)))

    async def test_ready_audio_exact_caption_three_buttons_and_receipt(self):
        await self.deliver()
        self.assertIn('Rate a song or two',self.bot.send_message.await_args.args[1])
        self.assertNotIn('reply_markup', self.bot.send_message.await_args.kwargs)
        kwargs = self.bot.send_audio.await_args.kwargs
        self.assertTrue(kwargs['caption'].startswith('⭐ rate  📝 lyrics  🦉 lilcusin'))
        self.assertIn('Why this pick:',kwargs['caption'])
        self.assertEqual(len(kwargs['caption_entities']), 3)
        buttons = kwargs['reply_markup'].inline_keyboard
        self.assertEqual(len(buttons), 1)
        self.assertEqual([b.text for b in buttons[0]], ['Already know it', 'Not for me', 'More like this'])
        async with self.database.sessions() as session:
            self.assertEqual((await session.get(DailyPickState, self.internal)).state, 'sent')
            control = await session.scalar(select(ChatControl))
            self.assertEqual(control.message_id, 42)
            self.assertTrue(control.payload['daily'])
            self.assertEqual((await session.scalar(select(RecommendationHistory))).track_id, self.track.id)
            self.assertIsNone(await session.scalar(select(TasteRequest)))
        # An acknowledged audio cannot be resent by a second worker call.
        req, job = await self.request()
        await self.delivery.send(req, 123, job, self.track, 'cached-audio')
        self.assertEqual(self.bot.send_audio.await_count, 1)

    async def test_feedback_is_owner_bound_and_known_is_not_a_dislike(self):
        await self.deliver()
        async with self.database.sessions() as session:
            token = (await session.scalar(select(ChatControl))).token
        from music_bot.workflow import FlowError
        with self.assertRaises(FlowError):
            await self.chat.control(token, 456, 42, 'known', 0)
        with self.assertRaises(FlowError):
            await self.chat.control(token, 123, 99, 'known', 0)
        payload, _ = await self.chat.control(token, 123, 42, 'known', 0)
        self.assertTrue(payload['daily'])
        async with self.database.sessions() as session:
            self.assertIsNone(await session.scalar(select(Rating)))
            self.assertEqual((await session.scalar(select(TrackPreference))).feedback, 'known')

    async def test_saved_persian(self):
        await preferences(self.database, 123, language='fa')
        await self.deliver()
        self.assertIn('سلیقه‌ت رو بهتر بشناسم',self.bot.send_message.await_args.args[1])
        self.assertTrue(self.bot.send_audio.await_args.kwargs['caption'].startswith('⭐ rate  📝 lyrics  🦉 lilcusin'))
        self.assertIn('سلیقه', self.bot.send_audio.await_args.kwargs['reply_markup'].inline_keyboard[0][1].text)

    async def test_opt_out_before_queue_and_before_send(self):
        await setting(self.database, 123, False)
        await self.daily.send(123, '2026-10-28')
        self.recs.queue.reserve.assert_not_awaited()
        await setting(self.database, 123, True)
        req, job = await self.request()
        await setting(self.database, 123, False)
        await self.delivery.send(req, 123, job, self.track, 'cached-audio')
        self.bot.send_message.assert_not_awaited()
        self.bot.send_audio.assert_not_awaited()

    async def test_disabled_and_empty_are_silent(self):
        self.delivery.settings = replace(self.delivery.settings, enabled=False)
        await self.daily.send(123, '2026-10-28')
        self.bot.send_message.assert_not_awaited()
        self.delivery.settings = replace(self.delivery.settings, enabled=True)
        self.recs.queue.reserve.return_value = RecommendationResult('no_candidates')
        await self.daily.send(123, '2026-10-29')
        async with self.database.sessions() as session:
            self.assertIsNone(await session.scalar(select(AudioRequest)))

    async def test_source_failure_and_recording_choices_are_silent(self):
        req, job = await self.request()
        await self.delivery.fail(job.id, phase='search')
        self.bot.send_message.assert_not_awaited()
        async with self.database.write() as session:
            current = await session.get(AudioRequest, req.id)
            current.state = 'pending'
        await self.delivery.show_choices(req, 123, [])
        self.bot.send_message.assert_not_awaited()
        async with self.database.sessions() as session:
            self.assertEqual((await session.get(AudioRequest, req.id)).state, 'failed')

    async def test_invalid_cached_file_retry_does_not_repeat_intro(self):
        req, job = await self.request()
        self.bot.send_audio.side_effect = TelegramBadRequest(method=SendAudio(chat_id=123, audio='cached'), message='wrong file identifier')
        with self.assertRaises(TelegramBadRequest):
            await self.delivery.send(req, 123, job, self.track, 'cached')
        self.bot.send_audio.side_effect = None
        async with self.database.sessions() as session:
            req = await session.get(AudioRequest, req.id)
        await self.delivery.send(req, 123, job, self.track, 'replacement')
        self.assertEqual(self.bot.send_message.await_count, 1)

    async def test_ambiguous_audio_is_not_retried_and_block_disables(self):
        req, job = await self.request()
        self.bot.send_audio.side_effect = TimeoutError()
        await self.delivery.send(req, 123, job, self.track, 'cached')
        await self.delivery.send(req, 123, job, self.track, 'cached')
        self.assertEqual(self.bot.send_audio.await_count, 1)
        async with self.database.write() as session:
            current = await session.get(AudioRequest, req.id)
            current.state = 'pending'
        self.bot.send_audio.side_effect = TelegramForbiddenError(method=SendAudio(chat_id=123, audio='cached'), message='blocked')
        await self.delivery.send(req, 123, job, self.track, 'cached')
        self.assertFalse(await setting(self.database, 123))

    async def test_late_audio_and_forget(self):
        req, job = await self.request()
        self.clock.stop()
        with patch('music_bot.daily_pick.utc_now', return_value=datetime(2026, 10, 29, 14, 30, tzinfo=UTC)):
            await self.delivery.send(req, 123, job, self.track, 'cached')
        self.bot.send_message.assert_not_awaited()
        await self.chat.forget(123)
        async with self.database.sessions() as session:
            self.assertIsNone(await session.get(DailyPickState, self.internal))

    async def test_schedule_lifecycle_and_daily_command(self):
        with patch.object(self.daily, 'send', new_callable=AsyncMock) as send, patch('music_bot.daily_pick.asyncio.sleep', new_callable=AsyncMock):
            await self.daily.tick(datetime(2026, 10, 28, 10, tzinfo=UTC))
            send.assert_not_awaited()
            await self.daily.tick(NOW)
            send.assert_awaited_once_with(123, '2026-10-28')
        self.daily.start()
        await self.daily.close()
        self.assertTrue(self.daily.task.done())
        message = NS(chat=NS(type='private'), from_user=NS(id=123, is_bot=False), text='/daily off', answer=AsyncMock())
        await daily_command(message, self.chat)
        self.assertFalse(await setting(self.database, 123))
        message.text = '/daily on'
        await daily_command(message, self.chat)
        self.assertTrue(await setting(self.database, 123))

    async def test_automatic_audio_never_learns_but_manual_request_does(self):
        await self.request()
        async with self.database.sessions() as session:
            self.assertIsNone(await session.scalar(select(TasteRequest)))
        async with self.database.write() as session:
            for req in await session.scalars(select(AudioRequest)):
                req.state = 'done'
        await self.delivery.request(123, self.track.id)
        async with self.database.sessions() as session:
            self.assertIsNotNone(await session.scalar(select(TasteRequest)))
