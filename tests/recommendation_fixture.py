"""Deterministic synthetic music for tests and a separate evaluation database."""

from music_bot.matching import encode_track, identity_key
from music_bot.models import AudioAnalysis, Rating, SimilarTrack, SongSubmission, Track, TrackTag, User
from music_bot.providers.common import TrackCandidate

TELEGRAM_ID = 424242


async def populate(database):
    async with database.write() as session:
        user = User(telegram_user_id=TELEGRAM_ID)
        session.add(user)
        await session.flush()
        tracks = {}
        specs = [("metal_seed", "Forge", "Loved Metal", "love", ["metal", "guitar"]),
                 ("piano_seed", "Ivory", "Liked Piano", "like", ["piano", "instrumental"]),
                 ("neutral", "Forge", "Neutral Song", "neutral", ["metal", "guitar"]),
                 ("dislike", "Forge", "Disliked Song", "dislike", ["harsh", "noise"])]
        specs += [(f"metal_{i}", f"Metal Artist {i}", f"Metal Candidate {i}", None, ["metal", "guitar"]) for i in range(8)]
        specs += [(f"piano_{i}", f"Piano Artist {i}", f"Piano Candidate {i}", None, ["piano", "instrumental"]) for i in range(8)]
        specs += [("persian", "گوگوش", "من آمده‌ام", None, ["piano", "instrumental"])]
        for name, artist, title, rating, tags in specs:
            track = Track(artist=artist, title=title, display_artist=artist, display_title=title, metadata_source="fixture")
            session.add(track)
            await session.flush()
            tracks[name] = track.id
            session.add_all(TrackTag(track_id=track.id, name=tag, weight=100, source="lastfm") for tag in tags)
            if rating:
                session.add(Rating(user_id=user.id, track_id=track.id, value=rating))
            seed = "metal_seed" if name.startswith("metal_") and name != "metal_seed" else "piano_seed"
            if not rating:
                candidate = TrackCandidate(title, artist, "lastfm", score=.95)
                session.add(SimilarTrack(track_id=tracks[seed], provider="lastfm", candidate_key=identity_key(artist, title),
                                         candidate=encode_track(candidate), score=.95))
        return tracks
