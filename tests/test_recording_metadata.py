import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
from music_bot.recording_metadata import clean_recording, search_label, resolve_metadata
from music_bot.providers.common import TrackCandidate
from music_bot.recording_search import recordings

class RecordingMetadataTests(unittest.IsolatedAsyncioTestCase):
    def test_repeated_credit_and_packaging_removed(self):
        title='Kanye West - Kanye West - Runaway (Official Video)'
        self.assertEqual(search_label('Kanye West',title,'youtube_music'),'Runaway — Kanye West')
        self.assertEqual(clean_recording('Lyrics Channel',title,'youtube_recording').artist,'Kanye West')

    def test_version_and_venue_visible_before_truncated_title(self):
        value=search_label('Kanye West','Kanye West - '+'Runaway '*20+'(Live at Wembley 2016)','youtube_music')
        self.assertTrue(value.startswith('Live at Wembley 2016 · '))
        self.assertLessEqual(len(value),64)
        self.assertTrue(value.endswith(' — Kanye West'))
        self.assertTrue(search_label('Artist','Song (Remix)','youtube_music').startswith('Remix · '))

    def test_real_catalogue_titles_and_versions_preserved(self):
        self.assertEqual(search_label('Oasis','Live Forever','itunes'),'Live Forever — Oasis')
        self.assertEqual(clean_recording('Artist','The Lyrics','itunes').title,'The Lyrics')
        self.assertIn('(Live)',clean_recording('Artist','Artist - Song (Live) (Official Video)','youtube_music').title)
        self.assertTrue(search_label('Artist','Song (Live)','youtube_music',locale='fa').startswith('اجرای زنده · '))

    def test_channel_name_not_promoted_to_artist_and_video_source_is_explicit(self):
        metadata=clean_recording('Random Lyrics Channel','Kanye West Runaway lyrics','youtube_recording')
        self.assertEqual(metadata.artist,'')
        self.assertEqual(metadata.title,'Kanye West Runaway')
        row=recordings([dict(videoId='abcdefghijk',title='Runaway',artists=[{'name':'Lyrics Channel'}],duration_seconds=200,resultType='video')])[0]
        self.assertEqual(row.source,'youtube_recording')

    def test_lyrics_suffix_is_not_mistaken_for_artist_credit(self):
        value = clean_recording('Channel','Runaway - Lyrics','youtube_recording')
        self.assertEqual((value.title,value.artist),('Runaway',''))

    async def test_title_first_upload_is_resolved_by_catalogue_not_guessed(self):
        track = NS(artist='Channel',title='Runaway - Kanye West',metadata_source='youtube_recording',duration=200)
        provider = NS(call=AsyncMock(return_value=[TrackCandidate(artist='Kanye West',title='Runaway',source='itunes',duration=200)]))
        self.assertEqual((await resolve_metadata(track,provider)).artist,'Kanye West')
        provider.call.side_effect = RuntimeError('fixture')
        self.assertEqual((await resolve_metadata(track,provider)).artist,'')

    async def test_catalogue_metadata_requires_artist_title_duration_and_version_evidence(self):
        track=NS(artist='Lyrics Channel',title='Kanye West Runaway lyrics',display_artist=None,display_title=None,metadata_source='youtube_recording',duration=200,album=None)
        provider=NS(call=AsyncMock(return_value=[TrackCandidate(artist='Kanye West',title='Runaway',source='itunes',duration=200,album='Some compilation')]))
        metadata=await resolve_metadata(track,provider)
        self.assertEqual((metadata.title,metadata.artist,metadata.album),('Runaway','Kanye West',None))
        self.assertEqual(track.artist,'Lyrics Channel')
        for row in [TrackCandidate(artist='Other',title='Runaway',source='itunes',duration=200),
                    TrackCandidate(artist='Kanye West',title='Runaway (Live)',source='itunes',duration=200),
                    TrackCandidate(artist='Kanye West',title='Runaway',source='itunes',duration=500)]:
            provider.call.return_value=[row]
            metadata=await resolve_metadata(track,provider)
            self.assertEqual(metadata.artist,'')

    async def test_ambiguous_or_failed_catalogue_lookup_never_uses_channel_as_artist(self):
        track=NS(artist='Channel',title='A B lyrics',metadata_source='youtube_recording',duration=None)
        provider=NS(call=AsyncMock(return_value=[TrackCandidate(artist='A',title='B',source='itunes'),TrackCandidate(artist='B',title='A',source='itunes')]))
        self.assertEqual((await resolve_metadata(track,provider)).artist,'')
        provider.call.side_effect=RuntimeError('fixture failure')
        self.assertEqual((await resolve_metadata(track,provider)).artist,'')
