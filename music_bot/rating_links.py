"""Public song references open fresh, recipient-owned rating controls."""
import asyncio
import re

from aiogram.types import MessageEntity

from .bot_copy import text as copy
from .i18n import language

PAYLOAD = re.compile(r'rate_([1-9][0-9]{0,17})\Z')
USERNAME = re.compile(r'[A-Za-z0-9_]{5,32}\Z')


async def bot_caption(bot, caption='', *, locale=None):
    caption = (caption + '  ' if caption else '') + '🦉 lilcusin'
    result = {'caption': caption, 'parse_mode': None}
    try:
        # Bot.me caches its result; a presentation lookup must not delay audio.
        async with asyncio.timeout(2):
            identity = await bot.me()
        username = identity.username
        if not isinstance(username, str) or not USERNAME.fullmatch(username):
            return result
        offset = len(caption[:caption.index('🦉 lilcusin')].encode('utf-16-le')) // 2
        result['caption_entities'] = [MessageEntity(type='text_link', offset=offset, length=11,
            url=f'https://t.me/{username}')]
    except Exception:
        pass  # Keep /rate usable even if bot identity is temporarily unavailable.
    return result


async def audio_caption(bot, track_id, *, locale=None, compact=False):
    caption = '⭐ rate  📝 lyrics'
    result = await bot_caption(bot, caption, locale=locale)
    if result.get('caption_entities'):
        url = result['caption_entities'][0].url
        rate_offset = len(caption[:caption.index('⭐ rate')].encode('utf-16-le')) // 2
        lyrics_offset = len(caption[:caption.index('📝 lyrics')].encode('utf-16-le')) // 2
        result['caption_entities'] = [MessageEntity(type='text_link', offset=rate_offset, length=6,
            url=f'{url}?start=rate_{track_id}'),
            MessageEntity(type='text_link', offset=lyrics_offset, length=9,
                url=f'{url}?start=lyrics_{track_id}'), *result['caption_entities']]
    return result


async def open_rating(message, service, payload):
    from .chat_ui import main_menu, show_card
    match = PAYLOAD.fullmatch(payload)
    track = await service.track(int(match[1])) if match else None
    if track is None:
        await message.answer(copy('stale'), reply_markup=main_menu())
        return
    # A public reference grants no write access. Each reader receives fresh
    # owner/message-bound controls; only their explicit button press saves a rating.
    await show_card(message, service, message.from_user.id, track, rating_mode=True)
