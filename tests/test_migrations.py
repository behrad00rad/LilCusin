from sqlalchemy import select

from music_bot.models import SongSubmission, Track, TrackTag, User
from tests.support import ServiceTestCase


class MigrationTests(ServiceTestCase):
    async def test_legacy_columns_and_data_survive_repeat_initialization(self):
        saved = await self.submissions.submit_text(self.user, "Artist - Song")
        async with self.database.sessions.begin() as session:
            track = Track(artist="Artist", title="Song", metadata_source="lastfm")
            session.add(track)
            await session.flush()
            session.add(TrackTag(track_id=track.id, name="rock", source="lastfm"))
        # Reproduce the previous schema only in this disposable test database.
        async with self.database.engine.begin() as connection:
            for table, column in [("tracks", "display_artist"), ("tracks", "display_title"), ("track_tags", "display_name")]:
                await connection.exec_driver_sql(f'ALTER TABLE "{table}" DROP COLUMN "{column}"')
        await self.database.initialize()
        await self.database.initialize()
        async with self.database.sessions() as session:
            self.assertEqual((await session.get(SongSubmission, saved.id)).raw_text, "Artist - Song")
            self.assertEqual((await session.scalar(select(User))).telegram_user_id, 123)
            track = await session.scalar(select(Track))
            self.assertEqual(track.title, "song")
            self.assertIsNone(track.display_title)
            self.assertEqual((await session.scalar(select(TrackTag))).name, "rock")
