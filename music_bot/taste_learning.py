"""Private taste evidence, separate from ratings and observed playback."""

from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import ForeignKey, String, UniqueConstraint, delete, select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base, UTCDateTime, utc_now

REQUEST_WINDOW = timedelta(days=90)
MAX_REQUEST_EVENTS = 500


class LearningState(Base):
    __tablename__ = 'recommendation_learning'
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    enabled: Mapped[bool] = mapped_column(default=True)
    revision: Mapped[int] = mapped_column(default=0)
    seed_cursor: Mapped[int] = mapped_column(default=0)
    generation: Mapped[str] = mapped_column(String(32), default=lambda: uuid4().hex)
    last_status: Mapped[str] = mapped_column(String(32), default='insufficient_preferences')
    saves_since: Mapped[datetime | None] = mapped_column(UTCDateTime())


class TasteRequest(Base):
    __tablename__ = 'taste_request_events'
    __table_args__ = (UniqueConstraint('user_id', 'request_key'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    track_id: Mapped[int] = mapped_column(ForeignKey('tracks.id'), index=True)
    request_key: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class TrackPreference(Base):
    __tablename__ = 'private_track_preferences'
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    track_id: Mapped[int] = mapped_column(ForeignKey('tracks.id'), primary_key=True)
    feedback: Mapped[str | None] = mapped_column(String(20))
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


async def learning_state(session, user_id):
    await session.execute(insert(LearningState).values(user_id=user_id, enabled=True, revision=0, seed_cursor=0,
        generation=uuid4().hex, last_status='insufficient_preferences')
                          .on_conflict_do_nothing(index_elements=['user_id']))
    return await session.get(LearningState, user_id, populate_existing=True)


async def invalidate(session, user_id):
    from .recommendations.queue import QueuedRecommendation
    state = await learning_state(session, user_id)
    state.revision += 1
    state.last_status = 'insufficient_preferences'
    await session.execute(delete(QueuedRecommendation).where(QueuedRecommendation.user_id == user_id))


async def record_request(session, user_id, track_id, request_key):
    from .feed_history import record_event
    await record_event(session, user_id, track_id, 'engaged')
    state = await learning_state(session, user_id)
    await session.execute(delete(TasteRequest).where(TasteRequest.user_id == user_id,
        TasteRequest.created_at <= utc_now() - REQUEST_WINDOW))
    if not state.enabled:
        return False
    result = await session.execute(insert(TasteRequest).values(user_id=user_id, track_id=track_id,
        request_key=request_key, created_at=utc_now()).on_conflict_do_nothing(index_elements=['user_id', 'request_key']))
    if not result.rowcount:
        return False
    old = select(TasteRequest.id).where(TasteRequest.user_id == user_id).order_by(
        TasteRequest.created_at.desc(), TasteRequest.id.desc()).offset(MAX_REQUEST_EVENTS)
    await session.execute(delete(TasteRequest).where(TasteRequest.id.in_(old)))
    await invalidate(session, user_id)
    return True


async def feedback(session, user_id, track_id, action):
    if action not in {'save', 'unsave', 'known', 'notforme'}:
        raise ValueError('Unsupported taste action')
    from .social import SavedSong, remove_saved
    row = await session.get(TrackPreference, (user_id, track_id))
    if row is None:
        row = TrackPreference(user_id=user_id, track_id=track_id)
        session.add(row)
    saved_row = await session.get(SavedSong, (user_id, track_id))
    saved = saved_row is not None
    before = (saved, row.feedback)
    renewed = False
    if action == 'save':
        from .feed_history import record_event
        await record_event(session, user_id, track_id, 'engaged')
        state = await learning_state(session, user_id)
        if saved_row is not None and state.saves_since and saved_row.created_at <= state.saves_since:
            saved_row.created_at = utc_now()
            renewed = True
        await session.execute(insert(SavedSong).values(user_id=user_id, track_id=track_id)
            .on_conflict_do_nothing(index_elements=['user_id', 'track_id']))
        row.feedback = None
        saved = True
    elif action == 'known':
        row.feedback = 'known'
    else:
        await remove_saved(session, user_id, track_id, update_taste=False)
        if action != 'unsave':
            row.feedback = 'not_for_me'
        saved = False
    if renewed or before != (saved, row.feedback):
        row.updated_at = utc_now()
        await invalidate(session, user_id)
