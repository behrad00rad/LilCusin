"""Bounded YouTube adapter. No caller URLs, cookies, shell, or inherited yt-dlp config."""
import asyncio
import json
import re
import sys
import shutil
from difflib import SequenceMatcher
from pathlib import Path
from types import SimpleNamespace
from .matching import match_text

VIDEO = re.compile(r'[A-Za-z0-9_-]{11}\Z')
VERSIONS = {'live', 'cover', 'remix', 'karaoke', 'instrumental', 'acoustic', 'sped', 'slowed', 'remaster',
            'extended', 'nightcore', 'reverb', '8d', '432hz', 'edit'}


def version_words(value):
    # match_text intentionally removes remaster labels; versions must be checked first.
    words = set(re.findall(r'\w+', value.casefold()))
    if 'remastered' in words:
        words.add('remaster')
    normalized = match_text(value)
    for phrase, version in {'کاور': 'cover', 'ریمیکس': 'remix', 'کارائوکه': 'karaoke',
                            'بی کلام': 'instrumental', 'اجرای زنده': 'live', 'آکوستیک': 'acoustic'}.items():
        if re.search(r'(?<!\w)' + phrase + r'(?!\w)', normalized):
            words.add(version)
    return words & VERSIONS


def base_title(value):
    """Remove edition labels, preserving ordinary titles such as Live Forever."""
    value = re.sub(r'\([^()]*\)|\[[^\[\]]*\]',
                   lambda m: '' if version_words(m[0]) else m[0], value)
    value = re.sub(r'\s+[-–—]\s+(?:live|acoustic|remix|instrumental|remaster(?:ed)?|sped up|slowed)(?:\b.*)$',
                   '', value, flags=re.I)
    return value.strip() or value


def song_title(value, target):
    noise = {'audio', 'visualizer', 'visualiser', 'hd', 'hq', '4k'} - set(match_text(target).split())
    return ' '.join(word for word in match_text(value).split() if word not in noise)


def artist_key(value):
    parts = re.split(r'\s+(?:feat\.?|ft\.?|featuring|x|and)\s+|[&,;]', value, flags=re.I)
    return tuple(sorted({match_text(part) for part in parts if match_text(part)}))


def without_artist_credit(value, artist):
    credit = re.split(r'\s+[-–—]\s+', value, maxsplit=1)
    if len(credit) == 2 and artist_key(credit[0]) == artist_key(artist):
        return credit[1]
    return re.sub(r'^' + re.escape(artist) + r'[\s:–—-]+', '', value, count=1, flags=re.I)

class FetchError(Exception):
    """Only fixed, sanitized messages may cross this boundary."""


def rank_candidates(track, entries, max_duration):
    result = []
    wanted = version_words(track.title)
    variants = getattr(track, 'allow_versions', False)
    for raw in entries:
        video = raw.get('id', '')
        title = str(raw.get('track') or raw.get('title') or '')[:200]
        artist = str(raw.get('artist') or raw.get('uploader') or '')[:150]
        duration = raw.get('duration')
        words = version_words(without_artist_credit(str(raw.get('title') or title), track.artist))
        if raw.get('track'):
            words |= version_words(title)
        if (not VIDEO.fullmatch(video) or raw.get('is_live') or raw.get('live_status') in {'is_live', 'is_upcoming'}
                or (raw.get('live_status') == 'was_live' and 'live' not in wanted)
                or (bool(words & {'cover', 'karaoke'}) if variants else words != wanted)
                or not isinstance(duration, (int, float))
                or not 0 < duration <= max_duration):
            continue
        if track.duration and abs(duration - track.duration) > max(12, track.duration * .08):
            continue
        target = match_text(track.title)
        normalized = match_text(title) if raw.get('track') else song_title(title, track.title)
        artist_text = match_text(track.artist)
        wanted_artists = artist_key(track.artist)
        credit = re.split(r'\s+[-–—]\s+', title, maxsplit=1)
        if not raw.get('track') and len(credit) == 2 and artist_key(credit[0]) == wanted_artists:
            normalized = song_title(credit[1], track.title)
        elif normalized != target:
            normalized = re.sub(r'(?<!\w)' + re.escape(artist_text) + r'(?!\w)', ' ', normalized)
            normalized = ' '.join(normalized.split())
        if variants:
            target = match_text(base_title(track.title))
            recording = str(raw.get('track') or without_artist_credit(str(raw.get('title') or title), track.artist))
            normalized = song_title(base_title(recording), base_title(track.title))
        context = match_text(artist + ' ' + title)
        a = 1.0 if (artist_key(artist) == wanted_artists or all(
            re.search(r'(?<!\w)' + re.escape(name) + r'(?!\w)', context) for name in wanted_artists)) else 0.0
        if variants and a != 1:
            continue
        t = SequenceMatcher(None, target, normalized).ratio()
        if raw.get('artist') and artist_key(str(raw['artist'])) != wanted_artists:
            continue
        if t < .82:
            continue
        uploader = match_text(str(raw.get('uploader') or raw.get('channel') or ''))
        official = uploader in {artist_text, artist_text + ' topic', artist_text.replace(' ', '') + 'vevo'}
        rich = bool(raw.get('track') and raw.get('artist') and a == 1 and t >= .95)
        duration_ok = bool(track.duration and abs(duration-track.duration) <= 5)
        score = .45 * a + .55 * t
        if score < .55:
            continue
        # Artist/Topic audio beats third-party lyric uploads with the same name.
        preference = .06 if official else 0
        if raw.get('track') or re.search(r'\baudio\b', str(raw.get('title', '')), re.I):
            preference += .03
        result.append(dict(id=video, title=title, artist=artist, duration=duration, score=score + preference,
                           exact=bool(duration_ok and (rich or (official and a == 1 and t == 1))),
                           identity_title=normalized, identity_artist='|'.join(wanted_artists) if a else match_text(artist),
                           version=sorted(words), recording_title=str(raw.get('track') or without_artist_credit(title, track.artist))))
    result.sort(key=lambda row: row['score'], reverse=True)
    unique = list({r['id']: r for r in result}.values())
    if variants:
        diverse = list({tuple(row['version']): row for row in reversed(unique)}.values())
        diverse.sort(key=lambda row: row['score'], reverse=True)
        return diverse[:3]
    return unique[:3]


