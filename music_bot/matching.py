"""Explainable identity comparison, independent of provider HTTP and Telegram."""

import hashlib
import json
import re
import unicodedata
from dataclasses import asdict, replace
from difflib import SequenceMatcher
from urllib.parse import unquote_plus, urlsplit

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


def match_text(value: str) -> str:
    # Apostrophes vary between tags and catalogue spellings (Don't / Dont).
    # Keep this comparison-only; persisted identity keys remain unchanged.
    value = re.sub(r"[’'ʼ`]+", '', value)
    value = re.sub(r'\b\d{4}\s+(?=remaster)', '', value, flags=re.IGNORECASE)
    return comparison_text(value)


def remove_reversed_candidates(candidates):
    """Prefer structured catalogues over reversed scrobble/video identities."""
    trusted = {(match_text(c.artist), match_text(c.title)) for c in candidates
               if c.artist and c.title and c.source in {'musicbrainz', 'deezer', 'itunes', 'user_corrected'}}
    return [c for c in candidates if not (c.artist and c.title
            and c.source in {'lastfm', 'youtube'}
            and (match_text(c.title), match_text(c.artist)) in trusted
            and match_text(c.title) != match_text(c.artist))]


def title_query_match(query: str, title: str, *, exact=False) -> bool:
    """Search-only equivalence for catalogue censorship; never an identity key."""
    wanted, actual = match_text(query), match_text(title)
    if wanted and (wanted == actual if exact else wanted in actual):
        return True
    marker = '\ue000'
    left = match_text(query.replace('*', marker)).split()
    right = match_text(title.replace('*', marker)).split()
    if not left or (exact and len(left) != len(right)) or len(left) > len(right):
        return False
    def word_match(a, b):
        if a == b:
            return True
        if marker in a and marker in b:
            return False
        masked, plain = (a, b) if marker in a else (b, a)
        if marker not in masked or len(masked.replace(marker, '')) < 2:
            return False
        pattern = re.sub(marker + '+', lambda _: r'[^\W_]{1,8}', re.escape(masked))
        return re.fullmatch(pattern, plain) is not None
    return any(all(word_match(a, b) for a, b in zip(left, right[start:start + len(left)]))
               for start in range(len(right) - len(left) + 1))


def search_text_match(query: str, value: str, *, exact=False) -> bool:
    """Discovery-only prefix/one-edit matching, never automatic confirmation."""
    left, right = match_text(query).split(), match_text(value).split()
    if not left or len(left) > len(right) or exact and len(left) != len(right):
        return False
    def close(a, b):
        if a == b or not exact and len(a) >= 3 and b.startswith(a):
            return True
        if min(len(a), len(b)) < 4 or abs(len(a) - len(b)) > 1:
            return False
        if len(a) == len(b):
            changes = [i for i in range(len(a)) if a[i] != b[i]]
            return len(changes) == 1 or (len(changes) == 2 and changes[1] == changes[0] + 1
                and a[changes[0]] == b[changes[1]] and a[changes[1]] == b[changes[0]])
        shorter, longer = (a, b) if len(a) < len(b) else (b, a)
        return any(longer[:i] + longer[i + 1:] == shorter for i in range(len(longer)))
    return any(all(close(a, b) for a, b in zip(left, right[start:start + len(left)]))
               for start in range(len(right) - len(left) + 1))


def search_query_matches_song(query: str, artist: str, title: str) -> bool:
    if title_query_match(query, title) or search_text_match(query, title):
        return True
    words = query.split()
    for boundary in range(1, min(len(words), 4)):
        song, performer = ' '.join(words[:boundary]), ' '.join(words[boundary:])
        performer = re.sub(r'^by\s+', '', performer, flags=re.I)
        if ((title_query_match(song, title, exact=True) or search_text_match(song, title, exact=True))
                and search_text_match(performer, artist)):
            return True
    return False


def identifier_key(provider: str, value: str):
    """Last.fm song URLs can differ only in typography or URL encoding."""
    if provider == 'lastfm':
        try:
            url = urlsplit(value)
            parts = url.path.strip('/').split('/')
            if (url.scheme in {'http', 'https'} and url.hostname in {'last.fm', 'www.last.fm'}
                    and not url.username and not url.password and not url.query and not url.fragment
                    and len(parts) == 4 and parts[0] == 'music' and parts[2] == '_'):
                return ('lastfm_song', match_text(unquote_plus(parts[1])), match_text(unquote_plus(parts[3])))
        except ValueError:
            pass
    return value


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
        "artist_aliases": tuple(data.get('artist_aliases', ())),
    })


def similarities(artist: str, title: str, candidate: TrackCandidate) -> tuple[float, float]:
    direct = tuple(
        SequenceMatcher(None, match_text(left), match_text(right or "")).ratio()
        for left, right in ((artist, candidate.artist), (title, candidate.title))
    )
    swapped = tuple(
        SequenceMatcher(None, match_text(left), match_text(right or "")).ratio()
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
                p in existing.external_ids and identifier_key(p, existing.external_ids[p]) != identifier_key(p, value)
                for p, value in candidate.external_ids.items() if p in {"musicbrainz", "lastfm"}
            )
            same_name = (match_text(existing.artist), match_text(existing.title)) == (match_text(candidate.artist), match_text(candidate.title))
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
    # For non-exact matches, validate that metadata is not incomplete.
    # Exact matches bypass this check to avoid false rejections from normalization differences.
    if not (a == 1 and t == 1) and not all(comparison_text(value or '') for value in (artist, title, best.artist, best.title)):
        return False, "incomplete_metadata", (a, t, 0, 0)
    score = confidence(artist, title, best)
    margin = score - confidence(artist, title, candidates[1]) if len(candidates) > 1 else 1
    same_identity = [candidate for candidate in candidates[1:]
                     if (match_text(best.artist), match_text(best.title)) ==
                     (match_text(candidate.artist or ''), match_text(candidate.title or ''))]
    conflict = any(best.external_ids.get(provider) and candidate.external_ids.get(provider)
                   and identifier_key(provider, candidate.external_ids[provider]) != identifier_key(provider, best.external_ids[provider])
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
