"""Tiny, generated test audio; no copyrighted recordings."""

import math
import struct
import wave

from music_bot.audio.common import SAMPLE_RATE


def click_track(path, bpm=120, seconds=12):
    frames = bytearray()
    interval = round(SAMPLE_RATE * 60 / bpm)
    for index in range(SAMPLE_RATE * seconds):
        phase = index % interval
        sample = 0.7 * math.exp(-phase / 100) * math.sin(2 * math.pi * 1000 * phase / SAMPLE_RATE) if phase < 700 else 0
        frames.extend(struct.pack("<h", int(sample * 32767)))
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(SAMPLE_RATE)
        output.writeframes(frames)


def feature_result():
    from music_bot.audio.features import SCALARS
    result = {name: 0.0 for name in SCALARS}
    result.update(bpm=120.0, beat_count=24, analysed_duration=12.0,
                  sample_rate=SAMPLE_RATE, chroma_mean=[0.0] * 12)
    return result
