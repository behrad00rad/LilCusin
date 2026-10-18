"""Run the Mini App independently, sharing the bot database without polling."""
import asyncio
import os
from contextlib import AsyncExitStack

import aiohttp
from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer

from .cache import CachedProviders
from .chat_service import ChatService
from .config import load_config
from .database import Database
from .miniapp import start_server
from .providers.lastfm import LastFMClient
from .providers.musicbrainz import MusicBrainzClient
from .recommendations import RecommendationService
from .workflow import Workflow


async def main():
    config = load_config()
    async with AsyncExitStack() as stack:
        database = Database()
        stack.push_async_callback(database.close)
        await database.initialize()
        session = await stack.enter_async_context(aiohttp.ClientSession())
        # Preserve provider relay support on installations that configure it.
        relay = getattr(config, 'music_api_base_url', None)
        if relay:
            providers = CachedProviders(database, LastFMClient(
                session, config.lastfm_api_key, relay + '/lastfm/2.0/', config.music_api_relay_secret),
                MusicBrainzClient(session, relay + '/musicbrainz/ws/2/recording/', config.music_api_relay_secret))
        else:
            providers = CachedProviders(database, LastFMClient(session, config.lastfm_api_key), MusicBrainzClient(session))
        workflow = Workflow(database, providers)
        chat = ChatService(database, RecommendationService(database, providers))
        identity = Bot(config.telegram_bot_token, session=AiohttpSession(
            api=TelegramAPIServer.from_base(config.telegram_api_base_url)))
        stack.push_async_callback(identity.session.close)
        chat.social_bot = identity
        bot_username = (await identity.me()).username
        runner = await start_server(config.telegram_bot_token, chat, workflow,
                                    os.environ.get('MINIAPP_HOST', '127.0.0.1'),
                                    int(os.environ.get('MINIAPP_PORT', '8091')),
                                    bot_username=bot_username)
        stack.push_async_callback(runner.cleanup)
        print('Lil Cusin Mini App ready; Telegram polling is handled by the existing bot.', flush=True)
        await asyncio.Event().wait()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception:
        print('Mini App startup failed; private error details omitted.', flush=True)
        raise SystemExit(1)
