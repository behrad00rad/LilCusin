"""Application API; user IDs are Telegram IDs, never internal User.id values."""

import re
from uuid import uuid4

from ..models import utc_now
from . import settings as S
from .candidates import generate
from .repository import load_profile, persist_selection, replay_batch
from .scoring import rank_candidate, select_varied
from .types import RecommendationResult


class RecommendationService:
    def __init__(self, database, providers=None):
        """Pass existing CachedProviders for bounded online fallback, or None for local/cache only."""
        self.database = database
        self.providers = providers

    async def recommend_for_user(self, user_id: int, limit: int = 5, *, random_seed: int | None = None,
                                 for_display: bool = False, batch_id: str | None = None) -> RecommendationResult:
        """For You: score against every explicit Love/Like seed."""
        return await self._recommend(user_id, limit, random_seed, for_display, batch_id)

    async def recommend_similar_to_track(self, user_id: int, track_id: int, limit: int = 5, *,
                                         random_seed: int | None = None, for_display: bool = False,
                                         batch_id: str | None = None) -> RecommendationResult:
        """More Like This: focus on a canonical track without creating/changing ratings."""
        if type(track_id) is not int or track_id <= 0:
            raise ValueError("track_id must be a positive canonical track ID")
        return await self._recommend(user_id, limit, random_seed, for_display, batch_id, track_id)

    async def _recommend(self, user_id, limit, random_seed, for_display, batch_id, selected_track_id=None):
        if type(user_id) is not int or user_id <= 0:
            raise ValueError("user_id must be a positive Telegram user ID")
        if type(limit) is not int or not 1 <= limit <= S.MAX_LIMIT:
            raise ValueError(f"limit must be from 1 to {S.MAX_LIMIT}")
        if batch_id is not None and (not for_display or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", batch_id)):
            raise ValueError("batch_id requires for_display and 1–64 letters, digits, hyphens or underscores")
        if for_display and batch_id is None:
            batch_id = uuid4().hex
        async with self.database.sessions() as session:
            profile = await load_profile(session, user_id, selected_track_id)
            if profile is None:
                return RecommendationResult("insufficient_preferences" if selected_track_id is None else "no_candidates")
            if for_display:
                replay = await replay_batch(session, profile.user_id, batch_id, profile.rated_aliases, selected_track_id)
                if replay is not None:
                    return replay
        candidates, related_artists = await generate(self.database, profile, self.providers, limit)
        now = utc_now()
        ranked = [row for item in candidates if (row := rank_candidate(item, profile, related_artists, now)) is not None]
        selected = select_varied(ranked, limit, random_seed)
        return await persist_selection(self.database, user_id, selected, for_display, batch_id, selected_track_id)
