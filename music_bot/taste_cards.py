"""Deliberately selected public music identity, independent of private ratings."""
import re
import secrets
from datetime import datetime, timedelta

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint, delete, select, update
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base, ChatControl, Track, User, UTCDateTime, utc_now

SHARE_TTL = timedelta(days=30)


class TasteCard(Base):
    __tablename__ = 'taste_cards'
    __table_args__ = (CheckConstraint('length(nickname) <= 40 AND length(bio) <= 240'),)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    taste_id: Mapped[str] = mapped_column(String(27), unique=True)
    nickname: Mapped[str] = mapped_column(default='')
    bio: Mapped[str] = mapped_column(default='')
    current_track_id: Mapped[int | None] = mapped_column(ForeignKey('tracks.id', ondelete='SET NULL'))
    share_token: Mapped[str | None] = mapped_column(String(32), unique=True)
    share_expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    revision: Mapped[int] = mapped_column(default=0)


class SignatureSong(Base):
    __tablename__ = 'taste_card_songs'
    __table_args__ = (UniqueConstraint('user_id', 'track_id'), CheckConstraint('position >= 0 AND position < 5'))
    user_id: Mapped[int] = mapped_column(ForeignKey('taste_cards.user_id', ondelete='CASCADE'), primary_key=True)
    position: Mapped[int] = mapped_column(primary_key=True)
    track_id: Mapped[int] = mapped_column(ForeignKey('tracks.id', ondelete='CASCADE'))


class CardError(ValueError):
    """Fixed, translatable codes only; never echo request data."""


def clean_text(value, maximum):
    if not isinstance(value, str) or len(value) > maximum:
        raise CardError('card_invalid')
    # Strip controls, including bidi overrides, while retaining Persian ZWNJ.
    import unicodedata
    return ''.join(c for c in value if not unicodedata.category(c).startswith('C') or c == '\u200c').strip()


def song_json(track, *, owner=False):
    from .chat_ui import safe_url
    value = {'artist': track.display_artist or track.artist, 'title': track.display_title or track.title,
             'artwork': safe_url(track.artwork_url, artwork=True)}
    if owner:
        value['id'] = track.id
    return value


async def invalidate_invitations(session, user_id):
    from .social import stop_invitation_swaps
    from .comparison_invitations import ComparisonInvitation
    await stop_invitation_swaps(session, select(ComparisonInvitation.token).where(
        (ComparisonInvitation.sender_id == user_id) | (ComparisonInvitation.recipient_id == user_id)))
    await session.execute(update(ComparisonInvitation).where(
        ((ComparisonInvitation.sender_id == user_id) | (ComparisonInvitation.recipient_id == user_id)),
        ComparisonInvitation.state.in_(['pending', 'consented'])).values(
            state='revoked', sender_snapshot={}, recipient_snapshot={}))


async def _card(session, telegram_id):
    user_id = await session.scalar(select(User.id).where(User.telegram_user_id == telegram_id))
    if user_id is None:
        raise CardError('card_stale')
    card = await session.get(TasteCard, user_id)
    if card is None:
        card = TasteCard(user_id=user_id, taste_id='LC-' + secrets.token_hex(12), nickname='', bio='', revision=0)
        session.add(card)
        await session.flush()
    return card


async def _projection(session, card, *, owner=False):
    songs = (await session.scalars(select(Track).join(SignatureSong).where(
        SignatureSong.user_id == card.user_id).order_by(SignatureSong.position))).all()
    current = await session.get(Track, card.current_track_id) if card.current_track_id else None
    value = {'taste_id': card.taste_id, 'nickname': card.nickname, 'bio': card.bio,
             'songs': [song_json(track, owner=owner) for track in songs],
             'current': song_json(current, owner=owner) if current else None}
    if owner:
        active = bool(card.share_token and card.share_expires_at and card.share_expires_at > utc_now())
        value.update(revision=card.revision, shared=active,
                     share_token=card.share_token if active else None,
                     expires_at=card.share_expires_at.isoformat() if active else None)
    return value


