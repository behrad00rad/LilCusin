import logging
import asyncio
from time import monotonic

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
from . import chat_handlers
from .guidance import show_guide
from .i18n import menu_labels
from .chat_ui import dismiss, main_menu, cancel_keyboard, recovery_keyboard, show_recommendations
from .bot_copy import text as copy

router = Router()
logger = logging.getLogger("music_bot")


@router.message(CommandStart())
async def start(message: Message, chat_service=None, get_song=None) -> None:
    if message.chat.type != "private" or submitter(message) is None:
        await message.answer(messages.PRIVATE_ONLY)
        return
    if chat_service is not None:
        await chat_service.ensure_user(submitter(message))
        parts = (message.text or '').split(maxsplit=1)
        if len(parts) == 2 and parts[1].startswith('swap_'):
            from .social_chat import show
            from .social import Social
            from .taste_cards import CardError
            from .i18n import tr
            try:
                swap = await Social(chat_service.database).read(message.from_user.id, parts[1][5:])
                if swap['state'] != 'sent': raise CardError('social_unavailable')
                await show(message, chat_service, message.from_user.id, parts[1][5:])
                if get_song is not None:
                    await get_song.begin(message, message.from_user.id, swap['song']['id'])
                else:
                    await message.answer(tr('get_song_unavailable'))
            except CardError as error:
                await message.answer(tr(str(error)))
            return
        if len(parts) == 2 and parts[1].startswith(('compare_', 'cmp_')):
            from . import invitation_chat
            if parts[1].startswith('compare_'):
                await invitation_chat.prepare(message, chat_service, message.from_user.id, parts[1][8:])
            else:
                await invitation_chat.show(message, chat_service, message.from_user.id, parts[1][4:])
            return
        if len(parts) == 2 and parts[1].startswith('get_'):
            from .miniapp_delivery import start_delivery
            await start_delivery(message, chat_service, get_song, parts[1])
            return
        if len(parts) == 2 and parts[1].startswith('taste_'):
            from .taste_card_chat import view_card
            await view_card(message, chat_service, parts[1][6:])
            return
    from .onboarding import welcome_keyboard
    from .i18n import tr
    await message.answer(tr('onboard_welcome'), reply_markup=welcome_keyboard())


@router.message(Command('version'))
async def version(message: Message):
    if message.chat.type == 'private' and submitter(message) is not None:
        from .build_info import BUILD_ID
        await message.answer('Lil Cusin · ' + BUILD_ID)


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    if message.chat.type == 'private':
        from .bot_copy import text
        await message.answer(text('guide'), reply_markup=main_menu())
    else:
        await message.answer(messages.PRIVATE_ONLY)


from . import taste_card_chat
router.message.register(taste_card_chat.command, Command('tastecard', 'cardname', 'cardbio', 'cardsearch', 'cardshare', 'cardhide', 'carddelete', 'cardimage'))
router.callback_query.register(taste_card_chat.callback, F.data.startswith('tc:'))
from . import invitation_chat
router.callback_query.register(invitation_chat.callback, F.data.startswith('ci:'))
from . import social_chat
router.callback_query.register(social_chat.callback, F.data.startswith('sc:') | F.data.startswith('ss:'))


@router.message(Command('swaps', 'socialsettings', 'socialreports', 'savedsongs'))
async def social_flow_command(message: Message, chat_service):
    user = submitter(message)
    if message.chat.type != 'private' or user is None: return
    await chat_service.ensure_user(user)
    command = message.text.split()[0].split('@')[0]
    if command == '/socialreports': await social_chat.moderation(message, chat_service)
    elif command == '/socialsettings': await social_chat.settings(message, chat_service, user.telegram_user_id)
    elif command == '/savedsongs': await social_chat.saved(message, chat_service, user.telegram_user_id)
    else: await social_chat.inbox(message, chat_service, user.telegram_user_id)


