"""Run with the runtime-based candidate, not the older dirty checkout."""
import asyncio
import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch
from aiogram.types import Message
from music_bot.lifecycle import PrivateActions
from music_bot.search_ack import SearchAcknowledgement
from music_bot.handlers import text_submission


def message(text='Fixture query'):
    return Message.model_validate({'message_id': 1, 'date': 1700000000,
        'chat': {'id': 123, 'type': 'private'},
        'from': {'id': 123, 'is_bot': False, 'first_name': 'Fixture'}, 'text': text})


class AckIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_handler_reuses_receipt_and_stops_status_before_presenting(self):
        pending = AsyncMock()
        query = message()
        submissions = NS(submit_search=AsyncMock(return_value=NS(id=1)))
        workflow = NS(start=AsyncMock(return_value=NS(kind='candidates')), schedule_cleanup=lambda _: None)
        chat = NS()
        async def present(*args, **kwargs):
            self.assertIs(kwargs['status_message'], pending)
            await pending.edit_text('RESULTS')
        async def run(event, data):
            return await text_submission(event, submissions, workflow, NS(), chat,
                                         search_receipt=data['search_receipt'])
        with patch.object(Message, 'answer', AsyncMock(return_value=pending)) as answer, \
             patch('music_bot.social_chat.note_reply', AsyncMock(return_value=False)), \
             patch('music_bot.onboarding.handle_reply', AsyncMock(return_value=False)), \
             patch('music_bot.handlers.present', side_effect=present), \
             patch('music_bot.handlers.dismiss', AsyncMock()), \
             patch('music_bot.message_reactions.acknowledge'):
            await SearchAcknowledgement()(run, query, {})
        answer.assert_awaited_once()
        self.assertEqual(pending.edit_text.await_args.args[0], 'RESULTS')

    async def test_uncooperative_old_handler_does_not_hold_new_query_silently(self):
        middleware = PrivateActions()
        started, release = asyncio.Event(), asyncio.Event()
        async def old_handler(event, data):
            started.set()
            try:
                await release.wait()
            except asyncio.CancelledError:
                await release.wait()
        old = asyncio.create_task(middleware(old_handler, message(), {}))
        await started.wait()
        next_handler = AsyncMock()
        try:
            with patch.object(Message, 'answer', AsyncMock()) as answer:
                await asyncio.wait_for(middleware(next_handler, message('New query'), {}), 3)
                answer.assert_awaited_once()
            next_handler.assert_not_awaited()
            self.assertFalse(old.done())
        finally:
            release.set()
            await old
        self.assertFalse(middleware.waiting)
        self.assertFalse(middleware.active)
