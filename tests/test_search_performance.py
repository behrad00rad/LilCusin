import asyncio
from types import SimpleNamespace as NS
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from aiogram.types import Message
from sqlalchemy import select

from music_bot.models import IdentificationFlow
from music_bot.providers.common import TrackCandidate
from music_bot.search_pipeline import SearchPipeline
from music_bot.handlers import text_submission
from tests.support import ServiceTestCase


ONE = TrackCandidate('Song', 'First Artist', 'musicbrainz')
TWO = TrackCandidate('Song', 'Second Artist', 'musicbrainz', youtube_views=1000)


class PipelineTests(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.catalogue = AsyncMock(return_value=([ONE], False))
        self.release = asyncio.Event()
        async def discover(query):
            await self.release.wait()
            return [TWO], False
        self.discovery = AsyncMock(side_effect=discover)
        self.pipeline = SearchPipeline(self.catalogue, self.discovery)

    async def asyncTearDown(self):
        await self.pipeline.close()

    async def test_catalogue_returns_before_discovery_and_complete_cache_skips_both(self):
        first, failed = await asyncio.wait_for(self.pipeline.search('song', progressive=True, fast=True), 1)
        self.assertEqual(first, [ONE])
        self.assertFalse(failed)
        self.assertFalse(self.release.is_set())
        self.release.set()
        key = self.pipeline.key('song', True, True)
        complete, _ = await self.pipeline.complete(key)
        self.assertEqual(complete, [ONE, TWO])
        repeat, _ = await self.pipeline.search(' SONG ', progressive=True, fast=True)
        self.assertEqual(repeat, complete)
        self.catalogue.assert_awaited_once()
        self.discovery.assert_awaited_once()
        self.assertNotIn('song', key)

    async def test_concurrent_waiters_share_work_and_cancelled_waiter_does_not_kill_search(self):
        cancelled = asyncio.create_task(self.pipeline.search('song'))
        await asyncio.sleep(0)
        cancelled.cancel()
        await asyncio.gather(cancelled, return_exceptions=True)
        self.release.set()
        first, second = await asyncio.gather(self.pipeline.search('song'), self.pipeline.search('song'))
        self.assertEqual(first, second)
        self.assertEqual(self.catalogue.await_count, 1)
        self.assertEqual(self.discovery.await_count, 1)

    async def test_ttl_capacity_and_defensive_copies(self):
        now = [0]
        self.pipeline.clock = lambda: now[0]
        self.pipeline.capacity = 1
        self.release.set()
        rows, _ = await self.pipeline.search('song')
        rows[0].external_ids['bad'] = 'mutated'
        repeat, _ = await self.pipeline.search('song')
        self.assertNotIn('bad', repeat[0].external_ids)
        now[0] = 301
        await self.pipeline.search('song')
        self.assertEqual(self.catalogue.await_count, 2)
        await self.pipeline.search('another')
        self.assertEqual(len(self.pipeline.cache), 1)

    async def test_failures_are_not_cached_and_shutdown_drains_tasks(self):
        self.catalogue.return_value = ([], True)
        self.discovery.side_effect = None
        self.discovery.return_value = ([], True)
        self.assertEqual(await self.pipeline.search('song'), ([], True))
        self.assertFalse(self.pipeline.cache)
        await self.pipeline.search('song')
        self.assertEqual(self.catalogue.await_count, 2)

    async def test_clear_cancels_pending_work_and_empty_source_does_not_win(self):
        self.catalogue.return_value = ([], False)
        waiting = asyncio.create_task(self.pipeline.search('song', progressive=True))
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        self.assertFalse(waiting.done())
        self.pipeline.clear()
        await asyncio.gather(waiting, return_exceptions=True)
        self.assertTrue(waiting.cancelled())
        self.assertFalse(self.pipeline.cache)
        self.assertFalse(self.pipeline.pending)

    async def test_inflight_budget_is_bounded(self):
        self.pipeline.max_pending = 1
        waiting = asyncio.create_task(self.pipeline.search('song'))
        await asyncio.sleep(0)
        self.assertEqual(await self.pipeline.search('different'), ([], True))
        self.release.set()
        await waiting


class ProgressiveFlowTests(ServiceTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.release = asyncio.Event()
        async def discover(query):
            await self.release.wait()
            return [TWO], False
        self.workflow.searches = SearchPipeline(AsyncMock(return_value=([ONE], False)), discover)
        saved = await self.submissions.submit_search(self.user, 'song')
        self.result = await self.workflow.start(saved.id, 123, fast=True)
        self.message = NS(message_id=100, edit_text=AsyncMock())
        await self.workflow.bind_candidates(self.result, 123, 100)

    async def finish(self):
        self.release.set()
        await self.workflow.searches.complete(self.result.search_key)
        await asyncio.gather(*list(self.workflow.background_tasks))

    async def test_late_results_append_without_changing_existing_callbacks(self):
        self.workflow.schedule_search_update(self.result, 123, self.message)
        await self.finish()
        async with self.database.sessions() as session:
            flow = await session.get(IdentificationFlow, self.result.submission_id)
            self.assertEqual([row['artist'] for row in flow.candidates], ['First Artist', 'Second Artist'])
            self.assertEqual(flow.revision, self.result.revision)
        keyboard = self.message.edit_text.await_args.kwargs['reply_markup']
        self.assertEqual(keyboard.inline_keyboard[0][0].callback_data,
                         f'c:{self.result.submission_id}:{self.result.revision}:0')
        self.assertIn('not total song plays', self.message.edit_text.await_args.args[0])
        chosen = await self.workflow.select(self.result.submission_id, 123, self.result.revision, 0, recover=True)
        self.assertEqual(chosen.artist, 'First Artist')

    async def test_closed_search_is_not_resurrected(self):
        self.workflow.schedule_search_update(self.result, 123, self.message)
        await self.workflow.close_candidates(self.result.submission_id, 123, self.result.revision, 100)
        await self.finish()
        self.message.edit_text.assert_not_awaited()

    async def test_selection_freezes_background_updates(self):
        self.workflow.schedule_search_update(self.result, 123, self.message)
        await self.workflow.select(self.result.submission_id, 123, self.result.revision, 0, recover=True)
        await self.finish()
        self.message.edit_text.assert_not_awaited()

    async def test_foreign_owner_cannot_publish_updates(self):
        self.workflow.schedule_search_update(self.result, 456, self.message)
        await self.finish()
        self.message.edit_text.assert_not_awaited()


class AcknowledgementTests(ServiceTestCase):
    async def test_hung_cleanup_cannot_block_acknowledgement_or_results(self):
        self.providers.call.return_value = [ONE]
        source = Message.model_validate({'message_id': 50, 'date': 1, 'text': 'song',
            'chat': {'id': 123, 'type': 'private'},
            'from': {'id': 123, 'is_bot': False, 'first_name': 'Test'}})
        pending = source.model_copy(update={'message_id': 51})
        release = asyncio.Event()
        async def cleanup(*args):
            await release.wait()
        with patch('music_bot.chat_cleanup.clear_previous_search', side_effect=cleanup), \
             patch('aiogram.types.Message.answer', AsyncMock(return_value=pending)) as answer, \
             patch('aiogram.types.Message.edit_text', AsyncMock()) as edited:
            await asyncio.wait_for(text_submission(source, self.submissions, self.workflow, NS(), chat_service=NS()), 2)
            answer.assert_awaited_once()
            edited.assert_awaited_once()
            self.assertFalse(release.is_set())
            release.set()
            await asyncio.gather(*list(self.workflow.background_tasks))
