"""Thin Bot API handlers. All outgoing channel-related messages are private."""

import logging
import re

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton as Button, InlineKeyboardMarkup, Message
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from . import messages as M
from .chat_ui import clean, main_menu
from .interactions import present
from .submissions import Submitter
from .workflow import FlowError

router = Router()
logger = logging.getLogger('music_bot')


def button(token, action, index, text):
    return Button(text=text, callback_data=f'h:{token}:{action}:{index}')


async def listing(message, user_id, channel_service, chat_service):
    rows = await channel_service.listing(user_id)
    if not rows:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[Button(text=M.CHANNEL_CONNECT, callback_data='channel_connect')]])
        await message.answer(M.CHANNELS_EMPTY, reply_markup=keyboard)
        return
    token = await chat_service.create_control(user_id, kind='channels', links=[row.id for row, _, _ in rows])
    text, keys = [M.CHANNELS_TITLE], []
    for index, (row, learned, review) in enumerate(rows):
        text.append(M.CHANNEL_ROW.format(number=index + 1, title=clean(row.title) or M.CHANNEL_UNTITLED,
                    status=M.CHANNEL_STATUSES[row.status], learned=learned, review=review))
        actions = [button(token, 'choose', index, M.CHANNEL_DISCONNECT.format(number=index + 1))]
        if review:
            actions.append(button(token, 'review', index, M.CHANNEL_REVIEW.format(number=index + 1)))
        keys.append(actions)
    sent = await message.answer('\n\n'.join(text), parse_mode=None, reply_markup=InlineKeyboardMarkup(inline_keyboard=keys))
    await chat_service.bind_control(token, sent.message_id)


async def connect_prompt(message, user, channel_service, chat_service):
    await chat_service.ensure_user(Submitter(user.id, user.username, user.full_name, user.language_code))
    code = await channel_service.new_code(user.id)
    await message.answer(M.CHANNEL_INSTRUCTIONS.format(code=code), parse_mode=None)


@router.message(F.text.in_({M.MENU_CHANNELS}))
@router.message(Command('connectchannel', 'channels', 'disconnectchannel'))
async def command(message, channel_service, chat_service):
    if message.chat.type != 'private' or message.from_user is None or message.from_user.is_bot:
        await message.answer(M.PRIVATE_ONLY)
        return
    if message.text.split()[0].split('@')[0] == '/connectchannel':
        await connect_prompt(message, message.from_user, channel_service, chat_service)
    else:
        await listing(message, message.from_user.id, channel_service, chat_service)


@router.callback_query(F.data.startswith('h:') | (F.data == 'channel_connect'))
async def callback(query, channel_service, chat_service, workflow, enrichment):
    answered = False
    try:
        if (not isinstance(query.message, Message) or query.message.chat.type != 'private'
                or query.message.chat.id != query.from_user.id or query.from_user.is_bot):
            raise FlowError('stale')
        if query.data == 'channel_connect':
            await query.answer(M.WORKING)
            answered = True
            await connect_prompt(query.message, query.from_user, channel_service, chat_service)
            return
        match = re.fullmatch(r'h:([a-f0-9]{32}):(choose|review|keep|remove):([0-9])', query.data or '')
        if match is None:
            raise FlowError('stale')
        token, action, index = match[1], match[2], int(match[3])
        channel = await channel_service.control(token, query.from_user.id, query.message.message_id, action, index)
        await query.answer(M.WORKING)
        answered = True
        if action == 'choose':
            token = await chat_service.create_control(query.from_user.id, kind='channel_disconnect', links=[channel.id])
            keys = [[button(token, 'keep', 0, M.CHANNEL_KEEP)], [button(token, 'remove', 0, M.CHANNEL_REMOVE)]]
            sent = await query.message.answer(M.CHANNEL_DISCONNECT_QUESTION.format(title=clean(channel.title) or M.CHANNEL_UNTITLED),
                parse_mode=None, reply_markup=InlineKeyboardMarkup(inline_keyboard=keys))
            await chat_service.bind_control(token, sent.message_id)
        elif action == 'review':
            result = await channel_service.review(query.from_user.id, channel.id)
            await present(query.message, result, query.from_user.id, workflow, enrichment, chat_service)
        else:
            await channel_service.disconnect(query.from_user.id, channel.id, action == 'remove')
            await query.message.answer(M.CHANNEL_REMOVED if action == 'remove' else M.CHANNEL_DISCONNECTED, reply_markup=main_menu())
            try:
                await query.message.edit_reply_markup(reply_markup=None)
            except TelegramBadRequest:
                pass
    except FlowError:
        if answered:
            await query.message.answer(M.CHANNEL_NO_REVIEW)
        else:
            await query.answer(M.STALE)
            answered = True
    except (TelegramBadRequest, TelegramForbiddenError):
        pass
    except Exception:
        logger.error('Channel action failed; details omitted for privacy.')
    finally:
        if not answered:
            try:
                await query.answer(M.FLOW_FAILED)
            except (TelegramBadRequest, TelegramForbiddenError):
                pass


@router.channel_post()
async def channel_post(message, bot, channel_service, workflow, enrichment, chat_service):
    if message.chat.type != 'channel':
        return
    try:
        connection = await channel_service.connect(message, bot)
        if connection:
            user_id, outcome = connection
            await bot.send_message(user_id, M.CHANNEL_OUTCOMES[outcome])
            return
        imported = await channel_service.ingest(message)
        if imported is None:
            return
        user_id, result = imported
        if result.kind == 'confirmed':
            enrichment.schedule(result.track_id)
            return
        anchor = await bot.send_message(user_id, M.CHANNEL_REVIEW_INTRO)
        await present(anchor, result, user_id, workflow, enrichment, chat_service)
    except (TelegramBadRequest, TelegramForbiddenError, FlowError):
        pass  # Pending records remain available through /channels.
    except Exception:
        logger.error('Channel post needs review; details omitted for privacy.')


@router.my_chat_member()
async def membership(event, bot, channel_service):
    if event.chat.type == 'channel':
        user_id = await channel_service.permission_change(event.chat.id, event.new_chat_member.status)
        if user_id is not None:
            try:
                await bot.send_message(user_id, M.CHANNEL_ACCESS_LOST)
            except (TelegramBadRequest, TelegramForbiddenError):
                pass
