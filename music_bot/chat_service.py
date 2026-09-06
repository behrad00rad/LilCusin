"""Private-chat state, authorized ratings, profile and personal-data removal."""

import json
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import delete, func, or_, select
from sqlalchemy.dialects.sqlite import insert

from .models import AudioAnalysis, ChannelConnectionCode, ChannelPost, ChatControl, IdentificationFlow, PlaylistChannel, Rating, RecommendationHistory, SongSubmission, Track, User, UserTrackSignal, utc_now
from .workflow import FlowError, owned_submission, save_rating

CONTROL_TTL = timedelta(minutes=30)


class ChatService:
    def __init__(self, database, recommendations):
        self.database = database
        self.recommendations = recommendations

    async def ensure_user(self, user):
        async with self.database.write() as session:
            fields = dict(username=user.username, display_name=user.display_name,
                          language_code=user.language_code, last_activity_at=utc_now())
            await session.execute(insert(User).values(telegram_user_id=user.telegram_user_id, **fields)
                .on_conflict_do_update(index_elements=["telegram_user_id"], set_=fields))

    async def create_control(self, user_id, *, tracks=(), seed=None, kind="list", submitted=False, links=()):
        token = uuid4().hex
        async with self.database.write() as session:
            internal = await session.scalar(select(User.id).where(User.telegram_user_id == user_id))
            if internal is None:
                raise FlowError("stale")
            await session.execute(delete(ChatControl).where(ChatControl.expires_at <= utc_now()))
            # Keep at most twenty active controls per user, with no unbounded UI state.
            old = select(ChatControl.token).where(ChatControl.user_id == internal).order_by(ChatControl.expires_at.desc()).offset(19)
            await session.execute(delete(ChatControl).where(ChatControl.token.in_(old)))
            session.add(ChatControl(token=token, user_id=internal,
                payload={"tracks": list(tracks), "seed": seed, "kind": kind, "used": [], "submitted": submitted, "links": list(links)},
                expires_at=utc_now() + CONTROL_TTL))
        return token

    async def bind_control(self, token, message_id):
        async with self.database.write() as session:
            row = await session.get(ChatControl, token)
            if row is not None:
                row.message_id = message_id

    async def control(self, token, user_id, message_id, action, index=None, rating=None):
        async with self.database.write() as session:
            row = await session.scalar(select(ChatControl).join(User).where(
                ChatControl.token == token, User.telegram_user_id == user_id,
                ChatControl.message_id == message_id, ChatControl.expires_at > utc_now()))
            if row is None:
                raise FlowError("stale")
            payload = dict(row.payload)
            if payload["kind"] == "forget" and action not in {"delete", "keep"}:
                raise FlowError("stale")
            if payload["kind"] != "forget" and action in {"delete", "keep"}:
                raise FlowError("stale")
            track = None
            if index is not None:
                if not 0 <= index < len(payload["tracks"]):
                    raise FlowError("stale")
                track = await session.get(Track, payload["tracks"][index])
                if track is None:
                    raise FlowError("stale")
            key = f"{action}:{index}"
            if rating is None:
                if key in payload["used"]:
                    raise FlowError("stale")
                payload["used"] = [*payload["used"], key]
                row.payload = payload
                if action in {"delete", "keep"}:
                    await session.delete(row)
            else:
                if payload["kind"] != "card" or track is None:
                    raise FlowError("stale")
                await save_rating(session, row.user_id, track.id, rating)
            return payload, track

    async def submitted_track(self, user_id, submission_id):
        async with self.database.sessions() as session:
            submission = await owned_submission(session, submission_id, user_id)
            if submission.identification_status != "confirmed" or submission.track_id is None:
                raise FlowError("stale")
            track = await session.get(Track, submission.track_id)
            if track is None:
                raise FlowError("stale")
            return track

    async def track(self, track_id):
        async with self.database.sessions() as session:
            return await session.get(Track, track_id)

    async def record_displayed(self, user_id, recommendations, token, seed):
        """Called only after sendMessage succeeded; record the exact displayed list."""
        if not recommendations:
            return
        async with self.database.write() as session:
            internal = await session.scalar(select(User.id).where(User.telegram_user_id == user_id))
            if internal is None:
                raise FlowError("stale")
            rows = [dict(user_id=internal, track_id=row.track_id, batch_id=token, position=index,
                         ranking_score=row.score, reason=row.reason, recommended_at=utc_now(),
                         source=json.dumps({"sources": list(row.sources), "exploration": row.exploration,
                                            "selected_track_id": seed}))
                    for index, row in enumerate(recommendations, 1)]
            await session.execute(insert(RecommendationHistory).values(rows).on_conflict_do_nothing(
                index_elements=["user_id", "batch_id", "track_id"]))

    async def profile(self, user_id):
        async with self.database.sessions() as session:
            internal = await session.scalar(select(User.id).where(User.telegram_user_id == user_id))
            counts = dict((await session.execute(select(Rating.value, func.count()).where(
                Rating.user_id == internal).group_by(Rating.value))).all())
            shown = await session.scalar(select(func.count()).select_from(RecommendationHistory).where(
                RecommendationHistory.user_id == internal))
            return counts, shown

    async def cancel_controls(self, user_id):
        async with self.database.write() as session:
            ids = select(User.id).where(User.telegram_user_id == user_id)
            await session.execute(delete(ChatControl).where(ChatControl.user_id.in_(ids)))
            await session.execute(delete(ChannelConnectionCode).where(ChannelConnectionCode.user_id.in_(ids)))

    async def forget(self, user_id, audio_analysis=None):
        # Private-chat middleware serializes updates; drain background work first.
        if audio_analysis is not None:
            await audio_analysis.cancel_user(user_id)
        async with self.database.write() as session:
            internal = await session.scalar(select(User.id).where(User.telegram_user_id == user_id))
            if internal is None:
                return
            submissions = select(SongSubmission.id).where(SongSubmission.user_id == internal)
            links = select(PlaylistChannel.id).where(PlaylistChannel.user_id == internal)
            await session.execute(delete(UserTrackSignal).where(UserTrackSignal.user_id == internal))
            await session.execute(delete(ChannelPost).where(ChannelPost.channel_id.in_(links)))
            await session.execute(delete(PlaylistChannel).where(PlaylistChannel.user_id == internal))
            await session.execute(delete(ChannelConnectionCode).where(ChannelConnectionCode.user_id == internal))
            await session.execute(delete(AudioAnalysis).where(or_(
                AudioAnalysis.requested_by == internal, AudioAnalysis.submission_id.in_(submissions))))
            await session.execute(delete(IdentificationFlow).where(IdentificationFlow.submission_id.in_(submissions)))
            for model in (ChatControl, Rating, RecommendationHistory, SongSubmission):
                await session.execute(delete(model).where(model.user_id == internal))
            await session.execute(delete(User).where(User.id == internal))
