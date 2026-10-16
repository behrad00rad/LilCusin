import asyncio
import aiosqlite
from pathlib import Path
from contextlib import asynccontextmanager

from sqlalchemy import URL, event, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from .models import Base
from .migrations import migrate

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "music_bot.sqlite3"


class Database:
    def __init__(self, path: Path = DEFAULT_PATH):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._closing = False
        self._driver_connections = {}
        self.engine = create_async_engine(
            URL.create("sqlite+aiosqlite", database=str(path)),
            echo=False, hide_parameters=True, async_creator=lambda: self._connect(path),
        )

        @event.listens_for(self.engine.sync_engine, "connect")
        def enable_foreign_keys(connection, _):
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def _connect(self, path):
        if self._closing:
            raise RuntimeError('Database is closed')
        driver = aiosqlite.connect(str(path), timeout=10)
        original_close = driver.close
        closing = None
        async def close_driver():
            nonlocal closing
            if closing is None:
                closing = asyncio.create_task(original_close())
            await asyncio.shield(closing)
            self._driver_connections.pop(driver, None)
        driver.close = close_driver
        opening = asyncio.ensure_future(driver)
        self._driver_connections[driver] = opening
        try:
            return await asyncio.shield(opening)
        except BaseException:
            await asyncio.gather(opening, return_exceptions=True)
            await close_driver()
            raise

    async def initialize(self) -> None:
        from . import fetch_models  # Additive Get song tables.
        from .preferences import UserPreferences  # Register the additive preferences table.
        from .taste_setup import TasteSetup
        async with self.engine.begin() as connection:
            await connection.exec_driver_sql("BEGIN IMMEDIATE")
            await connection.run_sync(migrate)
            await connection.run_sync(Base.metadata.create_all)

    @asynccontextmanager
    async def write(self):
        # Reserve the SQLite writer before read/modify/write operations. This
        # makes confirmation and rating idempotent across concurrent callbacks.
        async with self.sessions() as session:
            await session.execute(text("BEGIN IMMEDIATE"))
            try:
                yield session
                await session.commit()
            except BaseException:
                await session.rollback()
                raise

    async def close(self) -> None:
        self._closing = True
        await asyncio.gather(*self._driver_connections.values(), return_exceptions=True)
        await self.engine.dispose()
        await asyncio.gather(*(driver.close() for driver in list(self._driver_connections)), return_exceptions=True)
