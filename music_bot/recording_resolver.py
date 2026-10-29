"""Bounded catalogue-to-recording resolution using the shared chat discovery client."""
import asyncio
import json
import math
import re
from difflib import SequenceMatcher
from time import monotonic
from types import SimpleNamespace as NS

import aiohttp
from .matching import match_text
from .providers.common import request_json
from .providers.musicbrainz import shared_limiter, quoted_query, USER_AGENT
from .youtube_fetch import FetchError, VIDEO, artist_key, version_words, without_artist_credit


def valid_duration(value, maximum=900):
    # Unknown metadata is preferable to inventing a unit conversion.
    return value if (not isinstance(value, bool) and isinstance(value, (int, float))
                     and math.isfinite(value) and 1 <= value <= maximum) else None


def title_key(title, artist):
    title = without_artist_credit(title, artist)
    title = title.split('|', 1)[0].strip()
    title = re.sub(r'\s*[(\[]\s*(?:official(?:\s+(?:music\s+)?(?:audio|video))?|audio|lyrics?|hd|hq)\s*[)\]]', '', title, flags=re.I)
    return match_text(title)


def title_agreement(wanted, found):
    if wanted == found:
        return 2
    # Transliteration is only a candidate hint after an independently trusted artist match.
    if not re.fullmatch(r'[a-z ]+', wanted) or not re.fullmatch(r'[a-z ]+', found):
        return 0
    consonants = lambda value: re.sub(r'[aeiou ]', '', value)
    skeleton = consonants(wanted)
    return int(len(skeleton) >= 4 and skeleton == consonants(found)
               and SequenceMatcher(None, wanted, found).ratio() >= .65)


def artist_aliases(payload, artist):
    """One exact MusicBrainz artist entity; ambiguous/fuzzy search hits grant nothing."""
    matches = {}
    for entity in payload.get('artists', []):
        if not isinstance(entity, dict):
            continue
        names = [entity.get('name'), entity.get('sort-name')]
        names += [row.get('name') for row in entity.get('aliases', []) if isinstance(row, dict)]
        names = [name for name in names if isinstance(name, str) and name.strip()]
        identifier = entity.get('id')
        if (isinstance(identifier, str) and re.fullmatch(r'[a-fA-F0-9-]{36}', identifier)
                and any(artist_key(name) == artist_key(artist) for name in names)):
            matches.setdefault(identifier, set()).update(names)
    return sorted(next(iter(matches.values())))[:12] if len(matches) == 1 else []


def recording_aliases(payload, artist, titles):
    """A catalogue recording credit can bind a short artist name to its full entity."""
    wanted = {match_text(title) for title in titles}
    entities = []
    for row in payload.get('recordings', []):
        credits = row.get('artist-credit', []) if isinstance(row, dict) else []
        if match_text(row.get('title') or '') not in wanted or len(credits) != 1:
            continue
        credit = credits[0]
        if not isinstance(credit, dict) or not isinstance(credit.get('artist'), dict):
            continue
        entity = credit['artist']
        entities.append({**entity, 'aliases': [*entity.get('aliases', []), {'name': credit.get('name')}]})
    return artist_aliases({'artists': entities}, artist)


