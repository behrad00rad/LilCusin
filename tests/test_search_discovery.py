import asyncio
import json
from pathlib import Path
from types import SimpleNamespace as NS
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock

from music_bot.lyrics_search import LyricsSearch, LyricsSettings
from music_bot.matching import search_text_match, search_query_matches_song, strong_match
from music_bot.models import Track
from music_bot.providers.common import TrackCandidate, ProviderError, Failure
from tests.support import ServiceTestCase

KENDRICK = TrackCandidate(artist='Kendrick Lamar', title='Prayer', source='musicbrainz')
DISTURBED = TrackCandidate(artist='Disturbed', title='Prayer', source='musicbrainz')
ENTRIES = [dict(title='Madonna - Like A Prayer (Lyrics)', view_count=15000000),
           dict(title='Disturbed - Prayer (Lyrics)', view_count=1000000),
           dict(title='Kendrick Lamar - Prayer (Lyrics)', view_count=6000),
           dict(title='Kendrick Lamar - Prayer', view_count=3800000),
           dict(title='Prayer by Kendrick Lamar Instrumental [Unreleased Song]', view_count=9000000)]


def discovery(providers):
    fetcher = NS(base=lambda: ['metadata-extractor'], process=AsyncMock(
        return_value=json.dumps({'entries': ENTRIES}).encode()))
    return LyricsSearch(None, providers, fetcher=fetcher), fetcher


class SpellingTests(TestCase):
    def test_small_typos_and_transpositions_are_discovery_only(self):
        for query in ['prayer kendick', 'pryaer kendrick', 'prayer by kendrick', 'prayer kendrcik']:
            self.assertTrue(search_query_matches_song(query, 'Kendrick Lamar', 'Prayer'), query)
        self.assertFalse(search_query_matches_song('prayer kendick', 'Disturbed', 'Prayer'))
        self.assertFalse(search_text_match('pop', 'rap'))
        self.assertFalse(search_query_matches_song('prayer kendick', 'Kendrick Lamar', 'Luther'))
        self.assertFalse(strong_match('Disturbed', 'Prayer', [KENDRICK]))


