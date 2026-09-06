"""All ranking weights, thresholds and resource bounds for the first engine."""

from datetime import timedelta

RATING_WEIGHTS = {"love": 3.0, "like": 1.0, "neutral": 0.0, "dislike": -3.0}
SIGNAL_WEIGHTS = {"lastfm": 0.45, "tags": 0.30, "artist": 0.10, "audio": 0.15}
AUDIO_WEIGHTS = {"bpm": 0.50, "spectral": 0.30, "rms": 0.10, "chroma": 0.10}
RELATED_ARTIST_WEIGHT = 0.5
UNKNOWN_TAG_WEIGHT = 0.5
TAG_WEIGHT_SCALE = 100.0
BPM_OCTAVE_DECAY = 0.25
SUPPORT_BONUS = 0.15  # Add support from at most two other positive seeds.
NEGATIVE_FIRST = 0.10  # Times |dislike weight| and strongest close negative.
NEGATIVE_ADDITIONAL = 0.15  # Times |dislike weight| for up to two further negatives.
MAX_NEGATIVE_PENALTY = 0.90
NEGATIVE_TAG_THRESHOLD = 0.60
NEGATIVE_LASTFM_THRESHOLD = 0.70
NEGATIVE_AUDIO_THRESHOLD = 0.85
NEGATIVE_AUDIO_TAG_THRESHOLD = 0.25
HISTORY_COOLDOWN = timedelta(days=7)
HISTORY_WINDOW = timedelta(days=30)
HISTORY_MULTIPLIER = 0.35
SEED_VARIETY_PENALTY = 0.75
ARTIST_VARIETY_PENALTY = 0.25
EXPLORATION_FRACTION = 0.20
EXPLORATION_MIN_AFFINITY = 0.30
EXPLORATION_MIN_SCORE = 0.05
EXPLORATION_NEW_ARTIST_BONUS = 0.20
MAX_LIMIT = 20
MAX_POSITIVE_SEEDS = 40
MAX_NEGATIVE_SEEDS = 40
MAX_LOCAL_PER_SOURCE = 100
MAX_EDGES_PER_SEED = 10
MAX_CANDIDATES = 200
MAX_SEED_TAGS = 20
MAX_PROVIDER_CALLS = 3
PROVIDER_TIMEOUT = 8
RELATIONSHIP_TTL = timedelta(days=1)
RELATIONSHIP_GRACE = timedelta(days=1)
