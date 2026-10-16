"""Telegram navigation; persistence and scoring remain in application services."""

import logging

from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import Message, InlineKeyboardMarkup

from . import messages as M
from .i18n import menu_action
from .guidance import show_guide, language_picker
from .chat_ui import button, card_keyboard, dismiss, main_menu, parse_control, show_card, show_recommendations
from .submissions import Submitter
from .workflow import FlowError, RATINGS

logger = logging.getLogger('music_bot')


def private(message):
    return message.chat.type == 'private' and message.from_user is not None and not message.from_user.is_bot


async def command(message, chat_service):
    if not private(message):
        await message.answer(M.PRIVATE_ONLY)
        return
    user = message.from_user
    action = menu_action(message.text)
    if action is None:
        action = message.text.split()[0].split('@')[0].lstrip('/')
    if action in {'recommend', 'taste', 'forgetme'}:
        await chat_service.ensure_user(Submitter(user.id, user.username, user.full_name, user.language_code))
    if action == 'recommend':
        await show_recommendations(message, chat_service, user.id)
    elif action == 'send':
        await message.answer(M.SEND_SONG_PROMPT, reply_markup=main_menu())
    elif action == 'taste':
        from .taste_ui import show_taste
        await show_taste(message, chat_service, user.id)
    elif action == 'profile':
        counts, shown = await chat_service.profile(user.id)
        await message.answer(M.PROFILE_TEXT.format(**{value: counts.get(value, 0) for value in RATINGS}, shown=shown), reply_markup=main_menu())
    elif action == 'privacy':
        await message.answer(M.PRIVACY + '\n\nSearch text is sent to music catalogues (Last.fm, MusicBrainz and Deezer), without Telegram identifiers. '
            'Weak lyric-fragment searches may also send the phrase to YouTube or the configured lyrics provider. '
            'Existing private search input is removed by /forgetme; transient phrase results expire within 15 minutes. '
            'Get song sends artist/title searches to YouTube and temporarily downloads audio. '
            'When the operator enables the Lil Bro source, the confirmed YouTube link is sent to @musicbehbot; '
            'that provider may retain its copy and request history. '
            'Private job records and Telegram audio references expire by the configured retention period (default 7 days). '
            'Your chosen and rejected recordings are also saved privately for that period. '
            '/forgetme removes these personal records and cancels pending deliveries; shared source metadata and Telegram messages may remain.', reply_markup=main_menu())
    elif action == 'forgetme':
        token = await chat_service.create_control(user.id, kind='forget')
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[button(token, 'delete', M.FORGET_YES), button(token, 'keep', M.FORGET_NO)]])
        sent = await message.answer(M.FORGET_CONFIRM, reply_markup=keyboard)
        await chat_service.bind_control(token, sent.message_id)
    elif action == 'settings':
        await language_picker(message)
        await message.answer(M.SETTINGS_TEXT, reply_markup=main_menu())
    elif action == 'help':
        await show_guide(message)
    else:
        await message.answer(M.HELP if action == 'help' else M.UNSUPPORTED, reply_markup=main_menu())


async def callback(query, chat_service, get_song=None, workflow=None):
    acknowledged = False
    try:
        data = parse_control(query.data)
        if (data is None or not isinstance(query.message, Message) or query.message.chat.type != 'private'
                or query.message.chat.id != query.from_user.id or query.from_user.is_bot):
            raise FlowError('stale')
        token, action, index = data
        payload, track = await chat_service.control(token, query.from_user.id, query.message.message_id,
                action, index, rating=action if action in RATINGS else None)
        await query.answer(M.RATING_SAVED if action in RATINGS else M.WORKING)
        acknowledged = True
        if action in RATINGS:
            try:
                await query.message.edit_reply_markup(reply_markup=card_keyboard(token, action, payload.get('submitted', False)))
            except TelegramBadRequest:
                pass
        elif action == 'get':
            from .youtube_fetch import FetchError
            if get_song is None:
                await query.message.answer('Get song is unavailable.')
            else:
                await query.message.answer('Finding your song... You can /cancel while waiting.')
                try:
                    await get_song.request(query.from_user.id, track.id)
                except FetchError as error:
                    await query.message.answer(str(error))
        elif action == 'rate':
            await show_card(query.message, chat_service, query.from_user.id, track, payload['seed'])
        elif action in {'next', 'more', 'foryou'}:
            seed = track.id if action == 'more' else payload['seed'] if action == 'next' else None
            await show_recommendations(query.message, chat_service, query.from_user.id, seed)
            if payload.get('kind') == 'card':
                await dismiss(query.message)
        elif action == 'menu':
            await dismiss(query.message)
        elif action == 'delete':
            if get_song is not None:
                await get_song.cancel(query.from_user.id, forget=True)
            await chat_service.forget(query.from_user.id)
            if workflow is not None and workflow.lyrics is not None:
                workflow.lyrics.clear()
            await query.message.answer(M.FORGET_DONE, reply_markup=main_menu())
        else:
            await query.message.answer(M.FORGET_CANCELLED if action == 'keep' else M.MAIN_MENU, reply_markup=main_menu())
        if action in {'delete', 'keep'}:
            try:
                await query.message.edit_reply_markup(reply_markup=None)
            except TelegramBadRequest:
                pass
    except FlowError:
        if not acknowledged:
            await query.answer(M.STALE)
            acknowledged = True
    except (TelegramBadRequest, TelegramForbiddenError):
        pass
    except Exception:
        logger.error('Chat action failed; details omitted for privacy.')
        if acknowledged:
            await query.message.answer(M.FLOW_FAILED)
    finally:
        if not acknowledged:
            try:
                await query.answer(M.FLOW_FAILED)
            except (TelegramBadRequest, TelegramForbiddenError):
                pass
