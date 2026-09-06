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
        self.engine = create_async_engine(
            URL.create("sqlite+aiosqlite", database=str(path)),
            echo=False, hide_parameters=True, connect_args={"timeout": 10},
        )

        @event.listens_for(self.engine.sync_engine, "connect")
        def enable_foreign_keys(connection, _):
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def initialize(self) -> None:
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
        await self.engine.dispose()
