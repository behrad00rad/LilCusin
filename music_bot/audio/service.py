import asyncio
import logging
import tempfile
from datetime import timedelta
from pathlib import Path

from sqlalchemy import func, or_, select, update

from .. import messages
from ..models import AudioAnalysis, SongSubmission, Track, User, utc_now
from .analyzer import analyse_audio
from .common import ANALYZER_NAME, ANALYZER_VERSION, AudioError, Category, TOTAL_TIMEOUT
from .download import download_audio, validate_metadata
from .ffmpeg import available, convert_audio
from .features import validate_features

logger = logging.getLogger("music_bot")
USER_COOLDOWN = timedelta(seconds=60)


class AudioAnalysisService:
    def __init__(self, database, bot, config):
        self.database, self.bot, self.config = database, bot, config
        self.slots = asyncio.Semaphore(config.audio_analysis_concurrency)
        self.tasks = {}
        self.closing = False

    async def initialize(self):
        async with self.database.write() as session:
            await session.execute(update(AudioAnalysis).where(
                AudioAnalysis.status.in_(["pending", "processing"]),
            ).values(status="failed", error_category=Category.INTERRUPTED.value, updated_at=utc_now()))
        if not available():
            logger.warning("FFmpeg/ffprobe unavailable. Install ffmpeg to enable local audio analysis.")

    async def schedule(self, submission_id, telegram_user_id):
        """Called only after the rating prompt. Ownership is rechecked here."""
        if self.closing or len(self.tasks) >= self.config.audio_analysis_concurrency * 2:
            return
        async with self.database.write() as session:
            submission = await session.scalar(select(SongSubmission).join(User).where(
                SongSubmission.id == submission_id, User.telegram_user_id == telegram_user_id,
            ))
            if (submission is None or submission.submission_type != "telegram_audio"
                    or submission.identification_status != "confirmed" or submission.track_id is None):
                return
            row = await session.scalar(select(AudioAnalysis).where(
                AudioAnalysis.track_id == submission.track_id, AudioAnalysis.analyzer_name == ANALYZER_NAME,
                AudioAnalysis.analyzer_version == ANALYZER_VERSION,
            ))
            if row and row.status in ("succeeded", "pending", "processing"):
                return
            if row and row.submission_id == submission.id and row.attempts >= 3:
                return
            active_count = await session.scalar(select(func.count()).select_from(AudioAnalysis).where(
                AudioAnalysis.status.in_(["pending", "processing"])))
            if active_count >= self.config.audio_analysis_concurrency * 2:
                return
            recent = await session.scalar(select(AudioAnalysis.id).where(
                AudioAnalysis.requested_by == submission.user_id,
                or_(AudioAnalysis.status.in_(["pending", "processing"]),
                    AudioAnalysis.updated_at > utc_now() - USER_COOLDOWN),
            ).limit(1))
            if recent is not None:
                return
            if row is None:
                row = AudioAnalysis(track_id=submission.track_id, submission_id=submission.id,
                                    requested_by=submission.user_id, analyzer_name=ANALYZER_NAME,
                                    analyzer_version=ANALYZER_VERSION, status="pending")
                session.add(row)
            else:
                row.attempts = row.attempts + 1 if row.submission_id == submission.id else 1
                row.submission_id, row.requested_by = submission.id, submission.user_id
                row.status, row.error_category = "pending", None
                row.updated_at = utc_now()
            await session.flush()
            analysis_id = row.id
        # No worker gets an async DB session. A detached submission holds metadata only.
        task = asyncio.create_task(self._run(analysis_id, submission, telegram_user_id))
        self.tasks[analysis_id] = task
        task.add_done_callback(self._observe)

    @staticmethod
    def _observe(task):
        if not task.cancelled() and task.exception() is not None:
            logger.error("Audio analysis task failed; details omitted for privacy.")

    async def _status(self, analysis_id, status, *, category=None, features=None):
        if features is not None:
            validate_features(features)
        async with self.database.write() as session:
            row = await session.get(AudioAnalysis, analysis_id)
            row.status, row.error_category = status, category.value if category else None
            row.updated_at = utc_now()
            if features is not None:
                row.features, row.bpm = features, features["bpm"]
                track = await session.get(Track, row.track_id)
                # The latest successful local analysis is the sole writer of Track.bpm.
                track.bpm = row.bpm

    async def _run(self, analysis_id, submission, user_id):
        succeeded = False
        try:
            async with asyncio.timeout(TOTAL_TIMEOUT):
                async with self.slots:
                    await self._status(analysis_id, "processing")
                    validate_metadata(submission, self.config)
                    if not available():
                        raise AudioError(Category.MISSING_FFMPEG)
                    # Explicit OS temp root prevents a repository-local TMPDIR override.
                    with tempfile.TemporaryDirectory(prefix="music-bot-audio-", dir="/tmp") as directory:
                        root = Path(directory)
                        source, converted = root / "input.bin", root / "analysis.wav"
                        await download_audio(self.bot, submission, self.config, source)
                        await convert_audio(source, converted, self.config.max_audio_duration_seconds)
                        features = await analyse_audio(converted)
                    await self._status(analysis_id, "succeeded", features=features)
                    succeeded = True
            await self._notify(user_id, messages.audio_analysis_complete(features["bpm"]))
        except asyncio.CancelledError:
            if not succeeded:
                await self._status(analysis_id, "failed", category=Category.INTERRUPTED)
            raise
        except Exception as error:
            category = (Category.TIMEOUT if isinstance(error, TimeoutError) else
                        error.category if isinstance(error, AudioError) else Category.INTERNAL)
            logger.warning("Local audio analysis did not complete; details omitted for privacy.")
            await self._status(analysis_id, "failed", category=category)
            await self._notify(user_id, messages.AUDIO_ANALYSIS_FAILED)
        finally:
            self.tasks.pop(analysis_id, None)

    async def _notify(self, user_id, text):
        try:
            await asyncio.wait_for(self.bot.send_message(user_id, text), 10)
        except Exception:
            logger.warning("Could not deliver audio analysis status.")

    async def close(self):
        self.closing = True
        identifiers = list(self.tasks)
        tasks = list(self.tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        if identifiers:
            # Tasks cancelled before entering their coroutine have no finally block.
            async with self.database.write() as session:
                await session.execute(update(AudioAnalysis).where(
                    AudioAnalysis.id.in_(identifiers), AudioAnalysis.status.in_(["pending", "processing"]),
                ).values(status="failed", error_category=Category.INTERRUPTED.value, updated_at=utc_now()))
        self.tasks.clear()
