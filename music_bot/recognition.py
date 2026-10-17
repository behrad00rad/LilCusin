"""Bounded, ephemeral audio recognition. Never send Telegram URLs to providers."""
import asyncio
import io
import os
import re
import shutil
import tempfile
import time
import logging
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import aiohttp

from .config import ConfigError
from .i18n import language
from .youtube_fetch import FetchError, YouTubeFetcher, VIDEO

MAX_BYTES = 20_000_000
logger = logging.getLogger('music_bot')


def sample_offsets(duration):
    """Sample different useful sections, rather than seeking past a short clip."""
    if not isinstance(duration, (int, float)) or duration <= 0:
        return (0, 30, 60)
    end = max(0, int(duration) - 12)
    return tuple(dict.fromkeys((0, min(end, max(0, int(duration / 2) - 6)), end)))


class RecognitionError(Exception):
    pass


class RecognizedSong(str):
    """Display text with explicit identity; never parse artist/title from a label."""
    def __new__(cls, artist, title, links=(), *, artwork_url=None, album=None):
        value = super().__new__(cls, '\n'.join([artist + ' — ' + title, *links]))
        value.artist, value.title = artist, title
        value.artwork_url, value.album = artwork_url, album
        return value


def text(en, fa):
    return fa if language.get() == 'fa' else en


def youtube_id(value):
    """Accept only known public page shapes; reconstruct the downloader URL."""
    try:
        url = urlsplit(value.strip())
        if url.scheme != 'https' or url.username or url.password or url.port not in (None, 443):
            return None
        host = (url.hostname or '').lower()
        if host == 'youtu.be':
            candidate = url.path.removeprefix('/')
        elif host in {'youtube.com', 'www.youtube.com', 'm.youtube.com', 'music.youtube.com'}:
            if url.path == '/watch':
                candidate = parse_qs(url.query).get('v', [''])[0]
            elif url.path.startswith('/shorts/'):
                candidate = url.path[len('/shorts/'):]
            else:
                return None
        else:
            return None
        return candidate if VIDEO.fullmatch(candidate) else None
    except ValueError:
        return None


def social_url(value):
    """Only public post URLs on explicit platforms; never generic URL fetching."""
    try:
        url = urlsplit(value.strip())
        if (url.scheme != 'https' or url.username or url.password or url.port not in (None, 443)
                or any(c.isspace() or ord(c) < 32 for c in value) or '\\' in value or len(value) > 2048):
            return None
        host, path = (url.hostname or '').lower(), url.path
        rules = [
            ({'www.tiktok.com', 'tiktok.com', 'm.tiktok.com'}, r'/(?:@[^/]+/video/\d+|t/[A-Za-z0-9]+)/?'),
            ({'vm.tiktok.com', 'vt.tiktok.com'}, r'/[A-Za-z0-9]+/?'),
            ({'www.instagram.com', 'instagram.com'}, r'/(?:reel|reels|p|tv)/[A-Za-z0-9_-]+/?'),
            ({'www.pinterest.com', 'pinterest.com', 'www.pinterest.co.uk', 'pinterest.co.uk'}, r'/pin/\d+/?'),
            ({'pin.it'}, r'/[A-Za-z0-9]+/?'),
            ({'x.com', 'www.x.com', 'twitter.com', 'www.twitter.com'}, r'/[A-Za-z0-9_]+/status/\d+/?'),
            ({'soundcloud.com', 'www.soundcloud.com'}, r'/[^/]+/[^/]+/?'),
            ({'on.soundcloud.com'}, r'/[A-Za-z0-9]+/?'),
            ({'vimeo.com', 'www.vimeo.com'}, r'/\d+/?'),
        ]
        if any(host in hosts and re.fullmatch(pattern, path) for hosts, pattern in rules):
            return 'https://' + host + path  # Drop tracking/query parameters.
    except ValueError:
        pass
    return None


@dataclass(frozen=True)
class RecognitionSettings:
    enabled: bool = True

    @classmethod
    def environment(cls):
        value = os.getenv('RECOGNITION_ENABLED', 'true').strip().lower()
        if value not in {'true', 'false'}:
            raise ConfigError('RECOGNITION_ENABLED must be true or false')
        return cls(value == 'true')


