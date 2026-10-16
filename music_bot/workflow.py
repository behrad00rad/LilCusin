"""Persistent, owner-checked identification/correction/confirmation and ratings."""

from dataclasses import dataclass, field
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert

from .catalog import IdentityConflict, canonical_track
from .matching import confidence, decode_track, deduplicate, encode_track, similarities, match_decision, strong_match, match_text

import logging
import asyncio

logger = logging.getLogger("music_bot")
from .models import IdentificationFlow, Rating, SongSubmission, Track, User, utc_now
from .providers.common import ProviderError, TrackCandidate

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
    def __init__(self, database, providers, lyrics=None):
        self.database = database
        self.providers = providers
        self.lyrics = lyrics

    async def search_title(self, title, artist=None):
        """Browse titles and bounded title/artist hints; require explicit selection."""
        from .recommendations.repository import from_track
        from sqlalchemy import or_
        async with self.database.sessions() as session:
            rows=await session.scalars(select(Track).where(or_(Track.title.contains(title,autoescape=True),
                Track.display_title.contains(title,autoescape=True))).limit(100))
            candidates=[from_track(track).metadata for track in rows]
        failed = False
        available = False
        calls = [self.providers.call('lastfm', 'search_tracks', artist, title) if artist
                 else self.providers.call('lastfm', 'search_titles', title),
                 self.providers.call('musicbrainz', 'search_recordings', artist, title) if artist
                 else self.providers.call('musicbrainz', 'search_titles', title)]
        if getattr(self.providers, 'has_deezer', False) is True:
            calls.append(self.providers.call('deezer', 'search_tracks', artist, title) if artist
                         else self.providers.call('deezer', 'search_titles', title))
        for result in await asyncio.gather(*calls, return_exceptions=True):
            if isinstance(result, ProviderError):
                failed = True
            elif isinstance(result, BaseException):
                raise result
            else:
                available = True
                candidates += result
        # Keep the literal query, but also try a few title + artist boundaries.
        # These are catalogue searches, never automatic identity confirmations.
        hints = []
        if not artist:
            words = title.split()
            if 2 <= len(words) <= 8:
                for boundary in range(1, min(len(words), 4)):
                    song = ' '.join(words[:boundary])
                    performer = ' '.join(words[boundary:])
                    if performer.casefold().startswith('by '):
                        performer = performer[3:].strip()
                    if performer:
                        hints.append((performer, song))
            for result in await asyncio.gather(*[
                self.providers.call(provider, method, performer, song)
                for performer, song in hints
                for provider, method in [('lastfm', 'search_tracks'),
                                         ('musicbrainz', 'search_titles_by_artist')]
            ], return_exceptions=True):
                if isinstance(result, ProviderError):
                    failed = True
                elif isinstance(result, BaseException):
                    raise result
                else:
                    available = True
                    candidates += result
        def hint_match(candidate):
            return any(match_text(song) == match_text(candidate.title)
                       and match_text(performer) in match_text(candidate.artist)
                       for performer, song in hints)
        wanted = match_text(title)
        matches=[c for c in candidates if c.artist and c.title and (wanted in match_text(c.title) or hint_match(c))
                 and (not artist or match_text(artist) in match_text(c.artist))]
        # Within relevant prefix matches, popularity precedes literal title length.
        # Use one scale per search: Deezer rank when available, Last.fm listeners
        # otherwise. Missing popularity is unknown, never a fabricated count.
        has_rank = any((c.deezer_rank or 0) > 0 for c in matches)
        def popularity(candidate):
            return (candidate.deezer_rank or 0) if has_rank else (candidate.listeners or 0)
        matches.sort(key=lambda c:(not hint_match(c),not match_text(c.title).startswith(wanted),
                                   -popularity(c),match_text(c.title)!=wanted,len(match_text(c.title))))
        unique=[];seen=set()
        for candidate in matches:
            key=(match_text(candidate.artist),match_text(candidate.title))
            if key not in seen:unique.append(candidate);seen.add(key)
        if not artist and self.lyrics is not None:
            from .lyrics_search import needs_lyrics
            if needs_lyrics(title, unique):
                discovered, lyrics_failed = await self.lyrics.search(title)
                if discovered:
                    # A phrase match is discovery only; the caller still requires choice.
                    unique = deduplicate(discovered + unique)
                    available = True
                failed = failed or lyrics_failed
        return unique[:20],failed and not available

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
            if (not (submission.parsed_title or "").strip()
                    or (not (submission.parsed_artist or "").strip() and submission.submission_type != 'text')):
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
            artist = flow.corrected_artist if flow.corrected_artist is not None else submission.parsed_artist
            title = flow.corrected_title or submission.parsed_title
            flow.attempts += 1
            flow.revision += 1
            revision = flow.revision
            flow.state = "searching"
            flow.prompt_message_id = None
            flow.candidates = []
        title_only = not artist
        candidates, failed = await self.search_title(title) if title_only else await self.search(artist, title)
        async with self.database.write() as session:
            submission = await owned_submission(session, submission_id, user_id)
            flow = await session.get(IdentificationFlow, submission_id)
            active(flow, revision)
            if flow.state != "searching":
                raise FlowError("stale")
            flow.candidates = [encode_track(candidate) for candidate in candidates]
            accepted, reason, metrics = ((False, 'title_search_requires_choice', (0, 0, 0, 0)) if title_only
                                         else match_decision(artist, title, candidates))
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
        from .submissions import parse_search_query
        artist, title = parse_search_query(text)
        async with self.database.write() as session:
            flow = await session.scalar(select(IdentificationFlow).join(
                SongSubmission, SongSubmission.id == IdentificationFlow.submission_id,
            ).join(User).where(
                User.telegram_user_id == user_id, IdentificationFlow.prompt_message_id == reply_message_id,
            ))
            active(flow)
            if flow.state != "correction":
                raise FlowError("stale")
            flow.corrected_artist, flow.corrected_title = artist or '', title
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
