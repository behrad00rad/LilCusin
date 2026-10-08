"""Parsing and atomic submission persistence, independent of Telegram handlers."""

import re
from dataclasses import dataclass

from sqlalchemy.dialects.sqlite import insert

from .database import Database
from .models import SongSubmission, User, utc_now


class InvalidSubmission(ValueError):
    pass


def parse_song(value: str) -> tuple[str, str]:
    if value.lstrip().startswith("/"):
        raise InvalidSubmission("Commands are not song submissions")
    # Spaces avoid splitting hyphenated artist names; split just the first dash.
    parts = re.split(r"\s+[-–—]\s+", value.strip(), maxsplit=1)
    if len(parts) != 2 or any(not part.strip() for part in parts):
        raise InvalidSubmission("Expected Artist - Song title")
    return tuple(part.strip() for part in parts)


@dataclass(frozen=True)
class Submitter:
    telegram_user_id: int
    username: str | None = None
    display_name: str | None = None
    language_code: str | None = None


@dataclass(frozen=True)
class AudioMetadata:
    file_id: str
    file_unique_id: str
    performer: str | None = None
    title: str | None = None
    filename: str | None = None
    mime_type: str | None = None
    file_size: int | None = None
    duration: float | None = None


class SubmissionService:
    def __init__(self, database: Database):
        self.database = database

    async def _save(self, submitter: Submitter, **fields) -> SongSubmission:
        async with self.database.sessions.begin() as session:
            profile = {
                "username": submitter.username, "display_name": submitter.display_name,
                "language_code": submitter.language_code, "last_activity_at": utc_now(),
            }
            statement = insert(User).values(
                telegram_user_id=submitter.telegram_user_id, **profile,
            ).on_conflict_do_update(
                index_elements=[User.telegram_user_id], set_=profile,
            ).returning(User.id)
            user_id = (await session.execute(statement)).scalar_one()
            submission = SongSubmission(user_id=user_id, **fields)
            session.add(submission)
            await session.flush()
        return submission

    async def submit_text(self, user: Submitter, raw_text: str) -> SongSubmission:
        artist, title = parse_song(raw_text)
        return await self._save(
            user, submission_type="text", raw_text=raw_text,
            parsed_artist=artist, parsed_title=title,
        )

    async def submit_audio(self, user: Submitter, audio: AudioMetadata) -> SongSubmission:
        return await self._save(
            user, submission_type="telegram_audio",
            parsed_artist=audio.performer, parsed_title=audio.title,
            file_id=audio.file_id, file_unique_id=audio.file_unique_id,
            original_filename=audio.filename, mime_type=audio.mime_type,
            file_size=audio.file_size, duration=audio.duration,
        )
