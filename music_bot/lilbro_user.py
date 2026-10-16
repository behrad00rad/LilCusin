"""Optional, explicitly authorized Telegram user session for direct-link media fetching."""
import asyncio
from dataclasses import dataclass, field
import os
from pathlib import Path
from types import SimpleNamespace

from .config import ConfigError
from .lilbro_fetch import LILBRO_ID, LilBroFetcher, Pending
from .youtube_fetch import FetchError, VIDEO


@dataclass(frozen=True)
class UserSessionConfig:
    api_id: int
    api_hash: str = field(repr=False)
    session: Path = field(repr=False)

    @classmethod
    def environment(cls):
        import re
        try:
            api_id = int(os.getenv('TELEGRAM_API_ID', ''))
            api_hash = os.getenv('TELEGRAM_API_HASH', '').strip()
            if api_id <= 0 or not re.fullmatch(r'[a-fA-F0-9]{32}', api_hash):
                raise ValueError
        except ValueError:
            raise ConfigError('Telegram API credentials are missing or invalid; configure them locally.') from None
        root = Path(__file__).resolve().parent.parent
        session = Path(os.getenv('GET_SONG_LILBRO_SESSION', str(root/'data/lilbro-user.session'))).expanduser()
        if not session.is_absolute():
            session = root / session
        if session.suffix != '.session':
            raise ConfigError('Lil Bro session must be a private .session file.')
        return cls(api_id, api_hash, session.resolve())


class TelethonMediaSource:
    def __init__(self, settings, config=None):
        self.settings = settings
        self.config = config or UserSessionConfig.environment()

    async def download(self, fetcher, video, folder, alive, metadata, persist):
        if not self.config.session.is_file():
            raise FetchError('Lil Bro user session is not configured. Run the local sign-in helper.')
        try:
            from telethon import TelegramClient, events
        except ImportError:
            raise FetchError('Install the optional Lil Bro user-session dependencies.') from None
        client = TelegramClient(str(self.config.session), self.config.api_id, self.config.api_hash,
            connection_retries=1, request_retries=0, auto_reconnect=False, flood_sleep_threshold=0, timeout=10)
        pending = Pending(video)
        async def received(event):
            message = event.message
            if (message.sender_id != LILBRO_ID or message.chat_id != LILBRO_ID or message.out
                    or getattr(message, 'noforwards', False)):
                return
            wrapper = SimpleNamespace(message_id=message.id, reply_to_message=(
                SimpleNamespace(message_id=message.reply_to_msg_id) if message.reply_to_msg_id else None),
                entities=message.entities, caption_entities=[], caption='', text=message.raw_text,
                video=message.video, audio=message.audio, document=message.document, original=message)
            try:
                pending.messages.put_nowait(wrapper)
            except asyncio.QueueFull:
                pass
        try:
            await client.connect()
            if not await client.is_user_authorized():
                raise FetchError('Lil Bro user session is not signed in. Run the local sign-in helper.')
            me = await client.get_me()
            if me.bot:
                raise FetchError('Lil Bro user transport requires a user account, not a bot session.')
            entity = await client.get_entity('musicbehbot')
            if entity.id != LILBRO_ID or not entity.bot:
                raise FetchError('Lil Bro identity verification failed.')
            client.add_event_handler(received, events.NewMessage(chats=entity, incoming=True))
            client.add_event_handler(received, events.MessageEdited(chats=entity, incoming=True))
            if not await alive():
                raise FetchError('Request cancelled.')
            await persist({'lilbro_request_started': True, 'provider': 'lilbro', 'lilbro_transport': 'user'})
            sent = await client.send_message(entity, 'https://www.youtube.com/watch?v=' + video,
                                             link_preview=False)
            pending.request_id = sent.id
            await persist({'lilbro_request_message_id': sent.id})
            wrapper = await fetcher.wait_media(pending, alive)
            message = wrapper.original
            info = message.file
            limit = self.settings.disk_bytes - self.settings.max_bytes
            if (not info or not info.size or not 0 < info.size <= limit
                    or not (info.mime_type or '').startswith(('audio/', 'video/'))):
                raise FetchError('Source media is unsupported or exceeds the disk budget.')
            source = folder/'input.media'
            with source.open('wb') as output:
                async for chunk in client.iter_download(message.media, request_size=65536):
                    if not await alive():
                        raise FetchError('Request cancelled.')
                    if output.tell() + len(chunk) > limit:
                        raise FetchError('Source media exceeds the disk budget.')
                    output.write(chunk)
            await persist({'lilbro_response_message_id': message.id, 'source_video_id': video})
            return source
        finally:
            client.remove_event_handler(received)
            try:
                await asyncio.wait_for(client.disconnect(), timeout=5)
            except Exception:
                pass


class LilBroUserFetcher(LilBroFetcher):
    """Reuse matching/extraction and durable jobs; replace only the source transport."""
    def __init__(self, settings, bot, source=None):
        super().__init__(settings, bot)
        self.source = source or TelethonMediaSource(settings)

    async def accept(self, message):
        # User-session replies arrive through its own narrowly filtered event handler.
        # Consume old bot-to-bot messages without mixing the two account namespaces.
        sender, chat = getattr(message, 'from_user', None), getattr(message, 'chat', None)
        return bool(sender and sender.is_bot and sender.id == LILBRO_ID and chat
                    and chat.type == 'private' and chat.id == LILBRO_ID)

    async def fetch_selected(self, video, directory, alive, metadata, persist):
        if not VIDEO.fullmatch(video):
            raise FetchError('Invalid source.')
        if metadata.get('lilbro_request_started'):
            raise FetchError('Interrupted source request. Please request the song again.')
        folder = Path(directory)
        async with self.lock:
            try:
                async with asyncio.timeout(self.settings.timeout):
                    source = await self.source.download(self, video, folder, alive, metadata, persist)
                    if source != folder/'input.media':
                        raise FetchError('Invalid generated source path.')
                    result = await self.extract(source, folder, alive, metadata.get('duration'))
                    await persist({'provider': 'lilbro', 'lilbro_transport': 'user'})
                    return result
            except asyncio.CancelledError:
                raise
            except FetchError:
                raise
            except Exception:
                raise FetchError('Lil Bro user-session source unavailable. Please try again later.') from None
            finally:
                (folder/'input.media').unlink(missing_ok=True)
