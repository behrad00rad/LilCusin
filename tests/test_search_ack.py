import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from aiogram.types import Message
from music_bot.search_ack import SearchAcknowledgement, COPY


def message(text='Radiohead', **changes):
    return Message.model_validate(dict(message_id=1, date=1700000000,
        chat={'id': 123, 'type': 'private'},
        **{'from': {'id': 123, 'is_bot': False, 'first_name': 'Fixture', 'language_code': 'fa'}},
        text=text, **changes))


class SearchAckTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.pending = AsyncMock()
        self.answer = AsyncMock(return_value=self.pending)
        self.patch = patch.object(Message, 'answer', self.answer)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    async def test_receipt_precedes_database_and_lock_setup(self):
        async def blocked_setup(event, data):
            self.answer.assert_awaited_once()
            receipt = data['search_receipt']
            self.assertIs(receipt.claim(), self.pending)
            await receipt.stop()
            return 'results'
        result = await SearchAcknowledgement()(blocked_setup, message(), {})
        self.assertEqual(result, 'results')
        self.assertEqual(self.answer.await_args.args[0], COPY['received'][1])
        self.pending.delete.assert_not_awaited()

    async def test_slow_setup_gets_two_updates_and_no_late_edits(self):
        updates_done = asyncio.Event()
        async def edited(*args, **kwargs):
            if self.pending.edit_text.await_count == 2:
                updates_done.set()
        self.pending.edit_text.side_effect = edited
        async def slow(event, data):
            await asyncio.wait_for(updates_done.wait(), 1)
            receipt = data['search_receipt']
            receipt.claim()
            await receipt.stop()
            await self.pending.edit_text('RESULTS')
        await SearchAcknowledgement(delays=(.002, .002))(slow, message(), {})
        await asyncio.sleep(.01)
        self.assertEqual(self.pending.edit_text.await_count, 3)
        self.assertEqual(self.pending.edit_text.await_args.args[0], 'RESULTS')

    async def test_unexpected_error_finishes_receipt(self):
        async def broken(event, data): raise RuntimeError('offline fixture')
        await SearchAcknowledgement()(broken, message(), {})
        self.assertEqual(self.pending.edit_text.await_args.args[0], COPY['failed'][1])
        self.pending.delete.assert_not_awaited()

    async def test_cancellation_stops_notifications_and_removes_unused_receipt(self):
        started = asyncio.Event()
        async def blocked(event, data):
            started.set()
            await asyncio.Event().wait()
        task = asyncio.create_task(SearchAcknowledgement(delays=(.05, .05))(blocked, message(), {}))
        await started.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError): await task
        await asyncio.sleep(.06)
        self.pending.edit_text.assert_not_awaited()
        self.pending.delete.assert_awaited_once()

    async def test_special_reply_receipt_is_removed_without_touching_its_response(self):
        handler = AsyncMock(return_value='handled as note or onboarding')
        self.assertEqual(await SearchAcknowledgement()(handler, message(), {}), 'handled as note or onboarding')
        self.pending.delete.assert_awaited_once()

    async def test_claimed_receipt_cancelled_during_submission_is_not_left_loading(self):
        started = asyncio.Event()
        async def blocked(event, data):
            data['search_receipt'].claim()
            started.set()
            await asyncio.Event().wait()
        task = asyncio.create_task(SearchAcknowledgement()(blocked, message(), {}))
        await started.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError): await task
        self.pending.delete.assert_awaited_once()

    async def test_commands_and_groups_are_not_acknowledged_as_search(self):
        handler = AsyncMock()
        await SearchAcknowledgement()(handler, message('/cancel'), {})
        group = message().model_copy(update={'chat': message().chat.model_copy(update={'type': 'group'})})
        await SearchAcknowledgement()(handler, group, {})
        self.answer.assert_not_awaited()
        self.assertEqual(handler.await_count, 2)

    async def test_telegram_ack_failure_keeps_normal_handler_reply_attempt(self):
        self.answer.side_effect = TimeoutError()
        handler = AsyncMock(return_value='normal handler')
        self.assertEqual(await SearchAcknowledgement()(handler, message(), {}), 'normal handler')
        handler.assert_awaited_once()
