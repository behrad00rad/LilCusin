"""Plain-text Telegram lists, compact controls and conservative catalogue links."""

import re
import html
from urllib.parse import quote
from urllib.parse import urlsplit

from aiogram.types import InlineKeyboardButton as Button, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, LinkPreviewOptions

from . import messages as M
from .i18n import localized_reason
from .matching import identity_key
from .config import normalized_lil_bro_username
from .bot_copy import text as copy
from aiogram.exceptions import TelegramBadRequest


async def dismiss(message):
    """Remove a finished prompt; older messages can still be made inert."""
    try:
        await message.delete()
    except TelegramBadRequest:
        try:
            await message.edit_text(M.DONE, reply_markup=None)
        except TelegramBadRequest:
            await message.edit_reply_markup(reply_markup=None)


def main_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text=copy('rate_song'), style='primary'), KeyboardButton(text=M.MENU_FOR_YOU)],
        [KeyboardButton(text=M.MENU_PROFILE), KeyboardButton(text=M.MENU_CHANNELS)],
        [KeyboardButton(text=M.MENU_SETTINGS), KeyboardButton(text=M.MENU_HELP)],
    ], resize_keyboard=True)


def cancel_keyboard(request_id=None):
    data = f'cancelreq:{request_id}' if request_id else 'nav:cancel'
    return InlineKeyboardMarkup(inline_keyboard=[[Button(text=copy('cancel'), callback_data=data, style='danger')]])


def recovery_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[[
        Button(text=copy('search'), callback_data='nav:search'),
        Button(text=copy('recommend'), callback_data='nav:recommend')]])


def button(token, action, text, index=None):
    suffix = f':{index}' if index is not None else ''
    style = {'get': 'primary', 'love': 'success', 'like': 'success', 'dislike': 'danger',
             'delete': 'danger', 'menu': 'danger'}.get(action)
    return Button(text=text, callback_data=f'q:{token}:{action}{suffix}', style=style)


def parse_control(data):
    if not isinstance(data, str) or len(data.encode()) > 64:
        return None
    match = re.fullmatch(r'q:([a-f0-9]{32}):(get|versions|rate|details|more|love|like|neutral|dislike|save|unsave|known|notforme):([0-4])', data)
    if match:
        return match[1], match[2], int(match[3])
    match = re.fullmatch(r'q:([a-f0-9]{32}):(next|foryou|menu|delete|keep)', data)
    if match:
        return match[1], match[2], None
    return None


def safe_url(value, artwork=False):
    if artwork and isinstance(value,str) and '2a96cbd8b46e442fc41c2b86b821562f' in value:
        return None
    if not isinstance(value, str) or len(value) > 1000 or any(c.isspace() or ord(c) < 32 for c in value):
        return None
    try:
        url = urlsplit(value)
        hosts = {'lastfm.freetls.fastly.net', 'lastfm-img.freetls.fastly.net', 'lastfm-img2.akamaized.net'} if artwork else {'www.last.fm', 'last.fm', 'musicbrainz.org'}
        if artwork and re.fullmatch(r'is[1-5]-ssl\.mzstatic\.com', url.hostname or ''):
            hosts.add(url.hostname)  # Apple image CDN used in Shazam recognition responses.
        if (url.scheme != 'https' or url.hostname not in hosts or url.username or url.password
                or url.port not in (None, 443) or url.query or url.fragment or '\\' in value):
            return None
        return value
    except ValueError:
        return None


def catalogue(row):
    if link := safe_url(row.external_ids.get('lastfm')):
        return link
    mbid = row.external_ids.get('musicbrainz', '')
    if re.fullmatch(r'[a-fA-F0-9]{8}(?:-[a-fA-F0-9]{4}){3}-[a-fA-F0-9]{12}', mbid):
        return 'https://musicbrainz.org/recording/' + mbid
    return None


def clean(value, limit=120):
    return ' '.join(str(value or '').split())[:limit]


def lil_bro_url(artist, title, username=None):
    artist, title = clean(artist, 85), clean(title, 85)
    username = normalized_lil_bro_username(username)
    if not artist or not title or not username:
        return None
    query = quote(f'{artist} {title}', safe='')
    return f"https://t.me/{username}?text={query}"


