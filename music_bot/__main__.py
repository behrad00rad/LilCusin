import asyncio
import logging
import aiohttp
from contextlib import AsyncExitStack

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.types import BotCommand, BotCommandScopeAllPrivateChats, MenuButtonWebApp, WebAppInfo

from .config import ConfigError, load_config
from .database import Database
from .handlers import router
from .submissions import SubmissionService
from .cache import CachedProviders
from .enrichment import Enrichment
from .providers.lastfm import LastFMClient
from .providers.musicbrainz import MusicBrainzClient
from .workflow import Workflow
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
            providers = CachedProviders(database, LastFMClient(provider_session, config.lastfm_api_key),
                                        MusicBrainzClient(provider_session))
            enrichment = Enrichment(database, providers)
            stack.push_async_callback(enrichment.close)
            workflow = Workflow(database, providers)
            channels = ChannelService(database, workflow)
            await channels.initialize()
            update_tasks = UpdateTasks()
            stack.push_async_callback(update_tasks.close)
            dispatcher = Dispatcher(disable_fsm=True)
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
            if config.miniapp_url:
                miniapp = await start_server(config.telegram_bot_token, chat_service, workflow,
                                            config.miniapp_host, config.miniapp_port)
                stack.push_async_callback(miniapp.cleanup)
                await bot.set_chat_menu_button(menu_button=MenuButtonWebApp(
                    text='Open Lil Cusin', web_app=WebAppInfo(url=config.miniapp_url)))
            await configure_commands(bot)
            logger.info("Bot initialized; starting long polling.")
            # aiogram handles SIGINT/SIGTERM; cleanup drains handlers first.
            await dispatcher.start_polling(
                bot, allowed_updates=dispatcher.resolve_used_update_types(),
                close_bot_session=False, handle_as_tasks=True, tasks_concurrency_limit=20,
                submissions=SubmissionService(database), workflow=workflow,
                enrichment=enrichment,
                chat_service=chat_service,
                channel_service=channels,
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
    except Exception:
        logger.error("Unexpected application error; details omitted for privacy.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
