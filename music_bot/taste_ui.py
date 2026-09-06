"""Owner-scoped Telegram views for the compact taste dashboard."""

import re

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardButton as Button, InlineKeyboardMarkup, Message

from . import messages as M
from .chat_ui import clean, dismiss, main_menu
from .workflow import FlowError, RATINGS

router = Router()


def taste_keyboard(token):
    def key(text, action):
        return Button(text=text, callback_data=f't:{token}:{action}')
    return InlineKeyboardMarkup(inline_keyboard=[
        [key(M.TASTE_ARTISTS, 'artists'), key(M.TASTE_TAGS, 'tags')],
        [key(M.TASTE_CLUSTERS, 'clusters'), key(M.TASTE_RECENT, 'recent')],
        [key(M.TASTE_CORRECT, 'correct')], [key(M.TASTE_RESET, 'reset')],
        [key(M.MAIN_MENU, 'menu')],
    ])


def names(rows):
    return ', '.join(clean(display or normalized, 70) for display, normalized, _ in rows) or M.UNKNOWN


def overview(data):
    counts = data['counts']
    return M.TASTE_TEXT.format(
        artists=names(data['artists']), tags=names(data['tags']), songs=data['songs'],
        signals=data['signals'], channels=data['channels'], explanation=(
            M.TASTE_EXPLANATION + '\n' + (M.TASTE_RELIABILITY_GOOD if data['reliable'] else M.TASTE_RELIABILITY_LOW)),
        **{value: counts.get(value, 0) for value in RATINGS})


async def show_taste(message, service, user_id):
    data = await service.taste_summary(user_id)
    if data is None:
        await message.answer(M.TASTE_EMPTY, reply_markup=main_menu())
        return
    token = await service.create_control(user_id, kind='taste')
    sent = await message.answer(overview(data), parse_mode=None, reply_markup=taste_keyboard(token))
    await service.bind_control(token, sent.message_id)


def back(token):
    return InlineKeyboardMarkup(inline_keyboard=[[Button(text=M.BACK, callback_data=f't:{token}:overview')],
                                                  [Button(text=M.MAIN_MENU, callback_data=f't:{token}:menu')]])


async def edit(message, text, keyboard):
    try:
        await message.edit_text(text, parse_mode=None, reply_markup=keyboard)
    except TelegramBadRequest as error:
        if 'message is not modified' not in error.message.lower():
            raise


async def callback(query: CallbackQuery, chat_service):
    match = re.fullmatch(r't:([a-f0-9]{32}):(overview|artists|tags|clusters|recent|correct|pick[0-9]|reset|confirmreset|menu|cancel)', query.data or '')
    if (not match or not isinstance(query.message, Message) or query.message.chat.type != 'private'
            or query.message.chat.id != query.from_user.id or query.from_user.is_bot):
        await query.answer(M.STALE)
        return
    token, action = match.groups()
    try:
        payload = await chat_service.taste_control(token, query.from_user.id, query.message.message_id)
        data = await chat_service.taste_summary(query.from_user.id)
        if action == 'menu':
            await dismiss(query.message)
        elif action in {'overview', 'cancel'}:
            await chat_service.taste_control(token, query.from_user.id, query.message.message_id,
                                            state={'view': 'overview'})
            await edit(query.message, overview(data), taste_keyboard(token))
        elif action == 'artists':
            await edit(query.message, 'Explicit from ratings: ' + names(data['artists']) + '\n\nInferred from playlists: ' + names(data['inferred_artists']), back(token))
        elif action == 'tags':
            await edit(query.message, 'Explicit from ratings: ' + names(data['tags']) + '\n\nInferred from playlists: ' + names(data['inferred_tags']), back(token))
        elif action == 'clusters':
            clusters = names(data['tags'][:3])
            await edit(query.message, 'Current taste clusters: ' + clusters + '\n\n' + (M.TASTE_RELIABILITY_GOOD if data['reliable'] else M.TASTE_RELIABILITY_LOW), back(token))
        elif action == 'recent':
            marks = {'love': '❤️', 'like': '👍', 'neutral': '😐', 'dislike': '👎'}
            rows = []
            for source, _, value, artist_display, artist, title_display, title in data['recent']:
                marker = marks.get(value, '📻') if source == 'rating' else '📻'
                rows.append(f"{marker} {clean(artist_display or artist, 70)} — {clean(title_display or title, 90)}")
            await edit(query.message, 'Recent learning signals:\n' + ('\n'.join(rows) or M.UNKNOWN), back(token))
        elif action == 'correct':
            targets = await chat_service.taste_targets(query.from_user.id)
            await chat_service.taste_control(token, query.from_user.id, query.message.message_id,
                                            state={'view': 'correct', 'targets': targets})
            keys = [[Button(text=display[:50], callback_data=f't:{token}:pick{i}')]
                    for i, (_, _, display) in enumerate(targets)]
            keys.append([Button(text=M.CANCEL, callback_data=f't:{token}:cancel')])
            await edit(query.message, M.TASTE_CORRECT_HELP, InlineKeyboardMarkup(inline_keyboard=keys))
        elif action.startswith('pick'):
            payload = await chat_service.taste_control(token, query.from_user.id, query.message.message_id,
                                                      require='correct', state={'view': 'overview'})
            targets = payload.get('targets', [])
            index = int(action[4:])
            if index >= len(targets):
                raise FlowError('stale')
            await chat_service.reduce_taste(query.from_user.id, *targets[index][:2])
            await edit(query.message, M.TASTE_CORRECTED, back(token))
        elif action == 'reset':
            await chat_service.taste_control(token, query.from_user.id, query.message.message_id,
                                            state={'view': 'reset'})
            keys = [[Button(text=M.RESET_CONFIRM, callback_data=f't:{token}:confirmreset')],
                    [Button(text=M.CANCEL, callback_data=f't:{token}:cancel')]]
            await edit(query.message, M.TASTE_RESET_CONFIRM, InlineKeyboardMarkup(inline_keyboard=keys))
        elif action == 'confirmreset':
            await chat_service.taste_control(token, query.from_user.id, query.message.message_id,
                                            require='reset', state={'view': 'overview'})
            await chat_service.reset_learning(query.from_user.id)
            await edit(query.message, M.TASTE_RESET_DONE, back(token))
        await query.answer(M.WORKING)
    except FlowError:
        await query.answer(M.STALE)
    except TelegramBadRequest:
        await query.answer(M.FLOW_FAILED)


router.callback_query.register(callback, F.data.startswith('t:'))
