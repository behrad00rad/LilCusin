import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import AsyncMock, patch

from music_bot.providers.common import Failure, ProviderError
from music_bot.validate_sources import report, validate


class ValidationTests(unittest.IsolatedAsyncioTestCase):
    async def test_not_found_is_success_and_both_providers_run(self):
        with patch("music_bot.validate_sources.load_environment"), patch.dict("os.environ", {"LASTFM_API_KEY": "test-secret"}), patch("music_bot.validate_sources.LastFMClient") as lastfm, patch("music_bot.validate_sources.MusicBrainzClient") as musicbrainz, redirect_stdout(io.StringIO()) as output:
            lastfm.return_value.search_tracks = AsyncMock(return_value=[])
            lastfm.return_value.get_track_info = AsyncMock(return_value=None)
            lastfm.return_value.get_top_tags = AsyncMock(return_value=())
            lastfm.return_value.get_similar_tracks = AsyncMock(return_value=[])
            musicbrainz.return_value.search_recordings = AsyncMock(return_value=[])
            self.assertEqual(await validate([("Artist", "Title")]), 0)
            self.assertIn("track not found", output.getvalue())
            self.assertNotIn("test-secret", output.getvalue())

    async def test_lastfm_failure_does_not_skip_musicbrainz(self):
        with patch("music_bot.validate_sources.load_environment"), patch.dict("os.environ", {"LASTFM_API_KEY": "test-secret"}), patch("music_bot.validate_sources.LastFMClient") as lastfm, patch("music_bot.validate_sources.MusicBrainzClient") as musicbrainz, redirect_stdout(io.StringIO()):
            lastfm.return_value.search_tracks = AsyncMock(side_effect=ProviderError(Failure.AUTH))
            musicbrainz.return_value.search_recordings = AsyncMock(return_value=[])
            self.assertEqual(await validate([("Artist", "Title")]), 1)
            musicbrainz.return_value.search_recordings.assert_awaited_once()

    async def test_missing_key_still_checks_musicbrainz(self):
        with patch("music_bot.validate_sources.load_environment"), patch.dict("os.environ", {}, clear=True), patch("music_bot.validate_sources.MusicBrainzClient") as musicbrainz, redirect_stdout(io.StringIO()):
            musicbrainz.return_value.search_recordings = AsyncMock(return_value=[])
            self.assertEqual(await validate([("Artist", "Title")]), 2)
            musicbrainz.return_value.search_recordings.assert_awaited_once()

    def test_report_redacts_credentials(self):
        with patch.dict("os.environ", {"LASTFM_API_KEY": "test-secret", "TELEGRAM_BOT_TOKEN": "fake-token"}), redirect_stdout(io.StringIO()) as output:
            report("test-secret fake-token")
            self.assertEqual(output.getvalue(), "[redacted] [redacted]\n")
