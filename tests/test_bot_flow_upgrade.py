import asyncio
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace as NS
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from aiogram.types import Message
from sqlalchemy import select

from music_bot.chat_service import ChatService
from music_bot.fetch_models import AudioRequest, FetchJob
from music_bot.get_song import GetSong, FetchSettings
from music_bot.handlers import start
from music_bot.lifecycle import PrivateActions
from music_bot.models import ChatControl, Rating, Track, utc_now
from music_bot.submissions import Submitter
from music_bot.workflow import FlowError
from tests.support import ServiceTestCase


def message(text='', user=123):
    return Message.model_validate(dict(message_id=10, date=1, text=text,
        chat=dict(id=user, type='private'), **{'from': dict(id=user, is_bot=False, first_name='Test')}))


class ForegroundTests(IsolatedAsyncioTestCase):
    async def test_rapid_searches_only_run_latest_waiting_request(self):
        middleware = PrivateActions()
        started, cleaning, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
        async def slow(event, data):
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cleaning.set()
                await release.wait()
        original = asyncio.create_task(middleware(slow, message('First song'), {}))
        await started.wait()
        second, third = AsyncMock(), AsyncMock()
        middle = asyncio.create_task(middleware(second, message('Second song'), {}))
        await cleaning.wait()
        latest = asyncio.create_task(middleware(third, message('Third song'), {}))
        await asyncio.sleep(0)
        release.set()
        await asyncio.gather(middle, latest)
        self.assertTrue(original.cancelled())
        second.assert_not_awaited()
        third.assert_awaited_once()
        self.assertFalse(middleware.waiting)

    async def test_cancel_interrupts_search_and_drains_cleanup_before_next_action(self):
        middleware = PrivateActions()
        started, cleaned = asyncio.Event(), asyncio.Event()
        async def search(event, data):
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cleaned.set()
        task = asyncio.create_task(middleware(search, message('Artist - Song'), {}))
        await asyncio.wait_for(started.wait(), 1)
        async def cancel(event, data):
            self.assertTrue(cleaned.is_set())
        await asyncio.wait_for(middleware(cancel, message('/cancel'), {}), 1)
        self.assertTrue(task.cancelled())
        self.assertFalse(middleware.active)

    async def test_new_search_supersedes_old_search(self):
        middleware = PrivateActions()
        started = asyncio.Event()
        async def slow(event, data):
            started.set()
            await asyncio.Event().wait()
        previous = asyncio.create_task(middleware(slow, message('Old song'), {}))
        await started.wait()
        handler = AsyncMock()
        await asyncio.wait_for(middleware(handler, message('New song'), {}), 1)
        self.assertTrue(previous.cancelled())
        handler.assert_awaited_once()

    async def test_navigation_cannot_interrupt_account_deletion(self):
        middleware = PrivateActions()
        started, release = asyncio.Event(), asyncio.Event()
        async def deletion(event, data):
            started.set()
            await release.wait()
        task = asyncio.create_task(middleware(deletion, message('/forgetme'), {}))
        await started.wait()
        with patch.object(Message, 'answer', new_callable=AsyncMock):
            handler = AsyncMock()
            await middleware(handler, message('/cancel'), {})
            handler.assert_not_awaited()
            self.assertFalse(task.done())
        release.set()
        await task

    async def test_other_user_is_not_serialized_with_slow_search(self):
        middleware = PrivateActions()
        started, release = asyncio.Event(), asyncio.Event()
        async def slow(event, data):
            started.set()
            await release.wait()
        task = asyncio.create_task(middleware(slow, message('Song'), {}))
        await started.wait()
        handler = AsyncMock()
        await asyncio.wait_for(middleware(handler, message('Other', 456), {}), 1)
        handler.assert_awaited_once()
        release.set()
        await task


