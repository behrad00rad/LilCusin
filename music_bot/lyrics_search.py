"""Phrase discovery returns catalogue identities, never lyrics or media.

YouTube search is a free, best-effort discovery index, not proof of a lyric
match. Every hint must survive independent catalogue matching and user choice.
"""
import asyncio
import hashlib
import json
import os
import re
import tempfile
import weakref
from collections import OrderedDict
from dataclasses import dataclass, field
from time import monotonic
from types import SimpleNamespace

from .config import ConfigError
from .matching import match_text, similarities
from .providers.common import Failure, ProviderError, items, request_json, text
from .youtube_fetch import FetchError, YouTubeFetcher


@dataclass(frozen=True)
class LyricsSettings:
    provider: str = 'youtube'
    api_key: str = field(default='', repr=False)

    @classmethod
    def environment(cls):
        provider = os.getenv('LYRICS_SEARCH_PROVIDER', 'youtube').strip().lower()
        key = os.getenv('MUSIXMATCH_API_KEY', '').strip()
        if provider not in {'youtube', 'musixmatch', 'off'}:
            raise ConfigError('LYRICS_SEARCH_PROVIDER must be youtube, musixmatch or off')
        if provider == 'musixmatch' and not key:
            raise ConfigError('Missing required environment variable: MUSIXMATCH_API_KEY')
        return cls(provider, key)


def needs_lyrics(query, candidates):
    """Avoid extra work for titles and title/artist combinations already found."""
    normalized = match_text(query)
    words = normalized.split()
    if not 3 <= len(words) <= 40 or len(query) > 240:
        return False
    for candidate in candidates:
        if not candidate.title or not candidate.artist:
            continue
        title_words = match_text(candidate.title).split()
        if normalized == match_text(candidate.title) and ((candidate.listeners or 0) >= 10000
                                                         or (candidate.deezer_rank or 0) >= 400000):
            return False
        # A successful title + artist hint should not trigger a phrase search.
        if (len(words) > len(title_words) and set(title_words) <= set(words)
                and set(words) <= set(match_text(candidate.title + ' ' + candidate.artist).split())):
            return False
    return True


def video_hints(entries):
    """Parse conventional video titles only; unstructured guesses are discarded."""
    result = []
    for entry in entries[:5]:
        if not isinstance(entry, dict):
            continue
        artist, title = text(entry.get('artist')), text(entry.get('track'))
        if artist and title:
            pairs = [(artist, title)]
        else:
            label = text(entry.get('title')) or ''
            label = re.sub(r'\s*[\[(](?:official\s+)?(?:lyrics?|lyric video|audio|music video|video|hd|4k)[\])]\s*', ' ', label, flags=re.I)
            label = re.sub(r'\s*\|\s*(?:lyrics?|official.*)$', '', label, flags=re.I)
            label = re.sub(r'\s+(?:(?:ll|\|\||\||[-+])\s*)?(?:lyrics?|lyric video)\s*$', '', label, flags=re.I)
            label = re.sub('[\U0001f3b5\U0001f3b6]', '', label).strip()
            parts = re.split(r'\s+[–—-]\s+', label, maxsplit=1)
            # Both conventions exist. Catalogue validation, not word order, decides.
            pairs = [(parts[0], parts[1]), (parts[1], parts[0])] if len(parts) == 2 else []
        for artist, title in pairs:
            pair = (artist.strip(), title.strip())
            if (all(1 < len(value) <= 160 and match_text(value) for value in pair)
                    and tuple(map(match_text, pair)) not in {tuple(map(match_text, p)) for p in result}):
                result.append(pair)
            if len(result) == 3:
                return result
    return result


