import asyncio
import unittest
from unittest.mock import AsyncMock

from music_bot.lifecycle import UpdateTasks


class LifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_shutdown_cancels_and_observes_handlers(self):
        middleware = UpdateTasks()
        started = asyncio.Event()
        cleaned = asyncio.Event()

        async def handler(event, data):
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cleaned.set()

        task = asyncio.create_task(middleware(handler, None, {}))
        await started.wait()
        await middleware.close()
        self.assertTrue(task.cancelled())
        self.assertTrue(cleaned.is_set())
        self.assertFalse(middleware.tasks)
        late = AsyncMock()
        await middleware(late, None, {})
        late.assert_not_awaited()
