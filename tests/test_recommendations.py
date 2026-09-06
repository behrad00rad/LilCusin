import asyncio
import json
import math
import sqlite3
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

from sqlalchemy import delete, event, func, select, update

from music_bot.cache import CachedProviders, cache_key, encode
from music_bot.database import Database
from music_bot.matching import encode_track, identity_key
from music_bot.models import AudioAnalysis, ProviderCache, Rating, RecommendationHistory, SimilarTrack, SongSubmission, Track, TrackExternalID, TrackTag, User, utc_now
from music_bot.providers.common import Failure, ProviderError, Tag, TrackCandidate
from music_bot.recommendations import RecommendationService
from music_bot.recommendations.candidates import candidate_item, deduplicate
from music_bot.recommendations.candidates import generate
from music_bot.recommendations.repository import load_profile
from music_bot.recommendations.scoring import audio_similarity, clamp, evidence, rank_candidate, select_varied, tag_overlap
from music_bot.recommendations.types import Item, Profile, Seed
from tests.recommendation_fixture import TELEGRAM_ID, populate


class ScoringTests(unittest.TestCase):
    def item(self, name="candidate", artist="Band", **kwargs):
        return candidate_item(TrackCandidate(name, artist, "fixture", **kwargs))

    def test_weighted_tags_and_missing(self):
        self.assertAlmostEqual(tag_overlap({"a": 1, "b": .5}, {"a": .5, "c": 1}), .5 / 2.5)
        self.assertIsNone(tag_overlap({}, {"a": 1}))
        self.assertEqual(tag_overlap({"a": 1}, {"b": 1}), 0)

    def test_provider_clamping_and_lastfm_weight(self):
        self.assertEqual(clamp(100), 1)
        self.assertEqual(clamp(-3), 0)
        for value in (None, "invalid", math.nan, math.inf, True):
            self.assertIsNone(clamp(value))
        seed = Seed(Item(TrackCandidate("seed", "A", "fixture"), 1), "love")
        item = self.item(artist="B")
        item.links[1] = 1
        self.assertAlmostEqual(evidence(seed, item, {})[0], .45 / .55)
        item.tags = {"rock": 1}  # Missing seed tags remain neutral.
        self.assertAlmostEqual(evidence(seed, item, {})[0], .45 / .55)

    def test_compatible_audio_bpm_missing_and_version(self):
        a, b = self.item(), self.item("other")
        key = ("librosa", "1", 22050)
        a.analyses[key] = {"bpm": 120, "rms_mean": .5}
        b.analyses[key] = {"bpm": 120, "rms_mean": .5}
        self.assertEqual(audio_similarity(a, b), (1, True))
        b.analyses[key]["bpm"] = 60
        self.assertLess(audio_similarity(a, b)[0], .3)
        b.analyses[key]["bpm"] = None
        self.assertEqual(audio_similarity(a, b), (1, False))
        b.analyses = {("librosa", "2", 22050): {"bpm": 120}}
        self.assertEqual(audio_similarity(a, b), (None, False))

    def test_multiple_negatives_stronger_without_artist_or_genre_ban(self):
        positive = self.item("seed")
        positive.track_id = 1
        positive.tags = {"rock": 1, "guitar": 1}
        candidate = self.item()
        candidate.tags = positive.tags.copy()
        profile = Profile(1, [Seed(positive, "love")], [], {1}, set(), {})
        original = rank_candidate(candidate, profile, {}, utc_now()).score
        for count in range(3):
            negative = self.item(f"bad{count}")
            negative.track_id = count + 2
            negative.tags = {"rock": 1}  # One broad tag + same artist is not enough.
            profile.negatives.append(Seed(negative, "dislike"))
        self.assertEqual(rank_candidate(candidate, profile, {}, utc_now()).score, original)
        for negative in profile.negatives:
            negative.item.tags = positive.tags.copy()
        self.assertAlmostEqual(rank_candidate(candidate, profile, {}, utc_now()).score, original * .1)
        profile.negatives = profile.negatives[:1]
        self.assertAlmostEqual(rank_candidate(candidate, profile, {}, utc_now()).score, original * .7)

    def test_transitive_dedup_and_persian(self):
        a = self.item("من آمده‌ام", "گوگوش", external_ids={"musicbrainz": "x"})
        b = self.item("من آمده ام", "گوگوش", external_ids={"lastfm": "y"})
        c = self.item("Alias", "Alias", external_ids={"lastfm": "y"})
        result = deduplicate([a, b, c])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].metadata.external_ids, {"musicbrainz": "x", "lastfm": "y"})
        self.assertEqual(identity_key("كيوان", "علي"), identity_key("کیوان", "علی"))


class RecommendationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database = Database(Path(self.temp.name) / "recommendations.sqlite3")
        await self.database.initialize()
        self.service = RecommendationService(self.database)

    async def asyncTearDown(self):
        await self.database.close()
        self.temp.cleanup()

    async def count(self, model):
        async with self.database.sessions() as session:
            return await session.scalar(select(func.count()).select_from(model))

    async def test_cold_start_and_only_explicit_positive(self):
        self.assertEqual((await self.service.recommend_for_user(TELEGRAM_ID)).status, "insufficient_preferences")
        await populate(self.database)
        async with self.database.write() as session:
            await session.execute(update(Rating).where(Rating.value.in_(["love", "like"])).values(value="neutral"))
        self.assertEqual((await self.service.recommend_for_user(TELEGRAM_ID)).status, "insufficient_preferences")

    async def test_mixed_tastes_exclusions_exploration_and_determinism(self):
        tracks = await populate(self.database)
        result = await self.service.recommend_for_user(TELEGRAM_ID, random_seed=5)
        repeat = await self.service.recommend_for_user(TELEGRAM_ID, random_seed=5)
        self.assertEqual(result, repeat)
        self.assertEqual(len(result.recommendations), 5)
        self.assertEqual(sum(row.exploration for row in result.recommendations), 1)
        artists = {row.artist for row in result.recommendations}
        self.assertTrue(any(name.startswith("Metal") for name in artists))
        self.assertTrue(any(name.startswith("Piano") or name == "گوگوش" for name in artists))
        metal_score = next(row.score for row in result.recommendations if row.artist.startswith("Metal"))
        piano_score = next(row.score for row in result.recommendations if row.artist.startswith("Piano") or row.artist == "گوگوش")
        self.assertGreater(metal_score, piano_score)
        rated = {tracks[key] for key in ("metal_seed", "piano_seed", "neutral", "dislike")}
        self.assertFalse(rated & {row.track_id for row in result.recommendations})
        self.assertTrue(all(row.reason and 0 < row.score <= 1 for row in result.recommendations))
        self.assertEqual(await self.count(RecommendationHistory), 0)
        self.assertEqual(await self.count(Rating), 4)

    async def test_one_like_missing_metadata_and_tag_only(self):
        tracks = await populate(self.database)
        async with self.database.write() as session:
            await session.execute(delete(SimilarTrack))
            await session.execute(update(Rating).values(value="neutral"))
            await session.execute(update(Rating).where(Rating.track_id == tracks["piano_seed"]).values(value="like"))
        result = await self.service.recommend_for_user(TELEGRAM_ID)
        self.assertEqual(result.status, "ok")
        self.assertTrue(all("shared_tags" in row.sources for row in result.recommendations))
        self.assertTrue(all(row.artwork_url is None for row in result.recommendations))

    async def test_history_replay_concurrency_and_recent_exclusion(self):
        await populate(self.database)
        first, repeat = await asyncio.gather(*[self.service.recommend_for_user(
            TELEGRAM_ID, random_seed=9, for_display=True, batch_id="same-batch") for _ in range(2)])
        self.assertEqual(first, repeat)
        self.assertEqual(await self.count(RecommendationHistory), 5)
        fresh = await self.service.recommend_for_user(TELEGRAM_ID, random_seed=9, for_display=True, batch_id="next-batch")
        self.assertFalse({row.track_id for row in first.recommendations} & {row.track_id for row in fresh.recommendations})
        self.assertEqual(await self.count(RecommendationHistory), 10)
        async with self.database.write() as session:
            user = await session.scalar(select(User.id))
            session.add(Rating(user_id=user, track_id=first.recommendations[0].track_id, value="dislike"))
        replay = await self.service.recommend_for_user(TELEGRAM_ID, for_display=True, batch_id="same-batch")
        self.assertNotIn(first.recommendations[0].track_id, {row.track_id for row in replay.recommendations})
        self.assertEqual(await self.count(RecommendationHistory), 10)

    async def test_older_history_score_reduction(self):
        await populate(self.database)
        before = await self.service.recommend_for_user(TELEGRAM_ID, limit=20, random_seed=1)
        target = before.recommendations[0]
        async with self.database.write() as session:
            user_id = await session.scalar(select(User.id))
            session.add(RecommendationHistory(user_id=user_id, track_id=target.track_id,
                                               recommended_at=utc_now() - timedelta(days=10)))
        after = await self.service.recommend_for_user(TELEGRAM_ID, limit=20, random_seed=1)
        self.assertAlmostEqual(next(row.score for row in after.recommendations if row.track_id == target.track_id), target.score * .35)

    async def test_duplicate_external_candidate_and_rated_alias(self):
        tracks = await populate(self.database)
        async with self.database.write() as session:
            session.add(TrackExternalID(track_id=tracks["dislike"], provider="musicbrainz", external_identifier="disliked-id"))
            for title, artist, identifier in [("Alias Disliked", "Other", "disliked-id"),
                                              ("New Song", "New Artist", "new-id"), ("Alias New", "Other", "new-id")]:
                metadata = TrackCandidate(title, artist, "lastfm", score=1, external_ids={"musicbrainz": identifier})
                session.add(SimilarTrack(track_id=tracks["metal_seed"], provider="lastfm", candidate_key=identity_key(artist, title),
                                        candidate=encode_track(metadata), score=1))
        result = await self.service.recommend_for_user(TELEGRAM_ID, limit=20, random_seed=1)
        self.assertFalse(any(row.external_ids.get("musicbrainz") == "disliked-id" for row in result.recommendations))
        self.assertEqual(sum(row.external_ids.get("musicbrainz") == "new-id" for row in result.recommendations), 1)

    async def test_provider_failure_stale_fallback_and_fresh_empty_cache(self):
        tracks = await populate(self.database)
        async with self.database.write() as session:
            await session.execute(delete(SimilarTrack))
            await session.execute(delete(TrackTag))
            await session.execute(update(Rating).where(Rating.track_id == tracks["piano_seed"]).values(value="neutral"))
            metadata = TrackCandidate("Cached", "Other Artist", "lastfm", score=.9)
            key = cache_key("lastfm", "get_similar_tracks", ("Forge", "Loved Metal"))
            session.add(ProviderCache(key=key, provider="lastfm", method="get_similar_tracks", payload=encode([metadata]),
                                      retrieved_at=utc_now() - timedelta(days=2), expires_at=utc_now() - timedelta(hours=1)))
        provider = AsyncMock()
        provider.get_similar_tracks.side_effect = ProviderError(Failure.NETWORK)
        service = RecommendationService(self.database, CachedProviders(self.database, provider, None))
        result = await service.recommend_for_user(TELEGRAM_ID)
        self.assertTrue(any(row.title == "Cached" for row in result.recommendations))
        provider.get_similar_tracks.assert_awaited_once()
        async with self.database.write() as session:
            await session.execute(update(ProviderCache).values(payload=encode([]), expires_at=utc_now() + timedelta(minutes=5)))
        provider.reset_mock()
        await service.recommend_for_user(TELEGRAM_ID)
        provider.get_similar_tracks.assert_not_awaited()

    async def test_local_candidates_survive_provider_failure(self):
        tracks = await populate(self.database)
        async with self.database.write() as session:
            await session.execute(delete(SimilarTrack))
        providers = AsyncMock()
        providers.call.side_effect = ProviderError(Failure.RATE_LIMIT)
        result = await RecommendationService(self.database, providers).recommend_for_user(TELEGRAM_ID, limit=20)
        self.assertEqual(result.status, "ok")
        self.assertLessEqual(providers.call.await_count, 3)

    async def test_audio_candidates_require_compatible_analysis(self):
        tracks = await populate(self.database)
        async with self.database.write() as session:
            await session.execute(delete(SimilarTrack))
            await session.execute(delete(TrackTag))
            user_id = await session.scalar(select(User.id))
            submission = SongSubmission(user_id=user_id, track_id=tracks["piano_seed"], submission_type="telegram_audio")
            session.add(submission)
            await session.flush()
            for name, version, bpm in [("piano_seed", "1", 120), ("piano_0", "1", 121), ("piano_1", "2", 120)]:
                session.add(AudioAnalysis(track_id=tracks[name], requested_by=user_id, submission_id=submission.id,
                    analyzer_name="librosa", analyzer_version=version, status="succeeded", bpm=bpm,
                    features={"sample_rate": 22050, "bpm": bpm}))
        result = await self.service.recommend_for_user(TELEGRAM_ID)
        self.assertIn(tracks["piano_0"], {row.track_id for row in result.recommendations})
        self.assertNotIn(tracks["piano_1"], {row.track_id for row in result.recommendations})
        self.assertTrue(any("tempo" in row.reason for row in result.recommendations))

    async def test_query_count_does_not_grow_per_result(self):
        await populate(self.database)
        statements = []
        def record(connection, cursor, statement, parameters, context, executemany):
            statements.append(statement.split()[0])
        event.listen(self.database.engine.sync_engine, "before_cursor_execute", record)
        try:
            await self.service.recommend_for_user(TELEGRAM_ID, limit=1)
            small = len(statements)
            statements.clear()
            await self.service.recommend_for_user(TELEGRAM_ID, limit=15)
            large = len(statements)
        finally:
            event.remove(self.database.engine.sync_engine, "before_cursor_execute", record)
        self.assertLessEqual(large, small + 2)
        self.assertLess(large, 40)

    async def test_validation_and_no_candidates(self):
        await populate(self.database)
        for kwargs in ({"limit": 0}, {"limit": 21}, {"batch_id": "x"}, {"for_display": True, "batch_id": "bad space"}):
            with self.assertRaises(ValueError):
                await self.service.recommend_for_user(TELEGRAM_ID, **kwargs)
        async with self.database.write() as session:
            await session.execute(delete(SimilarTrack))
            await session.execute(delete(TrackTag))
        self.assertEqual((await self.service.recommend_for_user(TELEGRAM_ID)).status, "no_candidates")

    async def test_candidate_cap_retains_separate_clusters(self):
        await populate(self.database)
        async with self.database.sessions() as session:
            profile = await load_profile(session, TELEGRAM_ID)
        with patch("music_bot.recommendations.settings.MAX_CANDIDATES", 4):
            candidates, _ = await generate(self.database, profile, None, 5)
        self.assertEqual(len(candidates), 4)
        self.assertTrue(any("metal" in item.tags for item in candidates))
        self.assertTrue(any("piano" in item.tags for item in candidates))

    async def test_provider_timeout_is_bounded_and_uses_local_data(self):
        await populate(self.database)
        async with self.database.write() as session:
            await session.execute(delete(SimilarTrack))
        async def slow(*args):
            await asyncio.sleep(60)
        providers = AsyncMock()
        providers.call.side_effect = slow
        with patch("music_bot.recommendations.settings.PROVIDER_TIMEOUT", .01):
            result = await RecommendationService(self.database, providers).recommend_for_user(TELEGRAM_ID, limit=20)
        self.assertEqual(result.status, "ok")
        self.assertEqual(providers.call.await_count, 2)

    async def test_artist_relation_requires_positive_metadata_link(self):
        tracks = await populate(self.database)
        async with self.database.write() as session:
            await session.execute(delete(TrackTag))
            candidate = TrackCandidate("Dislike Relative", "Negative Only Artist", "lastfm", score=1)
            session.add(SimilarTrack(track_id=tracks["dislike"], provider="lastfm", candidate_key="negative-relation",
                                    candidate=encode_track(candidate), score=1))
            session.add(Track(artist="Negative Only Artist", title="Unrelated Local", metadata_source="fixture"))
            local = Track(artist="Metal Artist 0", title="Related Local", display_title="Related Local", metadata_source="fixture")
            session.add(local)
            await session.flush()
            local_id = local.id
        result = await self.service.recommend_for_user(TELEGRAM_ID, limit=20)
        self.assertIn(local_id, {row.track_id for row in result.recommendations})
        self.assertFalse(any(row.artist.casefold() == "negative only artist" for row in result.recommendations))

    async def test_persian_display_and_alias_rated_exclusion(self):
        tracks = await populate(self.database)
        before = await self.service.recommend_for_user(TELEGRAM_ID, limit=20)
        persian = next(row for row in before.recommendations if row.track_id == tracks["persian"])
        self.assertEqual(persian.artist, "گوگوش")
        self.assertEqual(persian.title, "من آمده‌ام")
        async with self.database.write() as session:
            user_id = await session.scalar(select(User.id))
            session.add(Rating(user_id=user_id, track_id=tracks["persian"], value="neutral"))
            alias = TrackCandidate("من آمده ام", "گوگوش", "lastfm", score=1)
            session.add(SimilarTrack(track_id=tracks["metal_seed"], provider="lastfm", candidate_key="persian-alias",
                                    candidate=encode_track(alias), score=1))
        after = await self.service.recommend_for_user(TELEGRAM_ID, limit=20)
        self.assertFalse(any(identity_key(row.artist, row.title) == identity_key(persian.artist, persian.title) for row in after.recommendations))

    async def test_conflicting_external_ids_do_not_create_tracks(self):
        tracks = await populate(self.database)
        before = await self.count(Track)
        async with self.database.write() as session:
            session.add_all([TrackExternalID(track_id=tracks["piano_0"], provider="musicbrainz", external_identifier="a"),
                             TrackExternalID(track_id=tracks["metal_0"], provider="lastfm", external_identifier="b")])
            metadata = TrackCandidate("Conflicting", "Conflicting Artist", "lastfm", score=1,
                                      external_ids={"musicbrainz": "a", "lastfm": "b"})
            session.add(SimilarTrack(track_id=tracks["metal_seed"], provider="lastfm", candidate_key="conflict",
                                    candidate=encode_track(metadata), score=1))
        result = await self.service.recommend_for_user(TELEGRAM_ID, limit=20)
        self.assertFalse(any(row.title == "Conflicting" for row in result.recommendations))
        self.assertEqual(await self.count(Track), before)

    async def test_additive_history_migration_preserves_legacy_rows(self):
        path = Path(self.temp.name) / "legacy.sqlite3"
        with sqlite3.connect(path) as connection:
            connection.execute("CREATE TABLE recommendation_history (id INTEGER PRIMARY KEY, user_id INTEGER, track_id INTEGER, recommended_at DATETIME, reason VARCHAR, source VARCHAR)")
            connection.execute("INSERT INTO recommendation_history VALUES (1, 2, 3, '2026-01-01', 'old reason', 'old source')")
        legacy = Database(path)
        try:
            await legacy.initialize()
            await legacy.initialize()
        finally:
            await legacy.close()
        with sqlite3.connect(path) as connection:
            row = connection.execute("SELECT * FROM recommendation_history").fetchone()
            self.assertEqual(row, (1, 2, 3, "2026-01-01", "old reason", "old source", None, None, None))

    async def test_selected_seed_focus_and_ratings_unchanged(self):
        tracks = await populate(self.database)
        async with self.database.write() as session:
            user_id = await session.scalar(select(User.id))
            session.add(Rating(user_id=user_id, track_id=tracks["piano_1"], value="dislike"))
        async with self.database.sessions() as session:
            before = (await session.execute(select(Rating.track_id, Rating.value, Rating.updated_at).order_by(Rating.id))).all()
        result = await self.service.recommend_similar_to_track(TELEGRAM_ID, tracks["piano_0"], random_seed=42)
        self.assertEqual(result.status, "ok")
        ids = {row.track_id for row in result.recommendations}
        self.assertFalse(ids & {tracks["piano_0"], tracks["piano_1"], tracks["piano_seed"]})
        self.assertTrue(all(row.artist.startswith("Piano") or row.artist == "گوگوش" for row in result.recommendations))
        self.assertTrue(all("selected" in row.reason and "liked" not in row.reason for row in result.recommendations))
        self.assertTrue(all(row.score < .75 for row in result.recommendations))  # Close disliked piano seed penalizes shared tags.
        await self.service.recommend_similar_to_track(TELEGRAM_ID, tracks["piano_seed"])  # An existing Like stays Like too.
        async with self.database.sessions() as session:
            after = (await session.execute(select(Rating.track_id, Rating.value, Rating.updated_at).order_by(Rating.id))).all()
        self.assertEqual(before, after)

    async def test_selected_seed_without_positive_ratings_and_history_replay(self):
        tracks = await populate(self.database)
        async with self.database.write() as session:
            await session.execute(update(Rating).where(Rating.value.in_(["love", "like"])).values(value="neutral"))
        self.assertEqual((await self.service.recommend_for_user(TELEGRAM_ID)).status, "insufficient_preferences")
        first = await self.service.recommend_similar_to_track(TELEGRAM_ID, tracks["piano_0"], limit=3,
                    random_seed=7, for_display=True, batch_id="selected-batch")
        repeat = await self.service.recommend_similar_to_track(TELEGRAM_ID, tracks["piano_0"], limit=3,
                    random_seed=7, for_display=True, batch_id="selected-batch")
        self.assertEqual(first, repeat)
        self.assertEqual(len(first.recommendations), 3)
        self.assertEqual(await self.count(RecommendationHistory), 3)
        fresh = await self.service.recommend_similar_to_track(TELEGRAM_ID, tracks["piano_0"], limit=3, random_seed=7)
        self.assertFalse({row.track_id for row in first.recommendations} & {row.track_id for row in fresh.recommendations})
        with self.assertRaisesRegex(ValueError, "another recommendation mode or selected track"):
            await self.service.recommend_similar_to_track(TELEGRAM_ID, tracks["metal_0"], for_display=True, batch_id="selected-batch")
        async with self.database.write() as session:
            await session.execute(update(Rating).where(Rating.track_id == tracks["piano_seed"]).values(value="like"))
        with self.assertRaisesRegex(ValueError, "another recommendation mode or selected track"):
            await self.service.recommend_for_user(TELEGRAM_ID, for_display=True, batch_id="selected-batch")
        self.assertEqual(await self.count(RecommendationHistory), 3)

    async def test_selected_seed_empty_and_cached_provider_failure(self):
        tracks = await populate(self.database)
        self.assertEqual((await self.service.recommend_similar_to_track(TELEGRAM_ID, 999999)).status, "no_candidates")
        async with self.database.write() as session:
            await session.execute(delete(SimilarTrack))
            await session.execute(delete(TrackTag))
        self.assertEqual((await self.service.recommend_similar_to_track(TELEGRAM_ID, tracks["piano_0"])).status, "no_candidates")
        async with self.database.write() as session:
            candidate = TrackCandidate("Cached Piano", "New Pianist", "lastfm", score=.9)
            session.add(SimilarTrack(track_id=tracks["piano_0"], provider="lastfm", candidate_key="cached-piano",
                                    candidate=encode_track(candidate), score=.9, updated_at=utc_now() - timedelta(hours=25)))
        providers = AsyncMock()
        providers.call.side_effect = ProviderError(Failure.NETWORK)
        result = await RecommendationService(self.database, providers).recommend_similar_to_track(TELEGRAM_ID, tracks["piano_0"])
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.recommendations[0].title, "Cached Piano")
        self.assertEqual(result.recommendations[0].reason, "Similar to the song you selected")
        providers.call.assert_awaited_once_with("lastfm", "get_similar_tracks", "Piano Artist 0", "Piano Candidate 0")
        self.assertEqual(await self.count(Rating), 4)
