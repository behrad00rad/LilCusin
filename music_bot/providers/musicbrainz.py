import asyncio
import re
import time
import weakref

import aiohttp

from .common import Failure, ProviderError, Release, TrackCandidate, items, number, request_json, text

API_URL = "https://musicbrainz.org/ws/2/recording/"
USER_AGENT = "LilRecommenderBro/0.1 (https://github.com/behrad00rad/LilRecommenderBro)"


class RateLimiter:
    """Serialize requests and leave at least one second between their starts."""

    def __init__(self, clock=time.monotonic, sleep=asyncio.sleep):
        self.clock = clock
        self.sleep = sleep
        self.lock = asyncio.Lock()
        self.next_request = 0.0

    async def __aenter__(self):
        await self.lock.acquire()
        try:
            delay = self.next_request - self.clock()
            if delay > 0:
                await self.sleep(delay)
            self.next_request = self.clock() + 1.0
        except BaseException:
            self.lock.release()
            raise

    async def __aexit__(self, *args):
        self.lock.release()


# All clients in the application's event loop share the limit, including lookup.
_limiters = weakref.WeakKeyDictionary()


def shared_limiter() -> RateLimiter:
    loop = asyncio.get_running_loop()
    if loop not in _limiters:
        _limiters[loop] = RateLimiter()
    return _limiters[loop]


def normalize_recording(raw: dict) -> TrackCandidate:
    credits = items(raw.get("artist-credit"))
    artist_parts = []
    for credit in credits:
        artist = credit.get("artist")
        artist = artist if isinstance(artist, dict) else {}
        name = text(credit.get("name")) or text(artist.get("name"))
        if name:
            joinphrase = credit.get("joinphrase")
            artist_parts.append(name + (joinphrase if isinstance(joinphrase, str) else ""))
    releases = items(raw.get("releases"))
    length = number(raw.get("length"))
    mbid = text(raw.get("id"))
    return TrackCandidate(
        title=text(raw.get("title")), artist=text("".join(artist_parts)),
        source="musicbrainz", album=text(releases[0].get("title")) if releases else None,
        duration=length / 1000 if length else None,
        external_ids={"musicbrainz": mbid} if mbid else {}, score=number(raw.get("score")),
        releases=tuple(Release(text(item.get("title")), "musicbrainz", text(item.get("id")),
                               text(item.get("date")), text(item.get("country"))) for item in releases),
    )


def quoted_query(value: str) -> str:
    # Escape Lucene syntax so submitted names remain literal search text.
    return '"' + re.sub(r'([+\-!(){}\[\]^"~*?:\\/|&])', r'\\\1', value) + '"'


class MusicBrainzClient:
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session

    async def _request(self, suffix: str = "", **params) -> dict:
        async with shared_limiter():
            return await request_json(
                self.session, API_URL + suffix,
                params={"fmt": "json", **params}, headers={"User-Agent": USER_AGENT},
            )

    async def search_recordings(self, artist: str, title: str) -> list[TrackCandidate]:
        payload = await self._request(
            query=f"artist:{quoted_query(artist)} AND recording:{quoted_query(title)}", limit=5,
        )
        if "recordings" not in payload or not isinstance(payload["recordings"], list):
            raise ProviderError(Failure.INVALID_RESPONSE)
        return [normalize_recording(item) for item in items(payload["recordings"])]

    async def get_recording(self, recording_id: str) -> TrackCandidate:
        # Identifiers form a URL path; never allow arbitrary paths or query strings.
        if not re.fullmatch(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", recording_id):
            raise ProviderError(Failure.REQUEST)
        payload = await self._request(recording_id, inc="artists+releases")
        if not text(payload.get("id")) or not text(payload.get("title")):
            raise ProviderError(Failure.INVALID_RESPONSE)
        return normalize_recording(payload)