class ShazamHTTP:
    """One bounded request; avoid the library's default twenty retries."""
    def __init__(self, session):
        self.session = session

    async def request(self, method, url, *args, **kwargs):
        # Upstream also routes discovery/v5 on cdn; amp returns 403 here.
        # Fix the profile instead of the old release's random device selection.
        if urlsplit(url).hostname == 'amp.shazam.com':
            url = url.replace('https://amp.shazam.com/', 'https://cdn.shazam.com/', 1)
            url = url.replace('/android/-/', '/iphone/-/').replace('/web/-/', '/iphone/-/')
        async with self.session.request(method, url, **kwargs,
                timeout=aiohttp.ClientTimeout(total=30), allow_redirects=False) as response:
            if response.status != 200:
                raise RecognitionError('provider')
            raw = bytearray()
            async for chunk in response.content.iter_chunked(65536):
                raw.extend(chunk)
                if len(raw) > 262144:
                    raise RecognitionError('provider')
            import json
            return json.loads(raw)


class ShazamProvider:
    def __init__(self, session=None, client=None):
        if client is None:
            try:
                from shazamio import Shazam
            except ImportError:
                raise ConfigError('Install requirements.txt for ShazamIO recognition') from None
            client = Shazam(http_client=ShazamHTTP(session), segment_duration_seconds=12)
        self.client = client

    async def recognize(self, sample):
        try:
            async with asyncio.timeout(40):
                data = await self.client.recognize(str(sample))
            if not isinstance(data, dict):
                raise RecognitionError('provider')
            track = data.get('track')
            if track is None and isinstance(data.get('matches'), list) and not data['matches']:
                return None
            if not isinstance(track, dict) or not all(isinstance(track.get(k), str) and track[k].strip()
                                                     for k in ('subtitle', 'title')):
                raise RecognitionError('provider')
            links = []
            candidate = track.get('url')
            if isinstance(candidate, str) and len(candidate) < 2048:
                url = urlsplit(candidate)
                if (url.scheme == 'https' and url.hostname in {'www.shazam.com', 'shazam.com'}
                        and not url.username and not url.password and url.port in (None, 443)):
                    links.append(candidate)
            from .chat_ui import safe_url
            images = track.get('images')
            artwork = None
            if isinstance(images, dict):
                artwork = safe_url(images.get('coverarthq'), artwork=True) or safe_url(images.get('coverart'), artwork=True)
            album = None
            for section in track.get('sections', []) if isinstance(track.get('sections'), list) else []:
                if not isinstance(section, dict) or not isinstance(section.get('metadata'), list):
                    continue
                for item in section['metadata']:
                    if (isinstance(item, dict) and item.get('title') == 'Album'
                            and isinstance(item.get('text'), str)):
                        album = item['text'][:200]
            return RecognizedSong(track['subtitle'][:200], track['title'][:200], links,
                                  artwork_url=artwork, album=album)
        except asyncio.CancelledError:
            raise
        except Exception:
            # Provider errors can include private request data; expose only a fixed code.
            raise RecognitionError('provider') from None


def ffmpeg_executable():
    binary = shutil.which('ffmpeg')
    if binary:
        return binary
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, RuntimeError):
        raise ConfigError('Recognition requires FFmpeg or imageio-ffmpeg') from None


class LimitedBuffer(io.BytesIO):
    def write(self, data):
        if self.tell() + len(data) > MAX_BYTES:
            raise RecognitionError('size')
        return super().write(data)


