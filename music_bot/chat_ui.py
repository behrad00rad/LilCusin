"""Plain-text Telegram lists, compact controls and conservative catalogue links."""

import re
import html
from urllib.parse import quote
from urllib.parse import urlsplit

from aiogram.types import InlineKeyboardButton as Button, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, LinkPreviewOptions

from . import messages as M
from .matching import identity_key
from .config import normalized_lil_bro_username


def main_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text=M.MENU_SEND), KeyboardButton(text=M.MENU_FOR_YOU)],
        [KeyboardButton(text=M.MENU_PROFILE), KeyboardButton(text=M.MENU_CHANNELS)],
        [KeyboardButton(text=M.MENU_SETTINGS), KeyboardButton(text=M.MENU_HELP)],
    ], resize_keyboard=True)


def button(token, action, text, index=None):
    suffix = f':{index}' if index is not None else ''
    return Button(text=text, callback_data=f'q:{token}:{action}{suffix}')


def parse_control(data):
    if not isinstance(data, str) or len(data.encode()) > 64:
        return None
    match = re.fullmatch(r'q:([a-f0-9]{32}):(rate|more|love|like|neutral|dislike):([0-4])', data)
    if match:
        return match[1], match[2], int(match[3])
    match = re.fullmatch(r'q:([a-f0-9]{32}):(next|foryou|menu|delete|keep)', data)
    if match:
        return match[1], match[2], None
    return None


def safe_url(value, artwork=False):
    if not isinstance(value, str) or len(value) > 1000 or any(c.isspace() or ord(c) < 32 for c in value):
        return None
    try:
        url = urlsplit(value)
        hosts = {'lastfm.freetls.fastly.net', 'lastfm-img2.akamaized.net'} if artwork else {'www.last.fm', 'last.fm', 'musicbrainz.org'}
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
    query = quote(f'{artist} - {title}', safe='')
    return f"https://t.me/{username}?text={query}"


def list_content(rows, token, seed_track=None):
    title = M.FOR_YOU_TITLE if seed_track is None else M.SIMILAR_TITLE.format(
        artist=clean(seed_track.display_artist or seed_track.artist, 70),
        title=clean(seed_track.display_title or seed_track.title, 70))
    lines, keyboard = [html.escape(title)], []
    for index, row in enumerate(rows):
        artist, song_title = clean(row.artist, 85), clean(row.title, 85)
        label = html.escape(f'{artist} — {song_title}')
        if url := lil_bro_url(artist, song_title):
            label = f'<a href="{html.escape(url, quote=True)}">{label}</a>'
        entry = f'{index + 1}. {label}'
        if row.album:
            entry += '\n' + html.escape(M.ALBUM_LINE.format(album=clean(row.album, 85)))
        entry += '\n' + html.escape(clean(row.reason, 120))
        lines.append(entry)
        actions = [button(token, 'rate', M.RATE_NUMBER.format(number=index + 1), index),
                   button(token, 'more', M.SIMILAR_NUMBER.format(number=index + 1), index)]
        if link := catalogue(row):
            actions.append(Button(text=M.CATALOGUE, url=link))
        if art := safe_url(row.artwork_url, artwork=True):
            actions.append(Button(text=M.ARTWORK, url=art))
        keyboard.append(actions)
    keyboard.append([button(token, 'next', M.ANOTHER_LIST), button(token, 'menu', M.MAIN_MENU)])
    if seed_track is not None:
        keyboard.append([button(token, 'foryou', M.AFTER_FOR_YOU)])
    lines.insert(1, M.LIL_BRO_HANDOFF_NOTE)
    return '\n\n'.join(lines), InlineKeyboardMarkup(inline_keyboard=keyboard)


def card_keyboard(token, selected=None, submitted=False):
    keyboard = [[button(token, value, M.rating_label(value, selected), 0)
                 for value in ('love', 'like', 'neutral', 'dislike')],
                [button(token, 'more', M.MORE_LIKE, 0),
                 button(token, 'foryou' if submitted else 'next', M.AFTER_FOR_YOU if submitted else M.CONTINUE)],
                [button(token, 'menu', M.DONE if submitted else M.MAIN_MENU)]]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


async def show_card(message, service, user_id, track, seed=None, rating=None, submitted=False, edit_existing=False):
    token = await service.create_control(user_id, tracks=[track.id], seed=seed, kind='card', submitted=submitted)
    text = M.CARD_TITLE.format(artist=clean(track.display_artist or track.artist), title=clean(track.display_title or track.title))
    if edit_existing:
        await message.edit_text(text, parse_mode=None, reply_markup=card_keyboard(token, rating, submitted))
        sent = message
    else:
        sent = await message.answer(text, parse_mode=None, reply_markup=card_keyboard(token, rating, submitted))
    await service.bind_control(token, sent.message_id)


async def show_recommendations(message, service, user_id, seed=None):
    seed_track = await service.track(seed) if seed is not None else None
    if seed is not None and seed_track is None:
        await message.answer(M.NO_RECOMMENDATIONS, reply_markup=main_menu())
        return
    if seed is None:
        result = await service.recommendations.recommend_for_user(user_id, limit=5)
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
        await message.answer(M.PREFERENCES_NEEDED if result.status == 'insufficient_preferences' else M.NO_RECOMMENDATIONS,
                             reply_markup=main_menu())
        return
    token = await service.create_control(user_id, tracks=[row.track_id for row in rows], seed=seed)
    text, keyboard = list_content(rows, token, seed_track)
    sent = await message.answer(text, parse_mode='HTML', reply_markup=keyboard,
                               link_preview_options=LinkPreviewOptions(is_disabled=True))
    await service.record_displayed(user_id, rows, token, seed)
    await service.bind_control(token, sent.message_id)