@router.message(Command('invitations', 'pickfavorites'))
async def social_command(message: Message, chat_service):
    user = submitter(message)
    if message.chat.type != 'private' or user is None:
        return
    await chat_service.ensure_user(user)
    if message.text.split()[0].split('@')[0] == '/invitations':
        await invitation_chat.listing(message, chat_service, user.telegram_user_id)
    else:
        from .onboarding import start_path
        await start_path(message, chat_service, user.telegram_user_id, 'pick')


@router.callback_query(F.data.startswith('ob:'))
async def onboarding_callback(query: CallbackQuery, chat_service):
    if (not isinstance(query.message, Message) or query.message.chat.type != 'private'
            or query.message.chat.id != query.from_user.id or query.from_user.is_bot
            or query.data not in {'ob:send', 'ob:pick'}):
        await query.answer(messages.STALE);return
    await query.answer()
    from .onboarding import start_path
    await chat_service.ensure_user(Submitter(query.from_user.id, query.from_user.username,
        query.from_user.full_name, query.from_user.language_code))
    await start_path(query.message, chat_service, query.from_user.id, query.data[3:])


router.message.register(chat_handlers.command, Command("search", "recommend", "profile", "taste", "privacy", "forgetme"))
router.message.register(chat_handlers.command, F.text.in_(menu_labels('MENU_SEND','MENU_FOR_YOU','MENU_PROFILE','MENU_SETTINGS','MENU_HELP')))
router.callback_query.register(chat_handlers.callback, F.data.startswith("q:"))


@router.callback_query(F.data.startswith('cancelreq:') | F.data.startswith('closereq:'))
async def cancel_request(query: CallbackQuery, get_song=None):
    import re
    match = re.fullmatch(r'(?:cancelreq|closereq):([a-f0-9]{32})', query.data or '')
    if (not match or get_song is None or not isinstance(query.message, Message)
            or query.message.chat.type != 'private' or query.message.chat.id != query.from_user.id or query.from_user.is_bot):
        await query.answer(messages.STALE)
        return
    try:
        await get_song.cancel_request(query.from_user.id, match[1], query.message.message_id)
        await query.answer(copy('cancelled'))
        if query.data.startswith('closereq:'):
            await dismiss(query.message)
    except FlowError:
        await query.answer(messages.STALE)


@router.callback_query(F.data.startswith('nav:'))
async def navigation(query: CallbackQuery, workflow: Workflow, chat_service=None, get_song=None, recognition=None):
    if (not isinstance(query.message, Message) or query.message.chat.type != 'private'
            or query.message.chat.id != query.from_user.id or query.from_user.is_bot
            or query.data not in {'nav:cancel', 'nav:search', 'nav:recommend'}):
        await query.answer(messages.STALE)
        return
    await query.answer()
    if query.data == 'nav:cancel':
        if recognition is not None:
            await recognition.cancel(query.from_user.id)
        if get_song is not None:
            await get_song.cancel(query.from_user.id)
        await workflow.cancel(query.from_user.id)
        if chat_service is not None:
            await chat_service.cancel_controls(query.from_user.id)
        try:
            await query.message.edit_text(copy('cancelled'), reply_markup=recovery_keyboard())
        except TelegramBadRequest:
            await query.message.answer(copy('cancelled'), reply_markup=recovery_keyboard())
    elif query.data == 'nav:recommend' and chat_service is not None:
        await show_recommendations(query.message, chat_service, query.from_user.id)
    else:
        await query.message.answer(messages.SEND_SONG_PROMPT, reply_markup=main_menu())


@router.callback_query(F.data.startswith('g:'))
async def get_song_choice(query: CallbackQuery, get_song=None):
    import re
    match = re.fullmatch(r'g:([a-f0-9]{32}):([0-2])', query.data or '')
    if (get_song is None or not match or not isinstance(query.message, Message)
            or query.message.chat.type != 'private' or query.message.chat.id != query.from_user.id
            or query.from_user.is_bot):
        await query.answer(messages.STALE)
        return
    try:
        await get_song.choose(query.from_user.id, match[1], query.message.message_id, int(match[2]))
    except FlowError:
        await query.answer(messages.STALE)
        return
    await query.answer(messages.WORKING)
    await get_song.bind_status(query.from_user.id, match[1], query.message.message_id)


