"""Telegram presentation and compact callback parsing; no provider or DB logic."""

import re

from aiogram.types import ForceReply, InlineKeyboardButton, InlineKeyboardMarkup

from . import messages
from .bot_copy import text as copy
from .recording_metadata import search_label, result_metadata, result_pages
from .i18n import language


def parse_callback(data):
    if not isinstance(data, str) or len(data.encode()) > 64:
        return None
    match = re.fullmatch(r"c:([1-9][0-9]{0,17}):([0-9]{1,8}):([0-9]{1,2})", data)
    if match:
        return "choose", *(int(value) for value in match.groups())
    match = re.fullmatch(r"n:([1-9][0-9]{0,17}):([0-9]{1,8})", data)
    if match:
        return "none", *(int(value) for value in match.groups())
    match = re.fullmatch(r"r:([1-9][0-9]{0,17}):(love|like|neutral|dislike)", data)
    if match:
        return "rate", int(match[1]), match[2]
    return None


def rating_keyboard(result):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=messages.rating_label(value, result.rating),
                             callback_data=f"r:{result.submission_id}:{value}")
        for value in ("love", "like", "neutral", "dislike")
    ]])


def candidate_keyboard(result, *, chat=False, offset=0, can_expand=True):
    slots, extent = result_pages(result.candidates)
    visible = {index for slot,index in slots.items() if offset <= slot < offset + 5}
    rows = [[InlineKeyboardButton(
        text=search_label(candidate.artist, candidate.title, candidate.source, locale=language.get(),
            duration=candidate.duration, metadata=result_metadata(candidate), flags=candidate.recording_metadata.get('flags', ())),
        callback_data=f"c:{result.submission_id}:{result.revision}:{index}",
    )] for index, candidate in enumerate(result.candidates) if index in visible]
    navigation = []
    if offset:
        navigation.append(InlineKeyboardButton(text='قبلی' if language.get() == 'fa' else 'Previous',
            callback_data=f'p:{result.submission_id}:{result.revision}:{max(0, offset - 5)}'))
    if offset + 5 < extent or (chat and can_expand and len(result.candidates) < 60):
        navigation.append(InlineKeyboardButton(text='بیشتر' if language.get() == 'fa' else 'More songs',
            callback_data=f'p:{result.submission_id}:{result.revision}:{min(offset + 5, extent)}'))
    if navigation:
        rows.append(navigation)
    rows.append([InlineKeyboardButton(text=messages.NONE, callback_data=f"n:{result.submission_id}:{result.revision}")])
    if chat:
        rows.append([InlineKeyboardButton(text=copy('close'),
                     callback_data=f'close:{result.submission_id}:{result.revision}', style='danger')])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def candidate_heading(result, *, chat=False):
    heading = messages.CHOOSE + ('\n\n' + copy('search_refine') if chat else '')
    return heading


async def present(message, result, user_id, workflow, enrichment, chat_service=None, status_message=None):
    if result.kind == "confirmed":
        rating_mode = False
        if chat_service is not None:
            from .chat_ui import show_card
            track = await chat_service.submitted_track(user_id, result.submission_id)
            rating_mode = await chat_service.submitted_is_audio(user_id, result.submission_id)
            await show_card(status_message or message, chat_service, user_id, track, rating=result.rating,
                            submitted=True, edit_existing=status_message is not None, rating_mode=rating_mode)
        else:
            await message.answer(messages.rating_prompt(result.artist, result.title), reply_markup=rating_keyboard(result))
        if not rating_mode:
            enrichment.schedule(result.track_id)
    elif result.kind == "candidates":
        keyboard = candidate_keyboard(result, chat=chat_service is not None)
        heading = candidate_heading(result, chat=chat_service is not None)
        if status_message is not None:
            await status_message.edit_text(heading, reply_markup=keyboard)
            sent = status_message
        else:
            sent = await message.answer(heading, reply_markup=keyboard)
        if chat_service is not None:
            await workflow.bind_candidates(result, user_id, sent.message_id)
            if result.search_key is not None:
                workflow.schedule_search_update(result, user_id, sent)
    elif result.kind == "limit":
        await message.answer(messages.LIMIT)
    else:
        wording = {"missing": messages.MISSING, "not_found": messages.NOT_FOUND,
                   "failure": messages.PROVIDER_FAILED}.get(result.kind, messages.CORRECTION)
        prompt = await message.answer(wording, reply_markup=ForceReply(selective=True))
        await workflow.bind_prompt(result, user_id, prompt.message_id)
    if status_message is not None and result.kind not in {'confirmed', 'candidates'}:
        from .chat_ui import dismiss
        await dismiss(status_message)
