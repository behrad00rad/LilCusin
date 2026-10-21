import asyncio
import unittest
from music_bot.search_progress import search_with_updates


class SearchProgressTests(unittest.IsolatedAsyncioTestCase):
    async def test_fast_search_has_no_delayed_updates(self):
        updates = []
        async def work(): return ['match']
        async def update(key): updates.append(key)
        self.assertEqual(await search_with_updates(work, update, delays=(.01, .01)), ['match'])
        await asyncio.sleep(.03)
        self.assertEqual(updates, [])

    async def test_slow_search_updates_twice_and_stops(self):
        updates = []
        async def work(): await asyncio.sleep(.04); return ['match']
        async def update(key): updates.append(key)
        self.assertEqual(await search_with_updates(work, update, delays=(.005, .005)), ['match'])
        self.assertEqual(updates, ['searching_slow', 'searching_sources'])

    async def test_cancelled_search_cannot_update_later(self):
        updates = []
        async def work(): await asyncio.sleep(10)
        async def update(key): updates.append(key)
        task = asyncio.create_task(search_with_updates(work, update, delays=(.02, .02)))
        await asyncio.sleep(0)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError): await task
        await asyncio.sleep(.05)
        self.assertEqual(updates, [])

    async def test_update_failure_does_not_fail_search(self):
        async def work(): await asyncio.sleep(.02); return ['match']
        async def update(key): raise RuntimeError('offline fixture')
        self.assertEqual(await search_with_updates(work, update, delays=(.001, .001)), ['match'])
