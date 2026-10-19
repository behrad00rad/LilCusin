"""Bounded, cached artwork enrichment; never blocks a song list or rating."""
import asyncio
import time
from sqlalchemy import select
from .enrichment import Enrichment
from .models import Track
from .providers.common import TrackCandidate
from .chat_ui import safe_url


class ArtworkLoader:
    def __init__(self, database, providers):
        self.database = database
        self.metadata = Enrichment(database, providers)
        self.providers = providers
        self.tasks = {}
        self.attempted = {}
        self.slots = asyncio.Semaphore(3)

    def schedule(self, track_id):
        now = time.monotonic()
        if track_id in self.tasks or len(self.tasks) >= 20 or now-self.attempted.get(track_id, -1000) < 60:
            return
        if len(self.attempted) >= 500:
            self.attempted.pop(next(iter(self.attempted)))
        self.attempted[track_id] = now
        task = asyncio.create_task(self.load(track_id))
        self.tasks[track_id] = task
        task.add_done_callback(lambda _: self.tasks.pop(track_id, None))

    async def load(self, track_id):
        try:
            async with self.slots:
                async with asyncio.timeout(12):
                    async with self.database.sessions() as session:
                        track = await session.get(Track, track_id)
                    if track is None or safe_url(track.artwork_url, artwork=True):
                        return
                    candidate = await self.providers.call('lastfm', 'get_track_info',
                        track.display_artist or track.artist, track.display_title or track.title)
                    if isinstance(candidate, TrackCandidate):
                        # Existing identity checks reject a different recording returned by autocorrect.
                        await self.metadata._metadata(track_id, candidate)
        except Exception:
            pass  # Missing art never changes identification, ratings, or availability.

    async def close(self):
        tasks = list(self.tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
