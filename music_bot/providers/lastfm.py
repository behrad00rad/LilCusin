import aiohttp

from .common import (
    Failure, ProviderError, Release, Tag, TrackCandidate, items, number, request_json, text,
)

API_URL = "https://ws.audioscrobbler.com/2.0/"


def normalize_tags(raw: object) -> tuple[Tag, ...]:
    if isinstance(raw, list):
        raw = [item for item in raw if isinstance(item, dict)]
    return tuple(
        Tag(name, "lastfm", number(item.get("count")))
        for item in items(raw)
        if (name := text(item.get("name")))
    )


def normalize_track(raw: dict) -> TrackCandidate:
    artist = raw.get("artist")
    if isinstance(artist, dict):
        artist = artist.get("name")
    album = raw.get("album")
    album = album if isinstance(album, dict) else {}
    images = album.get("image", raw.get("image"))
    artwork = next(
        (url for item in reversed(items(images))
         if (url := text(item.get("#text"))) and url.startswith("https://")),
        None,
    )
    identifiers = {}
    if mbid := text(raw.get("mbid")):
        identifiers["musicbrainz"] = mbid
    if url := text(raw.get("url")):
        identifiers["lastfm"] = url
    duration = number(raw.get("duration"))
    tags = raw.get("toptags")
    return TrackCandidate(
        title=text(raw.get("name")), artist=text(artist), source="lastfm",
        album=text(album.get("title")), artwork_url=artwork,
        duration=duration / 1000 if duration else None,
        external_ids=identifiers,
        tags=normalize_tags(tags.get("tag")) if isinstance(tags, dict) else (),
        score=number(raw.get("match")),
        releases=(Release(text(album.get("title")), "lastfm", text(album.get("mbid"))),) if album else (),
    )


class LastFMClient:
    def __init__(self, session: aiohttp.ClientSession, api_key: str):
        self.session = session
        self._api_key = api_key

    async def _request(self, method: str, artist: str, title: str, **params) -> dict | None:
        if not artist.strip() or not title.strip():
            raise ProviderError(Failure.REQUEST)
        payload = await request_json(self.session, API_URL, params={
            "method": method, "api_key": self._api_key, "format": "json",
            "artist": artist, "track": title, **params,
        })
        if "error" in payload:
            code = number(payload["error"])
            # Distinguish a known not-found response from other invalid parameters.
            message = text(payload.get("message")) or ""
            if code == 6 and message.casefold().rstrip(".! ") == "track not found":
                return None
            reason = {
                10: Failure.AUTH, 26: Failure.AUTH, 29: Failure.RATE_LIMIT,
                11: Failure.UNAVAILABLE, 16: Failure.UNAVAILABLE,
            }.get(code, Failure.REQUEST)
            raise ProviderError(reason)
        return payload

    async def search_tracks(self, artist: str, title: str) -> list[TrackCandidate]:
        payload = await self._request("track.search", artist, title, limit=5)
        if payload is None:
            return []
        results = payload.get("results")
        if not isinstance(results, dict):
            raise ProviderError(Failure.INVALID_RESPONSE)
        matches = results.get("trackmatches")
        if matches == "" or matches == {}:
            return []
        if not isinstance(matches, dict) or "track" not in matches:
            raise ProviderError(Failure.INVALID_RESPONSE)
        return [normalize_track(track) for track in items(matches["track"])]

    async def get_track_info(self, artist: str, title: str) -> TrackCandidate | None:
        payload = await self._request("track.getInfo", artist, title, autocorrect=1)
        if payload is None:
            return None
        if "track" not in payload:
            raise ProviderError(Failure.INVALID_RESPONSE)
        if payload["track"] in (None, "", {}):
            return None
        if not isinstance(payload["track"], dict):
            raise ProviderError(Failure.INVALID_RESPONSE)
        return normalize_track(payload["track"])

    async def get_top_tags(self, artist: str, title: str) -> tuple[Tag, ...]:
        payload = await self._request("track.getTopTags", artist, title)
        if payload is None:
            return ()
        tags = payload.get("toptags")
        if not isinstance(tags, dict):
            raise ProviderError(Failure.INVALID_RESPONSE)
        return normalize_tags(tags.get("tag"))

    async def get_similar_tracks(self, artist: str, title: str) -> list[TrackCandidate]:
        payload = await self._request("track.getSimilar", artist, title, limit=5)
        if payload is None:
            return []
        similar = payload.get("similartracks")
        if not isinstance(similar, dict):
            raise ProviderError(Failure.INVALID_RESPONSE)
        return [normalize_track(track) for track in items(similar.get("track"))]
