"""Public recording discovery, independent of catalogue identity matching."""
import asyncio
from contextlib import suppress
from collections import OrderedDict
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import math
import re
import sys
from time import monotonic

from .providers.common import TrackCandidate
from .matching import match_text

VIDEO = re.compile(r'[A-Za-z0-9_-]{11}\Z')
MUSIC_SEARCH = r"""import json,sys,itertools,re
from ytmusicapi import YTMusic
client=YTMusic()
songs=client.search(sys.argv[1], filter='songs', limit=8, ignore_spelling=False)[:6]
videos=[] if len(sys.argv)>2 and sys.argv[2]=='songs' else client.search(sys.argv[1], filter='videos', limit=8, ignore_spelling=False)[:6]
# Include upload-only recordings even when an unrelated catalogue song matched.
video_first=bool(re.search(r'\b(live|concert|cover|unreleased|leak)\b|اجرای زنده|کاور',sys.argv[1],re.I))
groups=(videos,songs) if video_first else (songs,videos)
rows=[row for pair in itertools.zip_longest(*groups) for row in pair if row is not None]
print(json.dumps(rows, ensure_ascii=True))
"""


def recordings(entries, *, music=True, max_duration=900, limit=12):
    """Retain provider order and distinct recording IDs, without title vetoes."""
    rows, seen = [], set()
    if not isinstance(entries, list):
        return rows
    for item in entries[:60]:
        if not isinstance(item, dict):
            continue
        video = item.get('videoId' if music else 'id')
        if not isinstance(video, str) or not VIDEO.fullmatch(video) or video in seen:
            continue
        if (item.get('isAvailable') is False or item.get('is_live')
                or item.get('live_status') in {'is_live', 'is_upcoming'}):
            continue
        if music and item.get('resultType') not in {'song', 'video'}:
            continue
        duration = item.get('duration_seconds' if music else 'duration')
        if music and duration is None and isinstance(item.get('duration'), str):
            parts = item['duration'].split(':')
            if 1 <= len(parts) <= 3 and all(p.isdigit() for p in parts):
                duration = sum(int(p) * 60 ** i for i, p in enumerate(reversed(parts)))
        if (isinstance(duration, bool) or not isinstance(duration, (int, float))
                or not math.isfinite(duration) or not 0 < duration <= max_duration):
            continue
        title = item.get('title')
        artists = item.get('artists') or []
        if music and not isinstance(artists, list):
            continue
        artist = ', '.join(a['name'] for a in artists if isinstance(a, dict) and isinstance(a.get('name'), str)) if music else (
            item.get('artist') or item.get('uploader') or item.get('channel'))
        if not isinstance(title, str) or not title.strip() or not isinstance(artist, str) or not artist.strip():
            continue
        album = item.get('album')
        album = album.get('name') if isinstance(album, dict) and isinstance(album.get('name'), str) else None
        rows.append(TrackCandidate(title=title.strip()[:200], artist=artist.strip()[:150],
            source='youtube_music' if music and item.get('resultType') == 'song' else 'youtube_recording', album=album,
            duration=duration, external_ids={'youtube': video},
            recording_metadata={'raw_title':title.strip()[:200], 'channel':artist.strip()[:150]},
            youtube_views=item.get('view_count') if not music and type(item.get('view_count')) is int and item['view_count'] >= 0 else None))
        seen.add(video)
    return rows[:limit]


def recording_relevance(query, row):
    target = match_text(query)
    title = re.sub(r'\([^)]*\)|\[[^]]*\]', ' ', row.title or '')
    title = re.sub(r'\s+(?:ft\.?|feat\.?|featuring)\s+.*$', '', title, flags=re.I)
    # An upload may include artist credits. This ranks a discovery choice only;
    # it never rewrites canonical identity or auto-confirms the upload.
    parts = re.split(r'\s+[-–—]\s+', title)
    if any(match_text(part) == target for part in parts):
        return 2
    return int(bool(target and re.search(r'(?<!\w)' + re.escape(target) + r'(?!\w)', match_text(title))))


