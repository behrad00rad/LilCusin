"""Numerical feature extraction only. Imported by the isolated CPU worker."""

import math
import wave

from .common import SAMPLE_RATE

SCALARS = {"bpm", "beat_count", "onset_strength_mean", "rms_mean", "rms_std",
           "spectral_centroid_mean", "spectral_centroid_std", "spectral_bandwidth_mean",
           "spectral_bandwidth_std", "spectral_rolloff_mean", "spectral_rolloff_std",
           "zero_crossing_rate_mean", "zero_crossing_rate_std", "analysed_duration", "sample_rate"}


def validate_features(result):
    if not isinstance(result, dict) or set(result) != SCALARS | {"chroma_mean"}:
        raise ValueError("Invalid feature fields")
    for key in SCALARS:
        value = result[key]
        if key == "bpm" and value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError("Invalid numerical feature")
    if result["sample_rate"] != SAMPLE_RATE or result["analysed_duration"] <= 0:
        raise ValueError("Invalid analysis format")
    if type(result["beat_count"]) is not int:
        raise ValueError("Invalid beat count")
    if result["bpm"] is not None and (result["bpm"] <= 0 or result["beat_count"] < 2):
        raise ValueError("Invalid tempo estimate")
    chroma = result["chroma_mean"]
    if not isinstance(chroma, list) or len(chroma) != 12:
        raise ValueError("Invalid chroma summary")
    if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) or not 0 <= x <= 1.000001 for x in chroma):
        raise ValueError("Invalid chroma values")
    return result


def extract_features(path):
    import librosa
    import numpy as np

    with wave.open(str(path), "rb") as audio:
        if audio.getnchannels() != 1 or audio.getsampwidth() != 2 or audio.getframerate() != SAMPLE_RATE:
            raise ValueError("Invalid analysis audio")
        samples = np.frombuffer(audio.readframes(audio.getnframes()), dtype="<i2").astype(np.float32) / 32768.0
    if samples.size == 0 or not np.isfinite(samples).all():
        raise ValueError("Invalid samples")
    hop = 512
    onset = librosa.onset.onset_strength(y=samples, sr=SAMPLE_RATE, hop_length=hop)
    tempo, beats = librosa.beat.beat_track(onset_envelope=onset, sr=SAMPLE_RATE, hop_length=hop)
    bpm = float(np.asarray(tempo).reshape(-1)[0])
    # An absent/zero beat estimate is unknown, not a guessed fallback tempo.
    result = {"bpm": bpm if bpm > 0 and len(beats) >= 2 else None,
              "beat_count": int(len(beats)), "onset_strength_mean": float(np.mean(onset)),
              "analysed_duration": float(len(samples) / SAMPLE_RATE), "sample_rate": SAMPLE_RATE}
    spectrum = np.abs(librosa.stft(samples, n_fft=2048, hop_length=hop))
    measures = (
        ("rms", lambda: librosa.feature.rms(y=samples, hop_length=hop)),
        ("spectral_centroid", lambda: librosa.feature.spectral_centroid(S=spectrum, sr=SAMPLE_RATE)),
        ("spectral_bandwidth", lambda: librosa.feature.spectral_bandwidth(S=spectrum, sr=SAMPLE_RATE)),
        ("spectral_rolloff", lambda: librosa.feature.spectral_rolloff(S=spectrum, sr=SAMPLE_RATE, roll_percent=0.85)),
        ("zero_crossing_rate", lambda: librosa.feature.zero_crossing_rate(samples, hop_length=hop)),
    )
    for name, measure in measures:
        values = measure()
        result[name + "_mean"] = float(np.mean(values))
        result[name + "_std"] = float(np.std(values))
    chroma = librosa.feature.chroma_stft(S=spectrum ** 2, sr=SAMPLE_RATE, tuning=0)
    result["chroma_mean"] = [float(value) for value in np.mean(chroma, axis=1)]
    return validate_features(result)
