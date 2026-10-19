"""Telegram navigation; persistence and scoring remain in application services."""

import logging

from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import Message, InlineKeyboardMarkup

from . import messages as M
from .i18n import menu_action
from .guidance import show_guide, language_picker
from .chat_ui import button, card_keyboard, dismiss, main_menu, parse_control, show_card, show_recommendations, recovery_keyboard
from .bot_copy import text as copy
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
    elif action in {'send', 'rate'}:
        await message.answer(copy('rate_prompt'), reply_markup=main_menu())
    elif action == 'search':
        await message.answer(M.SEND_SONG_PROMPT, reply_markup=main_menu())
    elif action == 'taste':
        from .taste_ui import show_taste
        await show_taste(message, chat_service, user.id)
    elif action == 'profile':
        counts, shown = await chat_service.profile(user.id)
        await message.answer(M.PROFILE_TEXT.format(**{value: counts.get(value, 0) for value in RATINGS}, shown=shown), reply_markup=main_menu())
    elif action == 'privacy':
        await message.answer(M.PRIVACY + '\n\n' + copy('learning_privacy') + '\n\nSearch text is sent to music catalogues (Last.fm, MusicBrainz and Deezer), without Telegram identifiers. '
            'Weak lyric-fragment searches may also send the phrase to YouTube or the configured lyrics provider. '
            'Existing private search input is removed by /forgetme; transient phrase results expire within 15 minutes. '
            'Get song sends artist/title searches to YouTube and temporarily downloads audio. '
            'When the operator enables the Lil Bro source, the confirmed YouTube link is sent to @musicbehbot; '
            'that provider may retain its copy and request history. '
            'Private job records and Telegram audio references expire by the configured retention period (default 7 days). '
            'Your chosen and rejected recordings are also saved privately for that period. '
            '/forgetme removes these personal records and cancels pending deliveries; shared source metadata and Telegram messages may remain.'
            '\n\n/tastecard lets you deliberately select a separate public card. /cardhide revokes its link; '
            '/carddelete removes the card without removing your ratings. /forgetme also removes the card. '
            'Copies and forwarded messages cannot be recalled. '
            '\n\nConsented comparison uses selected favorites only, not private ratings. '
            '/swaps contains chosen songs, optional notes and explicit reactions. /savedsongs lists your saves. '
            '/socialsettings controls Telegram alerts (off by default, at most three in 24 hours). '
            'Blocking or withdrawing consent stops pending swaps and alerts. Reports include the reported note '
            'for operator review. Reports over 90 days old are removed on the next social access; either account deletion removes them too. '
            'Expired swap notes are cleared on participant access; old exchanges are removed seven days after expiry. '
            'Deleting an exchange clears its note but keeps personal saves and explicit ratings; '
            '/forgetme removes the account and its social records.', reply_markup=main_menu())
    elif action == 'forgetme':
        token = await chat_service.create_control(user.id, kind='forget')
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[button(token, 'delete', M.FORGET_YES), button(token, 'keep', M.FORGET_NO)]])
        sent = await message.answer(M.FORGET_CONFIRM, reply_markup=keyboard)
        await chat_service.bind_control(token, sent.message_id)
    elif action == 'settings':
        await language_picker(message)
        from aiogram.types import InlineKeyboardButton
        from .i18n import tr
        await message.answer(M.SETTINGS_TEXT, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text=tr('social_settings'),callback_data='sc:settings')]]))
    elif action == 'help':
        await message.answer(copy('guide'), reply_markup=main_menu())
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
        await query.answer(copy('feedback_' + action) if action in {'save', 'unsave', 'known', 'notforme'}
                           else M.RATING_SAVED if action in RATINGS else M.WORKING)
        acknowledged = True
        if action in RATINGS:
            try:
                await query.message.edit_reply_markup(reply_markup=card_keyboard(token, action, payload.get('submitted', False), rating_mode=payload.get('kind') == 'rating'))
            except TelegramBadRequest:
                pass
            from .onboarding import after_rating
            await after_rating(query.message, chat_service, query.from_user.id)
            chat_service.recommendations.queue.warm(query.from_user.id)
        elif action in {'get', 'versions'}:
            from .youtube_fetch import FetchError
            if get_song is None:
                await query.message.answer('Get song is unavailable.')
            else:
                await get_song.begin(query.message, query.from_user.id, track.id, other_versions=action == 'versions')
        elif action == 'rate':
            if payload.get('kind') in {'card', 'rating'}:
                await query.message.edit_reply_markup(reply_markup=card_keyboard(token, expanded=True, submitted=payload.get('submitted', False)))
            else:
                await show_card(query.message, chat_service, query.from_user.id, track, payload['seed'], rating_mode=True)
        elif action == 'details':
            await show_card(query.message, chat_service, query.from_user.id, track, payload['seed'])
        elif action in {'save', 'unsave', 'known', 'notforme'}:
            if payload.get('kind') == 'card':
                await query.message.edit_reply_markup(reply_markup=card_keyboard(token,
                    submitted=payload.get('submitted', False), saved=payload.get('saved', False)))
            chat_service.recommendations.queue.warm(query.from_user.id)
        elif action in {'next', 'more', 'foryou'}:
            seed = track.id if action == 'more' else payload['seed'] if action == 'next' else None
            await show_recommendations(query.message, chat_service, query.from_user.id, seed)
        elif action == 'menu':
            await dismiss(query.message)
        elif action == 'delete':
            if get_song is not None:
                await get_song.cancel(query.from_user.id, forget=True)
            await chat_service.forget(query.from_user.id)
            if workflow is not None and workflow.lyrics is not None:
                workflow.lyrics.clear()
            if workflow is not None:
                workflow.searches.clear()
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
        if isinstance(query.message, Message) and query.message.chat.type == 'private' and query.message.chat.id == query.from_user.id:
            await query.message.answer(copy('stale'), reply_markup=recovery_keyboard())
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