@router.callback_query(F.data.startswith('v:'))
async def other_versions(query: CallbackQuery, get_song=None):
    import re
    from .youtube_fetch import FetchError
    match = re.fullmatch(r'v:([a-f0-9]{32})', query.data or '')
    if (not match or get_song is None or not isinstance(query.message, Message)
            or query.message.chat.type != 'private' or query.message.chat.id != query.from_user.id
            or query.from_user.is_bot):
        await query.answer(messages.STALE)
        return
    try:
        request_id = await get_song.other_versions(query.from_user.id, match[1], query.message.message_id)
    except FlowError:
        await query.answer(messages.STALE)
        return
    except FetchError as error:
        await query.answer(str(error))
        return
    await query.answer(messages.WORKING)
    pending = await query.message.answer(copy('queued'), reply_markup=cancel_keyboard())
    await get_song.bind_status(query.from_user.id, request_id, pending.message_id)


@router.callback_query(F.data.startswith('w:'))
async def wrong_song(query: CallbackQuery, get_song=None):
    import re
    from .youtube_fetch import FetchError
    match = re.fullmatch(r'w:([a-f0-9]{32})', query.data or '')
    if (get_song is None or not match or not isinstance(query.message, Message)
            or query.message.chat.type != 'private' or query.message.chat.id != query.from_user.id
            or query.from_user.is_bot):
        await query.answer(messages.STALE)
        return
    await query.answer(messages.WORKING)
    try:
        request_id = await get_song.wrong(query.from_user.id, match[1], query.message.message_id)
    except FlowError:
        await query.message.answer(messages.STALE)
        return
    except FetchError as error:
        await query.message.answer(str(error))
        return
    pending = await query.message.answer(copy('queued'), reply_markup=cancel_keyboard())
    await get_song.bind_status(query.from_user.id, request_id, pending.message_id)


@router.message(Command("cancel"))
async def cancel(message: Message, workflow: Workflow, chat_service=None, get_song=None, recognition=None) -> None:
    if message.chat.type != "private" or submitter(message) is None:
        await message.answer(messages.PRIVATE_ONLY)
        return
    if recognition is not None:
        await recognition.cancel(message.from_user.id)
    if get_song is not None:
        await get_song.cancel(message.from_user.id)
    await workflow.cancel(message.from_user.id)
    if chat_service is not None:
        await chat_service.cancel_controls(message.from_user.id)
        from .onboarding import set_mode
        await set_mode(chat_service, message.from_user.id, 'pick', False)
    await message.answer(copy('cancelled'), reply_markup=recovery_keyboard())


def submitter(message: Message) -> Submitter | None:
    user = message.from_user
    if user is None or user.is_bot or message.sender_chat is not None:
        return None
    return Submitter(user.id, user.username, user.full_name, user.language_code)


@router.message(Command('recognize'))
async def recognize_command(message: Message, recognition=None):
    if recognition is not None:
        await recognition.submit(message, message.reply_to_message or message)


@router.message(Command('rate'))
async def rate_command(message: Message, submissions: SubmissionService, workflow: Workflow, enrichment: Enrichment, chat_service=None):
    if message.chat.type != 'private' or submitter(message) is None:
        await message.answer(messages.PRIVATE_ONLY)
        return
    source = message.reply_to_message
    if source is not None and (source.audio is not None or song_document(source)):
        await audio_submission(message, submissions, workflow, enrichment, chat_service, source=source)
    else:
        await message.answer(copy('rate_prompt'), reply_markup=main_menu())


