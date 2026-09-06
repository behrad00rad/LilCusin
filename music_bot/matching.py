"""Explainable identity comparison, independent of provider HTTP and Telegram."""

import hashlib
import json
import re
import unicodedata
from dataclasses import asdict, replace
from difflib import SequenceMatcher

from .providers.common import Release, Tag, TrackCandidate

AUTO_CONFIRM_ARTIST_THRESHOLD = 0.90
AUTO_CONFIRM_TITLE_THRESHOLD = 0.90
AUTO_CONFIRM_COMBINED_THRESHOLD = 0.90
AUTO_CONFIRM_LEAD_THRESHOLD = 0.08

_NOISE = re.compile(
    r"\b(?:official\s+(?:audio|video)|lyrics?|lyric\s+video|remaster(?:ed)?(?:\s+\d{4})?|"
    r"\d{2,4}\s*kbps|www\.[^\s]+|https?://[^\s]+)\b", re.IGNORECASE,
)
_FILE_EXTENSION = re.compile(r"\.(?:mp3|m4a|aac|flac|wav|ogg|opus|wma)\s*$", re.IGNORECASE)


def comparison_text(value: str) -> str:
    value = _FILE_EXTENSION.sub("", unicodedata.normalize("NFKC", value)).casefold()
    value = value.translate(str.maketrans({"ي": "ی", "ى": "ی", "ك": "ک", "ـ": ""}))
    value = _NOISE.sub(" ", value)
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
    direct = tuple(
        SequenceMatcher(None, comparison_text(left), comparison_text(right or "")).ratio()
        for left, right in ((artist, candidate.artist), (title, candidate.title))
    )
    swapped = tuple(
        SequenceMatcher(None, comparison_text(left), comparison_text(right or "")).ratio()
        for left, right in ((title, candidate.artist), (artist, candidate.title))
    )
    return swapped if sum(swapped) > sum(direct) else direct


def confidence(artist: str, title: str, candidate: TrackCandidate) -> float:
    a, t = similarities(artist, title, candidate)
    # Provider scores can reflect relevance/popularity rather than identity.
    return (a + t) / 2


def deduplicate(candidates: list[TrackCandidate]) -> list[TrackCandidate]:
    result = []
    for candidate in candidates:
        if not candidate.artist or not candidate.title:
            continue
        for index, existing in enumerate(result):
            same_id = any(existing.external_ids.get(p) == value for p, value in candidate.external_ids.items())
            conflicting_id = any(
                p in existing.external_ids and existing.external_ids[p] != value
                for p, value in candidate.external_ids.items() if p in {"musicbrainz", "lastfm"}
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


def match_decision(artist: str, title: str, candidates: list[TrackCandidate]) -> tuple[bool, str, tuple[float, float, float, float]]:
    if not candidates:
        return False, "no_candidate", (0, 0, 0, 0)
    best = candidates[0]
    a, t = similarities(artist, title, best)
    if not all(comparison_text(value or '') for value in (artist, title, best.artist, best.title)):
        return False, "incomplete_metadata", (a, t, 0, 0)
    score = confidence(artist, title, best)
    margin = score - confidence(artist, title, candidates[1]) if len(candidates) > 1 else 1
    same_identity = [candidate for candidate in candidates[1:]
                     if identity_key(best.artist, best.title) == identity_key(candidate.artist or "", candidate.title or "")]
    conflict = any(best.external_ids.get(provider) and candidate.external_ids.get(provider)
                   and candidate.external_ids[provider] != best.external_ids[provider]
                   for candidate in same_identity for provider in ("musicbrainz", "lastfm"))
    metrics = (a, t, score, margin)
    if conflict:
        return False, "external_id_conflict", metrics
    if a == 1 and t == 1:
        return True, "exact_names", metrics
    if a >= AUTO_CONFIRM_ARTIST_THRESHOLD and t >= AUTO_CONFIRM_TITLE_THRESHOLD:
        return (margin >= AUTO_CONFIRM_LEAD_THRESHOLD,
                "both_names" if margin >= AUTO_CONFIRM_LEAD_THRESHOLD else "ambiguous", metrics)
    if score >= AUTO_CONFIRM_COMBINED_THRESHOLD and margin >= AUTO_CONFIRM_LEAD_THRESHOLD:
        return True, "combined_confidence", metrics
    return False, "below_threshold" if score < AUTO_CONFIRM_COMBINED_THRESHOLD else "ambiguous", metrics


def strong_match(artist: str, title: str, candidates: list[TrackCandidate]) -> bool:
    return match_decision(artist, title, candidates)[0]
