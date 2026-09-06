import asyncio
from dataclasses import replace
from datetime import timedelta

from sqlalchemy import func, select

from music_bot.matching import comparison_text, confidence, deduplicate, strong_match
from music_bot.models import IdentificationFlow, Rating, SongSubmission, Track, TrackExternalID, utc_now
from music_bot.providers.common import Failure, ProviderError, TrackCandidate
from music_bot.submissions import AudioMetadata, InvalidSubmission, Submitter
from music_bot.workflow import FlowError
from tests.support import ServiceTestCase

EXACT = TrackCandidate("Song", "Artist", "lastfm", album="Album", duration=120,
                       external_ids={"lastfm": "https://last.fm/music/Artist/_/Song"})


class IdentificationTests(ServiceTestCase):
    async def text(self, artist="Artist", title="Song"):
        return await self.submissions.submit_text(self.user, f"{artist} - {title}")

    async def test_strong_lastfm_match(self):
        self.providers.call.return_value = [EXACT]
        submission = await self.text()
        result = await self.workflow.start(submission.id, self.user.telegram_user_id)
        self.assertEqual(result.kind, "confirmed")
        self.providers.call.assert_awaited_once_with("lastfm", "search_tracks", "Artist", "Song")
        async with self.database.sessions() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(Rating)), 0)

    async def test_musicbrainz_fallback(self):
        self.providers.call.side_effect = [[], [], [replace(EXACT, source="musicbrainz", score=100)]]
        result = await self.workflow.start((await self.text()).id, 123)
        self.assertEqual(result.kind, "confirmed")
        self.assertEqual(self.providers.call.call_args.args[:2], ("musicbrainz", "search_recordings"))

    async def test_ambiguous_requires_confirmation_and_repeats_are_safe(self):
        other = replace(EXACT, title="Songs", external_ids={"lastfm": "other"})
        self.providers.call.side_effect = [[EXACT, other], [], []]
        submission = await self.text("Artistt", "Song")
        result = await self.workflow.start(submission.id, 123)
        self.assertEqual(result.kind, "candidates")
        selected = await asyncio.gather(*[
            self.workflow.select(submission.id, 123, result.revision, 0) for _ in range(2)
        ])
        self.assertEqual(selected[0].track_id, selected[1].track_id)
        async with self.database.sessions() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(Track)), 1)
            self.assertEqual(await session.scalar(select(func.count()).select_from(TrackExternalID)), 1)

    async def test_no_results(self):
        result = await self.workflow.start((await self.text()).id, 123)
        self.assertEqual(result.kind, "not_found")

    async def test_persian_and_arabic_comparison_preserves_display(self):
        self.assertEqual(comparison_text("كيهان"), comparison_text("کیهان"))
        self.assertEqual(comparison_text("من آمده‌ام"), comparison_text("من آمده ام"))
        candidate = replace(EXACT, artist="کیهان", title="من آمده‌ام")
        self.providers.call.return_value = [candidate]
        result = await self.workflow.start((await self.text("كيهان", "من آمده ام")).id, 123)
        self.assertEqual(result.kind, "confirmed")
        self.assertEqual(result.artist, "کیهان")

    async def test_noise_and_reversed_names_auto_confirm(self):
        self.providers.call.side_effect = [[], [EXACT]]
        noisy = await self.text("Song (Official Audio)", "Artist.mp3")
        result = await self.workflow.start(noisy.id, 123)
        self.assertEqual(result.kind, "confirmed")
        self.assertEqual(self.providers.call.call_args_list[1].args,
                         ("lastfm", "search_tracks", "Artist.mp3", "Song (Official Audio)"))

    async def test_conflicting_id_for_same_identity_requires_confirmation(self):
        conflict = replace(EXACT, external_ids={"lastfm": "different"})
        self.providers.call.return_value = [EXACT, conflict]
        result = await self.workflow.start((await self.text()).id, 123)
        self.assertEqual(result.kind, "candidates")

    async def test_cross_provider_deduplication_and_different_recordings(self):
        mb = replace(EXACT, source="musicbrainz", external_ids={"musicbrainz": "one"})
        combined = deduplicate([EXACT, mb])
        self.assertEqual(len(combined), 1)
        self.assertEqual(set(combined[0].external_ids), {"lastfm", "musicbrainz"})
        distinct = replace(mb, external_ids={"musicbrainz": "two"})
        self.assertEqual(len(deduplicate([mb, distinct])), 2)

    async def test_missing_audio_and_correction_preserve_original(self):
        submission = await self.submissions.submit_audio(self.user, AudioMetadata("file", "unique"))
        result = await self.workflow.start(submission.id, 123)
        self.assertEqual(result.kind, "missing")
        self.providers.call.assert_not_awaited()
        await self.workflow.bind_prompt(result, 123, 100)
        self.providers.call.return_value = [EXACT]
        result = await self.workflow.correct(123, 100, "Artist — Song")
        self.assertEqual(result.kind, "confirmed")
        async with self.database.sessions() as session:
            saved = await session.get(SongSubmission, submission.id)
            self.assertIsNone(saved.parsed_artist)
            self.assertIsNone(saved.parsed_title)
            self.assertEqual(saved.file_id, "file")
            self.assertEqual(await session.scalar(select(func.count()).select_from(SongSubmission)), 1)

    async def test_none_invalidates_candidates_without_confirmation(self):
        weak = replace(EXACT, title="Song remix", external_ids={})
        self.providers.call.return_value = [weak]
        submission = await self.text()
        result = await self.workflow.start(submission.id, 123)
        retry = await self.workflow.none(submission.id, 123, result.revision)
        self.assertEqual(retry.kind, "correction")
        with self.assertRaises(FlowError):
            await self.workflow.select(submission.id, 123, result.revision, 0)
        async with self.database.sessions() as session:
            self.assertIsNone((await session.get(SongSubmission, submission.id)).track_id)

    async def test_provider_failure_does_not_override_reliable_result(self):
        self.providers.call.side_effect = ProviderError(Failure.NETWORK)
        result = await self.workflow.start((await self.text()).id, 123)
        self.assertEqual(result.kind, "failure")
        self.providers.call.side_effect = [ProviderError(Failure.NETWORK), [EXACT]]
        result = await self.workflow.start((await self.text()).id, 123)
        self.assertEqual(result.kind, "confirmed")

    async def test_exact_names_without_optional_metadata_skip_fallback(self):
        self.providers.call.side_effect = [[replace(EXACT, album=None, duration=None)], ProviderError(Failure.NETWORK)]
        result = await self.workflow.start((await self.text()).id, 123)
        self.assertEqual(result.kind, 'confirmed')
        self.assertEqual(self.providers.call.await_count, 1)

    async def test_confidence_thresholds_both_names_and_rivals(self):
        self.assertTrue(strong_match("Artist", "Song", [EXACT]))
        self.assertFalse(strong_match("Other", "Song", [EXACT]))
        self.assertFalse(strong_match("Artist", "Completely different", [EXACT]))
        self.assertTrue(strong_match("Artist", "Song", [replace(EXACT, external_ids={})]))
        self.assertTrue(strong_match("Artist", "Song", [EXACT, replace(EXACT, title="Songs")]))
        self.assertGreater(confidence("Artist", "Song", EXACT), 0.94)

    async def test_multiple_submissions_external_id_reuses_track(self):
        self.providers.call.side_effect = [[EXACT], [replace(EXACT, artist="ARTIST")]]
        results = []
        for _ in range(2):
            results.append(await self.workflow.start((await self.text()).id, 123))
        self.assertEqual(results[0].track_id, results[1].track_id)

    async def test_ownership_expiry_cancel_and_missing_state(self):
        result = await self.workflow.start((await self.text()).id, 123)
        with self.assertRaises(FlowError):
            await self.workflow.bind_prompt(result, 999, 100)
        await self.workflow.bind_prompt(result, 123, 100)
        with self.assertRaises(FlowError):
            await self.workflow.correct(999, 100, "Artist - Song")
        with self.assertRaises(FlowError):
            await self.workflow.correct(123, 999, "Artist - Song")
        await self.workflow.cancel(123)
        with self.assertRaises(FlowError):
            await self.workflow.correct(123, 100, "Artist - Song")
        another = await self.workflow.start((await self.text()).id, 123)
        async with self.database.write() as session:
            flow = await session.get(IdentificationFlow, another.submission_id)
            flow.expires_at = utc_now() - timedelta(seconds=1)
        with self.assertRaises(FlowError):
            await self.workflow.bind_prompt(another, 123, 200)

    async def test_retries_limited_and_malformed_correction_safe(self):
        result = await self.workflow.start((await self.text()).id, 123)
        for attempt in range(2):
            await self.workflow.bind_prompt(result, 123, 100 + attempt)
            with self.assertRaises(InvalidSubmission):
                await self.workflow.correct(123, 100 + attempt, "bad")
            result = await self.workflow.correct(123, 100 + attempt, "Artist - Song")
        self.assertEqual(result.kind, "limit")

    async def test_two_corrections_stay_bound_to_their_submissions(self):
        first = await self.workflow.start((await self.text()).id, 123)
        second = await self.workflow.start((await self.text()).id, 123)
        await self.workflow.bind_prompt(first, 123, 100)
        await self.workflow.bind_prompt(second, 123, 200)
        self.providers.call.return_value = [EXACT]
        result = await self.workflow.correct(123, 100, "Artist - Song")
        self.assertEqual(result.submission_id, first.submission_id)
        async with self.database.sessions() as session:
            self.assertIsNone((await session.get(SongSubmission, second.submission_id)).track_id)

    async def test_cancel_while_searching_cannot_resurrect_flow(self):
        started, release = asyncio.Event(), asyncio.Event()

        async def search(*args):
            started.set()
            await release.wait()
            return [EXACT]

        self.providers.call.side_effect = search
        submission = await self.text()
        task = asyncio.create_task(self.workflow.start(submission.id, 123))
        await started.wait()
        await self.workflow.cancel(123)
        release.set()
        with self.assertRaises(FlowError):
            await task
        async with self.database.sessions() as session:
            self.assertIsNone((await session.get(SongSubmission, submission.id)).track_id)

    async def test_concurrent_submissions_reuse_canonical_identity(self):
        self.providers.call.return_value = [EXACT]
        one, two = await self.text(), await self.text()
        results = await asyncio.gather(self.workflow.start(one.id, 123), self.workflow.start(two.id, 123))
        self.assertEqual(results[0].track_id, results[1].track_id)