class RecordingResolver:
    def __init__(self, discovery):
        self.discovery = discovery
        self.alias_cache = {}

    async def aliases(self, artist, titles=()):
        key = (artist_key(artist), tuple(sorted(match_text(title) for title in titles)))
        cached = self.alias_cache.get(key)
        if cached and cached[0] > monotonic():
            return cached[1]
        aliases = []
        try:
            async with asyncio.timeout(5), aiohttp.ClientSession(trust_env=False) as session:
                async with shared_limiter():
                    payload = await request_json(session, 'https://musicbrainz.org/ws/2/artist/',
                        params={'fmt': 'json', 'limit': 5,
                                'query': f'artist:{quoted_query(artist)} OR alias:{quoted_query(artist)}'},
                        headers={'User-Agent': USER_AGENT})
                aliases = artist_aliases(payload, artist)
                if not aliases and titles:
                    terms = ' OR '.join('recording:' + quoted_query(title) for title in titles[:3])
                    async with shared_limiter():
                        payload = await request_json(session, 'https://musicbrainz.org/ws/2/recording/',
                            params={'fmt': 'json', 'limit': 5,
                                    'query': f'artist:{quoted_query(artist)} AND ({terms})'},
                            headers={'User-Agent': USER_AGENT})
                    aliases = recording_aliases(payload, artist, titles)
        except Exception:
            pass
        if len(self.alias_cache) >= 128:
            self.alias_cache.pop(next(iter(self.alias_cache)))
        self.alias_cache[key] = (monotonic() + 300, aliases)
        return aliases

    def rank(self, track, entries, aliases, maximum, *, structured=False):
        artists = {artist_key(name) for name in [track.artist, *aliases]}
        wanted = title_key(track.title, track.artist)
        duration = valid_duration(track.duration, maximum)
        rows = []
        for entry in entries:
            artist = str(entry.get('artist') or '')
            title = str(entry.get('track') or '')
            seconds = valid_duration(entry.get('duration'), maximum)
            if (not VIDEO.fullmatch(str(entry.get('id', ''))) or entry.get('is_live')
                    or entry.get('live_status') in {'is_live', 'is_upcoming', 'was_live'}
                    or artist_key(artist) not in artists or not title or seconds is None
                    or version_words(str(entry.get('title') or title) + ' ' + str(entry.get('album') or '')) != version_words(track.title)):
                continue
            agreement = title_agreement(wanted, title_key(title, artist))
            if not agreement:
                continue
            mismatch = bool(duration and abs(duration-seconds) > max(12, duration * .08))
            if mismatch:
                continue
            # Rich artist/track fields alone are not proof of an original upload.
            original = structured or (str(entry.get('uploader') or '').endswith(' - Topic')
                and 'provided to youtube by' in str(entry.get('description') or '').casefold())
            if not original:
                continue
            rows.append(dict(id=entry['id'], title=title, artist=artist, duration=seconds,
                score=1 if agreement == 2 else .8, exact=bool(agreement == 2 and duration and abs(duration-seconds) <= 5),
                duration_mismatch=bool(duration and abs(duration-seconds) > 5),
                title_mismatch=agreement != 2, duration_unknown=duration is None,
                identity_title=title_key(title, artist), identity_artist='|'.join(artist_key(track.artist)),
                version=sorted(version_words(title)), recording_title=title,
                source_policy='catalogue-music-v1'))
        rows.sort(key=lambda row: (row['exact'], row['score']), reverse=True)
        return list({row['id']: row for row in rows}.values())[:3]

    async def resolve(self, original, fetcher, directory, alive):
        track = NS(artist=getattr(original, 'display_artist', None) or original.artist,
                   title=getattr(original, 'display_title', None) or original.title,
                   duration=original.duration)
        aliases, successful, accepted = [], False, []
        incomplete = False

        async def check():
            if not await alive():
                raise FetchError('Request cancelled.')

        def entries(rows):
            return [dict(id=row.external_ids['youtube'], artist=row.artist, track=row.title,
                         title=row.title, duration=row.duration, album=row.album) for row in rows]

        try:
            async with asyncio.timeout(16):
                await check()
                rows, failed = await self.discovery.search(track.artist + ' ' + track.title, music_only=True)
                successful = not failed
                incomplete |= failed
                accepted = self.rank(track, entries(rows), [], fetcher.settings.max_duration, structured=True)
                if accepted:
                    await check()
                    return accepted
                await check()
                matching_titles = list(dict.fromkeys(row.title for row in rows
                    if title_agreement(title_key(track.title, track.artist), title_key(row.title, row.artist))))[:3]
                aliases = await self.aliases(track.artist, matching_titles)
                accepted = self.rank(track, entries(rows), aliases, fetcher.settings.max_duration, structured=True)
                if accepted:
                    await check()
                    return accepted
                alternate = next((name for name in aliases if artist_key(name) != artist_key(track.artist)
                                  and ',' not in name), None)
                if alternate:
                    await check()
                    rows, failed = await self.discovery.search(alternate + ' ' + track.title, music_only=True)
                    successful |= not failed
                    incomplete |= failed
                    accepted = self.rank(track, entries(rows), aliases, fetcher.settings.max_duration, structured=True)
                    if accepted:
                        await check()
                        return accepted
                # One broad upload search; inspect relevant results BEFORE strict artist rejection.
                await check()
                try:
                    async with asyncio.timeout(3):
                        data = await fetcher.process(fetcher.base() + ['--flat-playlist', '--dump-single-json',
                            '--skip-download', '--', 'ytsearch12:' + track.artist + ' ' + track.title], directory, alive, output=True)
                    payload = json.loads(data)
                    if not isinstance(payload, dict) or not isinstance(payload.get('entries'), list):
                        raise ValueError('Invalid search response')
                    successful = True
                    details, attempts = [], 0
                    for raw in payload.get('entries', [])[:12]:
                        if not isinstance(raw, dict) or not VIDEO.fullmatch(str(raw.get('id', ''))):
                            continue
                        label = str(raw.get('title') or '')
                        stripped = re.split(r'\s+[-–—]\s+', label, maxsplit=1)[-1]
                        if (version_words(label) != version_words(track.title)
                                or not title_agreement(title_key(track.title, track.artist), title_key(stripped, track.artist))):
                            continue
                        await check()
                        attempts += 1
                        try:
                            async with asyncio.timeout(3):
                                detail = json.loads(await fetcher.process(fetcher.base() + ['--skip-download',
                                    '--dump-single-json', '--', 'https://www.youtube.com/watch?v=' + raw['id']],
                                    directory, alive, output=True))
                            if isinstance(detail, dict) and detail.get('id') == raw['id']:
                                details.append(detail)
                            else:
                                incomplete = True
                        except (FetchError, ValueError, TimeoutError):
                            incomplete = True
                        if attempts >= 2:
                            break
                    accepted = self.rank(track, details, aliases, fetcher.settings.max_duration)
                except (FetchError, ValueError, TypeError, TimeoutError):
                    incomplete = True
        except TimeoutError:
            incomplete = True
        await check()
        if not accepted and (not successful or incomplete):
            raise FetchError('Source search unavailable.')
        return accepted
