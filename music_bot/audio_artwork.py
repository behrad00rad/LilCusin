"""Reuse canonical artwork for private audio tags and Telegram upload thumbnails."""
import asyncio
import hashlib
import shutil
from pathlib import Path
import aiohttp
from .chat_ui import safe_url
from .youtube_fetch import FetchError

MAX_IMAGE_BYTES = 2_000_000


def artwork_key(track):
    url = safe_url(track.artwork_url, artwork=True)
    return hashlib.sha256(url.encode()).hexdigest() if url else None


async def image_bytes(url):
    # Same strict CDN allowlist as the cards. Never follow a redirect to another host.
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8), trust_env=False) as session:
        async with session.get(url, allow_redirects=False) as response:
            if response.status != 200 or not response.headers.get('Content-Type', '').lower().startswith('image/'):
                raise ValueError('Artwork unavailable')
            if response.content_length and response.content_length > MAX_IMAGE_BYTES:
                raise ValueError('Artwork too large')
            data = bytearray()
            async for chunk in response.content.iter_chunked(16384):
                data.extend(chunk)
                if len(data) > MAX_IMAGE_BYTES:
                    raise ValueError('Artwork too large')
            if not data:
                raise ValueError('Artwork empty')
            return bytes(data)


def embed(path, cover, track):
    from mutagen.mp4 import MP4, MP4Cover
    from mutagen.id3 import ID3, ID3NoHeaderError, APIC, TALB, TIT2, TPE1
    artist, title = track.display_artist or track.artist, track.display_title or track.title
    if path.suffix == '.m4a':
        tags = MP4(path)
        tags['covr'] = [MP4Cover(cover, imageformat=MP4Cover.FORMAT_JPEG)]
        tags['\xa9nam'], tags['\xa9ART'] = [title], [artist]
        if track.album:
            tags['\xa9alb'] = [track.album]
        tags.save()
    elif path.suffix == '.mp3':
        try:
            tags = ID3(path)
        except ID3NoHeaderError:
            tags = ID3()
        tags.delall('APIC')
        tags.add(APIC(encoding=3, mime='image/jpeg', type=3, desc='Cover', data=cover))
        tags.add(TIT2(encoding=3, text=title))
        tags.add(TPE1(encoding=3, text=artist))
        if track.album:
            tags.add(TALB(encoding=3, text=track.album))
        tags.save(path)


def embed_atomic(path, cover, track, max_bytes):
    tagged = path.with_name('tagged' + path.suffix)
    try:
        shutil.copyfile(path, tagged)
        embed(tagged, cover, track)
        if tagged.stat().st_size >= max_bytes:
            raise ValueError('Tagged audio too large')
        tagged.replace(path)
    finally:
        tagged.unlink(missing_ok=True)


async def prepare(fetcher, track, path, directory, alive):
    """Return thumbnail + cache identity, or no artwork if the optional source fails."""
    url = safe_url(track.artwork_url, artwork=True)
    if not url:
        return None, None
    folder = Path(directory)
    source, thumbnail = folder/'cover.input', folder/'cover.jpg'
    try:
        source.write_bytes(await image_bytes(url))
        if not await alive():
            raise FetchError('Request cancelled.')
        # Decode within the existing bounded subprocess/disk/cancellation boundary.
        await fetcher.process(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(source),
            '-frames:v', '1', '-vf', 'scale=320:320:force_original_aspect_ratio=decrease',
            '-q:v', '5', '-fs', '190000', str(thumbnail)], directory, alive)
        cover = thumbnail.read_bytes()
        if not 0 < len(cover) < 200000 or not cover.startswith(b'\xff\xd8') or not cover.endswith(b'\xff\xd9'):
            raise ValueError('Unsupported thumbnail')
        if path.stat().st_size + len(cover) + 65536 >= fetcher.settings.max_bytes:
            return None, None
        occupied = sum(p.stat().st_size for p in folder.rglob('*') if p.is_file())
        if occupied + path.stat().st_size + len(cover) + 65536 > fetcher.settings.disk_bytes:
            thumbnail.unlink(missing_ok=True)
            return None, None
        task = asyncio.create_task(asyncio.to_thread(embed_atomic, path, cover, track, fetcher.settings.max_bytes))
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            await asyncio.gather(task, return_exceptions=True)
            raise
        return thumbnail, artwork_key(track)
    except asyncio.CancelledError:
        raise
    except Exception:
        # A cancelled request must never become a send simply because artwork is optional.
        if not await alive():
            raise FetchError('Request cancelled.') from None
        thumbnail.unlink(missing_ok=True)
        return None, None
    finally:
        source.unlink(missing_ok=True)
