"""Taste-card participation without requiring the Mini App."""
import asyncio
import re
from urllib.parse import quote

from aiogram.types import BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select

from .catalog import canonical_track, IdentityConflict
from .i18n import tr, language
from .models import ChatControl, User, utc_now
from .submissions import Submitter, parse_search_query, InvalidSubmission
from .taste_cards import CardError, TasteCards
from .providers.common import ProviderError


def public_text(card):
    lines = [card['nickname'], card['taste_id']]
    if card['bio']:
        lines += ['', card['bio']]
    lines += ['', tr('card_songs', n=len(card['songs']))]
    lines += [f"{i}. {song['artist']} — {song['title']}" for i, song in enumerate(card['songs'], 1)]
    if card['current']:
        song = card['current']
        lines += ['', tr('card_current'), f"{song['artist']} — {song['title']}"]
    return '\n'.join(lines)


async def show_card(message, chat, telegram_id):
    card = await TasteCards(chat.database).owner(telegram_id)
    rows = [[InlineKeyboardButton(text=tr('card_image'), callback_data='tc:image')],
            [InlineKeyboardButton(text=tr('invite_list'), callback_data='ci:list')]]
    for i, song in enumerate(card['songs'], 1):
        rows.append([
            InlineKeyboardButton(text=f"{i} · {tr('card_set_current')}", callback_data=f"tc:current:{song['id']}:{card['revision']}"),
            InlineKeyboardButton(text=tr('card_remove'), callback_data=f"tc:remove:{song['id']}:{card['revision']}")])
    if card['current']:
        rows.append([InlineKeyboardButton(text=tr('card_clear_current'), callback_data=f"tc:current:0:{card['revision']}")])
    if card['shared']:
        rows.append([InlineKeyboardButton(text=tr('card_hide'), callback_data=f"tc:hide:0:{card['revision']}")])
        rows.append([InlineKeyboardButton(text=tr('card_rotate'), callback_data=f"tc:askrotate:0:{card['revision']}")])
    visibility = tr('card_shared', date=card['expires_at'][:10]) if card['shared'] else tr('card_private')
    await message.answer(tr('card_title') + '\n\n' + visibility + '\n\n' + tr('card_preview') + '\n' +
                         public_text(card) + '\n\n' + tr('card_intro') + '\n\n' + tr('card_help'),
                         reply_markup=InlineKeyboardMarkup(inline_keyboard=rows) if rows else None, parse_mode=None)


async def view_card(message, chat, token):
    try:
        card = await TasteCards(chat.database).view(token)
        await message.answer(public_text(card) + '\n\n' + tr('card_public_hint') + '\n/tastecard', parse_mode=None,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=tr('invite_compare'), callback_data='ci:preview:'+token)]]))
    except CardError:
        await message.answer(tr('card_unavailable'))


async def share_card(message, cards, telegram_id, action, revision):
    card = await cards.sharing(telegram_id, action, revision)
    if action == 'hide':
        await message.answer(tr('card_private'))
    else:
        me = await message.bot.me()
        url = f"https://t.me/{me.username}?start=taste_{card['share_token']}"
        share = 'https://t.me/share/url?url=' + quote(url, safe='')
        await message.answer(tr('card_visibility') + '\n\n' + url,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text=tr('card_share'), url=share)]]), parse_mode=None)


async def send_image(message, chat, telegram_id):
    from .taste_card_image import portrait
    card = await TasteCards(chat.database).owner(telegram_id)
    image = await portrait(card, language.get())
    rows = []
    if card['shared']:
        me = await message.bot.me()
        rows.append([InlineKeyboardButton(text=tr('invite_compare'),
            url=f"https://t.me/{me.username}?start=compare_{card['share_token']}")])
    else:
        rows.append([InlineKeyboardButton(text=tr('card_publish'), callback_data=f"tc:publish:0:{card['revision']}")])
    await message.answer_photo(BufferedInputFile(image, filename='lilcusin-taste-card.jpg'),
        caption=tr('card_image_shared' if card['shared'] else 'card_image_private') + '\n\n' + tr('card_visibility'),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode=None)


