import asyncio
import weakref

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message

from . import messages
from .i18n import menu_action


class PrivateActions(BaseMiddleware):
    """Serialize mutations; let navigation cancel an in-flight foreground handler."""

    def __init__(self):
        self.locks = weakref.WeakValueDictionary()
        self.active = {}
        self.interruptible = set()
        self.waiting = {}

    async def __call__(self, handler, event, data):
        user = getattr(event, "from_user", None)
        if user is None:
            return await handler(event, data)
        chat = event.chat if isinstance(event, Message) else getattr(getattr(event, 'message', None), 'chat', None)
        if user.is_bot or chat is None or chat.type != 'private' or chat.id != user.id:
            return await handler(event, data)
        lock = self.locks.setdefault(user.id, asyncio.Lock())
        text = getattr(event, "text", None) or ""
        callback = getattr(event, "data", None) or ""
        command = text.split()[0].split('@')[0] if text.strip() else ''
        navigation = (command in {'/cancel', '/rate', '/start', '/search', '/help', '/recommend', '/profile', '/taste', '/channels', '/version'}
                      or menu_action(text) is not None or callback.startswith(('nav:', 'cancelreq:', 'closereq:', 'close:')))
        search = bool(text.strip() and not text.lstrip().startswith('/') and menu_action(text) is None)
        cancellable = search or command in {'/start', '/help', '/recommend', '/profile', '/taste', '/channels', '/version'} or menu_action(text) is not None or callback in {'nav:search', 'nav:recommend'} or (callback.startswith('q:') and any(x in callback for x in (':more:', ':next', ':foryou')))
        current = asyncio.current_task()
        if lock.locked():
            previous = self.active.get(user.id)
            if (navigation or search) and user.id in self.interruptible and previous is not None and previous is not asyncio.current_task():
                self.waiting[user.id] = current
                if not previous.cancelling():
                    previous.cancel()
                try:
                    await asyncio.gather(previous, return_exceptions=True)
                except asyncio.CancelledError:
                    if self.waiting.get(user.id) is current:
                        self.waiting.pop(user.id, None)
                    raise
                if self.waiting.get(user.id) is not current:
                    return
                self.waiting.pop(user.id, None)
            else:
                from .bot_copy import text as copy
                from .chat_ui import cancel_keyboard
                if isinstance(event, CallbackQuery):
                    await event.answer(copy('busy'))
                else:
                    await event.answer(copy('busy'), reply_markup=cancel_keyboard())
                return
        async with lock:
            self.active[user.id] = asyncio.current_task()
            if cancellable:
                self.interruptible.add(user.id)
            try:
                return await handler(event, data)
            finally:
                self.active.pop(user.id, None)
                self.interruptible.discard(user.id)


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
