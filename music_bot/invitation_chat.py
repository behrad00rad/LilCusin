"""Deliberate sharing of requests: no automatic messages to the other person."""
import re
from urllib.parse import quote

from aiogram.types import InlineKeyboardButton as Button, InlineKeyboardMarkup, Message
from sqlalchemy import select

from .comparison_invitations import ComparisonInvitations
from .i18n import tr
from .models import ChatControl, User, utc_now
from .taste_cards import TasteCards, CardError
from .submissions import Submitter


def snapshot_text(card):
    return card['nickname'] + '\n' + '\n'.join(
        f"• {song['artist'][:70]} — {song['title'][:90]}" for song in card['songs'])


async def prepare(message, chat, telegram_id, card_token):
    try:
        cards = TasteCards(chat.database)
        target = await cards.view(card_token)
        own = await cards.owner(telegram_id)
        if not own['nickname'] or not own['songs']:
            await message.answer(tr('invite_finish_card'), reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                Button(text=tr('onboard_pick'), callback_data='ob:pick')]]))
            return
        service = ComparisonInvitations(chat.database)
        revision = await service.target(card_token)
        token = await chat.create_control(telegram_id, kind='compare-request')
        async with chat.database.write() as session:
            row = await session.get(ChatControl, token)
            row.payload = {**row.payload, 'card_token': card_token, 'sender_revision': own['revision'],
                           'recipient_revision': revision}
        text = tr('invite_consent_prompt', name=target['nickname']) + '\n\n' + snapshot_text(own) + '\n\n' + tr('invite_scope')
        sent = await message.answer(text, parse_mode=None, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            Button(text=tr('invite_request'), callback_data='ci:req:'+token),
            Button(text=tr('card_cancel'), callback_data='tc:cancel')]]))
        await chat.bind_control(token, sent.message_id)
    except CardError as error:
        await message.answer(tr(str(error)))


async def show(message, chat, telegram_id, token):
    try:
        invitation = await ComparisonInvitations(chat.database).read(telegram_id, token)
        state = invitation['state']
        rows = []
        text = tr('invite_state_'+state)
        if state in {'pending', 'consented'}:
            text += '\n\n' + snapshot_text(invitation['sender']) + '\n\n' + snapshot_text(invitation['recipient'])
            text += '\n\n' + tr('invite_scope')
            if state == 'consented':
                rows.append([Button(text=tr('social_compare'),callback_data='sc:compare:'+token),
                             Button(text=tr('social_swap'),callback_data='sc:choose:'+token)])
            rows.append([Button(text=tr('social_block'),callback_data='sc:block:'+token),
                         Button(text=tr('social_report'),callback_data='sc:report:'+token)])
            if state == 'pending' and invitation['role'] == 'recipient':
                rows.append([Button(text=tr('invite_accept'), callback_data='ci:accept:'+token),
                             Button(text=tr('invite_decline'), callback_data='ci:decline:'+token)])
            if state == 'pending' and invitation['role'] == 'sender':
                me = await message.bot.me()
                url = f'https://t.me/{me.username}?start=cmp_{token}'
                rows.append([Button(text=tr('invite_send_to', name=invitation['recipient']['nickname']),
                                    url='https://t.me/share/url?url='+quote(url, safe=''))])
            rows.append([Button(text=tr('invite_revoke'), callback_data='ci:revoke:'+token)])
        await message.answer(text, parse_mode=None, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows) if rows else None)
    except CardError as error:
        await message.answer(tr(str(error)))


async def listing(message, chat, telegram_id):
    rows = await ComparisonInvitations(chat.database).listing(telegram_id)
    if not rows:
        await message.answer(tr('invite_empty'));return
    keys = []
    for row in rows:
        partner = row.get('recipient' if row['role'] == 'sender' else 'sender', {}).get('nickname', '')
        label = (partner[:40] + ' · ' if partner else '') + tr('invite_state_label_'+row['state'])
        keys.append([Button(text=label, callback_data='ci:view:'+row['token'])])
    await message.answer(tr('invite_list'), reply_markup=InlineKeyboardMarkup(inline_keyboard=keys))


async def callback(query, chat_service):
    if (not isinstance(query.message, Message) or query.message.chat.type != 'private'
            or query.message.chat.id != query.from_user.id or query.from_user.is_bot):
        await query.answer(tr('invite_unavailable'));return
    await query.answer()
    await chat_service.ensure_user(Submitter(query.from_user.id, query.from_user.username,
        query.from_user.full_name, query.from_user.language_code))
    data = query.data or ''
    if data == 'ci:list':
        await listing(query.message, chat_service, query.from_user.id);return
    match = re.fullmatch(r'ci:(preview|req|view|accept|decline|revoke):([A-Za-z0-9_-]{32})', data)
    if not match:
        await query.message.answer(tr('invite_invalid'));return
    action, token = match.groups()
    if action == 'preview':
        await prepare(query.message, chat_service, query.from_user.id, token);return
    try:
        service = ComparisonInvitations(chat_service.database)
        if action == 'req':
            async with chat_service.database.sessions() as session:
                row = await session.scalar(select(ChatControl).join(User).where(
                    User.telegram_user_id == query.from_user.id, ChatControl.token == token,
                    ChatControl.message_id == query.message.message_id, ChatControl.expires_at > utc_now()))
                if row is None or row.payload.get('kind') != 'compare-request':
                    raise CardError('invite_stale')
                payload = dict(row.payload)
            invitation = await service.create(query.from_user.id, payload['card_token'],
                                              payload['sender_revision'], payload['recipient_revision'])
            token = invitation['token']
        elif action in {'accept', 'decline', 'revoke'}:
            await service.decide(query.from_user.id, token, action)
        await show(query.message, chat_service, query.from_user.id, token)
    except CardError as error:
        await query.message.answer(tr(str(error)))