class RatingTests(ServiceTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.providers.call.return_value = [EXACT]
        self.submission = await self.submissions.submit_text(self.user, "Artist - Song")
        await self.workflow.start(self.submission.id, 123)

    async def test_each_rating_upsert_repeat_and_change(self):
        previous = None
        for value in ("love", "like", "neutral", "dislike"):
            await self.workflow.rate(self.submission.id, 123, value)
            async with self.database.sessions() as session:
                rating = await session.scalar(select(Rating))
                self.assertEqual(rating.value, value)
                if previous:
                    self.assertGreater(rating.updated_at, previous)
                previous = rating.updated_at
            await self.workflow.rate(self.submission.id, 123, value)
            async with self.database.sessions() as session:
                rating = await session.scalar(select(Rating))
                self.assertEqual(rating.updated_at, previous)
                self.assertEqual(await session.scalar(select(func.count()).select_from(Rating)), 1)

    async def test_invalid_foreign_and_unconfirmed_ratings(self):
        pending = await self.submissions.submit_text(Submitter(456), "Other - Song")
        for args in [(self.submission.id, 123, "skip"), (self.submission.id, 456, "love"),
                     (pending.id, 456, "like"), (999999, 123, "neutral")]:
            with self.subTest(args=args), self.assertRaises(FlowError):
                await self.workflow.rate(*args)

    async def test_concurrent_ratings_one_record(self):
        await asyncio.gather(*[self.workflow.rate(self.submission.id, 123, "love") for _ in range(3)])
        async with self.database.sessions() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(Rating)), 1)
