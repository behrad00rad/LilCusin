import asyncio
import json
import math
import sys
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from sqlalchemy import func, select

from music_bot.audio.analyzer import analyse_audio
from music_bot.audio.common import ANALYZER_NAME, ANALYZER_VERSION, AudioError, Category
from music_bot.audio.download import download_audio, validate_metadata
from music_bot.audio.features import validate_features
from music_bot.audio.ffmpeg import available, convert_audio
from music_bot.audio.process import run_process, worker_environment
from music_bot.audio.service import AudioAnalysisService
from music_bot.config import Config, ConfigError, load_config
from music_bot.models import AudioAnalysis, SongSubmission, Track, utc_now
from music_bot.submissions import AudioMetadata, Submitter
from tests.audio_fixture import click_track, feature_result
from tests.support import ServiceTestCase


def metadata(**changes):
    return SimpleNamespace(**{**dict(file_id="file", file_size=1000, duration=12,
                                   mime_type="audio/wav", original_filename="track.wav"), **changes})


class AudioValidationTests(unittest.TestCase):
    def test_limits_reject_unsafe_environment(self):
        for name, bad_values in {
            "MAX_AUDIO_FILE_MB": ("0", "21", "-1", "nan", "", "1.5"),
            "MAX_AUDIO_DURATION_SECONDS": ("0", "901", "inf"),
            "AUDIO_ANALYSIS_CONCURRENCY": ("0", "3", "lots"),
        }.items():
            for value in bad_values:
                with self.subTest(name=name, value=value), patch.dict("os.environ", {
                    "TELEGRAM_BOT_TOKEN": "123:fake", "LASTFM_API_KEY": "fake", name: value,
                }, clear=True), patch("music_bot.config.load_environment"):
                    with self.assertRaises(ConfigError) as error:
                        load_config()
                    self.assertIn(name, str(error.exception))

    def test_default_limits(self):
        config = Config("fake", "fake")
        self.assertEqual((config.max_audio_file_mb, config.max_audio_duration_seconds, config.audio_analysis_concurrency), (20, 900, 2))

    def test_metadata_validation(self):
        for changes, category in [({"file_id": None}, Category.METADATA),
                                  ({"file_size": 20_000_001}, Category.SIZE),
                                  ({"duration": 901}, Category.DURATION),
                                  ({"duration": math.nan}, Category.METADATA),
                                  ({"mime_type": "application/zip"}, Category.TYPE),
                                  ({"original_filename": "music.exe"}, Category.TYPE)]:
            with self.subTest(changes=changes), self.assertRaises(AudioError) as error:
                validate_metadata(metadata(**changes), Config("fake", "fake"))
            self.assertEqual(error.exception.category, category)
        validate_metadata(metadata(file_size=None, duration=None, mime_type=None, original_filename=None), Config("fake", "fake"))

    def test_invalid_numbers_and_semantics_rejected(self):
        for key, value in [("bpm", math.nan), ("rms_mean", math.inf), ("spectral_centroid_mean", -1),
                           ("beat_count", 1.5), ("chroma_mean", [0] * 13), ("chroma_mean", [math.nan] * 12)]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_features({**feature_result(), key: value})
        with self.assertRaises(ValueError):
            validate_features({**feature_result(), "genre": "fake"})
        unknown = {**feature_result(), "bpm": None, "beat_count": 0}
        self.assertIsNone(validate_features(unknown)["bpm"])
        self.assertEqual(json.loads(json.dumps(feature_result())), feature_result())


class DownloadTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory(dir="/tmp")
        self.path = Path(self.temp.name) / "input.bin"
        self.bot = AsyncMock()
        self.bot.get_file.return_value = SimpleNamespace(file_path="audio/remote", file_size=10)

    async def asyncTearDown(self):
        self.temp.cleanup()

    async def test_oversized_before_download(self):
        with self.assertRaises(AudioError):
            await download_audio(self.bot, metadata(file_size=20_000_001), Config("fake", "fake"), self.path)
        self.bot.get_file.assert_not_awaited()

    async def test_remote_size_checked(self):
        self.bot.get_file.return_value.file_size = 20_000_001
        with self.assertRaises(AudioError):
            await download_audio(self.bot, metadata(file_size=None), Config("fake", "fake"), self.path)
        self.bot.download_file.assert_not_awaited()

    async def test_stream_byte_limit_even_with_misleading_metadata(self):
        async def download(path, destination, **kwargs):
            destination.write(b"x" * 1_000_001)
        self.bot.download_file.side_effect = download
        with self.assertRaises(AudioError) as error:
            await download_audio(self.bot, metadata(), Config("fake", "fake", max_audio_file_mb=1), self.path)
        self.assertEqual(error.exception.category, Category.SIZE)

    async def test_malicious_filename_never_used_as_path(self):
        async def download(path, destination, **kwargs):
            destination.write(b"audio")
        self.bot.download_file.side_effect = download
        await download_audio(self.bot, metadata(original_filename="../../outside.wav"), Config("fake", "fake"), self.path)
        self.assertEqual([path.name for path in Path(self.temp.name).iterdir()], ["input.bin"])

    async def test_empty_download_and_network_failure(self):
        with self.assertRaises(AudioError):
            await download_audio(self.bot, metadata(), Config("fake", "fake"), self.path)
        self.bot.get_file.side_effect = ValueError("secret and private path")
        with self.assertRaises(AudioError) as error:
            await download_audio(self.bot, metadata(), Config("fake", "fake"), self.path)
        self.assertEqual(str(error.exception), Category.DOWNLOAD.value)


class ProcessingTests(unittest.IsolatedAsyncioTestCase):
    async def test_subprocess_timeout_and_output_limit(self):
        with self.assertRaises(AudioError) as error:
            await run_process([sys.executable, "-c", "import time; time.sleep(10)"], 0.05)
        self.assertEqual(error.exception.category, Category.TIMEOUT)
        with self.assertRaises(AudioError):
            await run_process([sys.executable, "-c", "print('x'*1000000)"], 5, output_limit=100)

    async def test_subprocess_cancellation_reaps_child(self):
        created = []
        original = asyncio.create_subprocess_exec
        async def spawn(*args, **kwargs):
            process = await original(*args, **kwargs)
            created.append(process)
            return process
        with patch("music_bot.audio.process.asyncio.create_subprocess_exec", side_effect=spawn):
            task = asyncio.create_task(run_process([sys.executable, "-c", "import time; time.sleep(10)"], 20))
            while not created:
                await asyncio.sleep(0.01)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        self.assertIsNotNone(created[0].returncode)

    async def test_missing_ffmpeg(self):
        with patch("music_bot.audio.ffmpeg.available", return_value=False), self.assertRaises(AudioError) as error:
            await convert_audio(Path("unused"), Path("unused"), 10)
        self.assertEqual(error.exception.category, Category.MISSING_FFMPEG)

    async def test_ffmpeg_failure_timeout_and_librosa_failure(self):
        for category in (Category.DECODE, Category.TIMEOUT):
            with patch("music_bot.audio.ffmpeg.available", return_value=True), patch("music_bot.audio.ffmpeg.run_process", side_effect=AudioError(category)), self.assertRaises(AudioError) as error:
                await convert_audio(Path("/tmp/unused"), Path("/tmp/unused2"), 10)
            self.assertEqual(error.exception.category, category)
        with patch("music_bot.audio.analyzer.run_process", return_value=b'{"error":"feature_extraction_failed"}'), self.assertRaises(AudioError) as error:
            await analyse_audio(Path("/tmp/unused"))
        self.assertEqual(error.exception.category, Category.FEATURES)

    @unittest.skipUnless(available(), "FFmpeg not installed")
    async def test_real_click_track_features_and_conversion(self):
        with tempfile.TemporaryDirectory(prefix="task8-fixture-", dir="/tmp") as directory:
            source, converted = Path(directory) / "click.wav", Path(directory) / "analysis.wav"
            click_track(source)
            await convert_audio(source, converted, 900)
            result = await analyse_audio(converted)
            self.assertLess(abs(result["bpm"] - 120), 5)
            self.assertGreater(result["beat_count"], 15)
            self.assertEqual(len(result["chroma_mean"]), 12)
            self.assertEqual(result["sample_rate"], 22050)
            self.assertAlmostEqual(result["analysed_duration"], 12)
            json.dumps(result, allow_nan=False)
            print(f"Click-track check: expected 120 BPM; estimated {result['bpm']:.6f} BPM; {result['beat_count']} beats; 12 seconds.")
        self.assertFalse(Path(directory).exists())

    @unittest.skipUnless(available(), "FFmpeg not installed")
    async def test_corrupt_and_excessively_long_content(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as directory:
            source, converted = Path(directory) / "input.bin", Path(directory) / "analysis.wav"
            source.write_bytes(b"not audio")
            with self.assertRaises(AudioError):
                await convert_audio(source, converted, 10)
            click_track(source, seconds=2)
            with self.assertRaises(AudioError) as error:
                await convert_audio(source, converted, 1)
            self.assertEqual(error.exception.category, Category.DURATION)

    def test_worker_environment_has_no_secrets(self):
        with patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "secret", "LASTFM_API_KEY": "private"}):
            environment = worker_environment(Path("/tmp/test"))
        self.assertNotIn("TELEGRAM_BOT_TOKEN", environment)
        self.assertNotIn("LASTFM_API_KEY", environment)


