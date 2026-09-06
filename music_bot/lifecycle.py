import asyncio
import weakref
from collections import OrderedDict
from time import monotonic

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery

from . import messages


class PrivateActions(BaseMiddleware):
    """One personal-data mutation per user; reject rapid duplicate navigation."""

    def __init__(self):
        self.locks = weakref.WeakValueDictionary()
        self.recent = OrderedDict()

    async def __call__(self, handler, event, data):
        user = getattr(event, "from_user", None)
        if user is None:
            return await handler(event, data)
        lock = self.locks.setdefault(user.id, asyncio.Lock())
        text = getattr(event, "text", None) or ""
        callback = getattr(event, "data", None) or ""
        navigation = (text.split("@")[0] == "/recommend" or text == messages.MENU_FOR_YOU
                      or callback.endswith((":next", ":foryou")) or ":more:" in callback)
        now = monotonic()
        if lock.locked() or navigation and now - self.recent.get(user.id, -10) < 3:
            await event.answer(messages.BUSY)
            return
        async with lock:
            if navigation:
                self.recent[user.id] = now
                self.recent.move_to_end(user.id)
                while len(self.recent) > 1000:
                    self.recent.popitem(last=False)
            return await handler(event, data)


class UpdateTasks(BaseMiddleware):
    """Drain concurrent handlers before closing their provider/DB resources."""

    def __init__(self):
        self.tasks = set()
        self.closing = False

    async def __call__(self, handler, event, data):
        if self.closing:
            return None
        task = asyncio.current_task()
        self.tasks.add(task)
        try:
            return await handler(event, data)
        finally:
            self.tasks.discard(task)

    async def close(self):
        self.closing = True
        tasks = list(self.tasks)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
