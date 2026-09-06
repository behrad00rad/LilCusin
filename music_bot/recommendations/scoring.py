"""Pure, explainable scoring. Missing optional signals leave the denominator."""

import math
import random
from collections import Counter

from .. import messages
from ..matching import comparison_text
from . import settings as S
from .types import Item, Ranked, Seed


def seed_weight(seed):
    return S.SELECTED_SEED_WEIGHT if seed.rating is None else S.RATING_WEIGHTS[seed.rating]


def clamp(value, default=None):
    if isinstance(value, bool):
        return default
    try:
        value = float(value)
        return min(1.0, max(0.0, value)) if math.isfinite(value) else default
    except (TypeError, ValueError):
        return default


def tag_weight(value):
    try:
        return clamp(float(value) / S.TAG_WEIGHT_SCALE, S.UNKNOWN_TAG_WEIGHT)
    except (TypeError, ValueError):
        return S.UNKNOWN_TAG_WEIGHT


def tag_overlap(left, right):
    if not left or not right:
        return None
    names = left.keys() | right.keys()
    denominator = sum(max(left.get(name, 0), right.get(name, 0)) for name in names)
    return sum(min(left.get(name, 0), right.get(name, 0)) for name in names) / denominator if denominator else None


def relative_similarity(left, right):
    if not all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) and x >= 0 for x in (left, right)):
        return None
    return 1.0 - abs(left - right) / max(left, right) if max(left, right) else 1.0


def weighted_available(values, weights):
    present = {name: value for name, value in values.items() if value is not None}
    denominator = sum(weights[name] for name in present)
    return sum(weights[name] * value for name, value in present.items()) / denominator if denominator else None


def audio_similarity(left: Item, right: Item):
    compatible = sorted(left.analyses.keys() & right.analyses.keys())
    if not compatible:
        return None, False
    # A single compatible version per comparison; never mix analyzer versions.
    a, b = left.analyses[compatible[-1]], right.analyses[compatible[-1]]
    bpm_a, bpm_b = a.get("bpm"), b.get("bpm")
    tempo = None
    if relative_similarity(bpm_a, bpm_b) is not None and bpm_a > 0 and bpm_b > 0:
        tempo = math.exp(-abs(math.log2(bpm_a / bpm_b)) / S.BPM_OCTAVE_DECAY)
    spectral = [relative_similarity(a.get(name), b.get(name)) for name in
                ("spectral_centroid_mean", "spectral_bandwidth_mean", "spectral_rolloff_mean", "zero_crossing_rate_mean")]
    spectral = [value for value in spectral if value is not None]
    chroma = None
    x, y = a.get("chroma_mean"), b.get("chroma_mean")
    if isinstance(x, list) and isinstance(y, list) and len(x) == len(y) == 12:
        if all(relative_similarity(u, v) is not None for u, v in zip(x, y)):
            denominator = math.sqrt(sum(u*u for u in x) * sum(v*v for v in y))
            if denominator:
                chroma = clamp(sum(u*v for u, v in zip(x, y)) / denominator)
    values = {"bpm": tempo, "spectral": sum(spectral) / len(spectral) if spectral else None,
              "rms": relative_similarity(a.get("rms_mean"), b.get("rms_mean")), "chroma": chroma}
    return weighted_available(values, S.AUDIO_WEIGHTS), tempo is not None and tempo >= S.NEGATIVE_AUDIO_THRESHOLD


def evidence(seed: Seed, candidate: Item, related_artists):
    artist = None
    if seed.item.metadata.artist and candidate.metadata.artist:
        a, b = comparison_text(seed.item.metadata.artist), comparison_text(candidate.metadata.artist)
        artist = 1.0 if a == b else related_artists.get((seed.item.track_id, b), 0.0) * S.RELATED_ARTIST_WEIGHT
    audio, close_tempo = audio_similarity(seed.item, candidate)
    values = {"lastfm": clamp(candidate.links.get(seed.item.track_id)),
              "tags": tag_overlap(seed.item.tags, candidate.tags), "artist": artist, "audio": audio}
    return weighted_available(values, S.SIGNAL_WEIGHTS) or 0.0, values, close_tempo


