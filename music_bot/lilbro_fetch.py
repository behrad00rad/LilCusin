"""Bot-to-bot media source. No user sessions, browser credentials or button clicks."""
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .youtube_fetch import FetchError, VIDEO, YouTubeFetcher

LILBRO_ID = 5098692079


def youtube_id(value):
    try:
        url = urlsplit(value)
        if url.scheme != 'https' or url.username or url.password:
            return None
        if url.hostname == 'youtu.be':
            video = url.path.strip('/')
        elif url.hostname in {'youtube.com', 'www.youtube.com', 'm.youtube.com'}:
            video = parse_qs(url.query).get('v', [''])[0] if url.path == '/watch' else ''
        elif url.hostname == 'song.link' and url.path.startswith('/y/'):
            video = url.path[3:]
        else:
            return None
        return video if VIDEO.fullmatch(video) else None
    except (ValueError, TypeError):
        return None


def source_ids(message):
    values = []
    for name in ('entities', 'caption_entities'):
        for entity in getattr(message, name, None) or []:
            if getattr(entity, 'url', None):
                values.append(entity.url)
    import re
    values.extend(re.findall(r'https://[^\s<>]+', (getattr(message, 'caption', '') or '') + ' ' + (getattr(message, 'text', '') or '')))
    return {identity for value in values if (identity := youtube_id(value))}


@dataclass
class Pending:
    video: str
    started: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    request_id: int | None = None
    messages: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=12))


