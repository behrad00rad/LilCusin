"""Feed discovery from currently consented friend shares, never private taste."""
from datetime import timedelta

from sqlalchemy import select

from .comparison_invitations import ComparisonInvitation, invitation_state, is_friendship
from .i18n import language
from .matching import identity_key
from .models import Rating, RecommendationHistory, Track, User, utc_now
from .recommendations.repository import load_items
from .social import SavedSong, SongSwap
from .taste_learning import TasteRequest, TrackPreference
from .taste_sharing import FriendTasteSharing, GuiltyPleasure


async def mix_friend_songs(database, telegram_id, rows, *, limit=5, exclude=()):
    if limit == 1 and rows:
        return rows[:1]
    async with database.write() as session:
        actor = await session.scalar(select(User.id).where(User.telegram_user_id == telegram_id))
        if actor is None:
            return rows[:limit]
        invitations = list(await session.scalars(select(ComparisonInvitation).where(
            ComparisonInvitation.state == 'consented',
            (ComparisonInvitation.sender_id == actor) | (ComparisonInvitation.recipient_id == actor))
            .order_by(ComparisonInvitation.accepted_at.desc(), ComparisonInvitation.token).limit(50)))
        shared = {}
        for invitation in invitations:
            if not is_friendship(invitation) or await invitation_state(session, invitation) != 'consented':
                continue
            snapshot = invitation.recipient_snapshot if invitation.sender_id == actor else invitation.sender_snapshot
            name = ' '.join(str(snapshot.get('nickname') or '').split())[:60]
            if not name:
                name = 'دوستت' if language.get() == 'fa' else 'your friend'
            friend_id = invitation.recipient_id if invitation.sender_id == actor else invitation.sender_id
            hidden_tracks = list(await session.scalars(select(Track).join(GuiltyPleasure).where(
                GuiltyPleasure.user_id == friend_id)))
            hidden_items = await load_items(session, hidden_tracks)
            hidden_aliases = set().union(*(item.identities for item in hidden_items.values()))
            candidates = {}
            for song in snapshot.get('songs', [])[:10]:
                if type(song.get('id')) is int:
                    candidates.setdefault(song['id'], 'shared')
            swaps = await session.scalars(select(SongSwap.track_id).where(
                SongSwap.invitation == invitation.token, SongSwap.sender_id == friend_id,
                SongSwap.recipient_id == actor, SongSwap.state == 'sent', SongSwap.expires_at > utc_now())
                .order_by(SongSwap.sent_at.desc()).limit(10))
            for track_id in swaps:
                candidates.setdefault(track_id, 'shared')
            sharing = await session.get(FriendTasteSharing, friend_id)
            if sharing is not None and sharing.enabled:
                positives = await session.execute(select(Rating.track_id, Rating.value).where(
                    Rating.user_id == friend_id, Rating.value == 'love')
                    .order_by(Rating.updated_at.desc(), Rating.track_id).limit(30))
                for track_id, value in positives:
                    candidates[track_id] = value
            candidate_items = await load_items(session, list(await session.scalars(select(Track).where(Track.id.in_(candidates)))))
            for track_id, value in candidates.items():
                if track_id in candidate_items and track_id not in hidden_items and not candidate_items[track_id].identities & hidden_aliases:
                    shared.setdefault(track_id, (name, value))
        if not shared:
            return rows[:limit]
        excluded = set(exclude)
        for model in (Rating, SavedSong, TrackPreference, TasteRequest):
            query = select(model.track_id).where(model.user_id == actor)
            if model is TrackPreference:
                query = query.where(model.feedback.in_(['known', 'not_for_me']))
            if model is TasteRequest:
                query = query.where(model.created_at > utc_now() - timedelta(days=90))
            excluded.update(await session.scalars(query))
        excluded.update(await session.scalars(select(RecommendationHistory.track_id).where(
            RecommendationHistory.user_id == actor,
            RecommendationHistory.recommended_at > utc_now() - timedelta(days=7))))
        items = await load_items(session, list(await session.scalars(select(Track).where(
            Track.id.in_(set(shared) | excluded)))))
        excluded_aliases = set().union(*(items[track_id].identities for track_id in excluded if track_id in items))
        for track_id, (name, value) in shared.items():
            item = items.get(track_id)
            if item is None or track_id in excluded or item.identities & excluded_aliases:
                continue
            track = await session.get(Track, track_id)
            from .miniapp import track_json
            reason = f'اشتراک‌گذاشته‌شده توسط {name}' if language.get() == 'fa' else f'Shared by {name}'
            if value == 'love':
                reason = f'از آهنگ‌های محبوب {name}' if language.get() == 'fa' else f'{name} loved this song'
            elif value == 'like':
                reason = f'پسندیده‌شده توسط {name}' if language.get() == 'fa' else f'Liked by {name}'
            friend = track_json(track, reason)
            identity = identity_key(friend['artist'], friend['title'])
            personal = [row for row in rows if row['id'] != track_id
                        and identity_key(row['artist'], row['title']) != identity]
            position = 1 if personal and limit > 1 else 0
            mixed = personal[:max(0, limit - 1)]
            mixed.insert(position, friend)
            # Composition is prefetch, not a view. Home records one-second visibility.
            return mixed
    return rows[:limit]
