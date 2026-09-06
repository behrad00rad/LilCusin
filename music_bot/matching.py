"""Explainable identity comparison, independent of provider HTTP and Telegram."""

import hashlib
import json
import unicodedata
from dataclasses import asdict, replace
from difflib import SequenceMatcher

from .providers.common import Release, Tag, TrackCandidate

AUTO_CONFIRM_ARTIST_THRESHOLD = 0.90
AUTO_CONFIRM_TITLE_THRESHOLD = 0.90
AUTO_CONFIRM_COMBINED_THRESHOLD = 0.90
AUTO_CONFIRM_LEAD_THRESHOLD = 0.08


def comparison_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    value = value.translate(str.maketrans({"ي": "ی", "ى": "ی", "ك": "ک", "ـ": ""}))
    value = "".join(
        " " if unicodedata.category(char)[0] in ("P", "Z") or char in "\u200c\u200d"
        else char for char in value if unicodedata.category(char) not in ("Mn", "Me")
    )
    return " ".join(value.split())


def identity_key(artist: str, title: str) -> str:
    return hashlib.sha256(json.dumps(
        [comparison_text(artist), comparison_text(title)], ensure_ascii=False,
    ).encode()).hexdigest()


def encode_track(track: TrackCandidate) -> dict:
    return asdict(track)


def decode_track(data: dict) -> TrackCandidate:
    return TrackCandidate(**{
        **data, "tags": tuple(Tag(**tag) for tag in data.get("tags", [])),
        "releases": tuple(Release(**release) for release in data.get("releases", [])),
    })


def similarities(artist: str, title: str, candidate: TrackCandidate) -> tuple[float, float]:
    return tuple(
        SequenceMatcher(None, comparison_text(left), comparison_text(right or "")).ratio()
        for left, right in ((artist, candidate.artist), (title, candidate.title))
    )


def confidence(artist: str, title: str, candidate: TrackCandidate) -> float:
    a, t = similarities(artist, title, candidate)
    relevance = 0.5
    if candidate.score is not None:
        relevance = min(1.0, candidate.score / 100 if candidate.source == "musicbrainz" else candidate.score)
    return 0.45 * a + 0.45 * t + 0.1 * relevance


def deduplicate(candidates: list[TrackCandidate]) -> list[TrackCandidate]:
    result = []
    for candidate in candidates:
        if not candidate.artist or not candidate.title:
            continue
        for index, existing in enumerate(result):
            same_id = any(existing.external_ids.get(p) == value for p, value in candidate.external_ids.items())
            conflicting_id = any(
                p in existing.external_ids and existing.external_ids[p] != value
                for p, value in candidate.external_ids.items() if p == "musicbrainz"
            )
            same_name = identity_key(existing.artist, existing.title) == identity_key(candidate.artist, candidate.title)
            if not conflicting_id and (same_id or same_name):
                result[index] = replace(
                    existing, external_ids={**candidate.external_ids, **existing.external_ids},
                    album=existing.album or candidate.album,
                    duration=existing.duration or candidate.duration,
                    artwork_url=existing.artwork_url or candidate.artwork_url,
                    releases=tuple(dict.fromkeys((*existing.releases, *candidate.releases))),
                )
                break
        else:
            result.append(candidate)
    return result


def strong_match(artist: str, title: str, candidates: list[TrackCandidate]) -> bool:
    if not candidates:
        return False
    best = candidates[0]
    a, t = similarities(artist, title, best)
    if not best.artist or not best.title:
        return False
    score = confidence(artist, title, best)
    margin = score - confidence(artist, title, candidates[1]) if len(candidates) > 1 else 1
    if any(best.external_ids.get(provider) and any(
        candidate.external_ids.get(provider) and candidate.external_ids[provider] != best.external_ids[provider]
        for candidate in candidates[1:]) for provider in ("musicbrainz", "lastfm")):
        return False
    return (a >= AUTO_CONFIRM_ARTIST_THRESHOLD and t >= AUTO_CONFIRM_TITLE_THRESHOLD
            and score >= AUTO_CONFIRM_COMBINED_THRESHOLD and margin >= AUTO_CONFIRM_LEAD_THRESHOLD)
