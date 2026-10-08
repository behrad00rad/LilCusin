import tempfile
import unittest
from datetime import UTC
from pathlib import Path

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from music_bot.database import Database
from music_bot.models import (
    Base, Rating, SongSubmission, Track, TrackExternalID, TrackTag, User,
)
from music_bot.submissions import AudioMetadata, InvalidSubmission, SubmissionService, Submitter, parse_song


class ParsingTests(unittest.TestCase):
    def test_valid_text(self):
        for raw, expected in [
            ("  Radiohead - Creep  ", ("Radiohead", "Creep")),
            ("AC-DC — Back in Black", ("AC-DC", "Back in Black")),
            ("گوگوش – من آمده‌ام", ("گوگوش", "من آمده‌ام")),
            ("Artist - Title - Live", ("Artist", "Title - Live")),
        ]:
            with self.subTest(raw=raw):
                self.assertEqual(parse_song(raw), expected)

    def test_malformed_and_commands(self):
        for raw in ("", "song", " - Title", "Artist - ", "/start", " /x - title", "Artist-Title"):
            with self.subTest(raw=raw), self.assertRaises(InvalidSubmission):
                parse_song(raw)


class DatabaseTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database = Database(Path(self.temp.name) / "test.sqlite3")
        await self.database.initialize()
        self.service = SubmissionService(self.database)
        self.user = Submitter(123456789012, "tester", "Test", "fa")

    async def asyncTearDown(self):
        await self.database.close()
        self.temp.cleanup()

    async def test_repeat_initialization_preserves_data_and_schema(self):
        await self.service.submit_text(self.user, "Artist - Song")
        await self.database.initialize()
        async with self.database.sessions() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(SongSubmission)), 1)
            self.assertEqual(await session.scalar(text("PRAGMA foreign_keys")), 1)
            tables = set((await session.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"))).scalars())
            self.assertEqual(tables, set(Base.metadata.tables))

    async def test_text_audio_pending_and_user_upsert(self):
        first = await self.service.submit_text(self.user, "گوگوش — من آمده‌ام")
        audio = AudioMetadata("file", "unique", duration=120, filename="song.mp3", mime_type="audio/mpeg", file_size=4000)
        second = await self.service.submit_audio(Submitter(self.user.telegram_user_id, "new"), audio)
        third = await self.service.submit_audio(self.user, audio)
        self.assertNotEqual(second.id, third.id)  # Every submission is retained.
        async with self.database.sessions() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(User)), 1)
            self.assertEqual(await session.scalar(select(func.count()).select_from(Rating)), 0)
            self.assertEqual(await session.scalar(select(func.count()).select_from(Track)), 0)
            user = await session.scalar(select(User))
            self.assertEqual(user.username, "tester")
            self.assertEqual(user.created_at.tzinfo, UTC)
            self.assertGreaterEqual(user.last_activity_at, user.created_at)
            for saved_id in (first.id, second.id):
                saved = await session.get(SongSubmission, saved_id)
                self.assertEqual(saved.identification_status, "pending")
                self.assertIsNone(saved.track_id)
                self.assertEqual(saved.created_at.tzinfo, UTC)
            stored_audio = await session.get(SongSubmission, second.id)
            self.assertIsNone(stored_audio.parsed_artist)
            self.assertIsNone(stored_audio.parsed_title)
            self.assertEqual(stored_audio.file_id, "file")
            self.assertEqual(stored_audio.file_unique_id, "unique")
            self.assertEqual(stored_audio.duration, 120)
            self.assertEqual(stored_audio.original_filename, "song.mp3")
            stored_text = await session.get(SongSubmission, first.id)
            self.assertEqual(stored_text.raw_text, "گوگوش — من آمده‌ام")
            self.assertEqual(stored_text.parsed_artist, "گوگوش")

    async def test_audio_metadata_preserved(self):
        saved = await self.service.submit_audio(
            self.user, AudioMetadata("f", "u", performer="Artist", title="Title"),
        )
        self.assertEqual((saved.parsed_artist, saved.parsed_title), ("Artist", "Title"))

    async def test_unique_telegram_id(self):
        await self.service.submit_text(self.user, "Artist - Song")
        with self.assertRaises(IntegrityError):
            async with self.database.sessions.begin() as session:
                session.add(User(telegram_user_id=self.user.telegram_user_id))

    async def test_invalid_text_does_not_create_user(self):
        with self.assertRaises(InvalidSubmission):
            await self.service.submit_text(self.user, "bad")
        async with self.database.sessions() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(User)), 0)

    async def test_rating_constraint(self):
        saved = await self.service.submit_text(self.user, "Artist - Song")
        async with self.database.sessions.begin() as session:
            track = Track(title="Song", artist="Artist", metadata_source="lastfm")
            session.add(track)
            await session.flush()
            session.add(Rating(user_id=saved.user_id, track_id=track.id, value="love"))
        with self.assertRaises(IntegrityError):
            async with self.database.sessions.begin() as session:
                session.add(Rating(user_id=saved.user_id, track_id=track.id, value="like"))

    async def test_track_tag_and_identifier_uniqueness(self):
        async with self.database.sessions.begin() as session:
            track = Track(title=" SONG ", artist="  ARTIST ", metadata_source="lastfm")
            session.add(track)
            await session.flush()
            session.add(TrackTag(track_id=track.id, name="ROCK", source="lastfm"))
            session.add(TrackExternalID(track_id=track.id, provider="musicbrainz", external_identifier="mbid"))
        duplicates = [
            Track(title="song", artist="artist", metadata_source="musicbrainz"),
            TrackTag(track_id=track.id, name="rock", source="lastfm"),
            TrackExternalID(track_id=track.id, provider="musicbrainz", external_identifier="mbid"),
        ]
        for duplicate in duplicates:
            with self.subTest(model=type(duplicate).__name__), self.assertRaises(IntegrityError):
                async with self.database.sessions.begin() as session:
                    session.add(duplicate)

    async def test_foreign_key_enforced(self):
        with self.assertRaises(IntegrityError):
            async with self.database.sessions.begin() as session:
                session.add(SongSubmission(user_id=999, submission_type="text"))