def rank_candidate(candidate, profile, related_artists, now):
    shown = profile.history.get(candidate.track_id)
    dates = [profile.history_aliases[key] for key in candidate.identities if key in profile.history_aliases]
    if dates:
        shown = max(dates + ([shown] if shown else []))
    if shown and shown > now - S.HISTORY_COOLDOWN:
        return None
    evidence_rows = []
    for seed in profile.positives:
        affinity, values, tempo = evidence(seed, candidate, related_artists)
        weighted = affinity * seed_weight(seed) / S.RATING_WEIGHTS["love"]
        evidence_rows.append((weighted, seed, affinity, values, tempo))
    evidence_rows.sort(key=lambda row: (-row[0], row[1].item.track_id))
    best, seed, affinity, signals, tempo = evidence_rows[0]
    if best <= 0:
        return None
    score = min(1.0, best + S.SUPPORT_BONUS * sum(row[0] for row in evidence_rows[1:3]))
    negatives = []
    for negative in profile.negatives:
        value, signals_negative, _ = evidence(negative, candidate, related_artists)
        tags = signals_negative["tags"] or 0
        overlap_count = len(negative.item.tags.keys() & candidate.tags.keys())
        close = ((signals_negative["lastfm"] or 0) >= S.NEGATIVE_LASTFM_THRESHOLD
                 or (tags >= S.NEGATIVE_TAG_THRESHOLD and overlap_count >= 2)
                 or ((signals_negative["audio"] or 0) >= S.NEGATIVE_AUDIO_THRESHOLD and tags >= S.NEGATIVE_AUDIO_TAG_THRESHOLD))
        if close:
            negatives.append(value * abs(S.RATING_WEIGHTS[negative.rating]))
    negatives.sort(reverse=True)
    if negatives:
        penalty = min(S.MAX_NEGATIVE_PENALTY, S.NEGATIVE_FIRST * negatives[0]
                      + S.NEGATIVE_ADDITIONAL * sum(negatives[1:3]))
        score *= 1 - penalty
    if shown and shown > now - S.HISTORY_WINDOW:
        score *= S.HISTORY_MULTIPLIER
    similar = signals["lastfm"]
    if similar is not None and similar > 0:
        reason = messages.REC_SIMILAR_LOVE if seed.rating == "love" else messages.REC_SIMILAR_LIKE
    elif sum(row[4] and (row[3]["tags"] or 0) > 0 for row in evidence_rows) >= 2:
        reason = messages.REC_TEMPO_TAGS
    elif len(seed.item.tags.keys() & candidate.tags.keys()) >= 2:
        reason = messages.REC_TAGS
    elif tempo:
        reason = messages.REC_TEMPO
    elif signals["audio"] is not None and signals["audio"] > 0:
        reason = messages.REC_AUDIO
    elif signals["artist"] == 1:
        reason = messages.REC_ARTIST
    elif (signals["artist"] or 0) > 0:
        reason = messages.REC_RELATED_ARTIST
    else:
        reason = messages.REC_SHARED_TAG
    if seed.rating is None:
        reason = messages.REC_SELECTED_REASONS[reason]
    return Ranked(candidate, score, reason, seed.item.track_id, affinity)


def select_varied(ranked, limit, random_seed=None):
    rng = random.Random(random_seed)
    pool = sorted(ranked, key=lambda row: (-row.score, comparison_text(row.item.metadata.artist), comparison_text(row.item.metadata.title)))
    exploration_count = int(limit * S.EXPLORATION_FRACTION + 0.5)
    core_count = min(len(pool), limit - exploration_count)
    chosen, seeds, artists = [], Counter(), Counter()

    def variety(row):
        artist = comparison_text(row.item.metadata.artist)
        return row.score / (1 + S.SEED_VARIETY_PENALTY * seeds[row.seed_id]) / (1 + S.ARTIST_VARIETY_PENALTY * artists[artist])

    def take(row, exploration=False):
        row.exploration = exploration
        chosen.append(row)
        seeds[row.seed_id] += 1
        artists[comparison_text(row.item.metadata.artist)] += 1
        pool.remove(row)

    for _ in range(core_count):
        take(max(pool, key=variety))
    while pool and len(chosen) < limit:
        relevant = [row for row in pool if row.affinity >= S.EXPLORATION_MIN_AFFINITY and row.score >= S.EXPLORATION_MIN_SCORE]
        if relevant and sum(row.exploration for row in chosen) < exploration_count:
            weights = [variety(row) * (1 + S.EXPLORATION_NEW_ARTIST_BONUS * (artists[comparison_text(row.item.metadata.artist)] == 0)) for row in relevant]
            take(rng.choices(relevant, weights=weights, k=1)[0], True)
        else:
            take(max(pool, key=variety))
    return chosen
