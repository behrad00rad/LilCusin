"""Synthetic provider fixtures: no network, downloads or assertions about catalogue availability."""
import unittest
from types import SimpleNamespace as NS
from music_bot.youtube_fetch import rank_candidates, confident

VIDEO = 'abcdefghijk'


class MatchingMatrixTests(unittest.TestCase):
    def match(self, artist, title, source_title, source_artist=None, uploader=None):
        track = NS(artist=artist, title=title, duration=200)
        row = dict(id=VIDEO, title=source_title, uploader=uploader or artist, duration=200)
        if source_artist:
            row.update(track=title, artist=source_artist)
        return rank_candidates(track, [row], 900)

    def test_english_persian_typography_and_real_title_words(self):
        cases = [
            ('Metallica', 'The Unforgiven', 'Metallica - The Unforgiven (Official Audio)'),
            ('Radiohead', 'Creep', 'Creep (Official Audio)'),
            ('Googoosh', 'Hamsafar', 'Googoosh - Hamsafar'),
            ('گوگوش', 'همسفر', 'گوگوش - همسفر (Official Audio)'),
            ('محسن یگانه', 'بهت قول میدم', 'محسن يگانه - بهت قول ميدم'),
            ('LSD', 'Audio', 'LSD - Audio (Official Audio)'),
            ('Low', 'Slow', 'Slow'),
            ('Prince', 'Prince', 'Prince'),
            ('Artist', "Don't Stop", 'Artist - Don’t Stop (Official Audio)'),
        ]
        for artist, title, source in cases:
            with self.subTest(artist=artist, title=title):
                self.assertTrue(confident(self.match(artist, title, source)))

    def test_collaboration_credit_formats_preserve_all_artists(self):
        for canonical, source in [('Artist feat. Guest', 'Artist & Guest'),
                                  ('Artist & Guest', 'Guest, Artist'),
                                  ('Artist featuring Guest', 'Artist ft. Guest')]:
            with self.subTest(canonical=canonical, source=source):
                self.assertTrue(confident(self.match(canonical, 'Song', 'Song', source_artist=source)))
        self.assertFalse(self.match('Artist & Guest', 'Song', 'Song', source_artist='Artist'))
        self.assertFalse(self.match('Artist & Guest', 'Song', 'Song', source_artist='Guest & Other'))
        self.assertTrue(self.match('Artist feat. Guest', 'Song', 'Artist & Guest - Song', uploader='Label'))

    def test_same_title_wrong_artist_and_artist_substrings_are_rejected(self):
        self.assertFalse(self.match('Radiohead', 'Creep', 'Creep', source_artist='Stone Temple Pilots'))
        rows = self.match('Artist', 'Song', 'OtherArtist - Song', uploader='OtherArtist')
        self.assertFalse(confident(rows))

    def test_requested_versions_are_kept_and_unrequested_versions_rejected(self):
        for version in ['Live', 'Remix', 'Acoustic', 'Remastered', 'کاور', 'ریمیکس', 'اجرای زنده', 'بی کلام']:
            with self.subTest(version=version):
                self.assertFalse(self.match('Artist', 'Song', 'Artist - Song ('+version+')'))
                self.assertTrue(self.match('Artist', 'Song ('+version+')', 'Artist - Song ('+version+')'))

    def test_artist_named_live_does_not_hide_a_live_recording(self):
        self.assertTrue(confident(self.match('Live', 'Lightning Crashes', 'Live - Lightning Crashes')))
        self.assertFalse(self.match('Live', 'Lightning Crashes', 'Live - Lightning Crashes (Live)'))