@router.callback_query(F.data.startswith('close:'))
async def close_search(query: CallbackQuery, workflow: Workflow):
    import re
    match = re.fullmatch(r'close:([1-9][0-9]{0,17}):([0-9]{1,8})', query.data or '')
    if (not match or not isinstance(query.message, Message) or query.message.chat.type != 'private'
            or query.message.chat.id != query.from_user.id or query.from_user.is_bot):
        await query.answer(messages.STALE)
        return
    try:
        await workflow.close_candidates(int(match[1]), query.from_user.id, int(match[2]), query.message.message_id)
        await query.answer()
        await dismiss(query.message)
    except FlowError:
        await query.answer(messages.STALE)


@router.message(F.video | F.voice | F.video_note | F.document)
async def recognize_media(message: Message, recognition=None, submissions=None, workflow=None, enrichment=None, chat_service=None):
    if song_document(message) and submissions is not None and workflow is not None:
        await audio_submission(message, submissions, workflow, enrichment, chat_service)
        return
    if recognition is not None:
        await recognition.submit(message)
    else:
        await message.answer(messages.UNSUPPORTED)


def song_document(message):
    from pathlib import PurePath
    document = getattr(message, 'document', None)
    return bool(document and ((document.mime_type or '').startswith('audio/') or
        PurePath(document.file_name or '').suffix.lower() in {'.mp3', '.m4a', '.aac', '.flac', '.ogg', '.opus', '.wav', '.wma'}))


@router.message(F.audio)
async def audio_submission(message: Message, submissions: SubmissionService,
                           workflow: Workflow, enrichment: Enrichment, chat_service=None, recognition=None, source=None) -> None:
    if message.chat.type != "private":
        await message.answer(messages.PRIVATE_ONLY)
        return
    user = submitter(message)
    if user is None:
        await message.answer(messages.NO_USER)
        return
    audio = (source or message).audio or (source or message).document
    metadata = AudioMetadata(
        audio.file_id, audio.file_unique_id, getattr(audio, 'performer', None), getattr(audio, 'title', None),
        audio.file_name, audio.mime_type, audio.file_size, getattr(audio, 'duration', None),
    )
    try:
        saved = await submissions.submit_audio(user, metadata)
    except SQLAlchemyError:
        logger.error("Could not persist audio submission.")
        await message.answer(messages.SAVE_FAILED)
        return
    pending = await message.answer(copy('lookup'), reply_markup=cancel_keyboard())
    try:
        started = monotonic()
        result = await workflow.start(saved.id, user.telegram_user_id, fast=chat_service is not None)
        logger.info('Chat search completed: %s in %.0f ms.', result.kind, (monotonic() - started) * 1000)
        await present(message, result, user.telegram_user_id, workflow, enrichment, chat_service,
                      status_message=pending if chat_service is not None else None)
    except asyncio.CancelledError:
        await workflow.cancel(user.telegram_user_id)
        await dismiss(pending)
        raise
    if chat_service is None:
        await dismiss(pending)


