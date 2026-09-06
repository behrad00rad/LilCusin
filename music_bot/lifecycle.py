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


class ChannelUpdates(BaseMiddleware):
    """Keep a channel's connection-code post ahead of subsequent audio posts."""

    def __init__(self, database, private_actions):
        self.locks = weakref.WeakValueDictionary()
        self.database, self.private_actions = database, private_actions

    async def __call__(self, handler, event, data):
        lock = self.locks.setdefault(event.chat.id, asyncio.Lock())
        async with lock:
            from sqlalchemy import select
            from .models import PlaylistChannel, User
            async with self.database.sessions() as session:
                owner = await session.scalar(select(User.telegram_user_id).join(
                    PlaylistChannel, PlaylistChannel.user_id == User.id,
                ).where(PlaylistChannel.telegram_chat_id == event.chat.id))
            if owner is None:
                return await handler(event, data)
            # Share the private-chat mutation lock: /forgetme cannot race an
            # in-flight identification and let old work target a recreated user.
            user_lock = self.private_actions.locks.setdefault(owner, asyncio.Lock())
            async with user_lock:
                return await handler(event, data)
