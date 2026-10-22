from dataclasses import asdict
from datetime import timedelta
import json as json_module
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from aiohttp.test_utils import make_mocked_request
from sqlalchemy import delete, select

from music_bot.chat_service import ChatService
from music_bot.feed_history import FeedHistory, excluded_ids, record_event
from music_bot.miniapp import create_app
from music_bot.models import Rating, Track, User, utc_now
from music_bot.recommendations import RecommendationService
from music_bot.recommendations.queue import QueuedRecommendation
from music_bot.recommendations.types import Recommendation, RecommendationResult
from music_bot.submissions import Submitter
from music_bot.taste_learning import feedback, record_request
from tests.support import ServiceTestCase
from tests.test_miniapp import TOKEN, signed


class LocalAPI:
    """Exercise real handlers/auth without opening Windows loopback sockets."""
    def __init__(self, app):
        self.app = app
        app.freeze()

    async def post(self, path, *, json, headers=None):
        request = make_mocked_request('POST', path, headers=headers or {})
        request.json = AsyncMock(return_value=json)
        match = await self.app.router.resolve(request)
        response = await self.app.middlewares[0](request, match.handler)
        return SimpleNamespace(status=response.status, json=AsyncMock(
            return_value=json_module.loads(response.text)))

    async def close(self):
        await self.app.cleanup()


