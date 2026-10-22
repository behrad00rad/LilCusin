"""Recipient-bound, selected-song consent. No private ratings or match scores."""
import re
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import CheckConstraint, ForeignKey, JSON, String, func, select, update, delete
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base, User, UTCDateTime, utc_now
from .taste_cards import CardError, TasteCard, _card, _projection

INVITATION_TTL = timedelta(hours=48)


class ComparisonInvitation(Base):
    __tablename__ = 'comparison_invitations'
    __table_args__ = (CheckConstraint('sender_id != recipient_id'),
        CheckConstraint("state IN ('pending','consented','declined','revoked')"))
    token: Mapped[str] = mapped_column(String(32), primary_key=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    recipient_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    sender_revision: Mapped[int]
    recipient_revision: Mapped[int]
    card_token: Mapped[str]
    sender_snapshot: Mapped[dict] = mapped_column(JSON)
    recipient_snapshot: Mapped[dict] = mapped_column(JSON)
    state: Mapped[str] = mapped_column(default='pending')
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())
    accepted_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


def selected_snapshot(card):
    return {key: card[key] for key in ['taste_id', 'nickname', 'songs']}


def is_friendship(invitation):
    return bool(invitation.sender_snapshot.get('friendship') and invitation.recipient_snapshot.get('friendship'))


def public_snapshot(snapshot):
    return {**{key: snapshot[key] for key in ['taste_id','nickname','songs']}, 'songs': [{k: v for k, v in song.items() if k in {'artist', 'title'}}
                                for song in snapshot['songs']]}


async def invitation_state(session, invitation):
    if invitation.state in {'declined', 'revoked'}:
        return invitation.state
    from .social import blocked
    if await blocked(session, invitation.sender_id, invitation.recipient_id):
        return 'revoked'
    if invitation.state == 'consented' and is_friendship(invitation):
        return 'consented'
    if invitation.expires_at <= utc_now():
        return 'expired'
    sender = await session.get(TasteCard, invitation.sender_id)
    recipient = await session.get(TasteCard, invitation.recipient_id)
    if (sender is None or recipient is None or sender.revision != invitation.sender_revision
            or recipient.revision != invitation.recipient_revision or recipient.share_token != invitation.card_token
            or not recipient.share_expires_at or recipient.share_expires_at <= utc_now()):
        return 'stale'
    return invitation.state


async def presentation(session, invitation, user_id):
    # Authorize before exposing even a nickname, state or selected song.
    if user_id not in {invitation.sender_id, invitation.recipient_id}:
        raise CardError('invite_unavailable')
    state = await invitation_state(session, invitation)
    value = dict(token=invitation.token, role='sender' if user_id == invitation.sender_id else 'recipient',
                 state=state, friendship=is_friendship(invitation),
                 expires_at=None if state=='consented' and is_friendship(invitation) else invitation.expires_at.isoformat())
    if state in {'pending', 'consented'}:
        from .taste_sharing import visible_snapshot
        sender=await visible_snapshot(session,invitation.sender_id,invitation.sender_snapshot)
        recipient=await visible_snapshot(session,invitation.recipient_id,invitation.recipient_snapshot)
        value.update(sender=public_snapshot(sender),
                     recipient=public_snapshot(recipient),
                     sender_consented=True, recipient_consented=state == 'consented')
    return value


