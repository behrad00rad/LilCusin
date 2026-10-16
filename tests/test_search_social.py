import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

from tests.support import ServiceTestCase
from music_bot.providers.common import TrackCandidate
from music_bot.recognition import social_url
from music_bot.lyrics_search import LyricsSearch, needs_lyrics
from music_bot.youtube_fetch import YouTubeFetcher, FetchError
from music_bot.providers.itunes import ITunesClient
from tests.test_providers import mock_session


class SearchIntentTests(ServiceTestCase):
    async def test_artist_query_keeps_artist_tracks(self):
        rows = [TrackCandidate(artist='Deftones', title='Change (In the House of Flies)', source='test'),
                TrackCandidate(artist='Other', title='Unrelated', source='test')]
        self.providers.call.return_value = rows
        results, failed = await self.workflow.search_title('deftones')
        self.assertEqual([row.artist for row in results], ['Deftones'])

    async def test_two_word_lyric_hint_reaches_discovery_without_hardcoded_song(self):
        self.assertTrue(needs_lyrics('someday kanye', []))
        song = TrackCandidate(artist='Kanye West', title='Ghost Town', source='itunes')
        self.providers.call.return_value = []
        self.workflow.lyrics = NS(search=AsyncMock(return_value=([song], False)))
        results, _ = await self.workflow.search_title('someday kanye')
        self.assertEqual(results, [song])
        self.workflow.lyrics.search.assert_awaited_once_with('someday kanye')

    async def test_popular_exact_title_is_not_displaced_by_an_ambiguous_artist_name(self):
        self.providers.call.return_value = [
            TrackCandidate(artist='Hello', title='Another Song', source='test', listeners=100),
            TrackCandidate(artist='Adele', title='Hello', source='test', listeners=100000)]
        rows, _ = await self.workflow.search_title('hello')
        self.assertEqual(rows[0].artist, 'Adele')

    async def test_lyric_validation_can_survive_lastfm_and_musicbrainz_outages(self):
        from music_bot.providers.common import ProviderError, Failure
        self.providers.has_itunes, self.providers.has_deezer = True, False
        song = TrackCandidate(artist='Artist', title='Song', source='itunes')
        async def call(provider, *args):
            if provider != 'itunes':
                raise ProviderError(Failure.NETWORK)
            return [song]
        self.providers.call.side_effect = call
        lyrics = LyricsSearch(None, self.providers)
        lyrics.discover = AsyncMock(return_value=[('Artist', 'Song')])
        self.assertEqual(await lyrics.search('someday someone'), ([song], False))

    async def test_explicit_artist_title_also_uses_independent_catalogue(self):
        from music_bot.providers.common import ProviderError, Failure
        self.providers.has_itunes, self.providers.has_deezer = True, False
        song = TrackCandidate(artist='Artist', title='Song', source='itunes')
        async def call(provider, *args):
            if provider != 'itunes':
                raise ProviderError(Failure.NETWORK)
            return [song]
        self.providers.call.side_effect = call
        rows, _ = await self.workflow.search('Artist', 'Song')
        self.assertEqual(rows, [song])


class SocialTests(unittest.IsolatedAsyncioTestCase):
    def test_allowlist_post_urls_and_strip_tracking(self):
        for url in ('https://www.instagram.com/reel/ABC_123/?igsh=tracking',
                    'https://www.tiktok.com/@artist/video/123456789', 'https://vm.tiktok.com/AbCd/',
                    'https://pin.it/AbCd/', 'https://www.pinterest.com/pin/12345/',
                    'https://x.com/artist/status/1234', 'https://soundcloud.com/artist/track'):
            with self.subTest(url=url):
                self.assertIsNotNone(social_url(url))
                self.assertNotIn('?', social_url(url))
        for url in ('http://instagram.com/reel/ABC', 'https://instagram.com.evil.test/reel/ABC',
                    'https://user@instagram.com/reel/ABC', 'https://127.0.0.1/video/123',
                    'https://www.instagram.com/profile/', 'file:///etc/passwd',
                    'https://pin.it:444/ABC', 'https://example.com/file.mp4'):
            self.assertIsNone(social_url(url))

    async def test_social_downloader_is_bounded_and_generic_extractor_disabled(self):
        fetcher = YouTubeFetcher(NS(timeout=10, max_bytes=20000000, max_duration=900))
        with tempfile.TemporaryDirectory() as folder:
            async def process(args, directory, alive):
                Path(directory, 'social.mp4').write_bytes(b'video')
            fetcher.process = AsyncMock(side_effect=process)
            path = await fetcher.fetch_social('https://instagram.com/reel/ABC/?tracking=1', folder, AsyncMock())
            self.assertEqual(path.name, 'social.mp4')
            args = fetcher.process.await_args.args[0]
            self.assertIn('--no-cookies-from-browser', args)
            self.assertIn('--max-filesize', args)
            self.assertNotIn('generic', args[args.index('--use-extractors') + 1].lower())
            self.assertEqual(args[-1], 'https://instagram.com/reel/ABC/')
            with self.assertRaises(FetchError):
                await fetcher.fetch_social('https://evil.test/file.mp4', folder, AsyncMock())

    async def test_short_link_redirect_cannot_reach_an_unapproved_host(self):
        from unittest.mock import MagicMock, patch
        response = NS(status=302, headers={'Location': 'https://127.0.0.1/internal'})
        response_context = MagicMock()
        response_context.__aenter__ = AsyncMock(return_value=response)
        response_context.__aexit__ = AsyncMock(return_value=False)
        session = NS(get=MagicMock(return_value=response_context))
        session_context = MagicMock()
        session_context.__aenter__ = AsyncMock(return_value=session)
        session_context.__aexit__ = AsyncMock(return_value=False)
        fetcher = YouTubeFetcher(NS(max_bytes=20000000, max_duration=900))
        fetcher.process = AsyncMock()
        with patch('aiohttp.ClientSession', return_value=session_context), tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(FetchError):
                await fetcher.fetch_social('https://pin.it/ABC/', folder, AsyncMock())
        fetcher.process.assert_not_awaited()

    async def test_itunes_maps_metadata_without_previews(self):
        session = mock_session({'results': [{'artistName': 'Artist', 'trackName': 'Song',
            'collectionName': 'Album', 'trackTimeMillis': 200000, 'previewUrl': 'https://unused.test'}]})
        # Existing test helper returns a ClientSession-like object.
        if isinstance(session, tuple):
            session = session[0]
        rows = await ITunesClient(session).search_titles('artist')
        self.assertEqual(rows[0].duration, 200)
        self.assertEqual(rows[0].source, 'itunes')
