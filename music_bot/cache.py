import asyncio
import hashlib
import json
import weakref
from dataclasses import asdict
from datetime import timedelta

from sqlalchemy.dialects.sqlite import insert

from .matching import decode_track, encode_track
from .models import ProviderCache, normalize_name, utc_now
from .providers.common import Failure, ProviderError, Tag, TrackCandidate

LONG_TTL = timedelta(days=7)
SIMILAR_TTL = timedelta(days=1)
SEARCH_TTL = timedelta(minutes=15)
NEGATIVE_TTL = timedelta(minutes=5)
STALE_GRACE = timedelta(days=1)


def cache_key(provider: str, method: str, arguments: tuple[str, ...]) -> str:
    # Only provider, operation and music identity enter the hash; no credentials.
    return hashlib.sha256(json.dumps(
        [provider, method, *[normalize_name(value) for value in arguments]],
        ensure_ascii=False, separators=(",", ":"),
    ).encode()).hexdigest()


def encode(value):
    if value is None:
        return {"kind": "none"}
    if isinstance(value, TrackCandidate):
        return {"kind": "track", "data": encode_track(value)}
    if isinstance(value, tuple):
        return {"kind": "tags", "data": [asdict(tag) for tag in value]}
    return {"kind": "tracks", "data": [encode_track(track) for track in value]}


def decode(payload):
    match payload["kind"]:
        case "none":
            return None
        case "track":
            return decode_track(payload["data"])
        case "tags":
            return tuple(Tag(**tag) for tag in payload["data"])
        case "tracks":
            return [decode_track(track) for track in payload["data"]]


class CachedProviders:
    def __init__(self, database, lastfm, musicbrainz):
        self.database = database
        self.lastfm = lastfm
        self.musicbrainz = musicbrainz
        self._locks = weakref.WeakValueDictionary()

    async def call(self, provider: str, method: str, *arguments: str):
        key = cache_key(provider, method, arguments)
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            async with self.database.sessions() as session:
                cached = await session.get(ProviderCache, key)
            now = utc_now()
            if cached and cached.expires_at > now:
                return decode(cached.payload)
            client = self.lastfm if provider == "lastfm" else self.musicbrainz
            try:
                async with asyncio.timeout(8):
                    value = await getattr(client, method)(*arguments)
            except (ProviderError, TimeoutError) as error:
                temporary = isinstance(error, TimeoutError) or error.reason in (
                    Failure.NETWORK, Failure.RATE_LIMIT, Failure.UNAVAILABLE,
                )
                # Bounded stale positive metadata is usable during outages.
                if temporary and cached and cached.expires_at + STALE_GRACE > now:
                    fallback = decode(cached.payload)
                    if fallback:
                        return fallback
                if isinstance(error, TimeoutError):
                    raise ProviderError(Failure.NETWORK) from None
                raise
            ttl = SIMILAR_TTL if method == "get_similar_tracks" else LONG_TTL
            if method.startswith("search"):
                ttl = SEARCH_TTL
            if not value:
                ttl = NEGATIVE_TTL
            record = dict(provider=provider, method=method, payload=encode(value),
                          retrieved_at=now, expires_at=now + ttl)
            async with self.database.sessions.begin() as session:
                await session.execute(insert(ProviderCache).values(key=key, **record)
                                      .on_conflict_do_update(index_elements=[ProviderCache.key], set_=record))
            return value
