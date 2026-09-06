import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from aiogram.types import CallbackQuery, ErrorEvent
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy.exc import SQLAlchemyError

from . import messages
from .submissions import AudioMetadata, InvalidSubmission, SubmissionService, Submitter
from .workflow import FlowError, Workflow
from .enrichment import Enrichment
from .interactions import parse_callback, present, rating_keyboard

router = Router()
logger = logging.getLogger("music_bot")


@router.message(CommandStart())
async def start(message: Message) -> None:
    await message.answer(messages.START)


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    await message.answer(messages.HELP)


@router.message(Command("cancel"))
async def cancel(message: Message, workflow: Workflow) -> None:
    if message.chat.type != "private" or submitter(message) is None:
        await message.answer(messages.PRIVATE_ONLY)
        return
    await workflow.cancel(message.from_user.id)
    await message.answer(messages.CANCELLED)


def submitter(message: Message) -> Submitter | None:
    user = message.from_user
    if user is None or user.is_bot or message.sender_chat is not None:
        return None
    return Submitter(user.id, user.username, user.full_name, user.language_code)


@router.message(F.audio)
async def audio_submission(message: Message, submissions: SubmissionService,
                           workflow: Workflow, enrichment: Enrichment, audio_analysis=None) -> None:
    if message.chat.type != "private":
        await message.answer(messages.PRIVATE_ONLY)
        return
    user = submitter(message)
    if user is None:
        await message.answer(messages.NO_USER)
        return
    audio = message.audio
    metadata = AudioMetadata(
        audio.file_id, audio.file_unique_id, audio.performer, audio.title,
        audio.file_name, audio.mime_type, audio.file_size, audio.duration,
    )
    try:
        saved = await submissions.submit_audio(user, metadata)
    except SQLAlchemyError:
        logger.error("Could not persist audio submission.")
        await message.answer(messages.SAVE_FAILED)
        return
    await message.answer(messages.audio_received(metadata))
    result = await workflow.start(saved.id, user.telegram_user_id)
    await present(message, result, user.telegram_user_id, workflow, enrichment, audio_analysis)


@router.message(F.text, ~F.text.lstrip().startswith("/"))
async def text_submission(message: Message, submissions: SubmissionService,
                          workflow: Workflow, enrichment: Enrichment, audio_analysis=None) -> None:
    if message.chat.type != "private":
        await message.answer(messages.PRIVATE_ONLY)
        return
    user = submitter(message)
    if user is None:
        await message.answer(messages.NO_USER)
        return
    try:
        if message.reply_to_message is not None:
            result = await workflow.correct(user.telegram_user_id, message.reply_to_message.message_id, message.text)
            await present(message, result, user.telegram_user_id, workflow, enrichment, audio_analysis)
            return
        saved = await submissions.submit_text(user, message.text)
    except InvalidSubmission:
        await message.answer(messages.INVALID_TEXT)
        return
    except FlowError:
        await message.answer(messages.STALE)
        return
    except SQLAlchemyError:
        logger.error("Could not persist text submission.")
        await message.answer(messages.SAVE_FAILED)
        return
    await message.answer(messages.text_received(saved.parsed_artist, saved.parsed_title))
    result = await workflow.start(saved.id, user.telegram_user_id)
    await present(message, result, user.telegram_user_id, workflow, enrichment, audio_analysis)


@router.message(~F.text)
async def unsupported_submission(message: Message) -> None:
    await message.answer(messages.UNSUPPORTED)


@router.callback_query()
async def callback(query: CallbackQuery, workflow: Workflow, enrichment: Enrichment, audio_analysis=None) -> None:
    acknowledgement = messages.STALE
    answered = False
    try:
        data = parse_callback(query.data)
        if not isinstance(query.message, Message) or query.message.chat.type != "private":
            acknowledgement = messages.PRIVATE_ONLY
            return
        if not data:
            return
        action, submission_id, *arguments = data
        if action == "rate":
            result = await workflow.rate(submission_id, query.from_user.id, *arguments)
            acknowledgement = messages.RATING_SAVED
        elif action == "choose":
            result = await workflow.select(submission_id, query.from_user.id, *arguments)
            acknowledgement = messages.WORKING
        else:
            result = await workflow.none(submission_id, query.from_user.id, *arguments)
            acknowledgement = messages.WORKING
        await query.answer(acknowledgement)
        answered = True
        if action == "rate":
            try:
                await query.message.edit_reply_markup(reply_markup=rating_keyboard(result))
            except TelegramBadRequest:
                pass  # Repeated ratings can leave the keyboard unchanged.
        else:
            try:
                await query.message.edit_reply_markup(reply_markup=None)
            except TelegramBadRequest:
                pass
            await present(query.message, result, query.from_user.id, workflow, enrichment, audio_analysis)
    except FlowError as error:
        acknowledgement = messages.FLOW_FAILED if str(error) == "failure" else messages.STALE
    except Exception:
        logger.error("Callback processing failed; details omitted for privacy.")
        acknowledgement = messages.FLOW_FAILED
    finally:
        if not answered:
            await query.answer(acknowledgement)


@router.errors()
async def unexpected_error(event: ErrorEvent) -> bool:
    logger.error("Update processing failed; details omitted for privacy.")
    message = event.update.message
    if message is not None:
        await message.answer(messages.FLOW_FAILED)
    return True
