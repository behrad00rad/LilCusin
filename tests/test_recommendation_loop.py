import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from sqlalchemy import delete, func, select, update

from music_bot.chat_service import ChatService
from music_bot.get_song import FetchSettings, GetSong
from music_bot.models import Rating, RecommendationHistory, SimilarTrack, Track, User, utc_now
from music_bot.providers.common import TrackCandidate
from music_bot.recommendations import RecommendationService
from music_bot.recommendations.queue import QueuedRecommendation
from music_bot.recommendations.repository import load_profile
from music_bot.recommendations.scoring import seed_weight
from music_bot.recommendations.types import Recommendation, RecommendationResult
from music_bot.taste_learning import LearningState, TasteRequest, TrackPreference, feedback, record_request
from music_bot.taste_setup import save_setup
from music_bot.social import SavedSong, remove_saved
from music_bot.workflow import FlowError, save_rating
from tests.recommendation_fixture import TELEGRAM_ID, populate
from tests.support import ServiceTestCase


class RecommendationLoopTests(ServiceTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.tracks = await populate(self.database)
        self.engine = RecommendationService(self.database)
        self.chat = ChatService(self.database, self.engine)
        async with self.database.sessions() as session:
            self.internal = await session.scalar(select(User.id).where(User.telegram_user_id == TELEGRAM_ID))

    async def asyncTearDown(self):
        await self.engine.close()
        await super().asyncTearDown()

    async def count(self, model):
        async with self.database.sessions() as session:
            return await session.scalar(select(func.count()).select_from(model))

    async def signal(self, key='one', track=None):
        async with self.database.write() as session:
            return await record_request(session, self.internal, track or self.tracks['metal_0'], key)

    async def test_request_evidence_deduplicates_and_repeat_weight_is_capped(self):
        self.assertTrue(await self.signal())
        self.assertFalse(await self.signal())
        for index in range(4):
            await self.signal(str(index))
        async with self.database.sessions() as session:
            profile = await load_profile(session, TELEGRAM_ID)
        seed = next(seed for seed in profile.positives if seed.item.track_id == self.tracks['metal_0'])
        self.assertEqual(seed.rating, 'requested')
        self.assertEqual(seed_weight(seed), .3)
        self.assertEqual(await self.count(Rating), 4)
        self.assertEqual(await self.count(TasteRequest), 5)

    async def test_explicit_neutral_overrides_requests_and_save(self):
        await self.signal()
        async with self.database.write() as session:
            await feedback(session, self.internal, self.tracks['metal_0'], 'save')
            await save_rating(session, self.internal, self.tracks['metal_0'], 'neutral')
        async with self.database.sessions() as session:
            profile = await load_profile(session, TELEGRAM_ID)
        self.assertNotIn(self.tracks['metal_0'], {seed.item.track_id for seed in profile.positives})

    async def test_save_is_stronger_and_known_is_not_a_negative(self):
        async with self.database.write() as session:
            await feedback(session, self.internal, self.tracks['metal_0'], 'save')
            await feedback(session, self.internal, self.tracks['piano_0'], 'known')
        async with self.database.sessions() as session:
            profile = await load_profile(session, TELEGRAM_ID)
        seed = next(seed for seed in profile.positives if seed.item.track_id == self.tracks['metal_0'])
        self.assertEqual(seed_weight(seed), 1.5)
        self.assertNotIn(self.tracks['piano_0'], {seed.item.track_id for seed in profile.negatives})
        result = await self.engine.recommend_for_user(TELEGRAM_ID)
        self.assertFalse({self.tracks['metal_0'], self.tracks['piano_0']} & {row.track_id for row in result.recommendations})

    async def test_not_for_me_is_separate_from_rating_and_can_be_corrected(self):
        async with self.database.write() as session:
            await feedback(session, self.internal, self.tracks['metal_0'], 'notforme')
        async with self.database.sessions() as session:
            profile = await load_profile(session, TELEGRAM_ID)
        self.assertIn(self.tracks['metal_0'], {seed.item.track_id for seed in profile.negatives})
        self.assertEqual(await self.count(Rating), 4)
        async with self.database.write() as session:
            await feedback(session, self.internal, self.tracks['metal_0'], 'save')
        async with self.database.sessions() as session:
            profile = await load_profile(session, TELEGRAM_ID)
        self.assertNotIn(self.tracks['metal_0'], {seed.item.track_id for seed in profile.negatives})

    async def test_pause_reset_and_forget_clear_private_evidence(self):
        await self.chat.set_learning(TELEGRAM_ID, False)
        self.assertFalse(await self.signal())
        await self.chat.set_learning(TELEGRAM_ID, True)
        self.assertTrue(await self.signal())
        await self.engine.queue.fill(TELEGRAM_ID)
        await self.chat.reset_learning(TELEGRAM_ID)
        for model in (TasteRequest, TrackPreference, QueuedRecommendation, Rating):
            self.assertEqual(await self.count(model), 0)
        await self.chat.forget(TELEGRAM_ID)
        self.assertEqual(await self.count(LearningState), 0)

    async def test_request_event_retention_is_bounded(self):
        with patch('music_bot.taste_learning.MAX_REQUEST_EVENTS', 2):
            for key in ('one', 'two', 'three'):
                await self.signal(key)
        self.assertEqual(await self.count(TasteRequest), 2)
        async with self.database.write() as session:
            await session.execute(update(TasteRequest).values(created_at=utc_now() - timedelta(days=91)))
        await self.signal('new')
        self.assertEqual(await self.count(TasteRequest), 1)

    async def test_get_song_records_once_without_download_or_rating(self):
        service = GetSong(self.database, AsyncMock(), FetchSettings(enabled=True), AsyncMock())
        first = await service.request(TELEGRAM_ID, self.tracks['metal_0'])
        repeat = await service.request(TELEGRAM_ID, self.tracks['metal_0'])
        self.assertEqual(first, repeat)
        self.assertEqual(await self.count(TasteRequest), 1)
        self.assertEqual(await self.count(Rating), 4)

    async def test_queue_reservations_are_distinct_and_do_not_record_display(self):
        first, second = await asyncio.gather(self.engine.queue.reserve(TELEGRAM_ID), self.engine.queue.reserve(TELEGRAM_ID))
        self.assertEqual(len(first.recommendations), 5)
        self.assertEqual(len(second.recommendations), 5)
        self.assertFalse({row.track_id for row in first.recommendations} & {row.track_id for row in second.recommendations})
        self.assertEqual(await self.count(RecommendationHistory), 0)

    async def test_queue_survives_restart_and_failed_send_release(self):
        batch = await self.engine.queue.reserve(TELEGRAM_ID)
        await self.engine.queue.release(TELEGRAM_ID, batch.batch_id)
        await self.engine.close()
        self.engine = RecommendationService(self.database)
        with patch.object(self.engine, '_recommend', new_callable=AsyncMock) as generate:
            replay = await self.engine.queue.reserve(TELEGRAM_ID)
            generate.assert_not_awaited()
        self.assertEqual([row.track_id for row in batch.recommendations], [row.track_id for row in replay.recommendations])

    async def test_stale_lease_expires_and_display_commits_only_sent_rows(self):
        batch = await self.engine.queue.reserve(TELEGRAM_ID)
        async with self.database.write() as session:
            await session.execute(update(QueuedRecommendation).where(QueuedRecommendation.lease == batch.batch_id)
                .values(lease_until=utc_now() - timedelta(seconds=1)))
        replay = await self.engine.queue.reserve(TELEGRAM_ID)
        self.assertEqual(batch.recommendations, replay.recommendations)
        await self.chat.record_displayed(TELEGRAM_ID, replay.recommendations[:2], 'test', None, queue_batch=replay.batch_id)
        await self.engine.queue.release(TELEGRAM_ID, replay.batch_id)
        self.assertEqual(await self.count(RecommendationHistory), 2)
        again = await self.engine.queue.reserve(TELEGRAM_ID)
        self.assertFalse({row.track_id for row in replay.recommendations[:2]} & {row.track_id for row in again.recommendations})

    async def test_preference_change_invalidates_queue_and_inflight_refill(self):
        started, proceed = asyncio.Event(), asyncio.Event()
        generate = self.engine._recommend
        async def delayed(*args, **kwargs):
            result = await generate(*args, **kwargs)
            started.set()
            await proceed.wait()
            return result
        with patch.object(self.engine, '_recommend', side_effect=delayed):
            filling = asyncio.create_task(self.engine.queue.fill(TELEGRAM_ID))
            await started.wait()
            await self.chat.reset_learning(TELEGRAM_ID)
            proceed.set()
            await filling
        self.assertEqual(await self.count(QueuedRecommendation), 0)

    async def test_feedback_controls_are_owner_and_message_bound(self):
        token = await self.chat.create_control(TELEGRAM_ID, tracks=[self.tracks['metal_0']])
        await self.chat.bind_control(token, 101)
        for user_id, message_id in ((999, 101), (TELEGRAM_ID, 102)):
            with self.assertRaises(FlowError):
                await self.chat.control(token, user_id, message_id, 'save', 0)
        for _ in range(2):
            await self.chat.control(token, TELEGRAM_ID, 101, 'save', 0)
        self.assertEqual(await self.count(TrackPreference), 1)

    async def test_queue_close_cancels_warming_without_new_history(self):
        with patch.object(self.engine, '_recommend', side_effect=asyncio.CancelledError):
            self.engine.queue.warm(TELEGRAM_ID)
            await asyncio.sleep(0)
            await self.engine.close()
        self.assertFalse(self.engine.queue.tasks)
        self.assertEqual(await self.count(RecommendationHistory), 0)

    async def test_expired_queue_and_recent_aliases_are_not_served(self):
        await self.engine.queue.fill(TELEGRAM_ID)
        async with self.database.write() as session:
            await session.execute(update(QueuedRecommendation).values(expires_at=utc_now() - timedelta(seconds=1)))
        with patch.object(self.engine.queue, 'fill', new_callable=AsyncMock):
            batch = await self.engine.queue.reserve(TELEGRAM_ID)
        self.assertFalse(batch.recommendations)

    async def test_recent_alias_added_after_prefetch_is_filtered(self):
        await self.engine.queue.fill(TELEGRAM_ID)
        async with self.database.write() as session:
            queued = await session.scalar(select(QueuedRecommendation).where(QueuedRecommendation.user_id == self.internal))
            original = await session.get(Track, queued.track_id)
            alias = Track(artist=original.artist + ' legacy alias', title=original.title,
                display_artist=original.display_artist, display_title=original.display_title, metadata_source='fixture')
            session.add(alias)
            await session.flush()
            session.add(RecommendationHistory(user_id=self.internal, track_id=alias.id, recommended_at=utc_now()))
            original_id = original.id
        result = await self.engine.queue.reserve(TELEGRAM_ID)
        self.assertNotIn(original_id, {row.track_id for row in result.recommendations})

    async def test_deleted_account_generation_cannot_receive_old_refill(self):
        started, proceed = asyncio.Event(), asyncio.Event()
        generate = self.engine._recommend
        async def delayed(*args, **kwargs):
            result = await generate(*args, **kwargs)
            started.set()
            await proceed.wait()
            return result
        with patch.object(self.engine, '_recommend', side_effect=delayed):
            filling = asyncio.create_task(self.engine.queue.fill(TELEGRAM_ID))
            await started.wait()
            await self.chat.forget(TELEGRAM_ID)
            async with self.database.write() as session:
                session.add(User(id=self.internal, telegram_user_id=999))
                await session.flush()
                from music_bot.taste_learning import learning_state
                await learning_state(session, self.internal)
            proceed.set()
            await filling
        self.assertEqual(await self.count(QueuedRecommendation), 0)

    async def test_setup_only_queue_excludes_known_history_and_reserved_candidates(self):
        async with self.database.write() as session:
            await session.execute(delete(Rating))
            await feedback(session, self.internal, self.tracks['metal_0'], 'known')
            for index in range(12):
                session.add(Track(artist='forge', title=f'setup song {index}', metadata_source='fixture'))
        await save_setup(self.database, TELEGRAM_ID, style='rock', artist='Forge')
        first = await self.engine.queue.reserve(TELEGRAM_ID)
        self.assertTrue(first.recommendations)
        await self.chat.record_displayed(TELEGRAM_ID, first.recommendations, 'starter', None, queue_batch=first.batch_id)
        second = await self.engine.queue.reserve(TELEGRAM_ID)
        self.assertFalse({row.track_id for row in first.recommendations} & {row.track_id for row in second.recommendations})
        self.assertNotIn(self.tracks['metal_0'], {row.track_id for row in second.recommendations})

    async def test_saved_library_is_private_and_summary_includes_activity(self):
        await self.signal()
        async with self.database.write() as session:
            await feedback(session, self.internal, self.tracks['piano_0'], 'save')
        self.assertEqual([row.id for row in await self.chat.saved_tracks(TELEGRAM_ID)], [self.tracks['piano_0']])
        self.assertFalse(await self.chat.saved_tracks(999))
        summary = await self.chat.taste_summary(TELEGRAM_ID)
        self.assertEqual((summary['requests'], summary['saves']), (1, 1))
        self.assertEqual(summary['songs'], 6)
        self.assertTrue(await self.chat.is_saved(TELEGRAM_ID, self.tracks['piano_0']))
        self.assertFalse(await self.chat.is_saved(999, self.tracks['piano_0']))

    async def test_only_requested_songs_bootstrap_without_onboarding(self):
        async with self.database.write() as session:
            await session.execute(delete(Rating))
        await self.signal(track=self.tracks['metal_seed'])
        result = await self.engine.recommend_for_user(TELEGRAM_ID)
        self.assertEqual(result.status, 'ok')
        self.assertTrue(all('requested' in row.reason for row in result.recommendations))
        self.assertEqual(await self.count(Rating), 0)

    async def test_next_refill_rotates_provider_seed_artists(self):
        async with self.database.write() as session:
            await session.execute(delete(SimilarTrack))
            for index in range(2):
                track = Track(artist='forge', title=f'another seed {index}', metadata_source='fixture')
                session.add(track)
                await session.flush()
                session.add(Rating(user_id=self.internal, track_id=track.id, value='love'))
        providers = AsyncMock()
        providers.call.return_value = []
        service = RecommendationService(self.database, providers)
        try:
            await service.queue.fill(TELEGRAM_ID)
            first = [call.args[2].casefold() for call in providers.call.await_args_list
                     if call.args[1] == 'get_similar_tracks']
            self.assertEqual(set(first), {'forge', 'ivory'})
            self.assertLessEqual(providers.call.await_count, 3)
        finally:
            await service.close()

    async def test_new_request_triggers_bounded_warm_and_disabled_fetch_does_not_learn(self):
        from unittest.mock import Mock
        service = GetSong(self.database, AsyncMock(), FetchSettings(enabled=True), AsyncMock())
        service.recommendations = Mock()
        request = await service.request(TELEGRAM_ID, self.tracks['metal_0'])
        self.assertEqual(await service.request(TELEGRAM_ID, self.tracks['metal_0']), request)
        service.recommendations.queue.warm.assert_called_once_with(TELEGRAM_ID)
        disabled = GetSong(self.database, AsyncMock(), FetchSettings(enabled=False), AsyncMock())
        from music_bot.youtube_fetch import FetchError
        with self.assertRaises(FetchError):
            await disabled.request(TELEGRAM_ID, self.tracks['piano_0'])
        self.assertEqual(await self.count(TasteRequest), 1)

    async def test_existing_private_library_seeds_recommendations(self):
        async with self.database.write() as session:
            await session.execute(delete(Rating))
            session.add(SavedSong(user_id=self.internal, track_id=self.tracks['metal_seed']))
        result = await self.engine.recommend_for_user(TELEGRAM_ID)
        self.assertEqual(result.status, 'ok')
        self.assertTrue(all('saved' in row.reason for row in result.recommendations))
        self.assertEqual(await self.count(TrackPreference), 0)

    async def test_known_does_not_remove_an_existing_save(self):
        async with self.database.write() as session:
            await feedback(session, self.internal, self.tracks['metal_0'], 'save')
            await feedback(session, self.internal, self.tracks['metal_0'], 'known')
        self.assertTrue(await self.chat.is_saved(TELEGRAM_ID, self.tracks['metal_0']))
        async with self.database.sessions() as session:
            profile = await load_profile(session, TELEGRAM_ID)
        self.assertIn(self.tracks['metal_0'], {seed.item.track_id for seed in profile.positives})
        self.assertNotIn(self.tracks['metal_0'], {seed.item.track_id for seed in profile.negatives})

    async def test_reset_keeps_library_but_stops_learning_from_old_saves(self):
        async with self.database.write() as session:
            await feedback(session, self.internal, self.tracks['metal_seed'], 'save')
        await self.chat.reset_learning(TELEGRAM_ID)
        self.assertTrue(await self.chat.is_saved(TELEGRAM_ID, self.tracks['metal_seed']))
        async with self.database.sessions() as session:
            self.assertIsNone(await load_profile(session, TELEGRAM_ID))
        async with self.database.write() as session:
            await feedback(session, self.internal, self.tracks['metal_seed'], 'save')
        async with self.database.sessions() as session:
            self.assertIsNotNone(await load_profile(session, TELEGRAM_ID))

    async def test_social_library_removal_invalidates_prefetched_queue(self):
        async with self.database.write() as session:
            await feedback(session, self.internal, self.tracks['metal_seed'], 'save')
        await self.engine.queue.fill(TELEGRAM_ID)
        self.assertGreater(await self.count(QueuedRecommendation), 0)
        async with self.database.write() as session:
            await remove_saved(session, self.internal, self.tracks['metal_seed'])
        self.assertEqual(await self.count(QueuedRecommendation), 0)
        self.assertFalse(await self.chat.is_saved(TELEGRAM_ID, self.tracks['metal_seed']))

    async def test_cached_batch_does_not_generate_again(self):
        await self.engine.queue.fill(TELEGRAM_ID)
        with patch.object(self.engine, '_recommend', new_callable=AsyncMock) as generate:
            result = await self.engine.queue.reserve(TELEGRAM_ID)
            generate.assert_not_awaited()
        self.assertEqual(len(result.recommendations), 5)

    async def test_two_service_instances_cannot_overfill_queue(self):
        tracks = []
        async with self.database.write() as session:
            for index in range(40):
                track = Track(artist='Concurrent artist', title=f'new {index}', metadata_source='fixture')
                session.add(track)
                await session.flush()
                tracks.append(Recommendation(track.id, track.artist, track.title, None, None, {}, .5, 'fixture', ('fixture',)))
        both_started = asyncio.Event()
        calls = []
        async def generate(*args, **kwargs):
            offset = len(calls) * 20
            calls.append(offset)
            if len(calls) == 2:
                both_started.set()
            await both_started.wait()
            return RecommendationResult('ok', tuple(tracks[offset:offset + 20]))
        other = RecommendationService(self.database)
        try:
            with patch.object(self.engine, '_recommend', side_effect=generate), patch.object(other, '_recommend', side_effect=generate):
                await asyncio.gather(self.engine.queue.fill(TELEGRAM_ID), other.queue.fill(TELEGRAM_ID))
            self.assertEqual(await self.count(QueuedRecommendation), 20)
        finally:
            await other.close()

    async def test_failed_control_creation_releases_reserved_batch(self):
        from music_bot.chat_ui import show_recommendations
        with patch.object(self.chat, 'create_control', side_effect=FlowError('stale')):
            with self.assertRaises(FlowError):
                await show_recommendations(AsyncMock(), self.chat, TELEGRAM_ID)
        async with self.database.sessions() as session:
            leased = await session.scalar(select(func.count()).select_from(QueuedRecommendation)
                .where(QueuedRecommendation.lease.is_not(None)))
        self.assertEqual(leased, 0)
        self.assertEqual(await self.count(RecommendationHistory), 0)

    async def test_shutdown_drains_short_refills_before_cancelling(self):
        started = asyncio.Event()
        finished = asyncio.Event()
        async def short_fill(*args):
            started.set()
            await asyncio.sleep(.02)
            finished.set()
        with patch.object(self.engine.queue, 'fill', side_effect=short_fill):
            self.engine.queue.warm(TELEGRAM_ID)
            await started.wait()
            await self.engine.close()
        self.assertTrue(finished.is_set())
