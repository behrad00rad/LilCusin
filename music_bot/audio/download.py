import asyncio
import math
from pathlib import PurePath

from .common import AudioError, Category

MIMES = {"audio/mpeg", "audio/mp3", "audio/mp4", "audio/x-m4a", "audio/aac",
         "audio/ogg", "audio/opus", "audio/flac", "audio/x-flac", "audio/wav", "audio/x-wav", "audio/vnd.wave"}
EXTENSIONS = {".mp3", ".m4a", ".mp4", ".aac", ".ogg", ".oga", ".opus", ".flac", ".wav"}


def validate_metadata(submission, config):
    if not submission.file_id:
        raise AudioError(Category.METADATA)
    size = submission.file_size
    if size is not None:
        if not isinstance(size, int) or size <= 0:
            raise AudioError(Category.METADATA)
        if size > config.max_audio_file_mb * 1_000_000:
            raise AudioError(Category.SIZE)
    duration = submission.duration
    if duration is not None:
        if not math.isfinite(duration) or duration < 0:
            raise AudioError(Category.METADATA)
        if duration > config.max_audio_duration_seconds:
            raise AudioError(Category.DURATION)
    # Missing labels defer to content probing. Provided labels must be allowed.
    if submission.mime_type and submission.mime_type.lower() not in MIMES:
        raise AudioError(Category.TYPE)
    if submission.original_filename and PurePath(submission.original_filename).suffix.lower() not in EXTENSIONS:
        raise AudioError(Category.TYPE)


class LimitedFile:
    """aiogram-compatible sink enforcing a byte ceiling while streaming."""

    def __init__(self, file, limit):
        self.file, self.limit, self.written = file, limit, 0

    def write(self, chunk):
        if self.written + len(chunk) > self.limit:
            raise AudioError(Category.SIZE)
        count = self.file.write(chunk)
        self.written += count
        return count

    def flush(self):
        self.file.flush()


async def download_audio(bot, submission, config, destination):
    validate_metadata(submission, config)
    limit = config.max_audio_file_mb * 1_000_000
    try:
        remote = await asyncio.wait_for(bot.get_file(submission.file_id), 10)
        if remote.file_size is not None and remote.file_size > limit:
            raise AudioError(Category.SIZE)
        if not remote.file_path:
            raise AudioError(Category.DOWNLOAD)
        # destination is generated internally; no Telegram filename is used.
        with destination.open("xb") as output:
            sink = LimitedFile(output, limit)
            await bot.download_file(remote.file_path, destination=sink, timeout=30,
                                    chunk_size=65536, seek=False)
        if not 0 < destination.stat().st_size <= limit:
            raise AudioError(Category.DECODE)
    except AudioError:
        raise
    except Exception:
        raise AudioError(Category.DOWNLOAD) from None
