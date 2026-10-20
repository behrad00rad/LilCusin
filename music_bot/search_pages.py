"""Owner-bound result pages with bounded discovery of unseen recordings."""
import asyncio
import re
import sys

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message

from . import messages
from .interactions import candidate_keyboard
from .matching import decode_track, encode_track, identity_key
from .models import IdentificationFlow
from .workflow import FlowError, Result, active, owned_submission

MORE_SEARCH = """import json,sys
from ytmusicapi import YTMusic
client=YTMusic()
print(json.dumps(client.search(sys.argv[1], filter='songs', limit=int(sys.argv[2]), ignore_spelling=False)))
"""


async def page_result(workflow, user_id, message_id, submission_id, revision, offset):
    async with workflow.database.sessions() as session:
        submission = await owned_submission(session, submission_id, user_id)
        flow = await session.get(IdentificationFlow, submission_id)
        active(flow, revision)
        if (flow.state != 'candidates' or flow.prompt_message_id != message_id
                or offset < 0 or offset > len(flow.candidates) or offset >= 60):
            raise FlowError('stale')
        original = list(flow.candidates)
        rows = [decode_track(row) for row in original]
        search_query = (' '.join(filter(None, (flow.corrected_artist, flow.corrected_title)))
                        if flow.corrected_artist is not None or flow.corrected_title
                        else submission.raw_text or ' '.join(filter(None, (submission.parsed_artist, submission.parsed_title))))
    if offset < len(rows):
        return Result('candidates', submission_id, revision, rows)
    provider = workflow.recording_search
    if provider is None:
        return Result('exhausted', submission_id, revision, rows)
    from .recording_search import recordings
    music = True
    async with asyncio.timeout(provider.timeout * 2 + .5):
        async with provider.slots:
            payload = await provider.process([sys.executable, '-c', MORE_SEARCH,
                ' '.join(search_query.split())[:300], str(min(100, max(30, len(rows) * 3)))])
            if not isinstance(payload, list) or not payload:
                music = False
                response = await provider.process([sys.executable, '-m', 'yt_dlp',
                    '--ignore-config', '--no-cookies', '--no-cookies-from-browser',
                    '--no-cache-dir', '--flat-playlist', '--skip-download', '--socket-timeout', '3',
                    '--retries', '0', '--quiet', '--no-warnings', '--dump-single-json', '--',
                    'ytsearch' + str(min(100, max(30, len(rows) * 3))) + ':' + ' '.join(search_query.split())[:300]])
                payload = response.get('entries') if isinstance(response, dict) else None
    if not isinstance(payload, list):
        raise FlowError('provider')
    names = {identity_key(row.artist, row.title) for row in rows}
    videos = {row.external_ids.get('youtube') for row in rows} - {None}
    additional = []
    for entry in payload[:150] if isinstance(payload, list) else []:
        for row in recordings([entry], music=music, max_duration=provider.max_duration):
            name = identity_key(row.artist, row.title)
            video = row.external_ids.get('youtube')
            if name not in names and video not in videos:
                additional.append(row)
                names.add(name)
                videos.add(video)
        if len(additional) == min(5, 60 - len(rows)):
            break
    async with workflow.database.write() as session:
        await owned_submission(session, submission_id, user_id)
        flow = await session.get(IdentificationFlow, submission_id)
        active(flow, revision)
        if (flow.state != 'candidates' or flow.prompt_message_id != message_id
                or flow.candidates != original):
            raise FlowError('stale')
        rows += additional
        flow.candidates = [encode_track(row) for row in rows]
    return Result('candidates' if additional else 'exhausted', submission_id, revision, rows)


async def search_page(query, workflow):
    match = re.fullmatch(r'p:([1-9][0-9]{0,17}):([0-9]{1,8}):([0-9]{1,2})', query.data or '')
    if (not match or not isinstance(query.message, Message) or query.message.chat.type != 'private'
            or query.from_user.is_bot or query.message.chat.id != query.from_user.id):
        await query.answer(messages.STALE)
        return
    submission_id, revision, offset = map(int, match.groups())
    await query.answer()
    try:
        result = await page_result(workflow, query.from_user.id, query.message.message_id,
                                   submission_id, revision, offset)
    except (FlowError, TimeoutError) as error:
        from .i18n import language
        text = messages.STALE if str(error) == 'stale' else (
            'جست‌وجو موقتاً در دسترس نیست؛ دوباره امتحان کن.' if language.get() == 'fa'
            else 'Search is temporarily unavailable. Try again.')
        await query.message.answer(text)
        return
    if result.kind == 'exhausted':
        from .i18n import language
        await query.message.answer('نتیجهٔ تازه‌ای پیدا نشد.' if language.get() == 'fa' else 'No more new songs found.')
        markup = query.message.reply_markup
        if markup is not None:
            from aiogram.types import InlineKeyboardMarkup
            rows = [[button for button in row if button.callback_data != query.data] for row in markup.inline_keyboard]
            await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=[row for row in rows if row]))
        return
    try:
        await query.message.edit_reply_markup(reply_markup=candidate_keyboard(result, chat=True, offset=offset,
            can_expand=result.kind != 'exhausted'))
    except TelegramBadRequest as error:
        if 'message is not modified' not in str(error).lower():
            raise