class DiscoveryTests(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.providers = NS(has_itunes=False, has_deezer=False, call=AsyncMock())
        async def call(provider, method, artist, title):
            if provider != 'musicbrainz':
                return []
            return [KENDRICK] if artist == 'Kendrick Lamar' and title == 'Prayer' else (
                [DISTURBED] if artist.lower() == 'disturbed' and title.lower() == 'prayer' else [])
        self.providers.call.side_effect = call
        self.search, self.fetcher = discovery(self.providers)

    async def test_popular_unreleased_candidate_is_validated_and_views_ranked(self):
        rows, failed = await self.search.search_titles('prayer')
        self.assertFalse(failed)
        self.assertEqual((rows[0].artist, rows[0].youtube_views), ('Kendrick Lamar', 3800000))
        self.assertIn('Disturbed', [row.artist for row in rows])
        self.assertFalse(any('instrumental' in call.args[3].lower() for call in self.providers.call.await_args_list))
        args = self.fetcher.process.call_args.args[0]
        self.assertIn('--skip-download', args)
        self.assertIn('--flat-playlist', args)
        self.assertEqual(args[-1], 'ytsearch20:prayer lyrics')
        self.assertFalse(Path(self.fetcher.process.call_args.args[1]).exists())

    async def test_typo_uses_corrected_discovery_identity(self):
        rows, failed = await self.search.search_titles('prayer kendick')
        self.assertFalse(failed)
        self.assertEqual([row.artist for row in rows], ['Kendrick Lamar'])

    async def test_unvalidated_popular_upload_does_not_become_a_song(self):
        self.providers.call.side_effect = None
        self.providers.call.return_value = []
        self.assertEqual(await self.search.search_titles('prayer'), ([], False))

    async def test_validation_outage_backs_off_and_off_mode_uses_no_extractor(self):
        self.providers.call.side_effect = ProviderError(Failure.NETWORK)
        self.assertEqual(await self.search.search_titles('prayer'), ([], True))
        self.assertEqual(await self.search.search_titles('prayer kendick'), ([], True))
        self.fetcher.process.assert_awaited_once()
        self.search.settings = LyricsSettings('off')
        self.assertEqual(await self.search.search_titles('prayer'), ([], False))
        self.fetcher.process.assert_awaited_once()

    async def test_missing_or_invalid_views_are_not_fabricated(self):
        for views in [None, True, -1, '9000000']:
            self.search.clear()
            self.fetcher.process.return_value = json.dumps({'entries': [
                dict(title='Kendrick Lamar - Prayer', view_count=views)]}).encode()
            rows, failed = await self.search.search_titles('prayer')
            self.assertFalse(failed)
            self.assertIsNone(rows[0].youtube_views)

    async def test_same_query_is_deduplicated_and_cache_is_bounded_and_hashed(self):
        first, second = await asyncio.gather(self.search.search_titles('prayer'), self.search.search_titles('prayer'))
        self.assertEqual(first, second)
        self.fetcher.process.assert_awaited_once()
        self.assertEqual(len(self.search.title_cache), 1)
        self.assertNotIn('prayer', repr(list(self.search.title_cache)))

    async def test_cancel_releases_capacity_and_removes_temporary_directory(self):
        started = asyncio.Event()
        async def wait(*args, **kwargs):
            started.set()
            await asyncio.Event().wait()
        self.fetcher.process.side_effect = wait
        task = asyncio.create_task(self.search.search_titles('prayer'))
        await started.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertFalse(Path(self.fetcher.process.call_args.args[1]).exists())
        self.assertFalse(self.search.capacity.locked())
        self.assertFalse(self.search.title_cache)
        self.providers.call.assert_not_awaited()

    async def test_only_two_distinct_extractions_are_admitted(self):
        two_started = asyncio.Event()
        calls = 0
        async def wait(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                two_started.set()
            await asyncio.Event().wait()
        self.fetcher.process.side_effect = wait
        tasks = [asyncio.create_task(self.search.search_titles(query))
                 for query in ['prayer', 'prayer kendick']]
        try:
            await two_started.wait()
            self.assertEqual(await self.search.search_titles('prayer kendrick'), ([], True))
            self.assertEqual(calls, 2)
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
        self.assertFalse(self.search.capacity.locked())


class DiscoveryWorkflowTests(ServiceTestCase):
    async def test_typo_and_common_title_return_choices_even_with_local_matches(self):
        other = TrackCandidate(artist='Other Artist', title='Prayer', source='musicbrainz')
        async with self.database.write() as session:
            session.add(Track(artist=other.artist, title=other.title, metadata_source='fixture'))
        async def call(provider, method, *args):
            if method == 'search_recordings' and args == ('Kendrick Lamar', 'Prayer'):
                return [KENDRICK]
            return [other] if method == 'search_titles' else []
        self.providers.call.side_effect = call
        self.workflow.lyrics, fetcher = discovery(self.providers)
        for query in ['prayer', 'prayer kendick']:
            saved = await self.submissions.submit_search(self.user, query)
            result = await self.workflow.start(saved.id, 123, fast=True)
            self.assertEqual(result.kind, 'candidates')
            self.assertEqual(result.candidates[0].artist, 'Kendrick Lamar')
            self.assertEqual(result.candidates[0].youtube_views, 3800000)
        self.assertEqual(fetcher.process.await_count, 2)
        from music_bot.interactions import present
        pending = NS(message_id=99, edit_text=AsyncMock())
        await present(NS(), result, 123, self.workflow, NS(), NS(), status_message=pending)
        label = pending.edit_text.call_args.kwargs['reply_markup'].inline_keyboard[0][0].text
        self.assertIn('YouTube 3,800,000', label)
        self.assertIn('not total song plays', pending.edit_text.call_args.args[0])
