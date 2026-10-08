import asyncio
import io
import logging
from dataclasses import replace
from datetime import timedelta
from unittest.mock import AsyncMock

from sqlalchemy import func, select

from music_bot.__main__ import SafeFormatter
from music_bot.cache import CachedProviders, cache_key
from music_bot.enrichment import Enrichment
from music_bot.models import ProviderCache, Rating, SimilarTrack, Track, TrackExternalID, TrackTag, utc_now
from music_bot.providers.common import Failure, ProviderError, Tag
from tests.support import ServiceTestCase
from tests.test_workflow import EXACT


class CacheTests(ServiceTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.lastfm = AsyncMock()
        self.musicbrainz = AsyncMock()
        self.cache = CachedProviders(self.database, self.lastfm, self.musicbrainz)
        self.lastfm.get_track_info.return_value = EXACT

    async def test_fresh_and_concurrent_hits(self):
        values = await asyncio.gather(*[self.cache.call("lastfm", "get_track_info", "Artist", "Song") for _ in range(3)])
        self.assertEqual(values, [EXACT] * 3)
        self.lastfm.get_track_info.assert_awaited_once()

    async def expire(self, days=0):
        async with self.database.write() as session:
            entry = await session.scalar(select(ProviderCache))
            entry.expires_at = utc_now() - timedelta(days=days, seconds=1)

    async def test_expired_refresh(self):
        await self.cache.call("lastfm", "get_track_info", "Artist", "Song")
        await self.expire()
        self.lastfm.get_track_info.return_value = replace(EXACT, album="New")
        refreshed = await self.cache.call("lastfm", "get_track_info", "Artist", "Song")
        self.assertEqual(refreshed.album, "New")
        self.assertEqual(self.lastfm.get_track_info.await_count, 2)

    async def test_temporary_failure_stale_grace_and_auth_rejection(self):
        await self.cache.call("lastfm", "get_track_info", "Artist", "Song")
        await self.expire()
        self.lastfm.get_track_info.side_effect = ProviderError(Failure.NETWORK)
        self.assertEqual(await self.cache.call("lastfm", "get_track_info", "Artist", "Song"), EXACT)
        self.lastfm.get_track_info.side_effect = ProviderError(Failure.AUTH)
        with self.assertRaises(ProviderError):
            await self.cache.call("lastfm", "get_track_info", "Artist", "Song")
        await self.expire(days=2)
        self.lastfm.get_track_info.side_effect = ProviderError(Failure.NETWORK)
        with self.assertRaises(ProviderError):
            await self.cache.call("lastfm", "get_track_info", "Artist", "Song")

    async def test_errors_not_cached_and_secrets_not_logged(self):
        secret = "FAKE_PRIVATE_LASTFM_KEY"
        self.lastfm.get_track_info.side_effect = ProviderError(Failure.AUTH)
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(SafeFormatter())
        logger = logging.getLogger("test.secret")
        logger.addHandler(handler)
        logger.propagate = False
        try:
            try:
                await self.cache.call("lastfm", "get_track_info", "گوگوش", "Song")
            except ProviderError as error:
                self.assertNotIn(secret, repr(error))
                logger.exception("%s", secret)
            self.assertNotIn(secret, stream.getvalue())
        finally:
            logger.removeHandler(handler)
        async with self.database.sessions() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(ProviderCache)), 0)
        key = cache_key("lastfm", "get_track_info", ("گوگوش", "Song"))
        self.assertEqual(key, cache_key("lastfm", "get_track_info", (" گوگوش ", "SONG")))
        self.assertNotIn(secret, key)

    async def test_ttls_and_empty_results(self):
        self.lastfm.get_top_tags.return_value = (Tag("rock", "lastfm"),)
        self.lastfm.get_similar_tracks.return_value = [EXACT]
        self.lastfm.search_tracks.return_value = []
        for method in ("get_track_info", "get_top_tags", "get_similar_tracks", "search_tracks"):
            await self.cache.call("lastfm", method, "Artist", "Song")
        async with self.database.sessions() as session:
            entries = (await session.scalars(select(ProviderCache))).all()
        durations = {e.method: e.expires_at - e.retrieved_at for e in entries}
        self.assertEqual(durations["get_track_info"], timedelta(days=7))
        self.assertEqual(durations["get_top_tags"], timedelta(days=7))
        self.assertEqual(durations["get_similar_tracks"], timedelta(days=1))
        self.assertEqual(durations["search_tracks"], timedelta(minutes=5))


