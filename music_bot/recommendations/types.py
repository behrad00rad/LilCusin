from dataclasses import dataclass, field
from datetime import datetime

from ..providers.common import TrackCandidate


@dataclass
class Item:
    metadata: TrackCandidate
    track_id: int | None = None
    tags: dict[str, float] = field(default_factory=dict)
    analyses: dict[tuple[str, str, int], dict] = field(default_factory=dict)
    links: dict[int, float | None] = field(default_factory=dict)
    sources: set[str] = field(default_factory=set)
    identities: set[tuple] = field(default_factory=set)


@dataclass
class Seed:
    item: Item
    rating: str | None  # None is an explicitly selected seed, not an inferred rating.


@dataclass
class Profile:
    user_id: int
    positives: list[Seed]
    negatives: list[Seed]
    rated_ids: set[int]
    rated_aliases: set[tuple]
    history: dict[int, datetime]
    history_aliases: dict[tuple, datetime] = field(default_factory=dict)
    selected_track_id: int | None = None


@dataclass
class Ranked:
    item: Item
    score: float
    reason: str
    seed_id: int
    affinity: float
    exploration: bool = False


@dataclass(frozen=True)
class Recommendation:
    track_id: int
    artist: str
    title: str
    album: str | None
    artwork_url: str | None
    external_ids: dict[str, str]
    score: float
    reason: str
    sources: tuple[str, ...]
    exploration: bool = False


@dataclass(frozen=True)
class RecommendationResult:
    status: str
    recommendations: tuple[Recommendation, ...] = ()
    batch_id: str | None = None
