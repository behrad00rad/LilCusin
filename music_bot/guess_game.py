"""Private persistence for Guess their taste. No Telegram or provider calls.

Recording IDs are the application's canonical tracks.id values. Public round
projection belongs to the game service; never serialize these models directly.
"""
import os
import secrets
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, JSON, delete, text
from sqlalchemy.orm import Mapped, mapped_column, validates

from .models import Base, UTCDateTime, utc_now


def enabled():
    return os.environ.get('GUESS_GAME', '').strip().lower() in {'1', 'true', 'yes', 'on'}


class GuessSettings(Base):
    __tablename__ = 'guess_settings'
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    allow_guess: Mapped[bool] = mapped_column(default=True, server_default=text('1'))


class GuessGame(Base):
    __tablename__ = 'guess_games'
    __table_args__ = (
        CheckConstraint('guesser_id != target_id'),
        CheckConstraint("status IN ('open','done','expired')"),
        CheckConstraint('score BETWEEN 0 AND 5'),
        CheckConstraint("(status = 'open' AND finished_at IS NULL) OR "
                        "(status != 'open' AND finished_at IS NOT NULL)"),
        Index('uq_guess_open_pair', 'guesser_id', 'target_id', unique=True,
              sqlite_where=text("status = 'open'")),
        Index('ix_guess_pair_created', 'guesser_id', 'target_id', 'created_at'),
    )
    id: Mapped[str] = mapped_column(primary_key=True, default=lambda: secrets.token_urlsafe(24))
    guesser_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    target_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    status: Mapped[str] = mapped_column(default='open')
    score: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class GuessRound(Base):
    __tablename__ = 'guess_rounds'
    __table_args__ = (
        CheckConstraint('idx BETWEEN 0 AND 4'),
        CheckConstraint("json_type(option_ids) = 'array' AND json_array_length(option_ids) = 4"),
        CheckConstraint('(picked_recording_id IS NULL AND correct IS NULL) OR '
                        '(picked_recording_id IS NOT NULL AND correct IS NOT NULL)'),
    )
    game_id: Mapped[str] = mapped_column(ForeignKey('guess_games.id', ondelete='CASCADE'), primary_key=True)
    idx: Mapped[int] = mapped_column(primary_key=True)
    correct_recording_id: Mapped[int] = mapped_column(ForeignKey('tracks.id', ondelete='CASCADE'))
    option_ids: Mapped[list] = mapped_column(JSON)
    picked_recording_id: Mapped[int | None] = mapped_column(ForeignKey('tracks.id', ondelete='CASCADE'))
    correct: Mapped[bool | None]

    @validates('option_ids')
    def validate_options(self, _, value):
        if (not isinstance(value, list) or len(value) != 4 or
                any(type(item) is not int or item <= 0 for item in value) or len(set(value)) != 4):
            raise ValueError('A round requires four distinct recording IDs')
        return list(value)


async def allow_guess(session, user_id, value=None):
    """Absent row means ON; an explicit opt-out never changes taste sharing."""
    if value is not None and type(value) is not bool:
        raise ValueError('allow_guess must be a boolean')
    row = await session.get(GuessSettings, user_id)
    if value is not None:
        if row is None:
            row = GuessSettings(user_id=user_id, allow_guess=value)
            session.add(row)
        else:
            row.allow_guess = value
        if not value:
            # Withdraw all persisted answers as soon as consent is withdrawn.
            await session.execute(delete(GuessGame).where(GuessGame.target_id == user_id))
    return row.allow_guess if row is not None else True


async def purge_games(session, first, second=None):
    """Called inside the unfriend/block transaction, including finished games."""
    pair = (GuessGame.guesser_id == first) | (GuessGame.target_id == first)
    if second is not None:
        pair &= (GuessGame.guesser_id == second) | (GuessGame.target_id == second)
    await session.execute(delete(GuessGame).where(pair))