class EnrichmentTests(ServiceTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.providers.call.return_value = [EXACT]
        submission = await self.submissions.submit_text(self.user, "Artist - Song")
        result = await self.workflow.start(submission.id, 123)
        self.track_id = result.track_id
        self.submission_id = submission.id
        self.enrichment = Enrichment(self.database, self.providers)

    async def asyncTearDown(self):
        await self.enrichment.close()
        await super().asyncTearDown()

    async def test_metadata_tags_ids_and_similar_deduplicate(self):
        enriched = replace(EXACT, album="New album", external_ids={**EXACT.external_ids, "musicbrainz": "mbid"},
                           tags=(Tag("Pop", "lastfm", 5),))
        similar = replace(EXACT, title="Other", external_ids={}, score=0.8)

        async def call(provider, method, *args):
            return {"get_track_info": enriched, "get_top_tags": (Tag("ROCK", "lastfm", 5), Tag(" rock ", "lastfm", 10), Tag("", "lastfm")),
                    "get_similar_tracks": [similar, similar, EXACT], "get_recording": enriched}[method]

        self.providers.call.side_effect = call
        for _ in range(2):
            await self.enrichment.enrich(self.track_id)
        async with self.database.sessions() as session:
            self.assertEqual((await session.get(Track, self.track_id)).album, "New album")
            self.assertEqual(await session.scalar(select(func.count()).select_from(Track)), 1)
            self.assertEqual(await session.scalar(select(func.count()).select_from(TrackExternalID)), 2)
            self.assertEqual(await session.scalar(select(func.count()).select_from(TrackTag)), 2)
            tag = await session.scalar(select(TrackTag).where(TrackTag.name == "rock"))
            self.assertEqual(tag.weight, 10)
            self.assertEqual(tag.display_name, "rock")
            similar_row = await session.scalar(select(SimilarTrack))
            self.assertEqual(similar_row.score, 0.8)
            self.assertEqual(await session.scalar(select(func.count()).select_from(SimilarTrack)), 1)

    async def test_missing_metadata_does_not_erase_existing(self):
        self.providers.call.side_effect = [replace(EXACT, album=None, duration=None, artwork_url=None), (), []]
        await self.enrichment.enrich(self.track_id)
        async with self.database.sessions() as session:
            track = await session.get(Track, self.track_id)
            self.assertEqual(track.album, "Album")
            self.assertEqual(track.duration, 120)

    async def test_different_track_metadata_not_applied(self):
        wrong = replace(EXACT, artist="Other artist", title="Other song", album="Wrong", external_ids={})
        await self.enrichment._metadata(self.track_id, wrong)
        async with self.database.sessions() as session:
            self.assertEqual((await session.get(Track, self.track_id)).album, "Album")

    async def test_rating_works_when_background_enrichment_fails(self):
        self.providers.call.side_effect = ProviderError(Failure.AUTH)
        self.enrichment.schedule(self.track_id)
        self.enrichment.schedule(self.track_id)
        self.assertEqual(len(self.enrichment.tasks), 1)
        result = await self.workflow.rate(self.submission_id, 123, "love")
        self.assertEqual(result.rating, "love")
        await asyncio.gather(*list(self.enrichment.tasks.values()))
        self.assertFalse(self.enrichment.tasks)
        async with self.database.sessions() as session:
            self.assertEqual(await session.scalar(select(Rating.value)), "love")

    async def test_enrichment_reuses_fresh_cache(self):
        lastfm, mb = AsyncMock(), AsyncMock()
        lastfm.get_track_info.return_value = EXACT
        lastfm.get_top_tags.return_value = ()
        lastfm.get_similar_tracks.return_value = []
        enrichment = Enrichment(self.database, CachedProviders(self.database, lastfm, mb))
        await enrichment.enrich(self.track_id)
        await enrichment.enrich(self.track_id)
        lastfm.get_track_info.assert_awaited_once()
        lastfm.get_top_tags.assert_awaited_once()
        lastfm.get_similar_tracks.assert_awaited_once()