class LilBroFetcher(YouTubeFetcher):
    provider = 'lilbro'

    def __init__(self, settings, bot):
        super().__init__(settings)
        self.bot = bot
        self.pending = None
        self.lock = asyncio.Lock()

    async def search(self, track, directory, alive):
        rows = await super().search(track, directory, alive)
        return [dict(row, exact=False, provider='lilbro') for row in rows]

    async def accept(self, message):
        """Consume provider updates before user-submission handlers, even after a restart."""
        sender = getattr(message, 'from_user', None)
        chat = getattr(message, 'chat', None)
        trusted = bool(sender and sender.is_bot and sender.id == LILBRO_ID and chat
                       and chat.type == 'private' and chat.id == LILBRO_ID)
        if not trusted:
            return False
        pending = self.pending
        if pending is not None and not getattr(message, 'has_protected_content', False):
            when = getattr(message, 'date', None)
            if when and when >= pending.started.replace(microsecond=0):
                try:
                    pending.messages.put_nowait(message)
                except asyncio.QueueFull:
                    pass
        return True

    def correlated(self, message, pending):
        if pending.request_id is None or message.message_id <= pending.request_id:
            return False
        reply = getattr(message, 'reply_to_message', None)
        if reply is not None:
            return reply.message_id == pending.request_id
        return pending.video in source_ids(message)

    async def wait_media(self, pending, alive):
        while True:
            if not await alive():
                raise FetchError('Request cancelled.')
            try:
                message = await asyncio.wait_for(pending.messages.get(), timeout=.25)
            except TimeoutError:
                continue
            if self.correlated(message, pending) and (message.video or message.audio or message.document):
                return message

    async def fetch_selected(self, video, directory, alive, metadata, persist):
        if not VIDEO.fullmatch(video):
            raise FetchError('Invalid source.')
        # A crash around sendMessage is ambiguous; don't send the upstream request again.
        if metadata.get('lilbro_request_started'):
            raise FetchError('Interrupted source request. Please request the song again.')
        async with self.lock:
            folder = Path(directory)
            stage = 'prepare'
            try:
                async with asyncio.timeout(self.settings.timeout):
                    if not await alive():
                        raise FetchError('Request cancelled.')
                    await persist({'lilbro_request_started': True, 'provider': 'lilbro'})
                    self.pending = pending = Pending(video)
                    stage = 'send'
                    sent = await self.bot.send_message('@musicbehbot', 'https://www.youtube.com/watch?v=' + video,
                                                       request_timeout=min(30, self.settings.timeout))
                    pending.request_id = sent.message_id
                    await persist({'lilbro_request_message_id': sent.message_id})
                    stage = 'wait'
                    message = await self.wait_media(pending, alive)
                    media = message.video or message.audio or message.document
                    # The hosted Bot API's getFile limit is 20 MB. Never follow public file URLs.
                    source_limit = min(19_000_000, self.settings.disk_bytes - self.settings.max_bytes)
                    if not media.file_size or not 0 < media.file_size <= source_limit:
                        raise FetchError('Source media exceeds the download limit.')
                    mime = getattr(media, 'mime_type', '') or ''
                    if not (mime.startswith('video/') or mime.startswith('audio/')):
                        raise FetchError('Unsupported source media.')
                    source = folder / 'input.media'
                    stage = 'download'
                    with source.open('wb') as output:
                        async def guard():
                            if not await alive():
                                raise FetchError('Request cancelled.')
                            if output.tell() > source_limit:
                                raise FetchError('Source media exceeds the download limit.')
                        # Guard every downloaded chunk, rather than waiting for the final file size.
                        file = await self.bot.get_file(media.file_id, request_timeout=30)
                        if not file.file_path:
                            raise FetchError('Source media unavailable.')
                        async for chunk in self.bot.session.stream_content(
                                self.bot.session.api.file_url(self.bot.token, file.file_path),
                                timeout=self.settings.timeout, chunk_size=65536):
                            await guard()
                            if output.tell() + len(chunk) > source_limit:
                                raise FetchError('Source media exceeds the download limit.')
                            output.write(chunk)
                    stage = 'extract'
                    path = await self.extract(source, folder, alive, metadata.get('duration'))
                    await persist({'lilbro_response_message_id': message.message_id,
                                   'source_video_id': video, 'provider': 'lilbro'})
                    return path
            except asyncio.CancelledError:
                raise
            except FetchError as error:
                await persist({'lilbro_failure': str(error), 'lilbro_stage': stage})
                raise
            except Exception as error:
                await persist({'lilbro_error_class': type(error).__name__, 'lilbro_stage': stage})
                raise FetchError('Lil Bro source unavailable. Please try again later.') from None
            finally:
                self.pending = None
                for filename in ('input.media',):
                    (folder / filename).unlink(missing_ok=True)

    async def probe(self, path, folder, alive):
        raw = await self.process(['ffprobe', '-v', 'error', '-show_entries',
            'format=duration:stream=codec_type,codec_name', '-of', 'json', str(path)], folder, alive, output=True)
        try:
            info = json.loads(raw)
            duration = float(info['format']['duration'])
            if not 0 < duration <= self.settings.max_duration:
                raise ValueError
            return duration, info['streams']
        except (KeyError, TypeError, ValueError):
            raise FetchError('Source duration or media unavailable.') from None

    async def extract(self, source, folder, alive, expected_duration=None):
        duration, streams = await self.probe(source, folder, alive)
        if expected_duration and abs(duration - expected_duration) > max(12, expected_duration * .08):
            raise FetchError('Source recording duration differs from the selected recording.')
        audio = next((s for s in streams if s.get('codec_type') == 'audio'), None)
        if audio is None:
            raise FetchError('Source contains no audio.')
        codec = audio.get('codec_name')
        path = folder / ('audio.m4a' if codec == 'aac' else 'audio.mp3')
        encoding = ['-c:a', 'copy'] if codec in {'aac', 'mp3'} else ['-c:a', 'libmp3lame', '-q:a', '5']
        try:
            await self.process(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(source), '-map', '0:a:0',
                '-vn', *encoding, '-fs', str(self.settings.max_bytes), str(path)], folder, alive)
            final_duration, final_streams = await self.probe(path, folder, alive)
            if (not path.exists() or not 0 < path.stat().st_size < self.settings.max_bytes
                    or abs(final_duration - duration) > 2 or not final_streams
                    or any(s.get('codec_type') != 'audio' or s.get('codec_name') not in {'aac', 'mp3'} for s in final_streams)):
                raise FetchError('Extracted audio is incomplete or unsupported.')
            return path
        except BaseException:
            path.unlink(missing_ok=True)
            raise


class LilBroInbound:
    def __init__(self, service):
        self.service = service

    async def __call__(self, handler, event, data):
        fetcher = self.service.fetcher
        if isinstance(fetcher, LilBroFetcher) and await fetcher.accept(event):
            return
        return await handler(event, data)


def configured_fetcher(settings, bot):
    provider = os.getenv('GET_SONG_PROVIDER', 'youtube').strip().lower()
    if provider == 'lilbro':
        transport = os.getenv('GET_SONG_LILBRO_TRANSPORT', 'bot').strip().lower()
        if transport == 'user':
            from .lilbro_user import LilBroUserFetcher
            return LilBroUserFetcher(settings, bot)
        if transport != 'bot':
            from .config import ConfigError
            raise ConfigError('Invalid Lil Bro transport.')
        return LilBroFetcher(settings, bot)
    if provider == 'youtube':
        return YouTubeFetcher(settings)
    from .config import ConfigError
    raise ConfigError('Invalid Get song provider.')
