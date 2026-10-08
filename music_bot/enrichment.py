import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert

from .catalog import attach_ids, save_tags
from .matching import deduplicate, encode_track, identity_key, similarities
from .models import SimilarTrack, Track, TrackExternalID, utc_now
from .providers.common import ProviderError

logger = logging.getLogger("music_bot")


class Enrichment:
    def __init__(self, database, providers):
        self.database = database
        self.providers = providers
        self.tasks = {}
        self.slots = asyncio.Semaphore(3)

    def schedule(self, track_id):
        if track_id not in self.tasks:
            self.tasks[track_id] = asyncio.create_task(self._background(track_id))

    async def _background(self, track_id):
        try:
            async with asyncio.timeout(35):
                async with self.slots:
                    await self.enrich(track_id)
        except Exception:
            logger.warning("Metadata enrichment failed or timed out; rating remains available.")
        finally:
            self.tasks.pop(track_id, None)

    async def close(self):
        tasks = list(self.tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _optional(self, provider, method, *args):
        try:
            return await self.providers.call(provider, method, *args)
        except ProviderError:
            logger.warning("Provider enrichment unavailable; keeping existing metadata.")
            return None

    async def _metadata(self, track_id, candidate):
        if candidate is None:
            return
        async with self.database.write() as session:
            track = await session.get(Track, track_id)
            if track is None:
                return
            identifiers = dict((await session.execute(select(
                TrackExternalID.provider, TrackExternalID.external_identifier,
            ).where(TrackExternalID.track_id == track_id))).all())
            shared = any(identifiers.get(p) == value for p, value in candidate.external_ids.items())
            exact = min(similarities(track.artist, track.title, candidate)) == 1
            if not shared and not exact:
                return  # Never enrich a different recording returned by autocorrect.
            for field in ("album", "duration", "artwork_url"):
                if (value := getattr(candidate, field)) is not None:
                    setattr(track, field, value)
            if candidate.artist and candidate.title:
                track.display_artist, track.display_title = candidate.artist, candidate.title
            track.updated_at = utc_now()
            await attach_ids(session, track.id, candidate.external_ids)
            await save_tags(session, track.id, candidate.tags)

    async def enrich(self, track_id):
        async with self.database.sessions() as session:
            track = await session.get(Track, track_id)
        if track is None:
            return
        artist, title = track.display_artist or track.artist, track.display_title or track.title
        info = await self._optional("lastfm", "get_track_info", artist, title)
        await self._metadata(track_id, info)
        tags = await self._optional("lastfm", "get_top_tags", artist, title)
        if tags:
            async with self.database.write() as session:
                await save_tags(session, track_id, tags)
        similar = await self._optional("lastfm", "get_similar_tracks", artist, title)
        if similar:
            async with self.database.write() as session:
                for candidate in deduplicate(similar):
                    key = identity_key(candidate.artist, candidate.title)
                    if key == identity_key(artist, title):
                        continue
                    values = dict(candidate=encode_track(candidate), score=candidate.score, updated_at=utc_now())
                    await session.execute(insert(SimilarTrack).values(
                        track_id=track_id, provider="lastfm", candidate_key=key, **values,
                    ).on_conflict_do_update(index_elements=["track_id", "provider", "candidate_key"], set_=values))
        async with self.database.sessions() as session:
            mbid = await session.scalar(select(TrackExternalID.external_identifier).where(
                TrackExternalID.track_id == track_id, TrackExternalID.provider == "musicbrainz",
            ))
        if mbid:
            recording = await self._optional("musicbrainz", "get_recording", mbid)
            await self._metadata(track_id, recording)