class FeedHistoryTests(ServiceTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.chat = ChatService(self.database, AsyncMock())
        await self.chat.ensure_user(Submitter(123))
        await self.chat.ensure_user(Submitter(456))
        self.engine = RecommendationService(self.database)
        self.chat.recommendations = self.engine
        async with self.database.write() as session:
            self.actor = await session.scalar(select(User.id).where(User.telegram_user_id == 123))
            self.other = await session.scalar(select(User.id).where(User.telegram_user_id == 456))
            tracks = [Track(artist='Fixture', title=f'Fresh {i}', metadata_source='fixture') for i in range(8)]
            session.add_all(tracks)
            await session.flush()
            self.ids = [track.id for track in tracks]
            for i, track in enumerate(tracks):
                row = Recommendation(track.id, track.artist, track.title, None, None, {}, 1, 'Similar', ())
                session.add(QueuedRecommendation(user_id=self.actor, track_id=track.id, payload=asdict(row),
                    position=i, expires_at=utc_now()+timedelta(days=1)))
        self.client = LocalAPI(create_app(TOKEN, self.chat, self.workflow))

    async def asyncTearDown(self):
        await self.client.close()
        await self.engine.close()
        await super().asyncTearDown()

    async def feed(self):
        response = await self.client.post('/api/recommendations', json={},
            headers={'X-Telegram-Init-Data': signed()})
        self.assertEqual(response.status, 200)
        return await response.json()

    async def event(self, token, track_id, event, key='event-key-0001', user=123, **extra):
        return await self.client.post('/api/feed/events', json={'events': [dict(
            token=token, track_id=track_id, event=event, event_id=key, **extra)]},
            headers={'X-Telegram-Init-Data': signed(user)})

    async def test_skip_survives_reopen_and_prefetch_stays_eligible(self):
        first = await self.feed()
        skipped, unseen = first['tracks'][0]['id'], first['tracks'][1]['id']
        response = await self.event(first['token'], skipped, 'skipped')
        self.assertEqual(response.status, 200)
        second = await self.feed()
        ids = [row['id'] for row in second['tracks']]
        self.assertNotIn(skipped, ids)
        self.assertEqual(ids[0], unseen, 'Reopen continues at the next unseen queued recording')
        self.assertIn(unseen, ids, 'A prefetched neighbour is not a view')
        async with self.database.sessions() as session:
            self.assertIsNone(await session.get(FeedHistory, (self.actor, unseen)))
            self.assertIsNone(await session.scalar(select(Rating).where(Rating.user_id == self.actor)))

    async def test_seen_day_skip_cooldowns_and_idempotency(self):
        start = utc_now()
        async with self.database.write() as session:
            await record_event(session, self.actor, self.ids[0], 'seen', now=start)
            self.assertIn(self.ids[0], await excluded_ids(session, self.actor, now=start))
            self.assertNotIn(self.ids[0], await excluded_ids(session, self.actor, now=start+timedelta(days=2)))
            await record_event(session, self.actor, self.ids[0], 'skipped', 'first-skip', now=start)
            await record_event(session, self.actor, self.ids[0], 'skipped', 'first-skip', now=start)
            row = await session.get(FeedHistory, (self.actor, self.ids[0]))
            self.assertEqual(row.skip_count, 1)
            self.assertIn(self.ids[0], await excluded_ids(session, self.actor, now=start+timedelta(days=13)))
            self.assertNotIn(self.ids[0], await excluded_ids(session, self.actor, now=start+timedelta(days=15)))
            await record_event(session, self.actor, self.ids[0], 'skipped', 'second-skip', now=start+timedelta(days=15))
            self.assertEqual(row.skip_count, 2)
            self.assertIn(self.ids[0], await excluded_ids(session, self.actor, now=start+timedelta(days=74)))
            self.assertNotIn(self.ids[0], await excluded_ids(session, self.actor, now=start+timedelta(days=76)))

    async def test_hide_thirty_days_permanent_hide_and_private_scope(self):
        start = utc_now()
        async with self.database.write() as session:
            await record_event(session, self.actor, self.ids[0], 'not_now', now=start)
            await record_event(session, self.actor, self.ids[1], 'hidden', now=start)
            self.assertIn(self.ids[0], await excluded_ids(session, self.actor, now=start+timedelta(days=29)))
            self.assertNotIn(self.ids[0], await excluded_ids(session, self.actor, now=start+timedelta(days=31)))
            self.assertIn(self.ids[1], await excluded_ids(session, self.actor, now=start+timedelta(days=365)))
            self.assertNotIn(self.ids[1], await excluded_ids(session, self.other, now=start))

    async def test_rated_and_requested_tracks_never_return(self):
        async with self.database.write() as session:
            session.add(Rating(user_id=self.actor, track_id=self.ids[0], value='love'))
            await record_request(session, self.actor, self.ids[1], 'fixture-request')
            await feedback(session, self.actor, self.ids[2], 'save')
            await feedback(session, self.actor, self.ids[2], 'unsave')
        feed = await self.feed()
        self.assertFalse(set(self.ids[:3]) & {row['id'] for row in feed['tracks']})

    async def test_events_require_owned_grants_and_reject_actor_injection(self):
        first = await self.feed()
        token, track_id = first['token'], first['tracks'][0]['id']
        for kwargs, status in [({'user': 456}, 403), ({'user_id': self.other}, 400)]:
            self.assertEqual((await self.event(token, track_id, 'seen', **kwargs)).status, status)
        self.assertEqual((await self.event(token, track_id, 'dislike')).status, 400)
        self.assertEqual((await self.client.post('/api/feed/events', json={'events': []})).status, 401)

    async def test_exhausted_feed_never_pads_and_refills_once(self):
        async with self.database.write() as session:
            for track_id in self.ids:
                await record_event(session, self.actor, track_id, 'hidden')
        with patch.object(self.engine, '_recommend', new_callable=AsyncMock,
                          return_value=RecommendationResult('no_candidates')) as generate:
            feed = await self.feed()
        self.assertEqual(feed['tracks'], [])
        self.assertEqual(feed['status'], 'caught_up')
        generate.assert_awaited_once()

    async def test_forget_deletes_private_feed_memory(self):
        async with self.database.write() as session:
            await record_event(session, self.actor, self.ids[0], 'hidden')
        await self.chat.forget(123)
        async with self.database.sessions() as session:
            self.assertIsNone(await session.scalar(select(FeedHistory).where(FeedHistory.user_id == self.actor)))
