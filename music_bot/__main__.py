import asyncio
import logging
import aiohttp
from contextlib import AsyncExitStack

from aiogram import Bot, Dispatcher

from .config import ConfigError, load_config
from .database import Database
from .handlers import router
from .submissions import SubmissionService
from .cache import CachedProviders
from .enrichment import Enrichment
from .providers.lastfm import LastFMClient
from .providers.musicbrainz import MusicBrainzClient
from .workflow import Workflow
from .lifecycle import UpdateTasks
from .audio.service import AudioAnalysisService

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
            bot = Bot(token=config.telegram_bot_token)
            stack.push_async_callback(bot.session.close)
            database = Database()
            stack.push_async_callback(database.close)
            await database.initialize()
            provider_session = await stack.enter_async_context(aiohttp.ClientSession())
            providers = CachedProviders(database, LastFMClient(provider_session, config.lastfm_api_key),
                                        MusicBrainzClient(provider_session))
            enrichment = Enrichment(database, providers)
            stack.push_async_callback(enrichment.close)
            audio_analysis = AudioAnalysisService(database, bot, config)
            stack.push_async_callback(audio_analysis.close)
            await audio_analysis.initialize()
            update_tasks = UpdateTasks()
            stack.push_async_callback(update_tasks.close)
            dispatcher = Dispatcher(disable_fsm=True)
            dispatcher.update.outer_middleware(update_tasks)
            dispatcher.include_router(router)
            logger.info("Bot initialized; starting long polling.")
            # aiogram handles SIGINT/SIGTERM; cleanup drains handlers first.
            await dispatcher.start_polling(
                bot, allowed_updates=dispatcher.resolve_used_update_types(),
                close_bot_session=False, handle_as_tasks=True, tasks_concurrency_limit=20,
                submissions=SubmissionService(database), workflow=Workflow(database, providers),
                enrichment=enrichment,
                audio_analysis=audio_analysis,
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
