"""Phase 1 schema. Durations are seconds; all timestamps round-trip as UTC."""

import unicodedata
from datetime import UTC, datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Float, ForeignKey, Index, JSON, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, validates
from sqlalchemy.types import TypeDecorator


def utc_now() -> datetime:
    return datetime.now(UTC)


def normalize_name(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).split()).casefold()


class UTCDateTime(TypeDecorator):
    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Timestamp must be timezone-aware")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value, dialect):
        return value.replace(tzinfo=UTC) if value is not None else None


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    username: Mapped[str | None]
    display_name: Mapped[str | None]
    language_code: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    last_activity_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class Track(Base):
    __tablename__ = "tracks"
    __table_args__ = (UniqueConstraint("artist", "title"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str]
    artist: Mapped[str]
    display_title: Mapped[str | None]
    display_artist: Mapped[str | None]
    album: Mapped[str | None]
    artwork_url: Mapped[str | None]
    duration: Mapped[float | None]
    bpm: Mapped[float | None]
    metadata_source: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, onupdate=utc_now)

    @validates("artist", "title")
    def normalize_identity(self, key, value):
        normalized = normalize_name(value)
        if not normalized:
            raise ValueError("Track artist and title must be nonempty")
        return normalized


class TrackExternalID(Base):
    __tablename__ = "track_external_ids"
    __table_args__ = (UniqueConstraint("provider", "external_identifier"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id"), index=True)
    provider: Mapped[str]
    external_identifier: Mapped[str]
    track: Mapped[Track] = relationship()


class TrackTag(Base):
    __tablename__ = "track_tags"
    __table_args__ = (UniqueConstraint("track_id", "name", "source"), Index("ix_track_tags_name_track", "name", "track_id"))

    id: Mapped[int] = mapped_column(primary_key=True)
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id"))
    name: Mapped[str]
    display_name: Mapped[str | None]
    weight: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str]
    track: Mapped[Track] = relationship()

    @validates("name", "source")
    def normalize_tag(self, key, value):
        return normalize_name(value)


class SongSubmission(Base):
    __tablename__ = "song_submissions"
    __table_args__ = (
        CheckConstraint("submission_type IN ('text', 'telegram_audio')"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    track_id: Mapped[int | None] = mapped_column(ForeignKey("tracks.id"), index=True)
    submission_type: Mapped[str]
    raw_text: Mapped[str | None]
    parsed_artist: Mapped[str | None]
    parsed_title: Mapped[str | None]
    file_id: Mapped[str | None]
    file_unique_id: Mapped[str | None]
    original_filename: Mapped[str | None]
    mime_type: Mapped[str | None]
    file_size: Mapped[int | None] = mapped_column(BigInteger)
    duration: Mapped[float | None]
    identification_status: Mapped[str] = mapped_column(String, default="pending")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    user: Mapped[User] = relationship()
    track: Mapped[Track | None] = relationship()


class Rating(Base):
    __tablename__ = "ratings"
    __table_args__ = (
        UniqueConstraint("user_id", "track_id"),
        CheckConstraint("value IN ('love', 'like', 'neutral', 'dislike')"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id"), index=True)
    value: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, onupdate=utc_now)
    user: Mapped[User] = relationship()
    track: Mapped[Track] = relationship()


class RecommendationHistory(Base):
    __tablename__ = "recommendation_history"
    __table_args__ = (
        Index("uq_recommendation_batch_track", "user_id", "batch_id", "track_id", unique=True),
        Index("ix_recommendation_user_time", "user_id", "recommended_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id"), index=True)
    recommended_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    reason: Mapped[str | None]
    source: Mapped[str | None]
    ranking_score: Mapped[float | None]
    batch_id: Mapped[str | None]
    position: Mapped[int | None]
    user: Mapped[User] = relationship()
    track: Mapped[Track] = relationship()


class IdentificationFlow(Base):
    __tablename__ = "identification_flows"

    submission_id: Mapped[int] = mapped_column(ForeignKey("song_submissions.id"), primary_key=True)
    state: Mapped[str] = mapped_column(default="searching")
    revision: Mapped[int] = mapped_column(default=0)
    attempts: Mapped[int] = mapped_column(default=0)
    corrected_artist: Mapped[str | None]
    corrected_title: Mapped[str | None]
    candidates: Mapped[list] = mapped_column(JSON, default=list)
    prompt_message_id: Mapped[int | None]
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())


class ProviderCache(Base):
    __tablename__ = "provider_cache"

    key: Mapped[str] = mapped_column(primary_key=True)
    provider: Mapped[str]
    method: Mapped[str]
    payload: Mapped[dict] = mapped_column(JSON)
    retrieved_at: Mapped[datetime] = mapped_column(UTCDateTime())
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())


class SimilarTrack(Base):
    """Normalized candidates, without creating unconfirmed canonical tracks."""

    __tablename__ = "similar_tracks"
    __table_args__ = (UniqueConstraint("track_id", "provider", "candidate_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id"), index=True)
    provider: Mapped[str]
    candidate_key: Mapped[str]
    candidate: Mapped[dict] = mapped_column(JSON)
    score: Mapped[float | None]
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class AudioAnalysis(Base):
    """Compact numerical results, versioned by analyzer; never raw audio."""

    __tablename__ = "audio_analyses"
    __table_args__ = (
        UniqueConstraint("track_id", "analyzer_name", "analyzer_version"),
        CheckConstraint("status IN ('pending', 'processing', 'succeeded', 'failed')"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id"), index=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("song_submissions.id"))
    requested_by: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    analyzer_name: Mapped[str]
    analyzer_version: Mapped[str]
    status: Mapped[str]
    error_category: Mapped[str | None]
    attempts: Mapped[int] = mapped_column(default=1)
    bpm: Mapped[float | None]
    features: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, onupdate=utc_now)
    track: Mapped[Track] = relationship()


class ChatControl(Base):
    """Short-lived owner/message-bound Telegram controls; no secret or raw messages."""

    __tablename__ = "chat_controls"

    token: Mapped[str] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    message_id: Mapped[int | None]
    payload: Mapped[dict] = mapped_column(JSON)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)


class ChannelConnectionCode(Base):
    __tablename__ = "channel_connection_codes"
    code_hash: Mapped[str] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())


class PlaylistChannel(Base):
    __tablename__ = "playlist_channels"
    __table_args__ = ({"sqlite_autoincrement": True},)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    telegram_chat_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    title: Mapped[str]
    status: Mapped[str] = mapped_column(default="connected")
    connected_at: Mapped[datetime] = mapped_column(UTCDateTime())
    after_message_id: Mapped[int]


class ChannelPost(Base):
    __tablename__ = "channel_posts"
    __table_args__ = (UniqueConstraint("channel_id", "message_id"),
                     UniqueConstraint("channel_id", "file_unique_id"), {"sqlite_autoincrement": True})
    id: Mapped[int] = mapped_column(primary_key=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("playlist_channels.id"), index=True)
    message_id: Mapped[int]
    file_unique_id: Mapped[str]
    submission_id: Mapped[int] = mapped_column(ForeignKey("song_submissions.id"), unique=True)
    track_id: Mapped[int | None] = mapped_column(ForeignKey("tracks.id"))
    status: Mapped[str] = mapped_column(default="processing")
    learn_allowed: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class UserTrackSignal(Base):
    __tablename__ = "user_track_signals"
    __table_args__ = (UniqueConstraint("user_id", "track_id", "channel_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id"), index=True)
    signal_type: Mapped[str] = mapped_column(default="playlist_channel")
    channel_id: Mapped[int] = mapped_column(ForeignKey("playlist_channels.id"), index=True)
    channel_post_id: Mapped[int] = mapped_column(ForeignKey("channel_posts.id"))
    weight: Mapped[float]
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
