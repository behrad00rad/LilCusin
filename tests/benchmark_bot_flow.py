"""Offline before/after experiment; delays are simulated, not Telegram timings.

Run: python -m tests.benchmark_bot_flow
The baseline is 80a6fc5 (the audited pre-change implementation).
"""
import asyncio
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time
from types import ModuleType, SimpleNamespace as NS
from unittest.mock import AsyncMock

from music_bot.get_song import GetSong
from music_bot.submissions import Submitter
from tests.test_bot_flow_upgrade import UpgradeTests
from tests.test_workflow import EXACT

BASELINE_REVISION = '80a6fc5'


def baseline(name):
    module = ModuleType('music_bot._baseline_' + name)
    module.__package__ = 'music_bot'
    sys.modules[module.__name__] = module
    source = subprocess.check_output(['git', 'show', BASELINE_REVISION + ':music_bot/' + name + '.py'], text=True)
    exec(compile(source, '<baseline ' + name + '>', 'exec'), module.__dict__)
    return module


async def sample(operation, count=5):
    rows = []
    for _ in range(count):
        begin = time.perf_counter()
        await operation()
        rows.append(round((time.perf_counter() - begin) * 1000, 2))
    return {'median_ms': round(statistics.median(rows), 2), 'samples_ms': rows}


async def main():
    old_flow, old_delivery = baseline('workflow'), baseline('get_song')
    case = UpgradeTests()
    await case.asyncSetUp()
    try:
        async def remote(*args):
            await asyncio.sleep(.2)
            return [EXACT]
        case.providers.call.side_effect = remote
        before = old_flow.Workflow(case.database, case.providers)
        async def search(workflow, fast=False):
            saved = await case.submissions.submit_search(Submitter(123), 'Artist - Song')
            if fast:
                await workflow.start(saved.id, 123, fast=True)
            else:
                await workflow.start(saved.id, 123)
        results = {'mode': 'offline; mocked Telegram/source; injected 200ms metadata and artwork delays',
                   'search_before': await sample(lambda: search(before)),
                   'search_after': await sample(lambda: search(case.workflow, True))}
        await case.workflow.close()
        async def slow_art(*args):
            await asyncio.sleep(.2)
        old = old_delivery.GetSong(case.database, case.bot,
            old_delivery.FetchSettings(enabled=True, per_hour=100), case.fetcher,
            artwork_loader=NS(load=AsyncMock(side_effect=slow_art)))
        old.root = case.service.root
        req = await old.request(123, case.track_id)
        await old.execute(await case.job(req))
        async def cached(service):
            req = await service.request(123, case.track_id)
            await service.execute(await case.job(req))
        results['cached_delivery_before'] = await sample(lambda: cached(old))
        case.service.settings = old.settings
        case.service.artwork_loader = NS(load=AsyncMock(side_effect=slow_art))
        results['cached_delivery_after'] = await sample(lambda: cached(case.service))
        print(json.dumps(results, indent=2))
    finally:
        await case.asyncTearDown()
        case.doCleanups()


if __name__ == '__main__':
    asyncio.run(main())