def merge_recordings(query, primary, supplement):
    rows, positions = [], {}
    for row in [*primary, *supplement]:
        video = row.external_ids['youtube']
        if video in positions:
            i = positions[video]
            if rows[i].source == 'youtube_recording':
                rows[i] = replace(rows[i], recording_metadata=row.recording_metadata)
            if rows[i].youtube_views is None and row.youtube_views is not None:
                rows[i] = replace(rows[i], youtube_views=row.youtube_views)
        else:
            positions[video] = len(rows)
            rows.append(row)
    if any(recording_relevance(query, row) == 2 for row in rows):
        rows.sort(key=lambda row: (recording_relevance(query, row),
                                  row.youtube_views if row.youtube_views is not None else -1), reverse=True)
    from .recording_metadata import prepare_results
    return prepare_results(query, rows)[:60]


class RecordingSearch:
    def __init__(self, *, timeout=4, ttl=300, capacity=128, concurrency=2, max_duration=900, clock=monotonic):
        self.timeout, self.ttl, self.capacity, self.clock = timeout, ttl, capacity, clock
        self.slots = asyncio.Semaphore(concurrency)
        self.max_duration = max_duration
        self.cache = OrderedDict()

    async def process(self, args):
        process = None
        try:
            async with asyncio.timeout(self.timeout):
                process = await asyncio.create_subprocess_exec(*args,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
                data = bytearray()
                while chunk := await process.stdout.read(65536):
                    data.extend(chunk)
                    if len(data) > 2_000_000:
                        return None
                await process.wait()
                return json.loads(data) if process.returncode == 0 else None
        except (OSError, TimeoutError, ValueError):
            return None
        finally:
            if process is not None:
                if process.returncode is None:
                    with suppress(ProcessLookupError):
                        process.kill()
                await process.wait()

    async def search(self, query, *, music_only=False):
        query = ' '.join(query.split())[:300]
        if not query:
            return [], False
        key = hashlib.sha256((str(music_only) + ':' + query.casefold()).encode()).hexdigest()
        entry = self.cache.get(key)
        if entry and entry[0] > self.clock():
            self.cache.move_to_end(key)
            return deepcopy(entry[1]), False
        self.cache.pop(key, None)
        # Bound queue wait as well as provider work. Cancellation kills the child.
        try:
            async with asyncio.timeout(self.timeout * 2 + .5):
                async with self.slots:
                    payload = await self.process([sys.executable, '-c', MUSIC_SEARCH, query, *(['songs'] if music_only else [])])
                    if music_only and isinstance(payload, list):
                        payload = [row for row in payload if isinstance(row, dict) and row.get('resultType') == 'song']
                    rows = recordings(payload, max_duration=self.max_duration, limit=30)
                    # Short/common queries need broader coverage even when Music
                    # returns matches. Keep both calls inside the same deadline.
                    if not music_only and (not rows or len(query.split()) <= 3):
                        payload = await self.process([sys.executable, '-m', 'yt_dlp',
                            '--ignore-config', '--no-cookies', '--no-cookies-from-browser',
                            '--no-cache-dir', '--flat-playlist', '--skip-download',
                            '--socket-timeout', '3', '--retries', '0', '--quiet', '--no-warnings',
                            '--dump-single-json', '--', 'ytsearch20:' + query])
                        supplement = recordings(payload.get('entries') if isinstance(payload, dict) else None,
                                                music=False, max_duration=self.max_duration, limit=20)
                        rows = merge_recordings(query, rows, supplement)
                    else:
                        if not music_only:
                            from .recording_metadata import prepare_results
                            rows = prepare_results(query, rows)
                        rows = rows[:60]
        except TimeoutError:
            return [], True
        if rows:
            self.cache[key] = (self.clock() + self.ttl, deepcopy(rows))
            self.cache.move_to_end(key)
            while len(self.cache) > self.capacity:
                self.cache.popitem(last=False)
        return rows, not rows and (not isinstance(payload, list) if music_only else payload is None)
