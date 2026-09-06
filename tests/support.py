import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

from aiogram import Dispatcher

from music_bot.database import Database
from music_bot.handlers import router
from music_bot.channel_handlers import router as channel_router
from music_bot.submissions import SubmissionService, Submitter
from music_bot.workflow import Workflow

dispatcher = Dispatcher(disable_fsm=True)
dispatcher.include_router(channel_router)
dispatcher.include_router(router)


class ServiceTestCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database = Database(Path(self.temp.name) / "test.sqlite3")
        await self.database.initialize()
        self.submissions = SubmissionService(self.database)
        self.providers = AsyncMock()
        self.providers.call.return_value = []
        self.workflow = Workflow(self.database, self.providers)
        self.user = Submitter(123, "test", "Test")

    async def asyncTearDown(self):
        await self.database.close()
        self.temp.cleanup()