class LyricsSearch:
    def __init__(self, session, providers, settings=None, fetcher=None, clock=monotonic):
        self.session, self.providers = session, providers
        self.settings = settings or LyricsSettings()
        self.fetcher = fetcher or YouTubeFetcher(SimpleNamespace(timeout=12, disk_bytes=2_000_000))
        self.clock = clock
        self.cache = OrderedDict()
        self.locks = weakref.WeakValueDictionary()
        self.capacity = asyncio.Semaphore(2)
        self.retry_after = 0

    def clear(self):
        self.cache.clear()

    async def discover(self, phrase):
        if self.settings.provider == 'musixmatch':
            payload = await request_json(self.session, 'https://api.musixmatch.com/ws/1.1/track.search', params={
                'apikey': self.settings.api_key, 'q_lyrics': phrase,
                'page_size': 3, 's_track_rating': 'desc', 'format': 'json',
            })
            message = payload.get('message', {})
            if not isinstance(message, dict) or not isinstance(message.get('header'), dict):
                raise ProviderError(Failure.INVALID_RESPONSE)
            status = message['header'].get('status_code')
            if status != 200:
                raise ProviderError(Failure.AUTH if status in (401, 403) else Failure.UNAVAILABLE)
            body = message.get('body')
            if not isinstance(body, dict):
                raise ProviderError(Failure.INVALID_RESPONSE)
            return [(row['track']['artist_name'], row['track']['track_name'])
                    for row in items(body.get('track_list'))[:3]
                    if isinstance(row.get('track'), dict)
                    and text(row['track'].get('artist_name')) and text(row['track'].get('track_name'))]
        async def alive():
            return True
        with tempfile.TemporaryDirectory(prefix='lilcusin-lyrics-') as directory:
            data = await self.fetcher.process(self.fetcher.base() + [
                '--flat-playlist', '--dump-single-json', '--skip-download', '--',
                'ytsearch5:' + ' '.join(phrase.split()) + ' lyrics',
            ], directory, alive, output=True)
            payload = json.loads(data)
            if not isinstance(payload, dict) or not isinstance(payload.get('entries'), list):
                raise ProviderError(Failure.INVALID_RESPONSE)
            return video_hints(payload['entries'])

    async def search(self, phrase):
        if self.settings.provider == 'off' or not needs_lyrics(phrase, []):
            return [], False
        key = hashlib.sha256(match_text(phrase).encode()).hexdigest()
        lock = self.locks.setdefault(key, asyncio.Lock())
        async with lock:
            now = self.clock()
            cached = self.cache.get(key)
            if cached and cached[0] > now:
                self.cache.move_to_end(key)
                return list(cached[1]), False
            if now < self.retry_after or self.capacity.locked():
                return [], True
            try:
                async with self.capacity, asyncio.timeout(22):
                    hints = await self.discover(phrase)
                    calls = [(artist, title, provider, method)
                             for artist, title in hints[:3]
                             for provider, method in [('lastfm', 'search_tracks'), ('musicbrainz', 'search_recordings')]]
                    results = await asyncio.gather(*[
                        self.providers.call(provider, method, artist, title)
                        for artist, title, provider, method in calls
                    ], return_exceptions=True)
                    matches, seen, available = [], set(), not hints
                    for (artist, title, _, _), result in zip(calls, results):
                        if isinstance(result, ProviderError):
                            continue
                        if isinstance(result, BaseException):
                            raise result
                        available = True
                        for candidate in result:
                            if not candidate.artist or not candidate.title or min(similarities(artist, title, candidate)) < .85:
                                continue
                            if match_text(candidate.title) != match_text(title):
                                continue
                            # Some social catalogues also index video-upload labels.
                            if (re.search(r'\b(?:lyrics?|official)\b', candidate.title, re.I)
                                    and not re.search(r'\b(?:lyrics?|official)\b', title, re.I)):
                                continue
                            if (self.settings.provider == 'youtube' and candidate.source == 'lastfm'
                                    and (candidate.listeners or 0) < 1000):
                                # Last.fm also contains user-scrobbled upload labels and
                                # inverted credits. Prefer MusicBrainz for obscure hints.
                                continue
                            identity = (match_text(candidate.artist), match_text(candidate.title))
                            if identity not in seen:
                                matches.append(candidate)
                                seen.add(identity)
                    if not available:
                        raise ProviderError(Failure.UNAVAILABLE)
            except (ProviderError, FetchError, TimeoutError, OSError, ValueError, TypeError):
                self.retry_after = self.clock() + 60
                return [], True
            # No phrase, snippet, video response, user ID or lyrics persisted.
            self.cache[key] = (self.clock() + (900 if matches else 60), tuple(matches[:10]))
            self.cache.move_to_end(key)
            while len(self.cache) > 128:
                self.cache.popitem(last=False)
            return matches[:10], False