class UpgradeTests(ServiceTestCase):
    async def test_expanded_audio_artist_credits_recover_by_title_with_choice(self):
        from music_bot.submissions import AudioMetadata
        from music_bot.providers.common import TrackCandidate, ProviderError, Failure
        band = 'LSD and the Search for God'
        exact = TrackCandidate(artist=band, title='Starting Over', source='itunes')
        unrelated = TrackCandidate(artist='Another Artist', title='Starting Over', source='itunes')
        self.providers.has_itunes = True
        async def call(provider, method, *args):
            if provider == 'lastfm':
                raise ProviderError(Failure.AUTH)
            return [unrelated, exact] if method == 'search_titles' else []
        self.providers.call.side_effect = call
        saved = await self.submissions.submit_audio(self.user, AudioMetadata(
            'fixture', 'expanded-credits', band + ' Andy Liszt Sophia Campbell', 'Starting Over'))
        result = await self.workflow.start(saved.id, 123, fast=True)
        self.assertEqual(result.kind, 'candidates')
        self.assertEqual(result.candidates, [exact])
        self.assertFalse(self.workflow.warm_tasks)
        result = await self.workflow.select(saved.id, 123, result.revision, 0)
        self.assertEqual((result.kind, result.artist, result.title), ('confirmed', band, 'Starting Over'))

    async def test_empty_healthy_fallback_is_not_an_outage(self):
        from music_bot.providers.common import ProviderError, Failure
        async def call(provider, *args):
            if provider == 'lastfm':
                raise ProviderError(Failure.AUTH)
            return []
        self.providers.call.side_effect = call
        candidates, failed = await self.workflow.search('Unmatched Artist', 'Unmatched Song')
        self.assertEqual(candidates, [])
        self.assertFalse(failed)

    async def test_all_catalogues_failed_is_still_an_outage(self):
        from music_bot.providers.common import ProviderError, Failure
        self.providers.call.side_effect = ProviderError(Failure.NETWORK)
        candidates, failed = await self.workflow.search('Unmatched Artist', 'Unmatched Song')
        self.assertEqual(candidates, [])
        self.assertTrue(failed)

    async def test_independent_fallbacks_run_concurrently(self):
        from music_bot.providers.common import ProviderError, Failure, TrackCandidate
        self.providers.has_itunes = True
        started = set()
        ready = asyncio.Event()
        async def call(provider, *args):
            if provider == 'lastfm':
                raise ProviderError(Failure.AUTH)
            started.add(provider)
            if started == {'musicbrainz', 'itunes'}:
                ready.set()
            await ready.wait()
            return [TrackCandidate(artist='Adele', title='Hello', source=provider)]
        self.providers.call.side_effect = call
        candidates, failed = await asyncio.wait_for(self.workflow.search('Adele', 'Hello'), 1)
        self.assertTrue(candidates)
        self.assertFalse(failed)

    async def test_unmatched_upload_requests_corrected_tags(self):
        from music_bot.submissions import AudioMetadata
        from music_bot.providers.common import ProviderError, Failure
        async def call(provider, *args):
            if provider == 'lastfm':
                raise ProviderError(Failure.AUTH)
            return []
        self.providers.call.side_effect = call
        saved = await self.submissions.submit_audio(self.user, AudioMetadata(
            'fixture', 'unmatched-tags', 'Promotional channel text', 'Unknown song', None, 'audio/mpeg', 100, 20))
        result = await self.workflow.start(saved.id, 123, fast=True)
        self.assertEqual(result.kind, 'missing')
        await self.workflow.bind_prompt(result, 123, 99)

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.chat = ChatService(self.database, None)
        await self.chat.ensure_user(self.user)
        async with self.database.write() as session:
            track = Track(artist='Artist', title='Song', duration=200, metadata_source='test')
            session.add(track)
            await session.flush()
            self.track_id = track.id
        self.bot = NS(send_audio=AsyncMock(return_value=NS(audio=NS(file_id='cached-audio'), message_id=8)),
                      send_message=AsyncMock(return_value=NS(message_id=9)), edit_message_text=AsyncMock(), delete_message=AsyncMock())
        async def audio(video, directory, alive):
            path = Path(directory) / 'audio.m4a'
            path.write_bytes(b'mock')
            return path
        self.fetcher = NS(search=AsyncMock(return_value=[dict(id='abcdefghijk', title='Song', artist='Artist', duration=200, exact=True, score=1)]),
                          fetch=AsyncMock(side_effect=audio))
        self.service = GetSong(self.database, self.bot, FetchSettings(enabled=True), self.fetcher)
        self.service.root = Path(self.temp.name) / 'fetch'
        self.service.root.mkdir()

    async def asyncTearDown(self):
        await self.service.close()
        await super().asyncTearDown()

    async def job(self, request):
        async with self.database.sessions() as session:
            return (await session.get(AudioRequest, request)).job_id

    async def test_start_offers_two_paths_without_creating_ratings(self):
        with patch.object(Message, 'answer', new_callable=AsyncMock) as answer:
            await start(message('/start'), self.chat)
        from music_bot.i18n import tr
        self.assertEqual(answer.await_args.args[0],tr('onboard_welcome'))
        rows=answer.await_args.kwargs['reply_markup'].inline_keyboard
        self.assertEqual([[button.callback_data for button in row] for row in rows],[['ob:send'],['ob:pick']])
        async with self.database.sessions() as session:
            self.assertIsNone(await session.scalar(select(Rating)))

    async def test_tagged_audio_uses_catalogue_when_shazam_has_no_match(self):
        from music_bot.handlers import audio_submission
        from unittest.mock import Mock
        inbound = Message.model_validate({**message().model_dump(), 'audio': dict(file_id='fixture',
            file_unique_id='fixture-unique', duration=200, performer='Artist', title='Song')})
        recognition = NS(enabled=True, submit=AsyncMock())
        pending = NS(message_id=77, edit_text=AsyncMock())
        enrichment = Mock()
        with patch.object(Message, 'answer', new_callable=AsyncMock, return_value=pending):
            await audio_submission(inbound, self.submissions, self.workflow, enrichment, self.chat, recognition)
        recognition.submit.assert_not_awaited()
        enrichment.schedule.assert_not_called()
        self.fetcher.fetch.assert_not_awaited()
        self.bot.send_audio.assert_not_awaited()
        self.assertFalse(self.workflow.warm_tasks)
        self.assertIn(':love:', pending.edit_text.await_args.kwargs['reply_markup'].inline_keyboard[0][0].callback_data)

    async def test_untagged_rating_audio_asks_for_identity_without_recognition(self):
        from music_bot.handlers import audio_submission
        from unittest.mock import Mock
        inbound = Message.model_validate({**message().model_dump(), 'audio': dict(file_id='fixture',
            file_unique_id='fixture-unique', duration=12)})
        recognition = NS(enabled=True, submit=AsyncMock())
        pending = NS(message_id=77, edit_text=AsyncMock(), delete=AsyncMock())
        with patch.object(Message, 'answer', new_callable=AsyncMock, return_value=pending) as answer:
            await audio_submission(inbound, self.submissions, self.workflow, Mock(), self.chat, recognition)
        recognition.submit.assert_not_awaited()
        self.providers.call.assert_not_awaited()
        from music_bot import messages
        self.assertEqual(answer.await_args.args[0], messages.MISSING)

    async def test_music_document_defaults_to_rating_without_download(self):
        from music_bot.handlers import recognize_media
        from unittest.mock import Mock
        inbound = Message.model_validate({**message().model_dump(), 'document': dict(file_id='fixture',
            file_unique_id='fixture-doc', file_name='song.mp3', mime_type='audio/mpeg')})
        recognition = NS(enabled=True, submit=AsyncMock())
        pending = NS(message_id=77, edit_text=AsyncMock(), delete=AsyncMock())
        with patch.object(Message, 'answer', new_callable=AsyncMock, return_value=pending):
            await recognize_media(inbound, recognition, self.submissions, self.workflow, Mock(), self.chat)
        recognition.submit.assert_not_awaited()
        self.providers.call.assert_not_awaited()

    async def test_close_search_invalidates_only_its_bound_candidates(self):
        saved = await self.submissions.submit_search(self.user, 'Song')
        result = await self.workflow.start(saved.id, 123)
        await self.workflow.bind_candidates(result, 123, 77)
        other = await self.submissions.submit_search(self.user, 'Song')
        other_result = await self.workflow.start(other.id, 123)
        await self.workflow.bind_candidates(other_result, 123, 88)
        for owner, msg in ((456, 77), (123, 88)):
            with self.assertRaises(FlowError):
                await self.workflow.close_candidates(saved.id, owner, result.revision, msg)
        await self.workflow.close_candidates(saved.id, 123, result.revision, 77)
        with self.assertRaises(FlowError):
            await self.workflow.select(saved.id, 123, result.revision, 0)
        self.assertEqual((await self.workflow.select(other.id, 123, other_result.revision, 0)).kind, 'confirmed')

    async def test_close_card_invalidates_rating_callbacks_without_changing_ratings(self):
        token = await self.chat.create_control(123, tracks=[self.track_id], kind='rating')
        await self.chat.bind_control(token, 77)
        with self.assertRaises(FlowError):
            await self.chat.control(token, 456, 77, 'menu')
        await self.chat.control(token, 123, 77, 'menu')
        with self.assertRaises(FlowError):
            await self.chat.control(token, 123, 77, 'love', 0, rating='love')
        async with self.database.sessions() as session:
            self.assertIsNone(await session.scalar(select(Rating)))

    def test_button_layout_and_wire_styles(self):
        from music_bot.chat_ui import card_keyboard, list_content
        from music_bot.bot_copy import text
        row = NS(artist='Artist', title='Song', album=None, reason='Similar', artwork_url=None, external_ids={})
        _, keyboard = list_content([row], 'a' * 32)
        self.assertEqual(len(keyboard.inline_keyboard[0]), 3)
        self.assertEqual(keyboard.inline_keyboard[0][2].text, '⋯')
        self.assertEqual(keyboard.inline_keyboard[0][0].model_dump(exclude_none=True)['style'], 'primary')
        self.assertEqual(keyboard.inline_keyboard[-1][-1].text, text('close'))
        ratings = card_keyboard('a' * 32, rating_mode=True)
        self.assertEqual([b.style for b in ratings.inline_keyboard[0]], ['success', 'success', None, 'danger'])
        self.assertFalse(any(':get:' in (b.callback_data or '') for r in ratings.inline_keyboard for b in r))

    async def test_delivery_removes_status_and_sends_plain_audio(self):
        pending = NS(message_id=77, edit_text=AsyncMock())
        source = NS(answer=AsyncMock(return_value=pending))
        req = await self.service.begin(source, 123, self.track_id)
        await self.service.execute(await self.job(req))
        self.bot.send_audio.assert_awaited_once()
        self.bot.send_message.assert_not_awaited()
        self.assertTrue(all(call.kwargs['message_id'] == 77 for call in self.bot.edit_message_text.await_args_list))
        self.bot.delete_message.assert_awaited_with(123, 77)
        self.assertIsNone(self.bot.send_audio.await_args.kwargs.get('reply_markup'))
        async with self.database.sessions() as session:
            self.assertIsNone(await session.scalar(select(Rating)))
        async with self.database.write() as session:
            track = await session.get(Track, self.track_id)
            track.artwork_url = 'https://lastfm.freetls.fastly.net/i/u/new.jpg'
        self.service.artwork_loader = NS(load=AsyncMock(side_effect=AssertionError('art must not delay cached audio')))
        await self.service.begin(source, 123, self.track_id)
        self.assertEqual(self.bot.send_audio.await_count, 2)
        self.assertEqual(self.fetcher.fetch.await_count, 1)
        self.service.artwork_loader.load.assert_not_awaited()

    async def test_next_request_removes_failed_status_without_deleting_audio(self):
        request_id = await self.service.request(123, self.track_id)
        async with self.database.write() as session:
            req = await session.get(AudioRequest, request_id)
            req.state, req.status_message_id, req.message_id = 'failed', 42, 99
        pending = NS(message_id=77, edit_text=AsyncMock())
        await self.service.begin(NS(answer=AsyncMock(return_value=pending)), 123, self.track_id)
        self.bot.delete_message.assert_any_await(123, 42)
        self.assertNotIn(((123, 99), {}), [(call.args, call.kwargs) for call in self.bot.delete_message.await_args_list])

    async def test_status_edit_failure_does_not_fail_delivery(self):
        req = await self.service.request(123, self.track_id)
        self.bot.edit_message_text.side_effect = RuntimeError('mock unavailable')
        await self.service.bind_status(123, req, 77)
        await self.service.execute(await self.job(req))
        async with self.database.sessions() as session:
            self.assertEqual((await session.get(AudioRequest, req)).state, 'done')
        self.bot.send_audio.assert_awaited_once()

    async def test_late_status_and_failure_cannot_overwrite_cancellation(self):
        req = await self.service.request(123, self.track_id)
        await self.service.bind_status(123, req, 77)
        await self.service.cancel_request(123, req, 77)
        self.bot.edit_message_text.reset_mock()
        await self.service.progress(req, 'fetching')
        self.assertFalse(await self.service.request_state(req, 'failed'))
        self.bot.edit_message_text.assert_not_awaited()
        async with self.database.sessions() as session:
            self.assertEqual((await session.get(AudioRequest, req)).state, 'cancelled')

    async def test_cancel_one_request_checks_owner_message_and_preserves_other_request(self):
        req = await self.service.request(123, self.track_id)
        await self.service.bind_status(123, req, 77)
        await self.chat.ensure_user(Submitter(456))
        other = await self.service.request(456, self.track_id)
        for user, msg in ((456, 77), (123, 999)):
            with self.assertRaises(FlowError):
                await self.service.cancel_request(user, req, msg)
        await self.service.cancel_request(123, req, 77)
        await self.service.execute(await self.job(other))
        self.assertEqual(self.bot.send_audio.await_args.args[0], 456)
        self.bot.send_audio.assert_awaited_once()

    async def test_choice_edits_same_status_and_binds_owner(self):
        req = await self.service.request(123, self.track_id, other_versions=True)
        await self.service.bind_status(123, req, 77)
        await self.service.execute(await self.job(req))
        self.bot.send_message.assert_not_awaited()
        with self.assertRaises(FlowError):
            await self.service.choose(456, req, 77, 0)
        await self.service.choose(123, req, 77, 0)
        await self.service.bind_status(123, req, 77)
        await self.service.execute(await self.job(req))
        self.bot.send_audio.assert_awaited_once()

    async def test_expired_card_recovers_without_reviving_forget_or_deleted_account(self):
        token = await self.chat.create_control(123, tracks=[self.track_id], kind='card')
        await self.chat.bind_control(token, 77)
        async with self.database.write() as session:
            (await session.get(ChatControl, token)).expires_at = utc_now() - timedelta(minutes=1)
        with self.assertRaises(FlowError):
            await self.chat.control(token, 456, 77, 'get', 0)
        with self.assertRaises(FlowError):
            await self.chat.control(token, 123, 99, 'get', 0)
        _, track = await self.chat.control(token, 123, 77, 'get', 0)
        self.assertEqual(track.id, self.track_id)
        forget = await self.chat.create_control(123, kind='forget')
        await self.chat.bind_control(forget, 78)
        async with self.database.write() as session:
            (await session.get(ChatControl, forget)).expires_at = utc_now() - timedelta(seconds=1)
        with self.assertRaises(FlowError):
            await self.chat.control(forget, 123, 78, 'delete')
        await self.chat.forget(123)
        await self.chat.ensure_user(self.user)
        with self.assertRaises(FlowError):
            await self.chat.control(token, 123, 77, 'get', 0)

    async def test_local_search_returns_before_slow_remote_enrichment(self):
        started, release = asyncio.Event(), asyncio.Event()
        async def remote(*args):
            started.set()
            await release.wait()
            return []
        self.providers.call.side_effect = remote
        saved = await self.submissions.submit_search(self.user, 'Artist - Song')
        result = await asyncio.wait_for(self.workflow.start(saved.id, 123, fast=True), 1)
        self.assertEqual(result.kind, 'confirmed')
        await asyncio.wait_for(started.wait(), 1)
        release.set()

    async def test_expired_candidate_choice_recovers_only_for_original_owner(self):
        from music_bot.models import IdentificationFlow
        saved = await self.submissions.submit_search(self.user, 'Song')
        result = await self.workflow.start(saved.id, 123)
        self.assertEqual(result.kind, 'candidates')
        async with self.database.write() as session:
            flow = await session.get(IdentificationFlow, saved.id)
            flow.expires_at = utc_now() - timedelta(seconds=1)
        with self.assertRaises(FlowError):
            await self.workflow.select(saved.id, 456, result.revision, 0, recover=True)
        with self.assertRaises(FlowError):
            await self.workflow.select(saved.id, 123, result.revision, 0)
        recovered = await self.workflow.select(saved.id, 123, result.revision, 0, recover=True)
        self.assertEqual(recovered.kind, 'confirmed')

    async def test_chat_provider_has_budget_and_cancels_slow_call(self):
        from music_bot.workflow import CHAT_FAST
        from music_bot.providers.common import ProviderError
        stopped = asyncio.Event()
        async def remote(*args):
            try:
                await asyncio.Event().wait()
            finally:
                stopped.set()
        self.providers.call.side_effect = remote
        context = CHAT_FAST.set(True)
        try:
            with self.assertRaises(ProviderError):
                await asyncio.wait_for(self.workflow.call('lastfm', 'search_titles', 'Song'), 3)
            self.assertTrue(stopped.is_set())
        finally:
            CHAT_FAST.reset(context)

    async def test_worker_runs_bounded_jobs_and_shutdown_drains_them(self):
        prime = await self.service.request(123, self.track_id)
        await self.service.execute(await self.job(prime))
        ready, release = asyncio.Event(), asyncio.Event()
        active = set()
        async def blocked(video, directory, alive):
            active.add(directory)
            if len(active) == 2:
                ready.set()
            await release.wait()
        self.fetcher.fetch.side_effect = blocked
        for index in range(3):
            user = 456 + index
            await self.chat.ensure_user(Submitter(user))
            async with self.database.write() as session:
                track = Track(artist='Artist', title=f'Track {index}', duration=200, metadata_source='test')
                session.add(track)
                await session.flush()
                track_id = track.id
            await self.service.request(user, track_id)
        await self.service.start()
        await asyncio.wait_for(ready.wait(), 3)
        self.assertEqual(len(self.service.jobs), 2)
        self.assertEqual(len(active), 2)
        pending = NS(message_id=77, edit_text=AsyncMock())
        await asyncio.wait_for(self.service.begin(NS(answer=AsyncMock(return_value=pending)), 123, self.track_id), 3)
        self.assertEqual(self.bot.send_audio.await_count, 2)
        await self.service.close()
        self.assertFalse(self.service.jobs)
        self.assertEqual(self.bot.send_audio.await_count, 2)
