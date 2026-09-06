import asyncio
import io
import logging
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp

from music_bot.__main__ import SafeFormatter
from music_bot.providers.common import Failure, ProviderError, request_json
from music_bot.providers.lastfm import LastFMClient, normalize_track
from music_bot.providers.musicbrainz import (
    MusicBrainzClient, RateLimiter, USER_AGENT, normalize_recording, shared_limiter,
)

MBID = "f2345678-1234-1234-1234-123456789abc"


def mock_session(payload=None, status=200, json_error=None):
    response = MagicMock(status=status)
    response.json = AsyncMock(return_value=payload, side_effect=json_error)
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=response)
    context.__aexit__ = AsyncMock(return_value=False)
    session = MagicMock()
    session.get.return_value = context
    return session


class NormalizationTests(unittest.TestCase):
    def test_lastfm_search_and_metadata_shapes(self):
        track = normalize_track({
            "name": "من آمده‌ام", "artist": {"name": "گوگوش"}, "duration": "240000",
            "mbid": MBID, "url": "https://www.last.fm/music/test",
            "album": {"title": "Album", "image": [{"#text": ""}, {"#text": "https://example.org/a.jpg"}]},
            "toptags": {"tag": [{"name": "pop", "count": "50"}]},
        })
        self.assertEqual(track.artist, "گوگوش")
        self.assertEqual(track.duration, 240)
        self.assertEqual(track.album, "Album")
        self.assertEqual(track.releases[0].title, "Album")
        self.assertEqual(track.external_ids["musicbrainz"], MBID)
        self.assertEqual(track.tags[0].weight, 50)
        self.assertEqual(track.artwork_url, "https://example.org/a.jpg")
        sparse = normalize_track({"name": "Song", "artist": "Artist", "mbid": ""})
        self.assertIsNone(sparse.album)
        self.assertEqual(sparse.tags, ())
        self.assertIn("external_ids", sparse.missing_metadata)

    def test_musicbrainz_normalization_and_missing_metadata(self):
        track = normalize_recording({
            "id": MBID, "title": "Song", "length": 123000, "score": "99",
            "artist-credit": [
                {"name": "Artist", "joinphrase": " & "},
                {"artist": {"name": "گوگوش"}},
            ], "releases": [{"title": "Album"}],
        })
        self.assertEqual(track.artist, "Artist & گوگوش")
        self.assertEqual(track.duration, 123)
        self.assertEqual(track.score, 99)
        self.assertEqual(track.external_ids, {"musicbrainz": MBID})
        self.assertEqual(track.album, "Album")
        self.assertIsNone(normalize_recording({"title": "Song"}).artist)