class AnalysisPersistenceTests(ServiceTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.bot = AsyncMock()
        self.bot.get_file.return_value = SimpleNamespace(file_path="audio/file", file_size=10)
        self.paths = []
        async def download(path, destination, **kwargs):
            self.paths.append(Path(destination.file.name).parent)
            destination.write(b"audio")
        self.bot.download_file.side_effect = download
        self.manager = AudioAnalysisService(self.database, self.bot, Config("fake", "fake"))
        self.patches = [patch("music_bot.audio.service.available", return_value=True),
                        patch("music_bot.audio.service.convert_audio", new_callable=AsyncMock),
                        patch("music_bot.audio.service.analyse_audio", new_callable=AsyncMock, return_value=feature_result())]
        self.available, self.convert, self.analyse = [p.start() for p in self.patches]

    async def asyncTearDown(self):
        await self.manager.close()
        for p in self.patches:
            p.stop()
        self.assertTrue(all(not path.exists() for path in self.paths))
        await super().asyncTearDown()

    async def submission(self, user=123, *, track_id=None, confirmed=True, text=False, file_id="file"):
        if text:
            saved = await self.submissions.submit_text(Submitter(user), "Artist - Song")
        else:
            saved = await self.submissions.submit_audio(Submitter(user), AudioMetadata(file_id, "unique", duration=12,
                                                      filename="test.wav", mime_type="audio/wav", file_size=1000))
        async with self.database.write() as session:
            if track_id is None:
                track = Track(artist="Artist", title=f"Song {saved.id}", metadata_source="lastfm")
                session.add(track)
                await session.flush()
                track_id = track.id
            if confirmed:
                stored = await session.get(SongSubmission, saved.id)
                stored.track_id, stored.identification_status = track_id, "confirmed"
        return saved.id, track_id

    async def finish(self):
        await asyncio.gather(*list(self.manager.tasks.values()))

    async def test_eligibility_and_success_bpm_sync(self):
        for options, user in [({"confirmed": False}, 123), ({"text": True}, 123), ({}, 456)]:
            submission, _ = await self.submission(**options)
            await self.manager.schedule(submission, user)
        self.assertFalse(self.manager.tasks)
        submission, track_id = await self.submission()
        await self.manager.schedule(submission, 123)
        await self.finish()
        async with self.database.sessions() as session:
            row = await session.scalar(select(AudioAnalysis))
            self.assertEqual(row.status, "succeeded")
            self.assertEqual(row.bpm, 120)
            self.assertEqual((await session.get(Track, track_id)).bpm, 120)
            self.assertEqual(row.features, feature_result())
        self.bot.send_message.assert_awaited_once()

    async def test_reuse_and_concurrent_duplicate_requests(self):
        one, track = await self.submission()
        two, _ = await self.submission(456, track_id=track)
        await asyncio.gather(self.manager.schedule(one, 123), self.manager.schedule(two, 456))
        await self.finish()
        await self.manager.schedule(two, 456)
        self.analyse.assert_awaited_once()
        async with self.database.sessions() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(AudioAnalysis)), 1)

    async def test_failure_retry_and_no_duplicate_rows(self):
        self.analyse.side_effect = AudioError(Category.FEATURES)
        submission, _ = await self.submission()
        await self.manager.schedule(submission, 123)
        await self.finish()
        async with self.database.write() as session:
            row = await session.scalar(select(AudioAnalysis))
            self.assertEqual(row.status, "failed")
            self.assertEqual(row.error_category, "feature_extraction_failed")
            row.updated_at = utc_now() - timedelta(minutes=2)
        self.analyse.side_effect = None
        await self.manager.schedule(submission, 123)
        await self.finish()
        async with self.database.sessions() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(AudioAnalysis)), 1)
            row = await session.scalar(select(AudioAnalysis))
            self.assertEqual(row.status, "succeeded")
            self.assertEqual(row.attempts, 2)

    async def test_missing_file_id_and_missing_ffmpeg(self):
        for uid, file_id, has_ffmpeg, category in [(123, None, True, "invalid_metadata"), (456, "f", False, "ffmpeg_unavailable")]:
            self.available.return_value = has_ffmpeg
            submission, _ = await self.submission(uid, file_id=file_id)
            await self.manager.schedule(submission, uid)
            await self.finish()
            async with self.database.sessions() as session:
                row = await session.scalar(select(AudioAnalysis).where(AudioAnalysis.submission_id == submission))
                self.assertEqual(row.error_category, category)
        self.bot.download_file.assert_not_awaited()

    async def test_timeout_and_cleanup(self):
        async def slow(path):
            await asyncio.sleep(10)
        self.analyse.side_effect = slow
        submission, _ = await self.submission()
        with patch("music_bot.audio.service.TOTAL_TIMEOUT", 0.1):
            await self.manager.schedule(submission, 123)
            await self.finish()
        async with self.database.sessions() as session:
            self.assertEqual((await session.scalar(select(AudioAnalysis))).error_category, "timeout")

    async def test_cancellation_cleanup_and_recovery(self):
        started = asyncio.Event()
        async def slow(path):
            started.set()
            await asyncio.sleep(10)
        self.analyse.side_effect = slow
        submission, _ = await self.submission()
        await self.manager.schedule(submission, 123)
        await started.wait()
        await self.manager.close()
        async with self.database.write() as session:
            row = await session.scalar(select(AudioAnalysis))
            self.assertEqual(row.error_category, "interrupted")
            row.status = "processing"
        await self.manager.initialize()
        async with self.database.sessions() as session:
            self.assertEqual((await session.scalar(select(AudioAnalysis))).status, "failed")

    async def test_shutdown_before_worker_starts(self):
        submission, _ = await self.submission()
        await self.manager.schedule(submission, 123)
        await self.manager.close()
        async with self.database.sessions() as session:
            row = await session.scalar(select(AudioAnalysis))
            self.assertEqual(row.status, "failed")
            self.assertEqual(row.error_category, "interrupted")
        self.assertFalse(self.manager.tasks)

    async def test_concurrency_and_user_rate_limit(self):
        started = 0
        maximum = 0
        release = asyncio.Event()
        async def slow(path):
            nonlocal started, maximum
            started += 1
            maximum = max(maximum, started)
            await release.wait()
            started -= 1
            return feature_result()
        self.analyse.side_effect = slow
        for uid in (123, 456, 789):
            submission, _ = await self.submission(uid)
            await self.manager.schedule(submission, uid)
        extra, _ = await self.submission(123)
        await self.manager.schedule(extra, 123)
        await asyncio.sleep(0.1)
        self.assertEqual(started, 2)
        self.assertEqual(len(self.manager.tasks), 3)
        release.set()
        await self.finish()
        self.assertEqual(maximum, 2)
