import asyncio

from aiogram import BaseMiddleware


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