class Recognition:
    def __init__(self, bot, provider, enabled=False, delivery=None):
        self.bot, self.provider, self.enabled = bot, provider, enabled
        self.delivery = delivery
        self.jobs = {}
        self.pending = {}
        self.recent = OrderedDict()
        self.cache = OrderedDict()
        self.worker = asyncio.Semaphore(1)
        self.admission = asyncio.Lock()
        self.ffmpeg = None
        self.fetcher = YouTubeFetcher(SimpleNamespace(timeout=120, max_bytes=MAX_BYTES,
            disk_bytes=60_000_000, max_duration=900))

    async def close(self):
        await asyncio.gather(*(self.cancel(user) for user in list(self.jobs)))
        self.cache.clear()
        self.recent.clear()

    async def cancel(self, user_id):
        task = self.jobs.get(user_id)
        if task:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            self.jobs.pop(user_id, None)
            pending = self.pending.pop(user_id, None)
            if pending:
                try:
                    await pending.delete()
                except Exception:
                    pass

    async def submit(self, message, source=None):
        async with self.admission:
            await self._submit(message, source)

    async def _submit(self, message, source=None):
        if message.chat.type != 'private' or not message.from_user or message.from_user.is_bot or message.sender_chat:
            return
        if not self.enabled:
            await message.answer(text('Music recognition is not configured yet.', 'تشخیص آهنگ هنوز فعال نشده.'))
            return
        user = message.from_user.id
        now = time.monotonic()
        if user in self.jobs or len(self.jobs) >= 20 or now - self.recent.get(user, -3600) < 30:
            await message.answer(text('Please wait before trying again.', 'کمی صبر کن و دوباره امتحان کن.'))
            return
        source = source or message
        media = source.audio or source.video or source.voice or source.video_note or source.document
        video = (youtube_id(source.text or '') or social_url(source.text or '')) if not media else None
        if not media and not video:
            await message.answer(text('Send audio, video, a voice note, or a public YouTube, TikTok, Instagram, Pinterest, X, SoundCloud or Vimeo post link. You can also reply to media with /recognize.',
                'فایل صوتی، ویدیو، ویس یا لینک پست عمومی از یوتیوب، تیک‌تاک، اینستاگرام، پینترست، ایکس، ساندکلاد یا ویمئو بفرست. روی پیام رسانه‌ای هم می‌تونی /recognize رو ریپلای کنی.'))
            return
        if media and (media.file_size is None or media.file_size > MAX_BYTES):
            await message.answer(text('Send a file smaller than 20 MB.', 'فایل کمتر از ۲۰ مگابایت بفرست.'))
            return
        self.recent[user] = now
        self.recent.move_to_end(user)
        while len(self.recent) > 10000:
            self.recent.popitem(last=False)
        pending = await message.answer(text('Listening… An audio fingerprint is sent to Shazam. Use /cancel to stop.',
            'دارم گوش می‌دم… اثر انگشت صوتی برای Shazam فرستاده می‌شه. برای لغو /cancel رو بزن.'))
        self.pending[user] = pending
        self.jobs[user] = asyncio.create_task(self.run(user, message, pending, media, video))

    async def run(self, user, message, pending, media, video):
        try:
            async with asyncio.timeout(240), self.worker:
                key = ('file:' + media.file_unique_id) if media else 'youtube:' + video
                cached = self.cache.get(key)
                if cached and time.monotonic() - cached[0] < 3600:
                    recognized = await message.answer(cached[1], parse_mode=None)
                    await self.deliver(message, cached[1], recognized)
                    return
                with tempfile.TemporaryDirectory(prefix='lilcusin-recognition-') as directory:
                    root = Path(directory)
                    if media:
                        file = await self.bot.get_file(media.file_id)
                        if not file.file_path or (file.file_size and file.file_size > MAX_BYTES):
                            raise RecognitionError('size')
                        with LimitedBuffer() as buffer:
                            await self.bot.download_file(file.file_path, destination=buffer, timeout=60)
                            source = root / 'input.media'
                            source.write_bytes(buffer.getvalue())
                    else:
                        source = (await self.fetcher.fetch_social(video, directory, self.alive)
                                  if video.startswith('https://') else await self.fetcher.fetch(video, directory, self.alive))
                    result = None
                    attempts = 0
                    for offset in sample_offsets(getattr(media, 'duration', None)):
                        sample = root / 'sample.wav'
                        sample.unlink(missing_ok=True)
                        await self.fetcher.process([self.ffmpeg or ffmpeg_executable(), '-nostdin', '-v', 'error', '-y',
                            '-protocol_whitelist', 'file,pipe', '-format_whitelist',
                            'mov,matroska,webm,ogg,mp3,wav,flac,aac', '-ss', str(offset), '-i', str(source),
                            '-t', '12', '-vn', '-map', '0:a:0', '-ac', '1', '-ar', '22050',
                            '-codec:a', 'pcm_s16le', str(sample)], directory, self.alive)
                        if not sample.exists() or sample.stat().st_size < 1024:
                            break
                        result = await self.provider.recognize(sample)
                        attempts += 1
                        if result:
                            break
                    if result:
                        self.cache[key] = (time.monotonic(), result)
                        while len(self.cache) > 500:
                            self.cache.popitem(last=False)
                        recognized = await message.answer(result, parse_mode=None)
                        await self.deliver(message, result, recognized)
                    else:
                        logger.info('Recognition completed: no_match after %s samples.', attempts)
                        from .chat_ui import recovery_keyboard
                        await message.answer(text('No recognition match found. You can type the song name or artist, or try another section of the audio.',
                            'تشخیص آهنگ نتیجه نداد. می‌تونی اسم آهنگ یا خواننده رو بنویسی، یا بخش دیگه‌ای از صدا رو بفرستی.'), reply_markup=recovery_keyboard())
        except asyncio.CancelledError:
            raise
        except RecognitionError as error:
            await message.answer(text('Recognition service unavailable. Try again later.', 'سرویس تشخیص فعلاً در دسترس نیست. بعداً دوباره امتحان کن.')
                if str(error) == 'provider' else text('File exceeds the 20 MB limit.', 'حجم فایل بیشتر از ۲۰ مگابایته.'))
        except (FetchError, OSError, TimeoutError):
            await message.answer(text('Couldn’t access playable audio. Posts must be public, under 15 minutes and 20 MB. Private/login-required, blocked or image-only posts cannot be recognized; send the video or audio file instead.',
                'نتونستم به صدای قابل پخش دسترسی پیدا کنم. پست باید عمومی، کوتاه‌تر از ۱۵ دقیقه و زیر ۲۰ مگابایت باشه. پست خصوصی، نیازمند ورود، مسدود یا عکسِ بدون صدا قابل تشخیص نیست؛ فایل ویدیو یا صدا رو بفرست.'))
        except Exception:
            # Transport errors may contain token-bearing URLs; never log exceptions.
            try:
                await message.answer(text('Recognition failed. Please try again later.', 'تشخیص آهنگ انجام نشد. بعداً دوباره امتحان کن.'))
            except Exception:
                pass
        finally:
            self.jobs.pop(user, None)
            self.pending.pop(user, None)
            try:
                await pending.delete()
            except Exception:
                pass

    async def alive(self):
        return True

    async def deliver(self, message, result, recognized_message=None):
        if self.delivery is None or not isinstance(result, RecognizedSong):
            return
        try:
            metadata = {}
            if result.artwork_url:
                metadata['artwork_url'] = result.artwork_url
            if result.album:
                metadata['album'] = result.album
            request_id = await self.delivery.request_recognized(message.from_user.id, result.artist, result.title, **metadata)
            if recognized_message is not None and hasattr(self.delivery, 'bind_status'):
                try:
                    await self.delivery.cached_request(message.from_user.id, request_id)
                    await self.delivery.bind_status(message.from_user.id, request_id, recognized_message.message_id)
                except Exception:
                    pass  # A failed optional button must not change a queued delivery.
        except asyncio.CancelledError:
            raise
        except FetchError as error:
            await message.answer(text('Song identified, but audio delivery could not start: ',
                                      'آهنگ پیدا شد، ولی ارسال فایل شروع نشد: ') + str(error))
        except Exception:
            await message.answer(text('Song identified, but audio delivery is unavailable. Try again later.',
                                      'آهنگ پیدا شد، ولی فعلاً ارسال فایل ممکن نیست. بعداً دوباره امتحان کن.'))

    def check(self):
        if self.enabled:
            self.ffmpeg = ffmpeg_executable()