class TasteCards:
    def __init__(self, database):
        self.database = database

    async def owner(self, telegram_id):
        async with self.database.write() as session:
            return await _projection(session, await _card(session, telegram_id), owner=True)

    async def view(self, token):
        if not isinstance(token, str) or not re.fullmatch(r'[A-Za-z0-9_-]{32}', token):
            raise CardError('card_unavailable')
        async with self.database.sessions() as session:
            card = await session.scalar(select(TasteCard).where(
                TasteCard.share_token == token, TasteCard.share_expires_at > utc_now()))
            if card is None:
                raise CardError('card_unavailable')
            return await _projection(session, card)

    async def update(self, telegram_id, data):
        if not isinstance(data, dict) or set(data) - {'action', 'revision', 'nickname', 'bio', 'track_id', 'token'}:
            raise CardError('card_invalid')
        action = data.get('action')
        allowed = {'edit': {'nickname', 'bio'}, 'add': {'track_id', 'token'},
                   'remove': {'track_id'}, 'current': {'track_id'}}
        if not isinstance(action, str) or action not in allowed or set(data) - {'action', 'revision'} != allowed[action]:
            raise CardError('card_invalid')
        if type(data.get('revision')) is not int:
            raise CardError('card_invalid')
        async with self.database.write() as session:
            card = await _card(session, telegram_id)
            if card.revision != data['revision']:
                raise CardError('card_conflict')
            if action == 'edit':
                card.nickname = clean_text(data['nickname'], 40)
                card.bio = clean_text(data['bio'], 240)
            else:
                track_id = data['track_id']
                if track_id is not None and (type(track_id) is not int or track_id <= 0):
                    raise CardError('card_invalid')
                songs = (await session.scalars(select(SignatureSong).where(
                    SignatureSong.user_id == card.user_id).order_by(SignatureSong.position))).all()
                ids = [song.track_id for song in songs]
                if action == 'add':
                    if type(track_id) is not int or not isinstance(data['token'], str):
                        raise CardError('card_invalid')
                    grant = await session.scalar(select(ChatControl).where(
                        ChatControl.token == data['token'], ChatControl.user_id == card.user_id,
                        ChatControl.expires_at > utc_now()))
                    if (grant is None or grant.payload.get('kind') not in {'miniapp', 'tastecard'}
                            or track_id not in grant.payload.get('tracks', [])):
                        raise CardError('card_stale')
                    if track_id not in ids:
                        if len(ids) >= 5:
                            raise CardError('card_full')
                        if await session.get(Track, track_id) is None:
                            raise CardError('card_stale')
                        position = next(i for i in range(5) if i not in {song.position for song in songs})
                        session.add(SignatureSong(user_id=card.user_id, position=position, track_id=track_id))
                    from .feed_history import record_event
                    await record_event(session, card.user_id, track_id, 'engaged')
                elif action == 'remove':
                    if track_id not in ids:
                        raise CardError('card_stale')
                    await session.execute(delete(SignatureSong).where(
                        SignatureSong.user_id == card.user_id, SignatureSong.track_id == track_id))
                    if card.current_track_id == track_id:
                        card.current_track_id = None
                else:
                    if track_id is not None and track_id not in ids:
                        raise CardError('card_stale')
                    card.current_track_id = track_id
            card.revision += 1
            await invalidate_invitations(session, card.user_id)
            await session.flush()
            return await _projection(session, card, owner=True)

    async def sharing(self, telegram_id, action, revision):
        if not isinstance(action, str) or action not in {'publish', 'hide', 'rotate', 'delete'} or type(revision) is not int:
            raise CardError('card_invalid')
        async with self.database.write() as session:
            card = await _card(session, telegram_id)
            if card.revision != revision:
                raise CardError('card_conflict')
            if action == 'delete':
                await invalidate_invitations(session, card.user_id)
                await session.delete(card)
                return {'deleted': True}
            if action == 'hide':
                await invalidate_invitations(session, card.user_id)
                card.share_token = card.share_expires_at = None
            else:
                if not card.nickname or not await session.scalar(select(SignatureSong.track_id).where(
                        SignatureSong.user_id == card.user_id).limit(1)):
                    raise CardError('card_incomplete')
                if action == 'rotate' or not card.share_token or card.share_expires_at <= utc_now():
                    await invalidate_invitations(session, card.user_id)
                    card.share_token = secrets.token_urlsafe(24)
                    card.share_expires_at = utc_now() + SHARE_TTL
                else:
                    return await _projection(session, card, owner=True)
            card.revision += 1
            await session.flush()
            return await _projection(session, card, owner=True)
