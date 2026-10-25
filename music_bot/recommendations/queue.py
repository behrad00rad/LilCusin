"""Durable, leased For You batches; warming never sends Telegram messages."""

import asyncio
from dataclasses import asdict
from datetime import datetime, timedelta
import logging
from uuid import uuid4
import weakref

from sqlalchemy import ForeignKey, JSON, delete, select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Mapped, mapped_column

from ..models import Base, Track, UTCDateTime, User, utc_now
from ..taste_learning import LearningState, REQUEST_WINDOW, TasteRequest, learning_state
from . import settings as S
from .repository import load_exclusions, load_items
from .types import Recommendation, RecommendationResult

QUEUE_TTL = timedelta(days=1)
LEASE_TTL = timedelta(minutes=2)
QUEUE_TARGET = 20
LOW_WATER = 10
logger = logging.getLogger(__name__)


class QueuedRecommendation(Base):
    __tablename__ = 'recommendation_queue'
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    track_id: Mapped[int] = mapped_column(ForeignKey('tracks.id'), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON)
    position: Mapped[int]
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    lease: Mapped[str | None]
    lease_until: Mapped[datetime | None] = mapped_column(UTCDateTime())


class RecommendationQueue:
    def __init__(self, service):
        self.service = service
        self.database = service.database
        self.tasks = {}
        self.dirty = set()
        self.locks = weakref.WeakValueDictionary()
        self.capacity = asyncio.Semaphore(2)
        self.closed = False

    async def close(self):
        self.closed = True
        tasks = list(self.tasks.values())
        if tasks:
            _, pending = await asyncio.wait(tasks, timeout=2)
            for task in pending:
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self.tasks.clear()
        self.dirty.clear()

    def warm(self, telegram_id):
        if self.closed:
            return
        if telegram_id in self.tasks:
            self.dirty.add(telegram_id)
            return
        if len(self.tasks) >= 32:
            return
        task = asyncio.create_task(self.fill(telegram_id))
        self.tasks[telegram_id] = task
        def completed(task):
            self.tasks.pop(telegram_id, None)
            if telegram_id in self.dirty:
                self.dirty.discard(telegram_id)
                self.warm(telegram_id)
        task.add_done_callback(completed)

    async def fill(self, telegram_id, *, feed=False):
        lock = self.locks.setdefault(telegram_id, asyncio.Lock())
        try:
            async with asyncio.timeout(30), lock, self.capacity:
                async with self.database.write() as session:
                    user_id = await session.scalar(select(User.id).where(User.telegram_user_id == telegram_id))
                    if user_id is None or self.closed:
                        return
                    state = await learning_state(session, user_id)
                    revision, cursor, generation = state.revision, state.seed_cursor, state.generation
                    await session.execute(delete(QueuedRecommendation).where(
                        QueuedRecommendation.user_id == user_id, QueuedRecommendation.expires_at <= utc_now()))
                    existing = list(await session.scalars(select(QueuedRecommendation.track_id).where(
                        QueuedRecommendation.user_id == user_id)))
                    feed_excluded = set()
                    if feed:
                        from ..feed_history import excluded_ids
                        feed_excluded = await excluded_ids(session, user_id)
                        await session.execute(delete(QueuedRecommendation).where(
                            QueuedRecommendation.user_id == user_id,
                            QueuedRecommendation.track_id.in_(feed_excluded)))
                        existing = [track_id for track_id in existing if track_id not in feed_excluded]
                    if len(existing) >= LOW_WATER:
                        return
                result = await self.service._recommend(telegram_id, QUEUE_TARGET, None, False, None,
                    exclude_track_ids=set(existing) | feed_excluded, seed_offset=cursor)
                async with self.database.write() as session:
                    state = await session.get(LearningState, user_id)
                    if state is None or state.generation != generation or state.revision != revision or self.closed:
                        return
                    state.seed_cursor += max(1, S.MAX_PROVIDER_CALLS - 1)
                    state.last_status = result.status
                    current = list(await session.scalars(select(QueuedRecommendation).where(QueuedRecommendation.user_id == user_id)))
                    current_ids = {row.track_id for row in current}
                    position_start = max((row.position for row in current), default=-1) + 1
                    additions = [row for row in result.recommendations if row.track_id not in current_ids]
                    for position, row in enumerate(additions[:max(0, QUEUE_TARGET - len(current))]):
                        await session.execute(insert(QueuedRecommendation).values(user_id=user_id,
                            track_id=row.track_id, payload=asdict(row), position=position_start + position,
                            expires_at=utc_now() + QUEUE_TTL).on_conflict_do_nothing(index_elements=['user_id', 'track_id']))
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning('Recommendation refill unavailable; details omitted for privacy.')

    async def reserve(self, telegram_id, limit=5, *, feed=False):
        if type(telegram_id) is not int or telegram_id <= 0:
            raise ValueError('Invalid Telegram user ID')
        if type(limit) is not int or not 1 <= limit <= S.MAX_LIMIT:
            raise ValueError('Invalid batch size')
        result = await self._reserve(telegram_id, limit, feed=feed)
        if feed and result.recommendations and len(result.recommendations) < min(5, limit):
            await self.fill(telegram_id, feed=True)
            await self.release(telegram_id, result.batch_id)
            return await self._reserve(telegram_id, limit, feed=True)
        if result.recommendations:
            return result
        await self.fill(telegram_id, feed=feed)
        return await self._reserve(telegram_id, limit, feed=feed)

    async def _reserve(self, telegram_id, limit, *, feed=False):
        batch = uuid4().hex
        async with self.database.write() as session:
            user_id = await session.scalar(select(User.id).where(User.telegram_user_id == telegram_id))
            if user_id is None:
                return RecommendationResult('insufficient_preferences')
            await session.execute(delete(TasteRequest).where(TasteRequest.user_id == user_id,
                TasteRequest.created_at <= utc_now() - REQUEST_WINDOW))
            await session.execute(delete(QueuedRecommendation).where(
                QueuedRecommendation.user_id == user_id, QueuedRecommendation.expires_at <= utc_now()))
            rows = list(await session.scalars(select(QueuedRecommendation).where(
                QueuedRecommendation.user_id == user_id).order_by(QueuedRecommendation.position, QueuedRecommendation.track_id)))
            _, blocked = await load_exclusions(session, user_id)
            if feed:
                from ..feed_history import excluded_ids
                excluded = await excluded_ids(session, user_id)
                excluded_items = await load_items(session, list(await session.scalars(
                    select(Track).where(Track.id.in_(excluded)))))
                for item in excluded_items.values():
                    blocked.update(item.identities)
            state = await session.get(LearningState, user_id)
            items = await load_items(session, list(await session.scalars(select(Track).where(
                Track.id.in_([row.track_id for row in rows])))))
            output = []
            for row in rows:
                item = items.get(row.track_id)
                if item is None or item.identities & blocked:
                    await session.delete(row)
                    continue
                if row.lease and row.lease_until and row.lease_until > utc_now():
                    blocked.update(item.identities)
                    continue
                if len(output) < limit:
                    row.lease, row.lease_until = batch, utc_now() + LEASE_TTL
                    values = dict(row.payload)
                    values['sources'] = tuple(values['sources'])
                    output.append(Recommendation(**values))
                    blocked.update(item.identities)
            status = state.last_status if state else 'insufficient_preferences'
            return RecommendationResult('ok' if output else ('no_candidates' if status == 'ok' else status), tuple(output), batch)

    async def release(self, telegram_id, batch):
        async with self.database.write() as session:
            user_id = await session.scalar(select(User.id).where(User.telegram_user_id == telegram_id))
            for row in await session.scalars(select(QueuedRecommendation).where(
                    QueuedRecommendation.user_id == user_id, QueuedRecommendation.lease == batch)):
                row.lease, row.lease_until = None, None
