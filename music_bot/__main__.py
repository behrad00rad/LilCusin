import asyncio
import logging
import aiohttp
from contextlib import AsyncExitStack

from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramNetworkError, TelegramRetryAfter
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.types import BotCommand, BotCommandScopeAllPrivateChats, MenuButtonWebApp, WebAppInfo

from .get_song import GetSong, FetchSettings
from .recognition import Recognition, RecognitionSettings, ShazamProvider
from .lilbro_fetch import LilBroInbound
from .config import ConfigError, load_config
from .database import Database
from .handlers import router
from .submissions import SubmissionService
from .cache import CachedProviders
from .enrichment import Enrichment
from .artwork import ArtworkLoader
from .providers.lastfm import LastFMClient
from .providers.musicbrainz import MusicBrainzClient
from .providers.deezer import DeezerClient
from .providers.itunes import ITunesClient
from .workflow import Workflow
from .lyrics_search import LyricsSearch, LyricsSettings
from .lifecycle import UpdateTasks, PrivateActions, ChannelUpdates
from .channels import ChannelService
from .channel_handlers import router as channel_router
from .taste_ui import router as taste_router
from .chat_service import ChatService
from .recommendations import RecommendationService
from . import messages
from .miniapp import start_server
from .guidance import LanguageMiddleware, router as guidance_router, configure_commands

logger = logging.getLogger("music_bot")


class SafeFormatter(logging.Formatter):
    """Never render dependency messages, exceptions, or request objects."""

    def format(self, record: logging.LogRecord) -> str:
        if record.name == "music_bot":
            text = record.getMessage()  # Application logs contain safe text only.
        elif record.levelno >= logging.WARNING:
            text = "Dependency warning or error; details omitted for privacy."
        else:
            text = "Dependency status update."
        return f"{record.levelname}: {text}"


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(SafeFormatter())
    logging.basicConfig(level=logging.WARNING, handlers=[handler], force=True)
    logger.setLevel(logging.INFO)


async def main() -> None:
    config = load_config()
    fetch_settings = FetchSettings.environment()
    lyrics_settings = LyricsSettings.environment()
    try:
        async with AsyncExitStack() as stack:
            bot = Bot(
                token=config.telegram_bot_token,
                session=AiohttpSession(
                    api=TelegramAPIServer.from_base(config.telegram_api_base_url)
                ),
            )
            stack.push_async_callback(bot.session.close)
            database = Database()
            stack.push_async_callback(database.close)
            await database.initialize()
            provider_session = await stack.enter_async_context(aiohttp.ClientSession())
            recognition_settings = RecognitionSettings.environment()
            recognition = Recognition(bot, ShazamProvider(provider_session) if recognition_settings.enabled else None,
                                      enabled=recognition_settings.enabled)
            recognition.check()
            stack.push_async_callback(recognition.close)
            providers = CachedProviders(database, LastFMClient(provider_session, config.lastfm_api_key),
                                        MusicBrainzClient(provider_session),
                                        DeezerClient(provider_session) if config.search_deezer_enabled else None,
                                        itunes=ITunesClient(provider_session))
            song_artwork = ArtworkLoader(database, providers)
            stack.push_async_callback(song_artwork.close)
            get_song = GetSong(database, bot, fetch_settings, artwork_loader=song_artwork)
            get_song.recognizer = ShazamProvider(provider_session)
            await get_song.start()
            recognition.delivery = get_song
            stack.push_async_callback(get_song.close)
            enrichment = Enrichment(database, providers)
            stack.push_async_callback(enrichment.close)
            workflow = Workflow(database, providers, LyricsSearch(provider_session, providers, lyrics_settings))
            stack.push_async_callback(workflow.close)
            channels = ChannelService(database, workflow)
            await channels.initialize()
            update_tasks = UpdateTasks()
            stack.push_async_callback(update_tasks.close)
            dispatcher = Dispatcher(disable_fsm=True)
            dispatcher.message.outer_middleware(LilBroInbound(get_song))
            dispatcher.edited_message.outer_middleware(LilBroInbound(get_song))
            dispatcher.update.outer_middleware(update_tasks)
            locale_middleware = LanguageMiddleware(database)
            dispatcher.message.outer_middleware(locale_middleware)
            dispatcher.callback_query.outer_middleware(locale_middleware)
            private_actions = PrivateActions()
            dispatcher.message.outer_middleware(private_actions)
            dispatcher.callback_query.outer_middleware(private_actions)
            channel_updates = ChannelUpdates(database, private_actions)
            dispatcher.channel_post.outer_middleware(channel_updates)
            dispatcher.my_chat_member.outer_middleware(channel_updates)
            dispatcher.include_router(guidance_router)
            dispatcher.include_router(channel_router)
            dispatcher.include_router(taste_router)
            dispatcher.include_router(router)
            chat_service = ChatService(database, RecommendationService(database, providers))
            chat_service.social_bot = bot
            if config.miniapp_url:
                miniapp = await start_server(config.telegram_bot_token, chat_service, workflow,
                                            config.miniapp_host, config.miniapp_port,
                                            bot_username=(await bot.me()).username)
                stack.push_async_callback(miniapp.cleanup)
                await bot.set_chat_menu_button(menu_button=MenuButtonWebApp(
                    text='Open Lil Cusin', web_app=WebAppInfo(url=config.miniapp_url)))
            try:
                await configure_commands(bot)
            except (TelegramNetworkError, TelegramRetryAfter):
                logger.warning('Command menu refresh unavailable; continuing to polling.')
            from .build_info import BUILD_ID
            logger.info("Bot initialized (%s); starting long polling.", BUILD_ID)
            # aiogram handles SIGINT/SIGTERM; cleanup drains handlers first.
            await dispatcher.start_polling(
                bot, allowed_updates=sorted(set(dispatcher.resolve_used_update_types()) | {'edited_message'}),
                close_bot_session=False, handle_as_tasks=True, tasks_concurrency_limit=20,
                submissions=SubmissionService(database), workflow=workflow,
                enrichment=enrichment,
                chat_service=chat_service,
                channel_service=channels,
                get_song=get_song,
                recognition=recognition,
            )
    finally:
        logger.info("Bot stopped; handler tasks, provider sessions and database closed.")


def run() -> int:
    configure_logging()
    try:
        asyncio.run(main())
    except ConfigError as error:
        logger.error("%s", error)
        return 1
    except KeyboardInterrupt:
        pass
    except Exception as error:
        logger.error("Unexpected application error (%s); details omitted for privacy.", type(error).__name__)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