class ProviderTests(unittest.IsolatedAsyncioTestCase):
    async def test_lastfm_search_empty_and_singleton(self):
        for raw, count in [( [], 0), ("", 0), ({"name": "Song", "artist": "Artist"}, 1)]:
            with self.subTest(raw=raw):
                session = mock_session({"results": {"trackmatches": {"track": raw}}})
                matches = await LastFMClient(session, "secret").search_tracks("Artist", "Song")
                self.assertEqual(len(matches), count)
                self.assertFalse(session.get.call_args.kwargs["allow_redirects"])

    async def test_lastfm_missing_track_and_optional_collections(self):
        client = LastFMClient(mock_session({"error": 6, "message": "Track not found"}), "secret")
        self.assertIsNone(await client.get_track_info("Artist", "Song"))
        self.assertEqual(await client.get_top_tags("Artist", "Song"), ())
        self.assertEqual(await client.get_similar_tracks("Artist", "Song"), [])
        client = LastFMClient(mock_session({"toptags": {"tag": []}}), "secret")
        self.assertEqual(await client.get_top_tags("Artist", "Song"), ())
        client = LastFMClient(mock_session({"similartracks": {"track": []}}), "secret")
        self.assertEqual(await client.get_similar_tracks("Artist", "Song"), [])

    async def test_lastfm_metadata_tags_similar(self):
        client = LastFMClient(mock_session({"track": {"name": "Song", "artist": {"name": "Artist"}}}), "secret")
        self.assertEqual((await client.get_track_info("Artist", "Song")).title, "Song")
        client = LastFMClient(mock_session({"toptags": {"tag": {"name": "rock", "count": "10"}}}), "secret")
        self.assertEqual((await client.get_top_tags("Artist", "Song"))[0].weight, 10)
        client = LastFMClient(mock_session({"similartracks": {"track": [{"name": "Other", "artist": {"name": "A"}, "match": "0.8"}]}}), "secret")
        self.assertEqual((await client.get_similar_tracks("Artist", "Song"))[0].score, 0.8)

    async def test_malformed_tag_entries_ignored(self):
        client = LastFMClient(mock_session({"toptags": {"tag": [None, "bad", {}, {"name": ""}, {"name": "Pop"}]}}), "secret")
        tags = await client.get_top_tags("Artist", "Song")
        self.assertEqual([tag.name for tag in tags], ["Pop"])

    async def test_lastfm_api_errors_are_safe(self):
        for code, expected in [(10, Failure.AUTH), (26, Failure.AUTH), (29, Failure.RATE_LIMIT), (11, Failure.UNAVAILABLE), (16, Failure.UNAVAILABLE), (3, Failure.REQUEST)]:
            with self.subTest(code=code):
                client = LastFMClient(mock_session({"error": code, "message": "secret"}), "secret")
                with self.assertRaises(ProviderError) as error:
                    await client.search_tracks("A", "B")
                self.assertEqual(error.exception.reason, expected)
                self.assertNotIn("secret", str(error.exception))

    async def test_http_failures_and_invalid_json(self):
        for status, expected in [(429, Failure.RATE_LIMIT), (503, Failure.UNAVAILABLE), (403, Failure.AUTH), (400, Failure.REQUEST), (302, Failure.REQUEST)]:
            with self.subTest(status=status), self.assertRaises(ProviderError) as error:
                await request_json(mock_session(status=status), "https://example.org")
            self.assertEqual(error.exception.reason, expected)
        for session in [mock_session(json_error=ValueError("secret")), mock_session([])]:
            with self.assertRaises(ProviderError) as error:
                await request_json(session, "https://example.org")
            self.assertEqual(error.exception.reason, Failure.INVALID_RESPONSE)

    async def test_network_errors_safe_when_logged(self):
        for exception in (aiohttp.ClientConnectionError("secret"), TimeoutError("secret")):
            session = MagicMock()
            session.get.side_effect = exception
            stream = io.StringIO()
            handler = logging.StreamHandler(stream)
            handler.setFormatter(SafeFormatter())
            logger = logging.getLogger("test.provider")
            logger.addHandler(handler)
            logger.propagate = False
            try:
                try:
                    await request_json(session, "https://example.org/?api_key=secret")
                except ProviderError as error:
                    self.assertEqual(error.reason, Failure.NETWORK)
                    logger.exception("secret: %s", error)
                self.assertNotIn("secret", stream.getvalue())
                self.assertNotIn("https://", stream.getvalue())
            finally:
                logger.removeHandler(handler)

    async def test_malformed_provider_shapes(self):
        for payload in ({}, {"results": []}, {"results": {"trackmatches": {"track": [1]}}}):
            with self.subTest(payload=payload), self.assertRaises(ProviderError):
                await LastFMClient(mock_session(payload), "secret").search_tracks("A", "B")
        with self.assertRaises(ProviderError):
            await MusicBrainzClient(mock_session({"recordings": "bad"})).search_recordings("A", "B")

    async def test_musicbrainz_search_lookup_headers_and_empty(self):
        session = mock_session({"recordings": []})
        client = MusicBrainzClient(session)
        with patch("music_bot.providers.musicbrainz.shared_limiter", return_value=RateLimiter(clock=lambda: 10, sleep=AsyncMock())):
            self.assertEqual(await client.search_recordings('گوگوش "x"', "Song"), [])
            kwargs = session.get.call_args.kwargs
            self.assertEqual(kwargs["headers"]["User-Agent"], USER_AGENT)
            self.assertIn(r'\"x\"', kwargs["params"]["query"])
            client = MusicBrainzClient(mock_session({"id": MBID, "title": "Song"}))
            self.assertEqual((await client.get_recording(MBID)).title, "Song")
            with self.assertRaises(ProviderError):
                await client.get_recording("../path?secret")

    async def test_musicbrainz_throttle_shared_and_concurrent(self):
        now = [10.0]
        delays = []

        async def sleep(delay):
            delays.append(delay)
            now[0] += delay

        limiter = RateLimiter(clock=lambda: now[0], sleep=sleep)
        starts = []

        async def request():
            async with limiter:
                starts.append(now[0])

        await asyncio.gather(request(), request(), request())
        self.assertEqual(starts, [10, 11, 12])
        self.assertEqual(delays, [1, 1])
        self.assertIs(shared_limiter(), shared_limiter())

    async def test_cancelled_throttle_releases_lock(self):
        limiter = RateLimiter(clock=lambda: 1, sleep=AsyncMock(side_effect=asyncio.CancelledError))
        limiter.next_request = 2
        with self.assertRaises(asyncio.CancelledError):
            async with limiter:
                pass
        self.assertFalse(limiter.lock.locked())
