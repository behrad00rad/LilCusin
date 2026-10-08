"""Persistent, owner-checked identification/correction/confirmation and ratings."""

from dataclasses import dataclass, field
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert

from .catalog import IdentityConflict, canonical_track
from .matching import confidence, decode_track, deduplicate, encode_track, similarities, match_decision, strong_match

import logging

logger = logging.getLogger("music_bot")
from .models import IdentificationFlow, Rating, SongSubmission, Track, User, utc_now
from .providers.common import ProviderError, TrackCandidate
from .submissions import parse_song

FLOW_TTL = timedelta(minutes=30)
MAX_ATTEMPTS = 3
RATINGS = {"love", "like", "neutral", "dislike"}


async def save_rating(session, user_id, track_id, value):
    """Shared upsert for confirmed submissions and displayed recommendations."""
    if value not in RATINGS:
        raise FlowError("stale")
    now = utc_now()
    await session.execute(insert(Rating).values(
        user_id=user_id, track_id=track_id, value=value, created_at=now, updated_at=now,
    ).on_conflict_do_update(index_elements=["user_id", "track_id"],
        set_={"value": value, "updated_at": now}, where=Rating.value != value))


class FlowError(ValueError):
    """Fixed internal reason, translated to centralized messages by the UI."""


@dataclass
class Result:
    kind: str
    submission_id: int
    revision: int = 0
    candidates: list[TrackCandidate] = field(default_factory=list)
    track_id: int | None = None
    artist: str | None = None
    title: str | None = None
    rating: str | None = None


async def owned_submission(session, submission_id, telegram_user_id):
    submission = await session.scalar(select(SongSubmission).join(User).where(
        SongSubmission.id == submission_id, User.telegram_user_id == telegram_user_id,
    ))
    if submission is None:
        raise FlowError("stale")
    return submission


def active(flow, revision=None):
    if flow is None or flow.expires_at <= utc_now() or flow.state in ("cancelled", "exhausted"):
        raise FlowError("stale")
    if revision is not None and revision != flow.revision:
        raise FlowError("stale")


async def confirmed_result(session, submission):
    from .channel_signals import learn_confirmed_channel_track
    await learn_confirmed_channel_track(session, submission)
    track = await session.get(Track, submission.track_id)
    rating = await session.scalar(select(Rating.value).where(
        Rating.user_id == submission.user_id, Rating.track_id == track.id,
    ))
    return Result("confirmed", submission.id, track_id=track.id,
                  artist=track.display_artist or track.artist,
                  title=track.display_title or track.title, rating=rating)