def confident(rows):
    if not rows or not rows[0]['exact']:
        return False
    first = rows[0]
    for other in rows[1:]:
        same = (first.get('identity_title') and first.get('identity_title') == other.get('identity_title')
                and first.get('identity_artist') == other.get('identity_artist')
                and first.get('version') == other.get('version')
                and abs(first['duration'] - other['duration']) <= 3)
        if not same and first['score'] - other['score'] < .08:
            return False
    return True


class YouTubeFetcher:
    def __init__(self, settings):
        self.settings = settings

    async def process(self, args, directory, alive, output=False):
        # stderr is discarded; URLs/provider errors never enter application logs.
        process = await asyncio.create_subprocess_exec(*args, cwd=directory,
            stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE if output else asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL)
        async def read():
            data = bytearray()
            if output:
                while chunk := await process.stdout.read(65536):
                    data.extend(chunk)
                    if len(data) > 2_000_000:
                        raise FetchError('Source response too large.')
            await process.wait()
            return bytes(data)
        task = asyncio.create_task(read())
        try:
            async with asyncio.timeout(self.settings.timeout):
                while not task.done():
                    if not await alive():
                        raise FetchError('Request cancelled.')
                    size = sum(p.stat().st_size for p in Path(directory).rglob('*') if p.is_file())
                    if size > self.settings.disk_bytes:
                        raise FetchError('Temporary storage limit reached.')
                    await asyncio.sleep(.1)
                data = await task
                if process.returncode:
                    raise FetchError('Audio source unavailable.')
                return data
        finally:
            if process.returncode is None:
                process.kill()
            await process.wait()
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    def base(self):
        return [sys.executable, '-m', 'yt_dlp', *(['--js-runtimes', 'node'] if shutil.which('node') else []),
                '--ignore-config', '--no-cookies', '--no-cookies-from-browser', '--no-cache-dir', '--no-playlist',
                '--limit-rate', '2M', '--socket-timeout', '15', '--retries', '1', '--fragment-retries', '1', '--no-warnings', '--quiet']

    async def search(self, track, directory, alive):
        # Canonical DB keys remove punctuation; search with the original catalogue spelling.
        artist = getattr(track, 'display_artist', None) or track.artist
        title = getattr(track, 'display_title', None) or track.title
        query = ' '.join((artist + ' ' + title).split())[:300]
        if not version_words(track.title):
            query += ' official audio'
        # Listing metadata must not require extracting every candidate's media formats.
        data = await self.process(self.base() + ['--flat-playlist', '--dump-single-json', '--skip-download', '--', 'ytsearch8:' + query],
                                  directory, alive, output=True)
        try:
            entries = json.loads(data).get('entries', [])
            rows = rank_candidates(track, entries, self.settings.max_duration)
            if not rows and track.duration:
                # Imported clip lengths are sometimes wrong. Require explicit selection.
                relaxed = SimpleNamespace(artist=track.artist, title=track.title, duration=None)
                rows = rank_candidates(relaxed, entries, self.settings.max_duration)
                for row in rows:
                    row.update(exact=False, duration_mismatch=True)
            if rows and not confident(rows):
                # Enrich only the two strongest candidates, not every search result.
                enriched = {row.get('id'): row for row in entries if isinstance(row, dict)}
                for row in rows[:2]:
                    try:
                        detail = json.loads(await self.process(self.base() + ['--skip-download',
                            '--dump-single-json', '--', 'https://www.youtube.com/watch?v=' + row['id']],
                            directory, alive, output=True))
                        if detail.get('id') == row['id']:
                            enriched[row['id']] = detail
                    except (FetchError, ValueError, TypeError, AttributeError):
                        if not await alive():
                            raise FetchError('Request cancelled.') from None
                refined = rank_candidates(track, enriched.values(), self.settings.max_duration)
                if not refined and track.duration:
                    relaxed = SimpleNamespace(artist=track.artist, title=track.title, duration=None)
                    refined = rank_candidates(relaxed, enriched.values(), self.settings.max_duration)
                    for row in refined:
                        row.update(exact=False, duration_mismatch=True)
                rows = refined
            return rows
        except (ValueError, TypeError, AttributeError):
            raise FetchError('Source metadata unavailable.') from None

    async def fetch(self, video, directory, alive):
        if not VIDEO.fullmatch(video):
            raise FetchError('Invalid source.')
        await self.process(self.base() + ['--max-filesize', str(self.settings.max_bytes),
            '--match-filter', f'duration <= {self.settings.max_duration} & !is_live',
            '-f', 'bestaudio[ext=m4a]/bestaudio[ext=webm]', '-o', 'source.%(ext)s',
            '--', 'https://www.youtube.com/watch?v=' + video], directory, alive)
        path = Path(directory) / 'source.m4a'
        if not path.exists():
            source = Path(directory) / 'source.webm'
            if not source.exists() or source.stat().st_size > self.settings.max_bytes:
                raise FetchError('Audio unavailable or too large.')
            # WebM/Opus is not a Telegram music container. Transcode only this fallback.
            path = Path(directory) / 'audio.mp3'
            await self.process(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(source), '-vn',
                                '-codec:a', 'libmp3lame', '-q:a', '5', str(path)],
                               directory, alive)
        if not path.exists() or not 0 < path.stat().st_size < self.settings.max_bytes:
            raise FetchError('Audio unavailable or too large.')
        probe = await self.process(['ffprobe', '-v', 'error', '-show_entries',
            'format=duration:stream=codec_type,codec_name', '-of', 'json', str(path)], directory, alive, output=True)
        try:
            info = json.loads(probe)
            duration = float(info['format']['duration'])
            streams = info['streams']
            if (not 0 < duration <= self.settings.max_duration or not streams
                    or any(s.get('codec_type') != 'audio' for s in streams)
                    or streams[0].get('codec_name') not in {'aac', 'mp3'}):
                raise ValueError
        except (ValueError, KeyError, TypeError):
            raise FetchError('Fetched media is unsupported or exceeds limits.') from None
        return path

    async def fetch_social(self, url, directory, alive):
        from .recognition import social_url
        safe = social_url(url)
        if safe is None:
            raise FetchError('Unsupported media link.')
        from urllib.parse import urlsplit, urljoin
        if urlsplit(safe).hostname in {'pin.it', 'on.soundcloud.com'}:
            import aiohttp
            try:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
                    for _ in range(4):
                        async with session.get(safe, allow_redirects=False) as response:
                            if response.status not in (301, 302, 303, 307, 308):
                                break
                            safe = social_url(urljoin(safe, response.headers.get('Location', '')))
                            if safe is None:
                                raise FetchError('Unsupported post redirect.')
            except (aiohttp.ClientError, TimeoutError):
                raise FetchError('Public post unavailable.') from None
        await self.process(self.base() + ['--use-extractors',
            'TikTok.*,vm.tiktok,Instagram.*,Pinterest.*,Twitter.*,Soundcloud.*,Vimeo',
            '--max-filesize', str(self.settings.max_bytes), '--playlist-end', '1',
            '--match-filter', f'duration <= {self.settings.max_duration} & !is_live',
            '-f', 'bestaudio/best', '-o', 'social.%(ext)s', '--', safe], directory, alive)
        files = [p for p in Path(directory).glob('social.*')
                 if p.suffix.lower() in {'.mp4', '.m4a', '.webm', '.mkv', '.mp3', '.ogg', '.wav', '.flac', '.aac'}]
        if len(files) != 1 or not 0 < files[0].stat().st_size <= self.settings.max_bytes:
            raise FetchError('Post has no supported playable audio/video.')
        return files[0]
