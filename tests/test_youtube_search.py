import json
import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

from music_bot.get_song import FetchSettings
from music_bot.youtube_fetch import YouTubeFetcher, FetchError, confident, rank_candidates


class YouTubeSearchTests(unittest.IsolatedAsyncioTestCase):
    def test_extra_upload_title_text_is_a_choice_not_an_automatic_match(self):
        track = NS(artist='Artist', title='Song Name', duration=200)
        rows = rank_candidates(track, [dict(id='abcdefghijk', title='Artist - Song Name extra upload credits and packaging',
            uploader='Artist', duration=200)], 900)
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]['title_mismatch'])
        self.assertFalse(confident(rows))
        for title, uploader in [('Other Song Name packaging credits', 'Unknown'),
                                ('Artist - Song Name (Cover)', 'Artist'),
                                ('Artist - Song Name (Karaoke)', 'Artist'),
                                ('Artist - Song Names packaging', 'Artist')]:
            self.assertFalse(rank_candidates(track, [dict(id='abcdefghijk', title=title, uploader=uploader, duration=200)], 900))

    def test_other_versions_offer_diversity_without_covers_or_wrong_artists(self):
        from music_bot.youtube_fetch import base_title
        self.assertEqual(base_title('Song (Live)'), 'Song')
        self.assertEqual(base_title('Live Forever'), 'Live Forever')
        track = NS(artist='Artist', title='Song', duration=None, allow_versions=True)
        entries = [dict(id='abcdefghij' + str(i), title='Artist - Song' + suffix,
                        artist=artist, duration=200) for i, (suffix, artist) in enumerate([
            ('', 'Artist'), (' (Live)', 'Artist'), (' (Acoustic)', 'Artist'),
            (' (Cover)', 'Artist'), ('', 'Other')])]
        rows = rank_candidates(track, entries, 900)
        self.assertEqual({tuple(r['version']) for r in rows}, {(), ('live',), ('acoustic',)})

    async def test_search_keeps_catalogue_punctuation(self):
        fetcher = YouTubeFetcher(FetchSettings())
        fetcher.process = AsyncMock(return_value=b'{"entries": []}')
        await fetcher.search(NS(artist='artist', title='untitled 02 l 06 23 2014', duration=None,
            display_artist='Artist', display_title='untitled 02 l 06.23.2014.'), '.', AsyncMock())
        query = fetcher.process.await_args.args[0][-1]
        self.assertEqual(query, 'ytsearch8:Artist untitled 02 l 06.23.2014. official audio')

    async def test_clip_duration_requires_choice_and_excludes_other_versions(self):
        fetcher = YouTubeFetcher(FetchSettings())
        rows = [dict(id='abcdefghijk', title='Kendrick Lamar - DNA.', uploader='Kendrick Lamar', duration=187),
                dict(id='bcdefghijkl', title='Kendrick Lamar - DNA. cover', uploader='Other', duration=187)]
        fetcher.process = AsyncMock(return_value=json.dumps({'entries': rows}).encode())
        result = await fetcher.search(NS(artist='Kendrick Lamar', title='DNA.', duration=116), '.', AsyncMock())
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0]['duration_mismatch'])
        self.assertFalse(confident(result))
        arguments = fetcher.process.call_args_list[0].args[0]
        self.assertIn('--flat-playlist', arguments)
        self.assertIn('--no-cookies-from-browser', arguments)

    async def test_matching_duration_has_no_mismatch_warning(self):
        fetcher = YouTubeFetcher(FetchSettings())
        fetcher.process = AsyncMock(return_value=json.dumps({'entries': [dict(id='abcdefghijk',
            title='Artist - Song', uploader='Artist', duration=187)]}).encode())
        result = await fetcher.search(NS(artist='Artist', title='Song', duration=187), '.', AsyncMock())
        self.assertNotIn('duration_mismatch', result[0])
        self.assertTrue(confident(result))

    async def test_bad_metadata_fails_with_fixed_error(self):
        fetcher = YouTubeFetcher(FetchSettings())
        fetcher.process = AsyncMock(return_value=b'private provider error')
        with self.assertRaisesRegex(FetchError, '^Source metadata unavailable.$'):
            await fetcher.search(NS(artist='Artist', title='Song', duration=187), '.', AsyncMock())

    def test_official_audio_beats_lyrics_and_equivalent_duplicates_need_no_choice(self):
        track = NS(artist='Artist', title='Song', duration=200)
        rows = [dict(id='abcdefghijk', title='Artist - Song (Official Audio)', uploader='Artist', duration=200),
                dict(id='bcdefghijkl', title='Song', uploader='Artist - Topic', duration=201),
                dict(id='cdefghijklm', title='Artist - Song (Lyrics)', uploader='Someone', duration=200)]
        ranked = rank_candidates(track, rows, 900)
        self.assertEqual(ranked[0]['id'], 'abcdefghijk')
        self.assertTrue(confident(ranked))

    def test_official_recording_is_not_ambiguous_with_matching_fan_upload(self):
        track = NS(artist='Kendrick Lamar', title='DNA.', duration=185)
        rows = [dict(id='abcdefghijk', title='DNA.', track='DNA.', artist='Kendrick Lamar', uploader='Kendrick Lamar', duration=186),
                dict(id='bcdefghijkl', title='DNA - Kendrick Lamar (AUDIO)', uploader='Fan', duration=187)]
        self.assertTrue(confident(rank_candidates(track, rows, 900)))

    def test_different_lengths_still_require_recording_choice(self):
        track = NS(artist='Artist', title='Song', duration=200)
        rows = [dict(id='abcdefghijk', title='Song', track='Song', artist='Artist', duration=200),
                dict(id='bcdefghijkl', title='Song', track='Song', artist='Artist', duration=205)]
        self.assertFalse(confident(rank_candidates(track, rows, 900)))

    def test_versions_and_wrong_explicit_artist_cannot_be_auto_selected(self):
        track = NS(artist='Artist', title='Song', duration=200)
        for label in ['Live', 'Remastered', 'Cover', 'Karaoke', 'Slowed + Reverb', 'Remix', 'Extended', '432hz']:
            self.assertFalse(rank_candidates(track, [dict(id='abcdefghijk', track='Song', artist='Artist',
                title='Artist - Song (' + label + ')', duration=200)], 900))
        self.assertFalse(rank_candidates(track, [dict(id='abcdefghijk', track='Song', artist='Other Artist',
            title='Song', duration=200)], 900))
        ranked = rank_candidates(track, [dict(id='abcdefghijk', title='Artist - Song', uploader='Fan', duration=200)], 900)
        self.assertFalse(confident(ranked))

    async def test_details_resolve_flat_search_uncertainty(self):
        fetcher = YouTubeFetcher(FetchSettings())
        flat = dict(id='abcdefghijk', title='Artist - Song (Audio)', uploader='Label', duration=200)
        detail = dict(id='abcdefghijk', track='Song', artist='Artist', title='Artist - Song (Audio)', duration=200)
        fetcher.process = AsyncMock(side_effect=[json.dumps({'entries': [flat]}).encode(), json.dumps(detail).encode()])
        result = await fetcher.search(NS(artist='Artist', title='Song', duration=200), '.', AsyncMock(return_value=True))
        self.assertTrue(confident(result))
        self.assertEqual(fetcher.process.await_count, 2)

    async def test_details_exposing_wrong_artist_remove_candidate(self):
        fetcher = YouTubeFetcher(FetchSettings())
        flat = dict(id='abcdefghijk', title='Artist - Song', uploader='Fan', duration=200)
        detail = dict(id='abcdefghijk', track='Song', artist='Other Artist', title='Song', duration=200)
        fetcher.process = AsyncMock(side_effect=[json.dumps({'entries': [flat]}).encode(), json.dumps(detail).encode()])
        self.assertEqual(await fetcher.search(NS(artist='Artist', title='Song', duration=200), '.', AsyncMock(return_value=True)), [])