class Workflow:
    def __init__(self, database, providers):
        self.database = database
        self.providers = providers

    async def search(self, artist, title):
        candidates = []
        failed = False
        try:
            candidates = await self.providers.call("lastfm", "search_tracks", artist, title)
        except ProviderError:
            failed = True
        ranked = sorted(deduplicate(candidates), key=lambda c: confidence(artist, title, c), reverse=True)
        if not strong_match(artist, title, ranked):
            try:
                candidates += await self.providers.call("lastfm", "search_tracks", title, artist)
            except ProviderError:
                failed = True
            ranked = sorted(deduplicate(candidates), key=lambda c: confidence(artist, title, c), reverse=True)
        # Album, duration and artwork belong to enrichment, not identity.
        if not strong_match(artist, title, ranked):
            try:
                candidates += await self.providers.call("musicbrainz", "search_recordings", artist, title)
            except ProviderError:
                failed = True
        # Irrelevant matches are not useful choices; both fields must be plausible.
        candidates = [c for c in deduplicate(candidates) if min(similarities(artist, title, c)) >= 0.45]
        candidates.sort(key=lambda c: confidence(artist, title, c), reverse=True)
        return candidates[:5], failed

    async def start(self, submission_id, user_id):
        async with self.database.write() as session:
            submission = await owned_submission(session, submission_id, user_id)
            if submission.identification_status == "confirmed":
                return await confirmed_result(session, submission)
            flow = await session.get(IdentificationFlow, submission_id)
            if flow is not None:
                raise FlowError("stale")
            flow = IdentificationFlow(submission_id=submission_id, expires_at=utc_now() + FLOW_TTL)
            session.add(flow)
            await session.flush()
            if not (submission.parsed_artist or "").strip() or not (submission.parsed_title or "").strip():
                flow.state = "correction"
                return Result("missing", submission_id, flow.revision)
        return await self.identify(submission_id, user_id)

    async def identify(self, submission_id, user_id):
        async with self.database.write() as session:
            submission = await owned_submission(session, submission_id, user_id)
            flow = await session.get(IdentificationFlow, submission_id)
            active(flow)
            if flow.attempts >= MAX_ATTEMPTS:
                flow.state = "exhausted"
                return Result("limit", submission_id)
            artist = flow.corrected_artist or submission.parsed_artist
            title = flow.corrected_title or submission.parsed_title
            flow.attempts += 1
            flow.revision += 1
            revision = flow.revision
            flow.state = "searching"
            flow.prompt_message_id = None
            flow.candidates = []
        candidates, failed = await self.search(artist, title)
        async with self.database.write() as session:
            submission = await owned_submission(session, submission_id, user_id)
            flow = await session.get(IdentificationFlow, submission_id)
            active(flow, revision)
            if flow.state != "searching":
                raise FlowError("stale")
            flow.candidates = [encode_track(candidate) for candidate in candidates]
            accepted, reason, metrics = match_decision(artist, title, candidates)
            logger.info("Identification decision: accepted=%s reason=%s artist=%.3f title=%.3f combined=%.3f margin=%.3f",
                        accepted, reason, *metrics)
            if accepted:
                try:
                    track = await canonical_track(session, candidates[0])
                except IdentityConflict:
                    flow.state = "correction"
                    return Result("failure", submission_id, revision)
                submission.track_id = track.id
                submission.identification_status = "confirmed"
                flow.state = "confirmed"
                await session.flush()
                return await confirmed_result(session, submission)
            if candidates:
                flow.state = "candidates"
                return Result("candidates", submission_id, revision, candidates)
            flow.state = "correction" if flow.attempts < MAX_ATTEMPTS else "exhausted"
            kind = "failure" if failed else "not_found"
            return Result(kind if flow.state == "correction" else "limit", submission_id, revision)

    async def select(self, submission_id, user_id, revision, index):
        async with self.database.write() as session:
            submission = await owned_submission(session, submission_id, user_id)
            flow = await session.get(IdentificationFlow, submission_id)
            active(flow, revision)
            if flow.state == "confirmed":
                return await confirmed_result(session, submission)
            if flow.state != "candidates" or not 0 <= index < len(flow.candidates):
                raise FlowError("stale")
            try:
                track = await canonical_track(session, decode_track(flow.candidates[index]))
            except IdentityConflict:
                raise FlowError("failure") from None
            submission.track_id = track.id
            submission.identification_status = "confirmed"
            flow.state = "confirmed"
            await session.flush()
            return await confirmed_result(session, submission)

    async def none(self, submission_id, user_id, revision):
        async with self.database.write() as session:
            await owned_submission(session, submission_id, user_id)
            flow = await session.get(IdentificationFlow, submission_id)
            active(flow, revision)
            if flow.state != "candidates":
                raise FlowError("stale")
            flow.candidates = []
            flow.revision += 1
            flow.state = "correction" if flow.attempts < MAX_ATTEMPTS else "exhausted"
            return Result("correction" if flow.state == "correction" else "limit", submission_id, flow.revision)

    async def bind_prompt(self, result, user_id, message_id):
        async with self.database.write() as session:
            await owned_submission(session, result.submission_id, user_id)
            flow = await session.get(IdentificationFlow, result.submission_id)
            active(flow, result.revision)
            if flow.state != "correction":
                raise FlowError("stale")
            flow.prompt_message_id = message_id

    async def correct(self, user_id, reply_message_id, text):
        artist, title = parse_song(text)
        async with self.database.write() as session:
            flow = await session.scalar(select(IdentificationFlow).join(
                SongSubmission, SongSubmission.id == IdentificationFlow.submission_id,
            ).join(User).where(
                User.telegram_user_id == user_id, IdentificationFlow.prompt_message_id == reply_message_id,
            ))
            active(flow)
            if flow.state != "correction":
                raise FlowError("stale")
            flow.corrected_artist, flow.corrected_title = artist, title
            flow.state = "searching"
            flow.prompt_message_id = None
            submission_id = flow.submission_id
        return await self.identify(submission_id, user_id)

    async def cancel(self, user_id):
        async with self.database.write() as session:
            flows = (await session.scalars(select(IdentificationFlow).join(
                SongSubmission, SongSubmission.id == IdentificationFlow.submission_id,
            ).join(User).where(User.telegram_user_id == user_id,
                              IdentificationFlow.state.in_(["correction", "candidates", "searching"])))).all()
            for flow in flows:
                flow.state = "cancelled"
                flow.prompt_message_id = None
                flow.revision += 1

    async def rate(self, submission_id, user_id, value):
        if value not in RATINGS:
            raise FlowError("stale")
        async with self.database.write() as session:
            submission = await owned_submission(session, submission_id, user_id)
            if submission.identification_status != "confirmed" or submission.track_id is None:
                raise FlowError("stale")
            await save_rating(session, submission.user_id, submission.track_id, value)
            return await confirmed_result(session, submission)

    async def review_channel(self, submission_id, user_id):
        """An explicit owner request reopens a stored channel item for correction."""
        from .models import ChannelPost
        async with self.database.write() as session:
            submission = await owned_submission(session, submission_id, user_id)
            post = await session.scalar(select(ChannelPost).where(ChannelPost.submission_id == submission_id))
            if post is None or post.status == "identified":
                raise FlowError("stale")
            flow = await session.get(IdentificationFlow, submission_id)
            if flow is not None:
                flow.state, flow.attempts = "searching", 0
                flow.expires_at = utc_now() + FLOW_TTL
                flow.revision += 1
                flow.prompt_message_id = None
            post.status = "review"
        if flow is None:
            return await self.start(submission_id, user_id)
        # Missing performer/title should ask for correction, not query empty metadata.
        if not (submission.parsed_artist and submission.parsed_title):
            async with self.database.write() as session:
                flow = await session.get(IdentificationFlow, submission_id)
                if flow is None:
                    raise FlowError("stale")
                flow.state = "correction"
                return Result("missing", submission_id, flow.revision)
        return await self.identify(submission_id, user_id)