def list_content(rows, token, seed_track=None):
    title = M.FOR_YOU_TITLE if seed_track is None else M.SIMILAR_TITLE.format(
        artist=clean(seed_track.display_artist or seed_track.artist, 70),
        title=clean(seed_track.display_title or seed_track.title, 70))
    lines, keyboard = [html.escape(title)], []
    for index, row in enumerate(rows):
        artist, song_title = clean(row.artist, 85), clean(row.title, 85)
        label = html.escape(f'{artist} — {song_title}')
        entry = f'{index + 1}. {label}'
        if row.album:
            entry += '\n' + html.escape(M.ALBUM_LINE.format(album=clean(row.album, 85)))
        entry += '\n' + html.escape(clean(localized_reason(row.reason), 120))
        lines.append(entry)
        actions = [button(token, 'get', '↓ ' + clean(song_title, 22), index),
                   button(token, 'rate', '♡', index), button(token, 'details', copy('options'), index),
                   button(token, 'save', copy('save'), index)]
        keyboard.append(actions)
    keyboard.append([button(token, 'next', M.ANOTHER_LIST), button(token, 'menu', copy('close'))])
    if seed_track is not None:
        keyboard.append([button(token, 'foryou', M.AFTER_FOR_YOU)])
    return '\n\n'.join(lines), InlineKeyboardMarkup(inline_keyboard=keyboard)


def card_keyboard(token, selected=None, submitted=False, expanded=False, rating_mode=False, saved=False):
    if rating_mode:
        return InlineKeyboardMarkup(inline_keyboard=[[
            button(token, value, M.rating_label(value, selected), 0)
            for value in ('love', 'like', 'neutral', 'dislike')],
            [button(token, 'more', copy('similar'), 0), button(token, 'menu', copy('close'))]])
    keyboard = [[button(token, 'get', copy('get'), 0)],
                [button(token, 'more', copy('similar'), 0), button(token, 'versions', copy('versions'), 0)]]
    for values in (('love', 'like'), ('neutral', 'dislike')):
        keyboard.append([button(token, value, M.rating_label(value, selected), 0) for value in values])
    keyboard.append([button(token, 'foryou' if submitted else 'next', M.AFTER_FOR_YOU if submitted else M.CONTINUE),
                     button(token, 'menu', copy('close'))])
    keyboard.append([button(token, 'unsave' if saved else 'save', copy('unsave' if saved else 'save'), 0)])
    keyboard.append([button(token, 'notforme', copy('notforme'), 0), button(token, 'known', copy('known'), 0)])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


async def show_card(message, service, user_id, track, seed=None, rating=None, submitted=False, edit_existing=False, rating_mode=False):
    saved = await service.is_saved(user_id, track.id)
    token = await service.create_control(user_id, tracks=[track.id], seed=seed, kind='rating' if rating_mode else 'card', submitted=submitted)
    text = copy('song', artist=clean(track.display_artist or track.artist), title=clean(track.display_title or track.title))
    if rating_mode:
        text += '\n\n' + M.RATING_QUESTION
    if edit_existing:
        await message.edit_text(text, parse_mode=None, reply_markup=card_keyboard(token, rating, submitted, rating_mode=rating_mode, saved=saved))
        sent = message
    else:
        sent = await message.answer(text, parse_mode=None, reply_markup=card_keyboard(token, rating, submitted, rating_mode=rating_mode, saved=saved))
    await service.bind_control(token, sent.message_id)


async def show_recommendations(message, service, user_id, seed=None):
    seed_track = await service.track(seed) if seed is not None else None
    if seed is not None and seed_track is None:
        await message.answer(M.NO_RECOMMENDATIONS, reply_markup=main_menu())
        return
    if seed is None:
        result = await service.recommendations.queue.reserve(user_id, limit=5)
    else:
        result = await service.recommendations.recommend_similar_to_track(user_id, seed, limit=5)
    # Defensive presentation dedup; history always describes the exact displayed rows.
    rows, ids, names, external = [], set(), set(), set()
    for row in result.recommendations:
        name = identity_key(row.artist, row.title)
        identifiers = set(row.external_ids.items())
        if row.track_id in ids or name in names or identifiers & external:
            continue
        rows.append(row)
        ids.add(row.track_id)
        names.add(name)
        external.update(identifiers)
        if len(rows) == 5:
            break
    if not rows:
        if seed is None and result.batch_id:
            await service.recommendations.queue.release(user_id, result.batch_id)
        await message.answer(copy('recommend_start' if result.status == 'insufficient_preferences' else 'recommend_empty')
                             if seed is None else M.NO_RECOMMENDATIONS,
                             reply_markup=main_menu())
        return
    try:
        token = await service.create_control(user_id, tracks=[row.track_id for row in rows], seed=seed)
        text, keyboard = list_content(rows, token, seed_track)
        sent = await message.answer(text, parse_mode='HTML', reply_markup=keyboard,
                                   link_preview_options=LinkPreviewOptions(is_disabled=True))
        await service.record_displayed(user_id, rows, token, seed, queue_batch=result.batch_id if seed is None else None)
        await service.bind_control(token, sent.message_id)
    finally:
        if seed is None and result.batch_id:
            await service.recommendations.queue.release(user_id, result.batch_id)
    if seed is None:
        service.recommendations.queue.warm(user_id)
