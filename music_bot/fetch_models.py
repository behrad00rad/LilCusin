"""Durable, private audio fetching records, separate from canonical catalogue tracks."""
from sqlalchemy import ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .models import Base, UTCDateTime, utc_now
from datetime import datetime

class FetchJob(Base):
    __tablename__ = 'audio_fetch_jobs'
    id: Mapped[str] = mapped_column(primary_key=True)
    track_id: Mapped[int] = mapped_column(ForeignKey('tracks.id'))
    key: Mapped[str] = mapped_column(unique=True)
    state: Mapped[str] = mapped_column(default='queued')
    video_id: Mapped[str | None]
    candidates: Mapped[list] = mapped_column(JSON, default=list)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)

class AudioRequest(Base):
    __tablename__ = 'audio_requests'
    id: Mapped[str] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    job_id: Mapped[str] = mapped_column(ForeignKey('audio_fetch_jobs.id'), index=True)
    state: Mapped[str] = mapped_column(default='pending')
    message_id: Mapped[int | None]
    delivered_video_id: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)

class AudioDelivery(Base):
    __tablename__ = 'audio_deliveries'
    __table_args__ = (UniqueConstraint('user_id', 'track_id', 'video_id'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    track_id: Mapped[int] = mapped_column(ForeignKey('tracks.id'))
    video_id: Mapped[str]
    file_id: Mapped[str]
    message_id: Mapped[int]
    artwork_key: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class AudioSource(Base):
    __tablename__ = 'audio_sources'
    __table_args__ = (UniqueConstraint('track_id', 'video_id'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    track_id: Mapped[int] = mapped_column(ForeignKey('tracks.id'))
    video_id: Mapped[str]
    fetch_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    fetched_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class AudioSelection(Base):
    """A user's recording correction; never a global change to canonical identity."""
    __tablename__ = 'audio_selections'
    __table_args__ = (UniqueConstraint('user_id', 'track_id'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    track_id: Mapped[int] = mapped_column(ForeignKey('tracks.id'))
    video_id: Mapped[str | None]
    rejected_ids: Mapped[list] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
