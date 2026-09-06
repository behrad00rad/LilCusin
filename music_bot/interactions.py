"""Telegram presentation and compact callback parsing; no provider or DB logic."""

import re

from aiogram.types import ForceReply, InlineKeyboardButton, InlineKeyboardMarkup

from . import messages


def parse_callback(data):
    if not isinstance(data, str) or len(data.encode()) > 64:
        return None
    match = re.fullmatch(r"c:([1-9][0-9]{0,17}):([0-9]{1,8}):([0-4])", data)
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


async def present(message, result, user_id, workflow, enrichment, audio_analysis=None):
    if result.kind == "confirmed":
        await message.answer(messages.rating_prompt(result.artist, result.title), reply_markup=rating_keyboard(result))
        enrichment.schedule(result.track_id)
        if audio_analysis is not None:
            await audio_analysis.schedule(result.submission_id, user_id)
    elif result.kind == "candidates":
        rows = [[InlineKeyboardButton(
            text=messages.candidate_label(candidate.artist, candidate.title),
            callback_data=f"c:{result.submission_id}:{result.revision}:{index}",
        )] for index, candidate in enumerate(result.candidates)]
        rows.append([InlineKeyboardButton(text=messages.NONE, callback_data=f"n:{result.submission_id}:{result.revision}")])
        await message.answer(messages.CHOOSE, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    elif result.kind == "limit":
        await message.answer(messages.LIMIT)
    else:
        wording = {"missing": messages.MISSING, "not_found": messages.NOT_FOUND,
                   "failure": messages.PROVIDER_FAILED}.get(result.kind, messages.CORRECTION)
        prompt = await message.answer(wording, reply_markup=ForceReply(selective=True))
        await workflow.bind_prompt(result, user_id, prompt.message_id)