async def search_songs(message, chat, workflow, query):
    user_id = message.from_user.id
    try:
        artist, title = parse_search_query(query)
        async with asyncio.timeout(30):
            candidates, failed = await workflow.search_title(title, artist=artist, discover_lyrics=False)
        tracks = []
        async with chat.database.write() as session:
            for candidate in candidates[:5]:
                try:
                    tracks.append(await canonical_track(session, candidate))
                except IdentityConflict:
                    continue
        if not tracks:
            await message.answer(tr('card_no_matches'));return False
        token = await chat.create_control(user_id, kind='tastecard', tracks=[track.id for track in tracks])
        rows = [[InlineKeyboardButton(text=f"{track.display_artist or track.artist} — {track.display_title or track.title}"[:100],
                    callback_data=f'tc:add:{token}:{track.id}')] for track in tracks]
        sent = await message.answer(tr('card_search_hint'), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
        await chat.bind_control(token, sent.message_id)
        return True
    except InvalidSubmission:
        await message.answer(tr('card_search_hint'))
    except (TimeoutError, ProviderError):
        await message.answer(tr('error'))
    return False


async def command(message, chat_service=None, workflow=None):
    user = message.from_user
    if chat_service is None or user is None or user.is_bot or message.chat.type != 'private':
        return
    await chat_service.ensure_user(Submitter(user.id, user.username, user.full_name, user.language_code))
    cards = TasteCards(chat_service.database)
    parts = (message.text or '').split(maxsplit=1)
    action = parts[0].split('@')[0].lstrip('/')
    value = parts[1] if len(parts) == 2 else ''
    try:
        card = await cards.owner(user.id)
        if action in {'cardname', 'cardbio'}:
            card = await cards.update(user.id, dict(action='edit', revision=card['revision'],
                nickname=value if action == 'cardname' else card['nickname'],
                bio=value if action == 'cardbio' else card['bio']))
        elif action in {'cardshare', 'carddelete'}:
            operation = 'publish' if action == 'cardshare' else 'delete'
            preview = '\n\n' + public_text(card) if operation == 'publish' else ''
            await message.answer(tr('card_confirm_' + operation) + preview + '\n\n' + tr('card_visibility'),
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text=tr('card_confirm'), callback_data=f"tc:{operation}:0:{card['revision']}"),
                    InlineKeyboardButton(text=tr('card_cancel'), callback_data='tc:cancel')]]), parse_mode=None)
            return
        elif action == 'cardhide':
            await share_card(message, cards, user.id, 'hide', card['revision'])
        elif action == 'cardimage':
            await send_image(message, chat_service, user.id)
            return
        elif action == 'cardsearch':
            await search_songs(message, chat_service, workflow, value)
            return
        await show_card(message, chat_service, user.id)
    except CardError as error:
        await message.answer(tr(str(error)))
    except InvalidSubmission:
        await message.answer(tr('card_search_hint'))
    except (TimeoutError, ProviderError):
        await message.answer(tr('error'))


async def callback(query, chat_service=None):
    if (chat_service is None or not isinstance(query.message, Message) or query.from_user.is_bot
            or query.message.chat.type != 'private' or query.message.chat.id != query.from_user.id):
        await query.answer(tr('card_stale'))
        return
    await query.answer()
    data = query.data or ''
    if data == 'tc:image':
        await send_image(query.message, chat_service, query.from_user.id)
        return
    if data == 'tc:cancel':
        await query.message.edit_reply_markup(reply_markup=None)
        return
    cards = TasteCards(chat_service.database)
    user_id = query.from_user.id
    try:
        match = re.fullmatch(r'tc:add:([a-f0-9]{32}):([1-9][0-9]{0,17})', data)
        if match:
            token, track_id = match.groups()
            async with chat_service.database.sessions() as session:
                grant = await session.scalar(select(ChatControl).join(User).where(
                    User.telegram_user_id == user_id, ChatControl.token == token,
                    ChatControl.message_id == query.message.message_id, ChatControl.expires_at > utc_now()))
                if grant is None:
                    raise CardError('card_stale')
            card = await cards.owner(user_id)
            await cards.update(user_id, dict(action='add', revision=card['revision'], track_id=int(track_id), token=token))
        else:
            match = re.fullmatch(r'tc:(current|remove|publish|hide|askrotate|rotate|delete):([0-9]{1,18}):([0-9]{1,12})', data)
            if not match:
                raise CardError('card_invalid')
            action, track_id, revision = match.groups()
            revision = int(revision)
            if action == 'askrotate':
                await query.message.answer(tr('card_confirm_rotate'), reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text=tr('card_confirm'), callback_data=f'tc:rotate:0:{revision}'),
                    InlineKeyboardButton(text=tr('card_cancel'), callback_data='tc:cancel')]]))
                return
            if action in {'current', 'remove'}:
                await cards.update(user_id, dict(action=action, revision=revision, track_id=int(track_id) or None))
            elif action == 'delete':
                await cards.sharing(user_id, action, revision)
                await query.message.answer(tr('card_deleted'))
                return
            else:
                await share_card(query.message, cards, user_id, action, revision)
        if match and data.startswith('tc:add:'):
            from .onboarding import after_pick
            if await after_pick(query.message, chat_service, user_id):
                return
        await show_card(query.message, chat_service, user_id)
    except CardError as error:
        await query.message.answer(tr(str(error)))
