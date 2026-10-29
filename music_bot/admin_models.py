"""Additive owner-console records. No credentials, messages or provider payloads."""
from datetime import datetime
from sqlalchemy import CheckConstraint, ForeignKey, Index, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .models import Base, UTCDateTime, utc_now


class AdminSession(Base):
    __tablename__ = 'admin_sessions'
    token_hash: Mapped[str] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    csrf_hash: Mapped[str]
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)


class AdminAudit(Base):
    __tablename__ = 'admin_audit'
    id: Mapped[int] = mapped_column(primary_key=True)
    # No names, Telegram IDs, request bodies or deleted-user identifiers.
    actor_id: Mapped[int | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'))
    action: Mapped[str]
    object_id: Mapped[int | None]
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, index=True)


class AdminLoginCode(Base):
    """Owner-issued desktop handoff; only a hash is persisted."""
    __tablename__ = 'admin_login_codes'
    code_hash: Mapped[str] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), unique=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)


class AdminStage(Base):
    __tablename__ = 'admin_onboarding_stages'
    __table_args__ = (UniqueConstraint('user_id', 'stage', 'source'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    stage: Mapped[str]
    source: Mapped[str] = mapped_column(default='first_party')
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, index=True)


class AdminMetric(Base):
    __tablename__ = 'admin_daily_metrics'
    __table_args__ = (UniqueConstraint('day', 'source', 'kind'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    day: Mapped[str] = mapped_column(index=True)
    source: Mapped[str] = mapped_column(default='first_party')
    kind: Mapped[str]
    count: Mapped[int] = mapped_column(default=0)
    duration_ms: Mapped[int] = mapped_column(default=0)


class AdminCollection(Base):
    __tablename__ = 'admin_collection'
    id: Mapped[int] = mapped_column(primary_key=True)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class AdSettings(Base):
    __tablename__ = 'ad_settings'
    id: Mapped[int] = mapped_column(primary_key=True)
    values: Mapped[dict] = mapped_column(JSON, default=dict)


class AdCampaign(Base):
    __tablename__ = 'ad_campaigns'
    __table_args__ = (CheckConstraint("status IN ('draft','pending_approval','approved','paused','completed','rejected')"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    advertiser: Mapped[str]
    campaign_type: Mapped[str]
    title: Mapped[str]
    description: Mapped[str]
    artwork_url: Mapped[str | None]
    destination_url: Mapped[str]
    starts_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    ends_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    status: Mapped[str] = mapped_column(default='draft', index=True)
    impression_limit: Mapped[int]
    daily_cap: Mapped[int]
    budget: Mapped[str | None]  # Decimal strings, never floats or inferred revenue.
    cpm: Mapped[str | None]
    placement: Mapped[str] = mapped_column(default='discovery_feed')
    targeting: Mapped[dict] = mapped_column(JSON, default=dict)
    source: Mapped[str] = mapped_column(default='first_party')
    version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class AdEvent(Base):
    __tablename__ = 'ad_events'
    __table_args__ = (UniqueConstraint('source', 'event_key'),
                     CheckConstraint("kind IN ('impression','click')"),
                     Index('ix_ad_event_campaign_day', 'campaign_id', 'kind', 'created_at'),
                     Index('ix_ad_event_user_day', 'user_id', 'kind', 'created_at'))
    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey('ad_campaigns.id'))
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    kind: Mapped[str]
    source: Mapped[str] = mapped_column(default='first_party')
    event_key: Mapped[str]
    impression_id: Mapped[int | None] = mapped_column(ForeignKey('ad_events.id', ondelete='CASCADE'))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
