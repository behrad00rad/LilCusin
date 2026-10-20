"""Owner-bound paging through existing search results without provider requests."""
import re

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message

from . import messages
from .interactions import candidate_keyboard
from .matching import decode_track
from .models import IdentificationFlow
from .workflow import FlowError, Result, active, owned_submission


async def page_result(workflow, user_id, message_id, submission_id, revision, offset):
    async with workflow.database.sessions() as session:
        await owned_submission(session, submission_id, user_id)
        flow = await session.get(IdentificationFlow, submission_id)
        active(flow, revision)
        if (flow.state != 'candidates' or flow.prompt_message_id != message_id
                or offset < 0 or offset % 5 or offset >= len(flow.candidates)):
            raise FlowError('stale')
        return Result('candidates', submission_id, revision, [decode_track(row) for row in flow.candidates])


async def search_page(query, workflow):
    match = re.fullmatch(r'p:([1-9][0-9]{0,17}):([0-9]{1,8}):([0-9]{1,2})', query.data or '')
    if (not match or not isinstance(query.message, Message) or query.message.chat.type != 'private'
            or query.from_user.is_bot or query.message.chat.id != query.from_user.id):
        await query.answer(messages.STALE)
        return
    submission_id, revision, offset = map(int, match.groups())
    try:
        result = await page_result(workflow, query.from_user.id, query.message.message_id,
                                   submission_id, revision, offset)
    except FlowError:
        await query.answer(messages.STALE)
        return
    await query.answer()
    try:
        await query.message.edit_reply_markup(reply_markup=candidate_keyboard(result, chat=True, offset=offset))
    except TelegramBadRequest as error:
        if 'message is not modified' not in str(error).lower():
            raise