@router.message(F.text, ~F.text.lstrip().startswith("/"))
async def text_submission(message: Message, submissions: SubmissionService,
                          workflow: Workflow, enrichment: Enrichment, chat_service=None, recognition=None) -> None:
    if message.chat.type != "private":
        await message.answer(messages.PRIVATE_ONLY)
        return
    user = submitter(message)
    if user is None:
        await message.answer(messages.NO_USER)
        return
    if chat_service is not None:
        from .social_chat import note_reply
        if await note_reply(message, chat_service):
            return
        from .onboarding import handle_reply
        if await handle_reply(message, chat_service, workflow):
            return
    if chat_service is not None and message.reply_to_message is None:
        workflow.schedule_cleanup(message)
    from .recognition import recognition_link
    if recognition is not None and (recognition_link(message.text) or message.text.strip().lower().startswith(('https://', 'http://'))):
        await recognition.submit(message)
        return
    pending = None
    try:
        if message.reply_to_message is not None:
            result = await workflow.correct(user.telegram_user_id, message.reply_to_message.message_id, message.text, fast=chat_service is not None)
            await present(message, result, user.telegram_user_id, workflow, enrichment, chat_service)
            await dismiss(message.reply_to_message)
            return
        pending = await message.answer(copy('lookup'), reply_markup=cancel_keyboard())
        acknowledged = monotonic()
        saved = await submissions.submit_search(user, message.text)
    except InvalidSubmission:
        if pending is not None:
            await pending.edit_text(messages.INVALID_TEXT, reply_markup=None)
        else:
            await message.answer(messages.INVALID_TEXT)
        return
    except FlowError:
        await message.answer(messages.STALE)
        return
    except SQLAlchemyError:
        logger.error("Could not persist text submission.")
        if pending is not None:
            await pending.edit_text(messages.SAVE_FAILED, reply_markup=None)
        else:
            await message.answer(messages.SAVE_FAILED)
        return
    try:
        started = monotonic()
        result = await workflow.start(saved.id, user.telegram_user_id, fast=chat_service is not None)
        logger.info('Chat search completed: %s in %.0f ms.', result.kind, (monotonic() - started) * 1000)
        await present(message, result, user.telegram_user_id, workflow, enrichment, chat_service,
                      status_message=pending if chat_service is not None else None)
        logger.info('Chat first results displayed in %.0f ms after acknowledgement.', (monotonic() - acknowledged) * 1000)
        if chat_service is not None and result.kind in {'confirmed', 'candidates'}:
            await dismiss(message)
    except asyncio.CancelledError:
        await workflow.cancel(user.telegram_user_id)
        await dismiss(pending)
        raise
    if chat_service is None:
        await dismiss(pending)


@router.message(~F.text)
async def unsupported_submission(message: Message) -> None:
    await message.answer(messages.UNSUPPORTED)


from .search_pages import search_page
router.callback_query.register(search_page, F.data.startswith('p:'))


@router.callback_query()
async def callback(query: CallbackQuery, workflow: Workflow, enrichment: Enrichment, chat_service=None) -> None:
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
            result = await workflow.select(submission_id, query.from_user.id, *arguments, recover=chat_service is not None)
            acknowledgement = messages.WORKING
        else:
            result = await workflow.none(submission_id, query.from_user.id, *arguments, recover=chat_service is not None)
            acknowledgement = messages.WORKING
        await query.answer(acknowledgement)
        answered = True
        if action == "rate":
            if chat_service is not None:
                from .chat_ui import show_card
                track = await chat_service.submitted_track(query.from_user.id, result.submission_id)
                await show_card(query.message, chat_service, query.from_user.id, track,
                                rating=result.rating, submitted=True, edit_existing=True,
                                rating_mode=await chat_service.submitted_is_audio(query.from_user.id, result.submission_id))
            else:
                try:
                    await query.message.edit_reply_markup(reply_markup=rating_keyboard(result))
                except TelegramBadRequest:
                    pass  # Repeated ratings can leave the keyboard unchanged.
        else:
            await present(query.message, result, query.from_user.id, workflow, enrichment, chat_service,
                          status_message=query.message if chat_service is not None and action != 'choose' else None)
            if chat_service is None:
                await dismiss(query.message)
    except FlowError as error:
        acknowledgement = messages.FLOW_FAILED if str(error) == "failure" else messages.STALE
        if chat_service is not None and isinstance(query.message, Message) and query.message.chat.type == 'private' and query.message.chat.id == query.from_user.id:
            await query.message.answer(copy('stale'), reply_markup=recovery_keyboard())
    except Exception:
        logger.error("Callback processing failed; details omitted for privacy.")
        acknowledgement = messages.FLOW_FAILED
    finally:
        if not answered:
            await query.answer(acknowledgement)


@router.errors()
async def unexpected_error(event: ErrorEvent) -> bool:
    logger.error("Update processing failed (%s); details omitted for privacy.", type(event.exception).__name__)
    message = event.update.message
    if message is not None:
        await message.answer(messages.FLOW_FAILED)
    return True
