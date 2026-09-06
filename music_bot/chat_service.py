"""Private-chat state, authorized ratings, profile and personal-data removal."""

import json
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import delete, func, select, text, update
from sqlalchemy.dialects.sqlite import insert

from .models import ChannelConnectionCode, ChannelPost, ChatControl, IdentificationFlow, PlaylistChannel, Rating, RecommendationHistory, SongSubmission, Track, TrackTag, User, UserTrackSignal, utc_now
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

    async def taste_control(self, token, user_id, message_id):
        async with self.database.sessions() as session:
            row = await session.scalar(select(ChatControl).join(User).where(
                ChatControl.token == token, User.telegram_user_id == user_id,
                ChatControl.message_id == message_id, ChatControl.expires_at > utc_now()))
            if row is None or row.payload.get('kind') != 'taste':
                raise FlowError('stale')

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

    async def taste_summary(self, user_id):
        async with self.database.sessions() as session:
            internal = await session.scalar(select(User.id).where(User.telegram_user_id == user_id))
            if internal is None:
                return None
            counts = dict((await session.execute(select(Rating.value, func.count()).where(
                Rating.user_id == internal).group_by(Rating.value))).all())
            songs = await session.scalar(select(func.count(SongSubmission.id)).where(
                SongSubmission.user_id == internal, SongSubmission.identification_status == 'confirmed'))
            signals = await session.scalar(select(func.count(UserTrackSignal.id)).where(UserTrackSignal.user_id == internal))
            channels = await session.scalar(select(func.count(PlaylistChannel.id)).where(PlaylistChannel.user_id == internal))
            positive_tracks = select(Rating.track_id).where(Rating.user_id == internal,
                                                             Rating.value.in_(['love', 'like']))
            inferred_tracks = select(UserTrackSignal.track_id).where(UserTrackSignal.user_id == internal)
            artists = (await session.execute(select(Track.display_artist, Track.artist, func.count())
                .where(Track.id.in_(positive_tracks)).group_by(Track.artist)
                .order_by(func.count().desc(), Track.artist).limit(5))).all()
            inferred_artists = (await session.execute(select(Track.display_artist, Track.artist, func.count())
                .where(Track.id.in_(inferred_tracks)).group_by(Track.artist)
                .order_by(func.count().desc(), Track.artist).limit(5))).all()
            tags = (await session.execute(select(TrackTag.display_name, TrackTag.name, func.count())
                .where(TrackTag.track_id.in_(positive_tracks)).group_by(TrackTag.name)
                .order_by(func.count().desc(), TrackTag.name).limit(8))).all()
            inferred_tags = (await session.execute(select(TrackTag.display_name, TrackTag.name, func.count())
                .where(TrackTag.track_id.in_(inferred_tracks)).group_by(TrackTag.name)
                .order_by(func.count().desc(), TrackTag.name).limit(8))).all()
            recent_ratings = (await session.execute(select(Rating.updated_at, Rating.value, Track.display_artist, Track.artist,
                Track.display_title, Track.title).join(Track, Track.id == Rating.track_id)
                .where(Rating.user_id == internal).order_by(Rating.updated_at.desc()).limit(5))).all()
            recent_signals = (await session.execute(select(UserTrackSignal.created_at, UserTrackSignal.signal_type,
                Track.display_artist, Track.artist, Track.display_title, Track.title)
                .join(Track, Track.id == UserTrackSignal.track_id).where(UserTrackSignal.user_id == internal)
                .order_by(UserTrackSignal.created_at.desc()).limit(5))).all()
            recent = sorted([('rating', *row) for row in recent_ratings]
                            + [('inferred', *row) for row in recent_signals], key=lambda row: row[1], reverse=True)[:5]
            explicit = sum(counts.values())
            return {'counts': counts, 'songs': songs or 0, 'signals': signals or 0,
                    'channels': channels or 0, 'artists': artists, 'inferred_artists': inferred_artists,
                    'tags': tags, 'inferred_tags': inferred_tags, 'recent': recent,
                    'reliable': explicit + (signals or 0) >= 5}

    async def taste_targets(self, user_id):
        summary = await self.taste_summary(user_id)
        if summary is None:
            return []
        combined = [*summary['artists'], *summary['inferred_artists']]
        artists = [('artist', normalized, display or normalized) for display, normalized, _ in combined]
        combined_tags = [*summary['tags'], *summary['inferred_tags']]
        tags = [('tag', normalized, display or normalized) for display, normalized, _ in combined_tags]
        seen, result = set(), []
        for target in artists + tags:
            key = target[:2]
            if key not in seen:
                seen.add(key)
                result.append(target)
        return result[:10]

    async def reduce_taste(self, user_id, kind, value):
        async with self.database.write() as session:
            internal = await session.scalar(select(User.id).where(User.telegram_user_id == user_id))
            if internal is None or kind not in {'artist', 'tag'}:
                raise FlowError('stale')
            tracks = select(Track.id).where(Track.artist == value) if kind == 'artist' else select(TrackTag.track_id).where(TrackTag.name == value)
            await session.execute(delete(UserTrackSignal).where(UserTrackSignal.user_id == internal,
                                                                 UserTrackSignal.track_id.in_(tracks)))
            await session.execute(update(Rating).where(Rating.user_id == internal, Rating.track_id.in_(tracks),
                                                       Rating.value.in_(['love', 'like'])).values(value='neutral', updated_at=utc_now()))

    async def reset_learning(self, user_id):
        async with self.database.write() as session:
            internal = await session.scalar(select(User.id).where(User.telegram_user_id == user_id))
            if internal is None:
                raise FlowError('stale')
            await session.execute(delete(Rating).where(Rating.user_id == internal))
            await session.execute(delete(UserTrackSignal).where(UserTrackSignal.user_id == internal))

    async def cancel_controls(self, user_id):
        async with self.database.write() as session:
            ids = select(User.id).where(User.telegram_user_id == user_id)
            await session.execute(delete(ChatControl).where(ChatControl.user_id.in_(ids)))
            await session.execute(delete(ChannelConnectionCode).where(ChannelConnectionCode.user_id.in_(ids)))

    async def forget(self, user_id):
        async with self.database.write() as session:
            internal = await session.scalar(select(User.id).where(User.telegram_user_id == user_id))
            if internal is None:
                return
            submissions = select(SongSubmission.id).where(SongSubmission.user_id == internal)
            links = select(PlaylistChannel.id).where(PlaylistChannel.user_id == internal)
            legacy_analysis = await session.scalar(text(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='audio_analyses'"))
            if legacy_analysis:
                await session.execute(text(
                    "DELETE FROM audio_analyses WHERE requested_by=:user_id OR submission_id IN "
                    "(SELECT id FROM song_submissions WHERE user_id=:user_id)"), {"user_id": internal})
            await session.execute(delete(UserTrackSignal).where(UserTrackSignal.user_id == internal))
            await session.execute(delete(ChannelPost).where(ChannelPost.channel_id.in_(links)))
            await session.execute(delete(PlaylistChannel).where(PlaylistChannel.user_id == internal))
            await session.execute(delete(ChannelConnectionCode).where(ChannelConnectionCode.user_id == internal))
            await session.execute(delete(IdentificationFlow).where(IdentificationFlow.submission_id.in_(submissions)))
            for model in (ChatControl, Rating, RecommendationHistory, SongSubmission):
                await session.execute(delete(model).where(model.user_id == internal))
            await session.execute(delete(User).where(User.id == internal))