class ComparisonInvitations:
    def __init__(self, database):
        self.database = database

    async def cleanup(self, telegram_id):
        async with self.database.write() as session:
            user_id = await session.scalar(select(User.id).where(User.telegram_user_id == telegram_id))
            participants = ((ComparisonInvitation.sender_id == user_id) | (ComparisonInvitation.recipient_id == user_id))
            rows=list(await session.scalars(select(ComparisonInvitation).where(participants,
                ComparisonInvitation.expires_at <= utc_now())))
            for row in rows:
                if row.state=='consented' and is_friendship(row):continue
                row.sender_snapshot=row.recipient_snapshot={}
                if row.expires_at < utc_now()-timedelta(days=7):await session.delete(row)

    async def create(self, telegram_id, card_token, sender_revision, recipient_revision):
        if (not isinstance(card_token, str) or not re.fullmatch(r'[A-Za-z0-9_-]{32}', card_token)
                or type(sender_revision) is not int or type(recipient_revision) is not int):
            raise CardError('invite_invalid')
        await self.cleanup(telegram_id)
        async with self.database.write() as session:
            sender = await _card(session, telegram_id)
            recipient = await session.scalar(select(TasteCard).where(
                TasteCard.share_token == card_token, TasteCard.share_expires_at > utc_now()))
            if recipient is None:
                raise CardError('invite_unavailable')
            if sender.user_id == recipient.user_id:
                raise CardError('invite_self')
            from .social import blocked
            if await blocked(session, sender.user_id, recipient.user_id):
                raise CardError('invite_unavailable')
            if sender.revision != sender_revision or recipient.revision != recipient_revision:
                raise CardError('invite_stale')
            own = await _projection(session, sender, owner=True)
            other = await _projection(session, recipient, owner=True)
            if not own['nickname'] or not own['songs']:
                raise CardError('card_incomplete')
            # Serialize duplicate taps and avoid minting another invitation for the same snapshots.
            existing = (await session.scalars(select(ComparisonInvitation).where(
                ComparisonInvitation.sender_id == sender.user_id, ComparisonInvitation.recipient_id == recipient.user_id,
                ComparisonInvitation.state.in_(['pending', 'consented']), ComparisonInvitation.expires_at > utc_now())
                .order_by(ComparisonInvitation.created_at.desc()).limit(10))).all()
            for row in existing:
                if is_friendship(row) and await invitation_state(session, row) in {'pending', 'consented'}:
                    return await presentation(session, row, sender.user_id)
            count = await session.scalar(select(func.count()).select_from(ComparisonInvitation).where(
                ComparisonInvitation.sender_id == sender.user_id,
                ComparisonInvitation.created_at > utc_now() - timedelta(days=1)))
            if count >= 5:
                raise CardError('invite_limit')
            row = ComparisonInvitation(token=secrets.token_urlsafe(24), sender_id=sender.user_id,
                recipient_id=recipient.user_id, sender_revision=sender.revision, recipient_revision=recipient.revision,
                card_token=card_token, sender_snapshot={**selected_snapshot(own),'friendship':True}, recipient_snapshot={**selected_snapshot(other),'friendship':True},
                state='pending', expires_at=min(utc_now() + INVITATION_TTL, recipient.share_expires_at))
            session.add(row)
            await session.flush()
            return await presentation(session, row, sender.user_id)

    async def target(self, card_token):
        """A shared card can reveal its own revision, never private ratings/contacts."""
        if not isinstance(card_token, str) or not re.fullmatch(r'[A-Za-z0-9_-]{32}', card_token):
            raise CardError('invite_unavailable')
        async with self.database.sessions() as session:
            row = await session.scalar(select(TasteCard).where(
                TasteCard.share_token == card_token, TasteCard.share_expires_at > utc_now()))
            if row is None:
                raise CardError('invite_unavailable')
            return row.revision

    async def read(self, telegram_id, token):
        await self.cleanup(telegram_id)
        async with self.database.sessions() as session:
            user_id = await session.scalar(select(User.id).where(User.telegram_user_id == telegram_id))
            if not isinstance(token, str) or not re.fullmatch(r'[A-Za-z0-9_-]{32}', token):
                raise CardError('invite_unavailable')
            row = await session.get(ComparisonInvitation, token)
            if row is None:
                raise CardError('invite_unavailable')
            return await presentation(session, row, user_id)

    async def decide(self, telegram_id, token, action):
        if not isinstance(action, str) or action not in {'accept', 'decline', 'revoke', 'unfriend'} or not isinstance(token, str):
            raise CardError('invite_invalid')
        async with self.database.write() as session:
            user_id = await session.scalar(select(User.id).where(User.telegram_user_id == telegram_id))
            row = await session.get(ComparisonInvitation, token)
            if row is None or user_id not in {row.sender_id, row.recipient_id}:
                raise CardError('invite_unavailable')
            if action not in {'revoke','unfriend'} and user_id != row.recipient_id:
                raise CardError('invite_unavailable')
            if action in {'revoke','unfriend'} and row.state=='consented' and is_friendship(row):
                from .social import stop_interactions
                await stop_interactions(session, user_id, row.recipient_id if row.sender_id==user_id else row.sender_id)
            elif action == 'unfriend':
                if row.state=='revoked' and row.accepted_at is not None:
                    return await presentation(session,row,user_id)
                raise CardError('invite_unavailable')
            elif action == 'revoke':
                row.state = 'revoked'
                # Revoked consent no longer retains the selected-song snapshots.
                row.sender_snapshot = row.recipient_snapshot = {}
                from .social import stop_invitation_swaps
                await stop_invitation_swaps(session, [row.token])
            else:
                state = await invitation_state(session, row)
                target = 'consented' if action == 'accept' else 'declined'
                if state == target:
                    return await presentation(session, row, user_id)
                if state != 'pending':
                    raise CardError('invite_stale')
                row.state = target
                if action == 'accept':
                    row.accepted_at = utc_now()
                    if is_friendship(row):
                        # Storage sentinel, not a user-facing friendship deadline.
                        row.expires_at = datetime(9999, 1, 1, tzinfo=timezone.utc)
                        from .social_activity import accepted
                        await accepted(session,row)
                else:
                    row.sender_snapshot = row.recipient_snapshot = {}
            await session.flush()
            return await presentation(session, row, user_id)

    async def listing(self, telegram_id):
        await self.cleanup(telegram_id)
        async with self.database.sessions() as session:
            user_id = await session.scalar(select(User.id).where(User.telegram_user_id == telegram_id))
            rows = (await session.scalars(select(ComparisonInvitation).where(
                (ComparisonInvitation.sender_id == user_id) | (ComparisonInvitation.recipient_id == user_id))
                .order_by(ComparisonInvitation.state.in_(['pending','consented']).desc(),
                          ComparisonInvitation.created_at.desc()).limit(100))).all()
            return [await presentation(session, row, user_id) for row in rows]
