import json
import math
import shutil
import wave

from .common import AudioError, Category, CONVERSION_TIMEOUT, SAMPLE_RATE
from .process import run_process, worker_environment

FORMATS = "mp3,wav,flac,ogg,mov,aac"


def available():
    return bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


async def convert_audio(source, destination, maximum_duration):
    if not available():
        raise AudioError(Category.MISSING_FFMPEG)
    env = worker_environment(source.parent)
    probe = await run_process([
        shutil.which("ffprobe"), "-v", "quiet", "-protocol_whitelist", "file,pipe",
        "-format_whitelist", FORMATS, "-select_streams", "a:0",
        "-show_entries", "stream=codec_type,duration:format=duration", "-of", "json", str(source),
    ], 10, env=env)
    try:
        metadata = json.loads(probe)
        if not metadata.get("streams") or metadata["streams"][0].get("codec_type") != "audio":
            raise ValueError
        for raw in (metadata.get("format", {}).get("duration"), metadata["streams"][0].get("duration")):
            if raw is not None and raw != "N/A":
                duration = float(raw)
                if not math.isfinite(duration) or duration <= 0:
                    raise ValueError
                if duration > maximum_duration:
                    raise AudioError(Category.DURATION)
    except (ValueError, KeyError, TypeError, IndexError):
        raise AudioError(Category.DECODE) from None
    await run_process([
        shutil.which("ffmpeg"), "-nostdin", "-v", "quiet", "-y", "-threads", "1",
        "-protocol_whitelist", "file,pipe", "-format_whitelist", FORMATS, "-i", str(source),
        "-map", "0:a:0", "-vn", "-sn", "-dn", "-ac", "1", "-ar", str(SAMPLE_RATE),
        "-t", str(maximum_duration + 1), "-fs", str((maximum_duration + 2) * SAMPLE_RATE * 2 + 4096),
        "-c:a", "pcm_s16le", "-threads", "1", str(destination),
    ], CONVERSION_TIMEOUT, env=env)
    # Catches absent/false container duration without decoding unbounded audio.
    try:
        with wave.open(str(destination), "rb") as audio:
            duration = audio.getnframes() / audio.getframerate()
            if duration > maximum_duration:
                raise AudioError(Category.DURATION)
            if duration <= 0 or audio.getnchannels() != 1 or audio.getframerate() != SAMPLE_RATE:
                raise AudioError(Category.DECODE)
    except (wave.Error, EOFError, OSError):
        raise AudioError(Category.DECODE) from None
