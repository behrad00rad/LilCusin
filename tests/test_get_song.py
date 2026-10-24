import asyncio
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch
from sqlalchemy import select
from tests.support import ServiceTestCase
from music_bot.chat_service import ChatService
from music_bot.models import Track
from music_bot.get_song import GetSong, FetchSettings
from music_bot.fetch_models import AudioRequest, AudioDelivery, FetchJob, AudioSelection
from music_bot.youtube_fetch import FetchError, rank_candidates, confident, YouTubeFetcher
from music_bot.workflow import FlowError
from music_bot.submissions import Submitter

VIDEO = 'abcdefghijk'

class GetSongTests(ServiceTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.chat = ChatService(self.database, None)
        await self.chat.ensure_user(self.user)
        async with self.database.write() as s:
            track = Track(artist='Artist', title='Song', duration=200, metadata_source='test')
            s.add(track)
            await s.flush()
            self.track_id = track.id
        self.bot = NS(edit_message_text=AsyncMock(), delete_message=AsyncMock(),
                      send_audio=AsyncMock(return_value=NS(audio=NS(file_id='telegram-file'), message_id=8)),
                      send_message=AsyncMock(return_value=NS(message_id=9)))
        self.fetcher = NS(search=AsyncMock(return_value=[dict(id=VIDEO, title='Song', artist='Artist',
            duration=200, score=1, exact=True)]), fetch=AsyncMock(side_effect=self.audio))
        self.service = GetSong(self.database, self.bot, FetchSettings(enabled=True), self.fetcher)
        self.service.root = Path(self.temp.name) / 'fetch'
        self.service.root.mkdir()

    async def audio(self, video, directory, alive):
        p = Path(directory) / 'source.m4a'
        p.write_bytes(b'mocked audio')
        return p

    async def job(self, request_id):
        async with self.database.sessions() as s:
            req = await s.get(AudioRequest, request_id)
            return req.job_id, req.state

    async def test_delivery_then_cache_skips_source(self):
        req = await self.service.request(123, self.track_id)
        job, _ = await self.job(req)
        await self.service.execute(job)
        self.assertEqual((await self.job(req))[1], 'done')
        second = await self.service.request(123, self.track_id)
        await self.service.execute((await self.job(second))[0])
        self.assertEqual(self.fetcher.search.await_count, 1)
        self.assertEqual(self.fetcher.fetch.await_count, 1)
        self.assertEqual(self.bot.send_audio.call_args.kwargs['audio'], 'telegram-file')
        self.assertEqual(list(self.service.root.iterdir()), [])

    def strict_fetcher(self, rows):
        fetcher = YouTubeFetcher(self.service.settings)
        fetcher.search = AsyncMock(return_value=rows)
        fetcher.fetch = AsyncMock(side_effect=self.audio)
        self.service.fetcher = fetcher
        return fetcher

    async def test_legacy_unverified_cache_and_preference_cannot_bypass_original_policy(self):
        request = await self.service.request(123, self.track_id)
        await self.service.execute((await self.job(request))[0])
        async with self.database.write() as s:
            req = await s.get(AudioRequest, request)
            s.add(AudioSelection(user_id=req.user_id, track_id=self.track_id, video_id=VIDEO, rejected_ids=[]))
        fetcher = self.strict_fetcher([])
        retry = await self.service.request(123, self.track_id)
        await self.service.execute((await self.job(retry))[0])
        self.assertEqual(self.bot.send_audio.await_count, 1)
        fetcher.fetch.assert_not_awaited()
        self.assertEqual((await self.job(retry))[1], 'failed')
        async with self.database.sessions() as s:
            self.assertIsNone((await s.scalar(select(AudioSelection))).video_id)
            self.assertIsNotNone(await s.scalar(select(AudioDelivery)))  # No bulk cache deletion.

    async def test_verified_catalogue_cache_remains_reusable(self):
        self.fetcher.search.return_value[0]['source_policy'] = 'catalogue-original-v1'
        request = await self.service.request(123, self.track_id)
        await self.service.execute((await self.job(request))[0])
        fetcher = self.strict_fetcher([])
        retry = await self.service.request(123, self.track_id)
        await self.service.execute((await self.job(retry))[0])
        fetcher.search.assert_not_awaited()
        fetcher.fetch.assert_not_awaited()
        self.assertEqual((await self.job(retry))[1], 'done')

    async def test_legacy_choice_cannot_authorize_unverified_original(self):
        self.fetcher.search.return_value[0]['exact'] = False
        request = await self.service.request(123, self.track_id)
        await self.service.execute((await self.job(request))[0])
        self.strict_fetcher([])
        with self.assertRaises(FlowError):
            await self.service.choose(123, request, 9, 0)

    async def test_explicit_alternatives_keep_manual_choice_separate(self):
        rows = [dict(id=VIDEO, title='Artist - Song', artist='Artist', duration=200,
                     score=1, exact=False, recording_title='Song')]
        fetcher = self.strict_fetcher(rows)
        request = await self.service.request(123, self.track_id, other_versions=True)
        await self.service.execute((await self.job(request))[0])
        self.assertEqual((await self.job(request))[1], 'choice')
        fetcher.fetch.assert_not_awaited()
        await self.service.choose(123, request, 9, 0)
        async with self.database.sessions() as s:
            req = await s.get(AudioRequest, request)
            selected = await s.get(FetchJob, req.job_id)
            self.assertEqual(selected.metadata_json['source_policy'], 'explicit-alternative-v1')
        await self.service.execute((await self.job(request))[0])
        self.assertEqual((await self.job(request))[1], 'done')
        # An explicitly chosen unlabelled alternative must not become the default original.
        fetcher.search.return_value = []
        retry = await self.service.request(123, self.track_id)
        await self.service.execute((await self.job(retry))[0])
        self.assertEqual((await self.job(retry))[1], 'failed')
        self.assertEqual(self.bot.send_audio.await_count, 1)

    async def test_artwork_exception_or_timeout_does_not_block_audio_delivery(self):
        await self.check_artwork_failure(RuntimeError('private details'))

    async def test_artwork_timeout_does_not_block_audio_delivery(self):
        await self.check_artwork_failure(TimeoutError())

    async def check_artwork_failure(self, error):
        req = await self.service.request(123, self.track_id)
        job_id, _ = await self.job(req)
        with patch('music_bot.get_song.prepare_artwork', AsyncMock(side_effect=error)), \
             self.assertLogs('music_bot', level='WARNING') as logs:
            await self.service.execute(job_id)
        self.assertEqual((await self.job(req))[1], 'done')
        self.assertNotIn('private details', ' '.join(logs.output))
        self.assertIsNone(self.bot.send_audio.await_args.kwargs.get('thumbnail'))
        self.bot.send_audio.assert_awaited_once()

    async def test_prepared_thumbnail_is_sent_and_cover_identity_cached(self):
        from aiogram.types import FSInputFile
        async with self.database.write() as session:
            track = await session.get(Track, self.track_id)
            track.display_title, track.display_artist = 'Song', 'Artist'
        async def prepare(fetcher, track, path, folder, alive):
            thumbnail = Path(folder) / 'cover.jpg'
            thumbnail.write_bytes(b'mocked JPEG')
            return thumbnail, 'cover-identity'
        req = await self.service.request(123, self.track_id)
        with patch('music_bot.get_song.prepare_artwork', AsyncMock(side_effect=prepare)):
            await self.service.execute((await self.job(req))[0])
        sent = self.bot.send_audio.await_args.kwargs
        self.assertIsInstance(sent['thumbnail'], FSInputFile)
        self.assertEqual(sent['title'], 'Song')
        self.assertEqual(sent['performer'], 'Artist')
        async with self.database.sessions() as session:
            delivery = await session.scalar(select(AudioDelivery))
            self.assertEqual(delivery.artwork_key, 'cover-identity')
        self.assertEqual(list(self.service.root.iterdir()), [])

    async def test_recognized_identity_is_deduplicated_without_ratings(self):
        from music_bot.models import Rating, SongSubmission
        first = await self.service.request_recognized(123, 'Artist', 'Song')
        second = await self.service.request_recognized(123, 'Artist', 'Song')
        self.assertEqual(first, second)
        async with self.database.sessions() as session:
            self.assertEqual(len((await session.scalars(select(Track))).all()), 1)
            self.assertIsNone(await session.scalar(select(Rating)))
            self.assertIsNone(await session.scalar(select(SongSubmission)))

    async def test_shazam_art_fills_existing_coverless_track(self):
        art = 'https://is1-ssl.mzstatic.com/image/thumb/Music/test/400x400cc.jpg'
        await self.service.request_recognized(123, 'Artist', 'Song', artwork_url=art, album='Album')
        async with self.database.sessions() as session:
            track = await session.get(Track, self.track_id)
            self.assertEqual(track.artwork_url, art)
            self.assertEqual(track.album, 'Album')

    async def test_other_version_choice_has_separate_identity_and_owner_checks(self):
        async with self.database.write() as session:
            original = await session.get(Track, self.track_id)
            original.title, original.display_title = 'Song (Live)', 'Song (Live)'
        self.fetcher.search.return_value = [dict(id=VIDEO, title='Artist - Song (Official Audio)',
            recording_title='Song', artist='Artist', duration=200, score=1, exact=True, version=[])]
        req = await self.service.request(123, self.track_id, other_versions=True)
        await self.service.execute((await self.job(req))[0])
        self.assertTrue(self.fetcher.search.await_args.args[0].allow_versions)
        self.assertEqual(self.fetcher.search.await_args.args[0].title, 'Song')
        self.assertEqual((await self.job(req))[1], 'choice')
        await self.service.choose(123, req, 9, 0)
        async with self.database.sessions() as session:
            request = await session.get(AudioRequest, req)
            selected = await session.get(FetchJob, request.job_id)
            track = await session.get(Track, selected.track_id)
            self.assertNotEqual(track.id, self.track_id)
            self.assertEqual(track.display_title, 'Song')
        await self.service.execute((await self.job(req))[0])
        self.assertEqual((await self.job(req))[1], 'done')
        with self.assertRaises(FlowError):
            await self.service.other_versions(456, req, 8)
        with self.assertRaises(FlowError):
            await self.service.other_versions(123, req, 99)
        await self.service.other_versions(123, req, 8)

    async def test_recognition_versions_control_is_bound_to_owner_and_message(self):
        message = NS(message_id=55, edit_reply_markup=AsyncMock())
        request = await self.service.request(123, self.track_id)
        await self.service.bind_recognition_versions(123, request, message)
        keyboard = message.edit_reply_markup.await_args.kwargs['reply_markup']
        from music_bot.chat_ui import parse_control
        token, action, index = parse_control(keyboard.inline_keyboard[0][0].callback_data)
        self.assertEqual(action, 'versions')
        await self.chat.control(token, 123, 55, action, index)
        for user, message_id in ((456, 55), (123, 99)):
            with self.assertRaises(FlowError):
                await self.chat.control(token, user, message_id, action, index)

    async def test_downloaded_audio_shazam_artwork_matches_selected_recording(self):
        from music_bot.recognition import RecognizedSong
        art = 'https://is1-ssl.mzstatic.com/image/thumb/Music/test/400x400cc.jpg'
        self.service.recognizer = NS(recognize=AsyncMock(return_value=RecognizedSong(
            'Artist', 'Song', artwork_url=art, album='Album')))
        self.fetcher.process = AsyncMock()
        async with self.database.sessions() as session:
            track = await session.get(Track, self.track_id)
        with patch('music_bot.recognition.ffmpeg_executable', return_value='ffmpeg'):
            await self.service.shazam_artwork(track, Path(self.temp.name)/'test.m4a',
                self.temp.name, AsyncMock(return_value=True))
        self.assertEqual(track.artwork_url, art)
        self.assertEqual(track.album, 'Album')
        self.assertIn(track.id, self.service.art_attempted)

    async def test_shazam_artwork_rejects_wrong_version(self):
        from music_bot.recognition import RecognizedSong
        art = 'https://is1-ssl.mzstatic.com/image/thumb/Music/test/400x400cc.jpg'
        self.service.recognizer = NS(recognize=AsyncMock(return_value=RecognizedSong(
            'Artist', 'Song (Live)', artwork_url=art)))
        self.fetcher.process = AsyncMock()
        async with self.database.sessions() as session:
            track = await session.get(Track, self.track_id)
        with patch('music_bot.recognition.ffmpeg_executable', return_value='ffmpeg'):
            await self.service.shazam_artwork(track, Path(self.temp.name)/'test.m4a',
                self.temp.name, AsyncMock(return_value=True))
        self.assertIsNone(track.artwork_url)

    async def test_unreachable_existing_cover_can_be_replaced_with_verified_shazam_art(self):
        from music_bot.recognition import RecognizedSong
        art = 'https://is1-ssl.mzstatic.com/image/thumb/Music/test/400x400cc.jpg'
        async with self.database.write() as session:
            track = await session.get(Track, self.track_id)
            track.artwork_url = 'https://lastfm.freetls.fastly.net/i/u/cover.jpg'
        self.service.recognizer = NS(recognize=AsyncMock(return_value=RecognizedSong(
            'Artist', 'Song', artwork_url=art)))
        self.fetcher.process = AsyncMock()
        with patch('music_bot.recognition.ffmpeg_executable', return_value='ffmpeg'):
            await self.service.shazam_artwork(track, Path(self.temp.name)/'test.m4a', self.temp.name,
                AsyncMock(return_value=True), force=True)
        self.assertEqual(track.artwork_url, art)

    async def test_transient_search_failure_retries_once(self):
        row = dict(id=VIDEO, title='Song', artist='Artist', duration=200, score=1, exact=True)
        self.fetcher.search.side_effect = [FetchError('Audio source unavailable.'), [row]]
        req = await self.service.request(123, self.track_id)
        await self.service.execute((await self.job(req))[0])
        self.assertEqual((await self.job(req))[1], 'done')
        self.assertEqual(self.fetcher.search.await_count, 2)

    async def test_transient_download_failure_retries_once(self):
        attempts = 0
        async def fetch(*args):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise FetchError('Audio source unavailable.')
            return await self.audio(*args)
        self.fetcher.fetch.side_effect = fetch
        req = await self.service.request(123, self.track_id)
        await self.service.execute((await self.job(req))[0])
        self.assertEqual((await self.job(req))[1], 'done')
        self.assertEqual(attempts, 2)

    async def test_search_failure_is_bounded_and_explained(self):
        self.fetcher.search.side_effect = FetchError('Audio source unavailable.')
        req = await self.service.request(123, self.track_id)
        await self.service.execute((await self.job(req))[0])
        self.assertEqual((await self.job(req))[1], 'failed')
        self.assertEqual(self.fetcher.search.await_count, 2)
        self.assertIn('Could not verify an original recording', self.bot.send_message.await_args.args[1])

    async def test_wrong_button_is_bound_to_delivered_request_and_message(self):
        req = await self.service.request(123, self.track_id)
        await self.service.execute((await self.job(req))[0])
        self.assertIsNone(self.bot.send_audio.call_args.kwargs.get('reply_markup'))
        for user, message in [(456, 8), (123, 99)]:
            with self.assertRaises(FlowError):
                await self.service.wrong(user, req, message)
        async with self.database.sessions() as s:
            original = await s.get(AudioRequest, req)
            self.assertEqual(original.delivered_video_id, VIDEO)
            self.assertIsNone(await s.scalar(select(AudioSelection)))
        first, second = await asyncio.gather(self.service.wrong(123, req, 8), self.service.wrong(123, req, 8))
        self.assertEqual(first, second)
        self.fetcher.fetch.assert_awaited_once()

    async def test_old_delivery_keeps_its_identity_when_search_job_is_reused(self):
        original = await self.service.request(123, self.track_id)
        await self.service.execute((await self.job(original))[0])
        later = await self.service.request(123, self.track_id)
        await self.service.execute((await self.job(later))[0])
        async with self.database.sessions() as s:
            job = await s.get(FetchJob, (await s.get(AudioRequest, original)).job_id)
            self.assertIsNone(job.video_id)
        await self.service.wrong(123, original, 8)
        async with self.database.sessions() as s:
            self.assertEqual((await s.scalar(select(AudioSelection))).rejected_ids, [VIDEO])

    async def test_wrong_callback_acknowledges_before_queue_without_fetching(self):
        from aiogram.types import Message
        from music_bot.handlers import wrong_song
        req = await self.service.request(123, self.track_id)
        await self.service.execute((await self.job(req))[0])
        query = NS(data='w:'+req, from_user=NS(id=123, is_bot=False), answer=AsyncMock(),
            message=Message.model_validate(dict(message_id=8, date=1, chat=dict(id=123, type='private'))))
        self.fetcher.search.reset_mock()
        self.fetcher.fetch.reset_mock()
        real_wrong = self.service.wrong
        async def queued(*args):
            query.answer.assert_awaited_once()
            return await real_wrong(*args)
        with patch.object(Message, 'answer', new_callable=AsyncMock, return_value=NS(message_id=99)), patch.object(self.service, 'wrong', side_effect=queued):
            await wrong_song(query, self.service)
        self.fetcher.search.assert_not_awaited()
        self.fetcher.fetch.assert_not_awaited()

    async def test_wrong_song_alternatives_and_saved_choice_survive_new_service(self):
        replacement = 'bcdefghijkl'
        req = await self.service.request(123, self.track_id)
        await self.service.execute((await self.job(req))[0])
        retry = await self.service.wrong(123, req, 8)
        self.fetcher.search.return_value = [dict(id=VIDEO, title='Song', artist='Artist', duration=200, score=1, exact=True),
                                          dict(id=replacement, title='Song', artist='Artist', duration=200, score=1, exact=True)]
        recovered = GetSong(self.database, self.bot, self.service.settings, self.fetcher)
        recovered.root = self.service.root
        await recovered.execute((await self.job(retry))[0])
        self.assertEqual((await self.job(retry))[1], 'choice')
        async with self.database.sessions() as s:
            job = await s.get(FetchJob, (await s.get(AudioRequest, retry)).job_id)
            self.assertEqual([row['id'] for row in job.candidates], [replacement])
        await self.service.choose(123, retry, 9, 0)
        await self.service.execute((await self.job(retry))[0])
        async with self.database.sessions() as s:
            self.assertEqual((await s.scalar(select(AudioSelection))).video_id, replacement)
        fresh_service = GetSong(self.database, self.bot, self.service.settings, self.fetcher)
        fresh_service.root = self.service.root
        later = await fresh_service.request(123, self.track_id)
        await fresh_service.execute((await self.job(later))[0])
        self.assertEqual(self.fetcher.fetch.await_count, 2)
        self.assertEqual(self.fetcher.search.await_count, 2)
        self.assertEqual(self.bot.send_audio.call_args.kwargs['audio'], 'telegram-file')
        self.assertEqual((await self.job(later))[1], 'done')
        self.assertEqual(list(self.service.root.iterdir()), [])

    async def test_wrong_song_does_not_change_another_users_cache(self):
        await self.chat.ensure_user(Submitter(456, 'other', 'Other'))
        req = await self.service.request(123, self.track_id)
        other = await self.service.request(456, self.track_id)
        await self.service.execute((await self.job(req))[0])
        await self.service.wrong(123, req, 8)
        async with self.database.sessions() as s:
            deliveries = list((await s.scalars(select(AudioDelivery))).all())
            self.assertEqual(len(deliveries), 1)
            self.assertEqual(deliveries[0].user_id, (await s.get(AudioRequest, other)).user_id)
        again = await self.service.request(456, self.track_id)
        await self.service.execute((await self.job(again))[0])
        self.fetcher.fetch.assert_awaited_once()
        self.assertEqual(self.bot.send_audio.call_args.kwargs['audio'], 'telegram-file')

    async def test_wrong_song_obeys_limits_without_invalidating_cache(self):
        req = await self.service.request(123, self.track_id)
        await self.service.execute((await self.job(req))[0])
        self.service.settings = replace(self.service.settings, per_hour=1)
        with self.assertRaises(FetchError):
            await self.service.wrong(123, req, 8)
        async with self.database.sessions() as s:
            self.assertIsNone(await s.scalar(select(AudioSelection)))
            self.assertIsNotNone(await s.scalar(select(AudioDelivery)))
            self.assertEqual((await s.get(AudioRequest, req)).state, 'done')

    async def test_expired_feedback_and_rejected_choice_fail_server_side(self):
        from datetime import timedelta
        from music_bot.models import utc_now
        req = await self.service.request(123, self.track_id)
        await self.service.execute((await self.job(req))[0])
        retry = await self.service.wrong(123, req, 8)
        async with self.database.write() as s:
            original = await s.get(AudioRequest, req)
            original.created_at = utc_now() - timedelta(days=10)
            current = await s.get(AudioRequest, retry)
            current.state, current.message_id = 'choice', 9
            job = await s.get(FetchJob, current.job_id)
            job.candidates = [dict(id=VIDEO, title='Song', artist='Artist', duration=200)]
        with self.assertRaises(FlowError):
            await self.service.wrong(123, req, 8)
        with self.assertRaises(FlowError):
            await self.service.choose(123, retry, 9, 0)

    async def test_no_alternatives_never_resends_rejected_audio(self):
        req = await self.service.request(123, self.track_id)
        await self.service.execute((await self.job(req))[0])
        retry = await self.service.wrong(123, req, 8)
        await self.service.execute((await self.job(retry))[0])
        self.assertEqual((await self.job(retry))[1], 'failed')
        self.fetcher.fetch.assert_awaited_once()
        self.bot.send_audio.assert_awaited_once()
        self.assertIn('No other matching recordings', self.bot.send_message.call_args.args[1])

    async def test_forget_and_retention_remove_recording_corrections(self):
        from datetime import timedelta
        from music_bot.models import utc_now
        req = await self.service.request(123, self.track_id)
        await self.service.execute((await self.job(req))[0])
        retry = await self.service.wrong(123, req, 8)
        async with self.database.write() as s:
            (await s.scalar(select(AudioSelection))).updated_at = utc_now() - timedelta(days=10)
        await self.service.maintenance()
        async with self.database.sessions() as s:
            self.assertIsNone(await s.scalar(select(AudioSelection)))
        await self.service.cancel(123, forget=True)
        await self.chat.forget(123)
        with self.assertRaises(FlowError):
            await self.service.wrong(123, req, 8)

    async def test_forget_removes_existing_private_correction(self):
        req = await self.service.request(123, self.track_id)
        await self.service.execute((await self.job(req))[0])
        await self.service.wrong(123, req, 8)
        await self.service.cancel(123, forget=True)
        await self.chat.forget(123)
        async with self.database.sessions() as s:
            self.assertIsNone(await s.scalar(select(AudioSelection)))

    async def test_cached_audio_never_refetches_for_artwork_upgrade(self):
        from music_bot.audio_artwork import artwork_key
        req = await self.service.request(123, self.track_id)
        await self.service.execute((await self.job(req))[0])
        async with self.database.write() as s:
            track = await s.get(Track, self.track_id)
            track.artwork_url = 'https://lastfm.freetls.fastly.net/i/u/300x300/album.jpg'
            key = artwork_key(track)
        async def prepare(fetcher, track, path, folder, alive):
            thumbnail = Path(folder)/'cover.jpg'
            thumbnail.write_bytes(b'test image')
            return thumbnail, key
        with patch('music_bot.get_song.prepare_artwork', AsyncMock(side_effect=prepare)) as decorate:
            req = await self.service.request(123, self.track_id)
            await self.service.execute((await self.job(req))[0])
            self.assertNotIn('thumbnail', self.bot.send_audio.call_args.kwargs)
            req = await self.service.request(123, self.track_id)
            await self.service.execute((await self.job(req))[0])
            self.assertEqual(decorate.await_count, 0)
        self.assertEqual(self.fetcher.fetch.await_count, 1)
        self.assertEqual(self.bot.send_audio.call_args.kwargs['audio'], 'telegram-file')
        self.assertNotIn('thumbnail', self.bot.send_audio.call_args.kwargs)
        async with self.database.sessions() as s:
            self.assertIsNone((await s.scalar(select(AudioDelivery))).artwork_key)

    async def test_duplicate_requests_share_job(self):
        first, second = await asyncio.gather(self.service.request(123, self.track_id), self.service.request(123, self.track_id))
        self.assertEqual(first, second)
        await self.chat.ensure_user(Submitter(456, 'other', 'Other'))
        other = await self.service.request(456, self.track_id)
        self.assertEqual((await self.job(first))[0], (await self.job(other))[0])

    async def test_uncertain_choice_is_bound_to_user_and_message(self):
        self.fetcher.search.return_value[0]['exact'] = False
        req = await self.service.request(123, self.track_id)
        await self.service.execute((await self.job(req))[0])
        self.assertEqual((await self.job(req))[1], 'choice')
        self.fetcher.fetch.assert_not_awaited()
        with self.assertRaises(FlowError):
            await self.service.choose(456, req, 9, 0)
        with self.assertRaises(FlowError):
            await self.service.choose(123, req, 10, 0)
        await self.service.choose(123, req, 9, 0)
        await self.service.execute((await self.job(req))[0])
        self.assertEqual((await self.job(req))[1], 'done')
        with self.assertRaises(FlowError):
            await self.service.choose(123, req, 9, 0)

    async def test_limits_and_cancel(self):
        self.service.settings = replace(self.service.settings, per_hour=1)
        req = await self.service.request(123, self.track_id)
        await self.service.cancel(123)
        with self.assertRaises(FetchError):
            await self.service.request(123, self.track_id)
        self.assertFalse(await self.service.alive((await self.job(req))[0]))

    async def test_failure_cleans_partial_files(self):
        async def fail(video, directory, alive):
            (Path(directory) / 'source.part').write_bytes(b'partial')
            raise RuntimeError('sensitive provider error')
        self.fetcher.fetch.side_effect = fail
        req = await self.service.request(123, self.track_id)
        await self.service.execute((await self.job(req))[0])
        self.assertEqual((await self.job(req))[1], 'failed')
        self.assertEqual(list(self.service.root.iterdir()), [])
        self.assertNotIn('sensitive', str(self.bot.send_message.call_args))
        keyboard = self.bot.send_message.call_args.kwargs['reply_markup']
        self.assertEqual(keyboard.inline_keyboard[0][0].url,
                         'https://www.youtube.com/watch?v=' + VIDEO)

    async def test_recovery_and_no_ambiguous_resend(self):
        req = await self.service.request(123, self.track_id)
        job_id, _ = await self.job(req)
        async with self.database.write() as s:
            (await s.get(FetchJob, job_id)).state = 'running'
            (await s.get(AudioRequest, req)).state = 'sending'
        stale = self.service.root / 'job-stale'
        stale.mkdir()
        (stale / 'part').write_bytes(b'partial')
        await self.service.start()
        await self.service.close()
        self.assertEqual((await self.job(req))[1], 'uncertain')
        self.assertFalse(stale.exists())
        self.bot.send_audio.assert_not_awaited()

    async def test_forget_removes_cache_and_waiters(self):
        req = await self.service.request(123, self.track_id)
        await self.service.execute((await self.job(req))[0])
        await self.service.cancel(123, forget=True)
        await self.chat.forget(123)
        async with self.database.sessions() as s:
            self.assertIsNone(await s.scalar(select(AudioDelivery)))
            self.assertIsNone(await s.scalar(select(AudioRequest)))

    async def test_stale_cache_fetches_again(self):
        from aiogram.exceptions import TelegramBadRequest
        from aiogram.methods import SendAudio
        req = await self.service.request(123, self.track_id)
        await self.service.execute((await self.job(req))[0])
        error = TelegramBadRequest(method=SendAudio(chat_id=123, audio='old'), message='wrong file identifier')
        self.bot.send_audio.side_effect = [error, NS(audio=NS(file_id='new-file'), message_id=10)]
        req = await self.service.request(123, self.track_id)
        await self.service.execute((await self.job(req))[0])
        self.assertEqual((await self.job(req))[1], 'done')
        self.assertEqual(self.fetcher.fetch.await_count, 2)

    def test_matching_rejects_wrong_versions_and_duration(self):
        track = NS(artist='Artist', title='Song', duration=200)
        rows = [dict(id=VIDEO, artist='Artist', track='Song', title='Artist - Song', duration=200)]
        ranked = rank_candidates(track, rows, 900)
        self.assertTrue(confident(ranked))
        for change in [dict(title='Artist Song live'), dict(duration=500), dict(is_live=True), dict(id='bad')]:
            self.assertEqual(rank_candidates(track, [{**rows[0], **change}], 900), [])
        track.title = 'Song live'
        self.assertTrue(rank_candidates(track, [{**rows[0], 'track':'Song live', 'title':'Artist Song live'}], 900))

    async def test_cache_never_reused_for_another_user(self):
        req = await self.service.request(123, self.track_id)
        await self.service.execute((await self.job(req))[0])
        await self.chat.ensure_user(Submitter(456, 'other', 'Other'))
        req = await self.service.request(456, self.track_id)
        await self.service.execute((await self.job(req))[0])
        self.assertEqual(self.fetcher.fetch.await_count, 2)
        self.assertNotIsInstance(self.bot.send_audio.call_args.kwargs['audio'], str)

    async def test_queue_and_duration_limits(self):
        self.service.settings = replace(self.service.settings, queue_limit=1)
        await self.service.request(123, self.track_id)
        await self.chat.ensure_user(Submitter(456, 'other', 'Other'))
        with self.assertRaises(FetchError):
            await self.service.request(456, self.track_id)
        await self.service.cancel(123)
        async with self.database.write() as s:
            (await s.get(Track, self.track_id)).duration = 9999
        with self.assertRaises(FetchError):
            await self.service.request(456, self.track_id)

    async def test_worker_cancellation_cleans_artifact(self):
        reached = asyncio.Event()
        async def waiting(video, directory, alive):
            (Path(directory) / 'partial').write_bytes(b'partial')
            reached.set()
            await asyncio.Event().wait()
        self.fetcher.fetch.side_effect = waiting
        req = await self.service.request(123, self.track_id)
        task = asyncio.create_task(self.service.execute((await self.job(req))[0]))
        await asyncio.wait_for(reached.wait(), 5)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        self.assertEqual(list(self.service.root.iterdir()), [])
        self.bot.send_audio.assert_not_awaited()

    async def test_restart_resumes_interrupted_fetch(self):
        req = await self.service.request(123, self.track_id)
        job_id, _ = await self.job(req)
        async with self.database.write() as s:
            (await s.get(FetchJob, job_id)).state = 'running'
        await self.service.start()
        try:
            async with asyncio.timeout(10):
                while (await self.job(req))[1] != 'done':
                    await asyncio.sleep(.05)
        finally:
            await self.service.close()
        self.bot.send_audio.assert_awaited_once()

    async def test_control_canonical_identity_and_cross_user_rejection(self):
        token = await self.chat.create_control(123, tracks=[self.track_id])
        await self.chat.bind_control(token, 10)
        with self.assertRaises(FlowError):
            await self.chat.control(token, 456, 10, 'get', 0)
        with self.assertRaises(FlowError):
            await self.chat.control(token, 123, 11, 'get', 0)
        with self.assertRaises(FlowError):
            await self.chat.control(token, 123, 10, 'get', 4)
        _, track = await self.chat.control(token, 123, 10, 'get', 0)
        self.assertEqual(track.id, self.track_id)
        await self.chat.control(token, 123, 10, 'get', 0)  # Repeat supports cache requests.

    async def test_subprocess_cancel_kills_and_waits(self):
        from unittest.mock import patch, Mock
        from music_bot.youtube_fetch import YouTubeFetcher
        process = NS(returncode=None, kill=Mock(), wait=AsyncMock())
        with patch('asyncio.create_subprocess_exec', AsyncMock(return_value=process)):
            with self.assertRaises(FetchError):
                await YouTubeFetcher(self.service.settings).process(['safe-tool'], self.service.root,
                    AsyncMock(return_value=False))
        process.kill.assert_called_once()
        process.wait.assert_awaited()

    async def test_subprocess_timeout_and_disk_budget(self):
        from unittest.mock import patch, Mock
        from music_bot.youtube_fetch import YouTubeFetcher
        for disk in (False, True):
            async def wait():
                await asyncio.Event().wait()
            process = NS(returncode=None, kill=Mock(), wait=AsyncMock(side_effect=wait))
            def kill():
                process.returncode = -9
                process.wait.side_effect = None
            process.kill.side_effect = kill
            if disk:
                (self.service.root / 'oversized').write_bytes(b'large')
            settings = replace(self.service.settings, timeout=.02, disk_bytes=1 if disk else 10000)
            with patch('asyncio.create_subprocess_exec', AsyncMock(return_value=process)):
                with self.assertRaises((FetchError, TimeoutError)):
                    await YouTubeFetcher(settings).process(['safe-tool'], self.service.root,
                        AsyncMock(return_value=True))
            process.kill.assert_called_once()

    async def test_retention_removes_personal_audio_records(self):
        from datetime import timedelta
        from music_bot.models import utc_now
        req = await self.service.request(123, self.track_id)
        await self.service.execute((await self.job(req))[0])
        async with self.database.write() as s:
            (await s.get(AudioRequest, req)).created_at = utc_now() - timedelta(days=10)
            delivery = await s.scalar(select(AudioDelivery))
            delivery.created_at = utc_now() - timedelta(days=10)
        await self.service.maintenance()
        async with self.database.sessions() as s:
            self.assertIsNone(await s.get(AudioRequest, req))
            self.assertIsNone(await s.scalar(select(AudioDelivery)))

    async def test_get_callback_acknowledges_before_queue_and_never_fetches(self):
        from unittest.mock import patch
        from aiogram.types import Message
        from music_bot.chat_handlers import callback
        token = await self.chat.create_control(123, tracks=[self.track_id])
        await self.chat.bind_control(token, 10)
        message = Message.model_validate(dict(message_id=10, date=1, chat=dict(id=123, type='private')))
        query = NS(data=f'q:{token}:get:0', message=message, from_user=NS(id=123, is_bot=False), answer=AsyncMock())
        with patch.object(Message, 'answer', new_callable=AsyncMock) as answer:
            answer.return_value = NS(message_id=99, edit_text=AsyncMock())
            original = self.service.request
            async def queued(user, track, **kwargs):
                query.answer.assert_awaited_once()
                answer.assert_awaited_once()
                return await original(user, track, **kwargs)
            with patch.object(self.service, 'request', side_effect=queued):
                await callback(query, self.chat, self.service)
        self.fetcher.search.assert_not_awaited()
        self.fetcher.fetch.assert_not_awaited()

    async def test_different_canonical_versions_do_not_share_jobs(self):
        async with self.database.write() as s:
            version = Track(artist='Artist', title='Song live', duration=200, metadata_source='test')
            s.add(version)
            await s.flush()
            other_id = version.id
        first = await self.service.request(123, self.track_id)
        second = await self.service.request(123, other_id)
        self.assertNotEqual((await self.job(first))[0], (await self.job(second))[0])

    async def test_adapter_preserves_m4a_and_checks_actual_media(self):
        import json
        from music_bot.youtube_fetch import YouTubeFetcher
        fetcher = YouTubeFetcher(self.service.settings)
        async def process(args, directory, alive, output=False):
            if args[0] == 'ffprobe':
                return json.dumps({'format': {'duration': '200'}, 'streams': [{'codec_type':'audio','codec_name':'aac'}]}).encode()
            (Path(directory) / 'source.m4a').write_bytes(b'audio')
            return b''
        fetcher.process = AsyncMock(side_effect=process)
        path = await fetcher.fetch(VIDEO, self.service.root, AsyncMock(return_value=True))
        self.assertEqual(path.suffix, '.m4a')
        self.assertFalse(any(c.args[0][0] == 'ffmpeg' for c in fetcher.process.call_args_list))
        self.assertIn('--ignore-config', fetcher.process.call_args_list[0].args[0])
        with self.assertRaises(FetchError):
            await fetcher.fetch('https://example.com', self.service.root, AsyncMock(return_value=True))

    async def test_adapter_rejects_oversized_and_overlong_media(self):
        import json
        from music_bot.youtube_fetch import YouTubeFetcher
        settings = replace(self.service.settings, max_bytes=10)
        fetcher = YouTubeFetcher(settings)
        for size, duration in [(11, '200'), (5, '9999')]:
            async def process(args, directory, alive, output=False):
                if args[0] == 'ffprobe':
                    return json.dumps({'format': {'duration': duration}, 'streams': [{'codec_type':'audio','codec_name':'aac'}]}).encode()
                (Path(directory) / 'source.m4a').write_bytes(b'x' * size)
                return b''
            fetcher.process = AsyncMock(side_effect=process)
            with self.assertRaises(FetchError):
                await fetcher.fetch(VIDEO, self.service.root, AsyncMock(return_value=True))

    async def test_disabled_worker_cancels_recovered_requests(self):
        req = await self.service.request(123, self.track_id)
        self.service.settings = replace(self.service.settings, enabled=False)
        await self.service.start()
        await self.service.close()
        self.assertEqual((await self.job(req))[1], 'cancelled')
        self.fetcher.fetch.assert_not_awaited()
