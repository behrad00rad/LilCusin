"""Anonymous catalogue metadata only; never request previews or audio."""
import asyncio

from .common import Failure, ProviderError, TrackCandidate, items, number, request_json, text
from ..matching import match_text
from .musicbrainz import RateLimiter


def normalize_track(raw):
    artist = raw.get('artist') if isinstance(raw.get('artist'), dict) else {}
    album = raw.get('album') if isinstance(raw.get('album'), dict) else {}
    identifier = raw.get('id')
    rank = number(raw.get('rank'))
    return TrackCandidate(
        artist=text(artist.get('name')), title=text(raw.get('title')), source='deezer',
        album=text(album.get('title')), duration=number(raw.get('duration')),
        external_ids={'deezer': str(identifier)} if isinstance(identifier, int) and not isinstance(identifier, bool) and identifier > 0 else {},
        deezer_rank=min(rank, 1_000_000) if rank is not None else None,
    )


class DeezerClient:
    def __init__(self, session):
        self.session = session
        self.limiter = RateLimiter()

    async def _search(self, query):
        async with self.limiter:
            payload = await request_json(self.session, 'https://api.deezer.com/search',
                                         params={'q': query, 'limit': 100, 'order': 'RANKING'})
        if 'error' in payload:
            raise ProviderError(Failure.UNAVAILABLE)
        if not isinstance(payload.get('data'), list):
            raise ProviderError(Failure.INVALID_RESPONSE)
        return [normalize_track(row) for row in items(payload['data'])[:100]]

    async def search_tracks(self, artist, title):
        return await self._search(artist + ' ' + title)

    async def search_titles(self, title):
        rows = await self._search(title)
        wanted = match_text(title)
        # A short prefix can hide covers under the full catalogue title. Expand
        # at most one popular completion, without any hard-coded song or artist.
        completions = [row for row in rows if row.title and match_text(row.title).startswith(wanted)
                       and len(wanted.split()) >= 2
                       and len(match_text(row.title).split()) >= len(wanted.split()) + 3]
        if completions:
            best = max(completions, key=lambda row: row.deezer_rank or 0)
            try:
                async with asyncio.timeout(3):
                    rows += await self._search(match_text(best.title))
            except (ProviderError, TimeoutError):
                pass  # Completion failure must preserve the initial catalogue results.
        return rows
