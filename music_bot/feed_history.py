"""Private Home-feed memory. Browsing events never update ratings or taste."""

from datetime import datetime, timedelta
import os

from sqlalchemy import ForeignKey, JSON, or_, select
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base, UTCDateTime, utc_now

try:
    SKIP_COOLDOWN_DAYS = max(1, min(365, int(os.getenv('SKIP_COOLDOWN_DAYS', '14'))))
except ValueError:
    SKIP_COOLDOWN_DAYS = 14


class FeedHistory(Base):
    __tablename__ = 'feed_history'
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    track_id: Mapped[int] = mapped_column(ForeignKey('tracks.id', ondelete='CASCADE'), primary_key=True)
    seen_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    skipped_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    skip_count: Mapped[int] = mapped_column(default=0)
    skip_ids: Mapped[list] = mapped_column(JSON, default=list)
    hidden_until: Mapped[datetime | None] = mapped_column(UTCDateTime())
    hidden_forever: Mapped[bool] = mapped_column(default=False)
    engaged: Mapped[bool] = mapped_column(default=False)


async def record_event(session, user_id, track_id, event, event_id='', *, now=None):
    """Caller authorizes the track first; repeated skip deliveries are idempotent."""
    if event not in {'seen', 'skipped', 'not_now', 'hidden', 'engaged'}:
        raise ValueError('Invalid feed event')
    now = now or utc_now()
    row = await session.get(FeedHistory, (user_id, track_id))
    if row is None:
        row = FeedHistory(user_id=user_id, track_id=track_id, skip_count=0,
                          skip_ids=[], hidden_forever=False, engaged=False)
        session.add(row)
    if event == 'engaged':
        row.engaged = True
    elif event == 'seen':
        row.seen_at = now
    elif event == 'skipped':
        if event_id and event_id in row.skip_ids:
            return
        row.skip_count += 1
        row.skipped_at = now
        row.skip_ids = (row.skip_ids + [event_id])[-8:]
        until = now + timedelta(days=60 if row.skip_count >= 2 else SKIP_COOLDOWN_DAYS)
        row.hidden_until = max(row.hidden_until or until, until)
    elif event == 'not_now':
        until = now + timedelta(days=30)
        row.hidden_until = max(row.hidden_until or until, until)
    else:
        row.hidden_forever = True


async def excluded_ids(session, user_id, *, now=None):
    """Also cover pre-existing actions, before feed memory was introduced."""
    from .models import Rating
    from .social import SavedSong, SongSwap
    from .taste_cards import SignatureSong, TasteCard
    from .fetch_models import AudioRequest, FetchJob
    from .taste_learning import TasteRequest
    now = now or utc_now()
    queries = [select(FeedHistory.track_id).where(FeedHistory.user_id == user_id, or_(
        FeedHistory.engaged.is_(True), FeedHistory.hidden_forever.is_(True),
        FeedHistory.hidden_until > now, FeedHistory.seen_at > now - timedelta(days=1))),
        select(Rating.track_id).where(Rating.user_id == user_id),
        select(SavedSong.track_id).where(SavedSong.user_id == user_id),
        select(SignatureSong.track_id).where(SignatureSong.user_id == user_id),
        select(TasteCard.current_track_id).where(TasteCard.user_id == user_id),
        select(SongSwap.track_id).where(SongSwap.sender_id == user_id, SongSwap.sent_at.is_not(None)),
        select(FetchJob.track_id).join(AudioRequest, AudioRequest.job_id == FetchJob.id)
            .where(AudioRequest.user_id == user_id),
        select(TasteRequest.track_id).where(TasteRequest.user_id == user_id)]
    return set(await session.scalars(queries[0].union(*queries[1:]))) - {None}


async def filter_rows(database, telegram_id, rows, extra=()):
    """Recheck aliases after queue/friend composition, under the authenticated actor."""
    from .models import Track, User
    from .providers.common import TrackCandidate
    from .recommendations.repository import aliases, load_items
    async with database.sessions() as session:
        user_id = await session.scalar(select(User.id).where(User.telegram_user_id == telegram_id))
        ids = await excluded_ids(session, user_id) | set(extra)
        items = await load_items(session, list(await session.scalars(select(Track).where(Track.id.in_(ids)))))
        blocked = set().union(*(item.identities for item in items.values())) if items else set()
    return [row for row in rows if row['id'] not in ids and not aliases(TrackCandidate(
        title=row['title'], artist=row['artist'], source='feed')) & blocked]
