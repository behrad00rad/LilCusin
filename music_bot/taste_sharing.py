"""Explicit positive-rating sharing and owner-only guilty pleasures."""
from datetime import datetime
from sqlalchemy import ForeignKey, delete, select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Mapped, mapped_column
from aiohttp import web

from .models import Base, Rating, Track, User, UTCDateTime, utc_now


class FriendTasteSharing(Base):
    __tablename__ = 'friend_taste_sharing'
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    enabled: Mapped[bool] = mapped_column(default=True)


class GuiltyPleasure(Base):
    __tablename__ = 'guilty_pleasures'
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    track_id: Mapped[int] = mapped_column(ForeignKey('tracks.id', ondelete='CASCADE'), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


async def save_privacy(session, user_id, track_id, rating, guilty=None):
    if guilty is False:
        await session.execute(delete(GuiltyPleasure).where(
            GuiltyPleasure.user_id == user_id, GuiltyPleasure.track_id == track_id))
    elif guilty is True:
        await session.execute(insert(GuiltyPleasure).values(user_id=user_id, track_id=track_id,
            created_at=utc_now()).on_conflict_do_nothing(index_elements=['user_id', 'track_id']))
    return bool(await session.get(GuiltyPleasure, (user_id, track_id), populate_existing=True))


def sharing_enabled(setting):
    # Missing preference uses the product default; saved opt-outs remain respected.
    return setting is None or bool(setting.enabled)

def rating_visibility(rating, private, sharing):
    return 'friends' if rating == 'love' and sharing and not private else 'private'

async def visible_snapshot(session, owner, snapshot):
    """Filter current locks (including catalogue aliases) from friend projections."""
    from .recommendations.repository import load_items
    hidden=list(await session.scalars(select(Track).join(GuiltyPleasure).where(GuiltyPleasure.user_id==owner)))
    if not hidden:return snapshot
    private=await load_items(session,hidden)
    aliases=set().union(*(item.identities for item in private.values()))
    ids=[song['id'] for song in snapshot.get('songs',[]) if type(song.get('id')) is int]
    items=await load_items(session,list(await session.scalars(select(Track).where(Track.id.in_(ids)))))
    songs=[song for song in snapshot.get('songs',[]) if song.get('id') not in private and not (song.get('id') in items and items[song['id']].identities & aliases)]
    return {**snapshot,'songs':songs}


async def own_rating_states(database, telegram_id, tracks):
    async with database.sessions() as session:
        actor = await session.scalar(select(User.id).where(User.telegram_user_id == telegram_id))
        ids = [row['id'] for row in tracks]
        ratings = dict((await session.execute(select(Rating.track_id, Rating.value).where(
            Rating.user_id == actor, Rating.track_id.in_(ids)))).all())
        private = set(await session.scalars(select(GuiltyPleasure.track_id).where(
            GuiltyPleasure.user_id == actor, GuiltyPleasure.track_id.in_(ids))))
        sharing=await session.get(FriendTasteSharing,actor)
        for row in tracks:
            row['visibility']=rating_visibility(ratings.get(row['id']),row['id'] in private,sharing_enabled(sharing))
            row['rating'] = ratings.get(row['id'])
            row['guilty'] = row['id'] in private


def register_taste_sharing(app, chat, body):
    async def settings(request):
        enabled = None
        guess_value = None
        from .guess_game import enabled as guess_enabled, allow_guess
        if request.method == 'POST':
            data = await body(request)
            if set(data) == {'allow_guess'} and guess_enabled() and type(data['allow_guess']) is bool:
                guess_value = data['allow_guess']
            elif set(data) == {'enabled'} and type(data['enabled']) is bool:
                enabled = data['enabled']
            else:
                raise web.HTTPBadRequest(text='Choose whether to share positive ratings.')
        async with chat.database.write() as session:
            actor = await session.scalar(select(User.id).where(User.telegram_user_id == request['user']['id']))
            row = await session.get(FriendTasteSharing, actor)
            if enabled is not None:
                if row is None:
                    row = FriendTasteSharing(user_id=actor, enabled=enabled)
                    session.add(row)
                else:
                    row.enabled = enabled
            result = {'enabled': sharing_enabled(row), 'guess_game': guess_enabled()}
            if result['guess_game']:
                result['allow_guess'] = await allow_guess(session, actor, guess_value)
            return web.json_response(result)

    async def private_likes(request):
        async with chat.database.sessions() as session:
            tracks = list(await session.scalars(select(Track).join(GuiltyPleasure).join(User,
                User.id == GuiltyPleasure.user_id).where(
                    User.telegram_user_id == request['user']['id'])
                .order_by(GuiltyPleasure.created_at.desc()).limit(20)))
            rows = [{'id': track.id, 'title': track.display_title or track.title,
                     'artist': track.display_artist or track.artist} for track in tracks]
        token = await chat.create_control(request['user']['id'], tracks=[row['id'] for row in rows], kind='miniapp') if rows else None
        return web.json_response({'tracks': rows, 'token': token})

    app.router.add_get('/api/taste-sharing', settings)
    app.router.add_post('/api/taste-sharing', settings)
    app.router.add_get('/api/taste-sharing/private', private_likes)

    async def privacy(request):
        from .models import ChatControl
        data = await body(request)
        if (not {'token','track_id','private'} <= set(data) or set(data)-{'token','track_id','private','confirm_shared'} or type(data['track_id']) is not int
                or not isinstance(data['token'], str) or type(data['private']) is not bool):
            raise web.HTTPBadRequest(text='Choose a song and privacy lock state.')
        async with chat.database.write() as session:
            grant = await session.scalar(select(ChatControl).join(User).where(
                ChatControl.token == data['token'], User.telegram_user_id == request['user']['id'],
                ChatControl.expires_at > utc_now()))
            if grant is None or grant.payload.get('kind') != 'miniapp' or data['track_id'] not in grant.payload.get('tracks', []):
                raise web.HTTPForbidden(text='Refresh this song list first.')
            if data['private'] is False and data.get('confirm_shared') is not True:
                raise web.HTTPConflict(text='Confirm before removing the privacy lock.')
            guilty = await save_privacy(session, grant.user_id, data['track_id'], None, data['private'])
            rating=await session.scalar(select(Rating.value).where(Rating.user_id==grant.user_id,Rating.track_id==data['track_id']))
            sharing=await session.get(FriendTasteSharing,grant.user_id)
            visibility=rating_visibility(rating,guilty,sharing_enabled(sharing))
        return web.json_response({'guilty': guilty,'visibility':visibility})

    app.router.add_post('/api/rating-privacy', privacy)
