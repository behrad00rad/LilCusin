"""Bounded complete-result caching and progressively available public matches."""
import asyncio
from collections import OrderedDict
from copy import deepcopy
import hashlib
import json
from time import monotonic

from .matching import deduplicate, remove_reversed_candidates
from .models import normalize_name
from .providers.common import ProviderError


class SearchPipeline:
    def __init__(self, catalogue, discovery, *, clock=monotonic, ttl=300, capacity=128, max_pending=8):
        self.catalogue, self.discovery = catalogue, discovery
        self.clock, self.ttl, self.capacity, self.max_pending = clock, ttl, capacity, max_pending
        self.cache = OrderedDict()
        self.pending = {}

    def key(self, query, progressive, fast):
        return hashlib.sha256(json.dumps([normalize_name(query), progressive, fast], ensure_ascii=False).encode()).hexdigest()

    def cached(self, key):
        entry = self.cache.get(key)
        if entry and entry[0] > self.clock():
            self.cache.move_to_end(key)
            return deepcopy(entry[1])
        self.cache.pop(key, None)
        return None

    async def search(self, query, *, progressive=False, fast=False):
        key = self.key(query, progressive, fast)
        cached = self.cached(key)
        if cached is not None:
            return cached
        entry = self.pending.get(key)
        if entry is None:
            if len(self.pending) >= self.max_pending:
                return [], True
            ready = asyncio.get_running_loop().create_future()
            task = asyncio.create_task(self._run(key, query, ready, progressive))
            entry = self.pending[key] = (ready, task)
            task.add_done_callback(lambda done: self._finished(key, done))
        return deepcopy(await asyncio.shield(entry[0] if progressive else entry[1]))

    def _finished(self, key, task):
        entry = self.pending.get(key)
        if entry is not None and entry[1] is task:
            self.pending.pop(key, None)
        if not task.cancelled():
            task.exception()  # Retrieve failures even if a foreground waiter left.

    async def _branch(self, loader, query):
        try:
            return await loader(query)
        except (ProviderError, TimeoutError):
            return [], True

    async def _run(self, key, query, ready, progressive):
        catalogue = asyncio.create_task(self._branch(self.catalogue, query))
        discovery = asyncio.create_task(self._branch(self.discovery, query))
        tasks = {catalogue, discovery}
        first = []
        try:
            waiting = set(tasks)
            while waiting:
                done, waiting = await asyncio.wait(waiting, return_when=asyncio.FIRST_COMPLETED)
                # Prefer catalogue if both sources became ready together.
                for task in (catalogue, discovery):
                    if task in done:
                        rows, failed = task.result()
                        if rows and not ready.done():
                            first = list(rows[:10]) if progressive else []
                            ready.set_result((deepcopy(first or rows), failed))
            rows, failed = catalogue.result()
            suggestions, discovery_failed = discovery.result()
            merged = remove_reversed_candidates(deduplicate((first if progressive else []) + suggestions + rows))[:20]
            result = (merged, failed and discovery_failed)
            if not result[1] and merged:
                self.cache[key] = (self.clock() + self.ttl, deepcopy(result))
                self.cache.move_to_end(key)
                while len(self.cache) > self.capacity:
                    self.cache.popitem(last=False)
            if not ready.done():
                ready.set_result(deepcopy(result))
            return result
        finally:
            if not ready.done():
                ready.cancel()
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    async def complete(self, key):
        cached = self.cached(key)
        if cached is not None:
            return cached
        entry = self.pending.get(key)
        return await asyncio.shield(entry[1]) if entry is not None else ([], True)

    def clear(self):
        self.cache.clear()
        entries = list(self.pending.values())
        self.pending.clear()
        for ready, task in entries:
            ready.cancel()
            task.cancel()

    async def close(self):
        tasks = [task for _, task in self.pending.values()]
        self.clear()
        await asyncio.gather(*tasks, return_exceptions=True)
