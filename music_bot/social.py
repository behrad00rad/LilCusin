"""Selected-song comparison and explicit reciprocal exchanges, shared by chat/API."""
import re
import secrets
import asyncio
from datetime import datetime, timedelta
from sqlalchemy import CheckConstraint, ForeignKey, UniqueConstraint, select, func, update, delete
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.sqlite import insert
from .models import Base, User, Track, Rating, UTCDateTime, normalize_name, utc_now
from .taste_cards import CardError, TasteCard
from .comparison_invitations import ComparisonInvitation, invitation_state, public_snapshot


class SocialSettings(Base):
    __tablename__ = 'social_settings'
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    notifications: Mapped[bool] = mapped_column(default=False)
    suspended: Mapped[bool] = mapped_column(default=False)


class SocialBlock(Base):
    __tablename__ = 'social_blocks'
    owner_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    target_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    handle: Mapped[str] = mapped_column(unique=True, default=lambda: secrets.token_urlsafe(24))
    label: Mapped[str] = mapped_column(default='')
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class SongSwap(Base):
    __tablename__ = 'song_swaps'
    __table_args__ = (CheckConstraint("state IN ('draft','sent','cancelled','deleted')"),)
    token: Mapped[str] = mapped_column(primary_key=True)
    invitation: Mapped[str] = mapped_column(ForeignKey('comparison_invitations.token', ondelete='CASCADE'), index=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    recipient_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    track_id: Mapped[int] = mapped_column(ForeignKey('tracks.id'))
    note: Mapped[str] = mapped_column(default='')
    state: Mapped[str] = mapped_column(default='draft')
    loved: Mapped[bool] = mapped_column(default=False)
    saved: Mapped[bool] = mapped_column(default=False)
    reply_to: Mapped[str | None]  # No FK: deletion of a source must not leak another user's identifier.
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    sent_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())


class SavedSong(Base):
    __tablename__ = 'social_saved_songs'
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    track_id: Mapped[int] = mapped_column(ForeignKey('tracks.id'), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class SocialNotice(Base):
    __tablename__ = 'social_notices'
    __table_args__ = (UniqueConstraint('swap_token', 'user_id', 'event'),)
    token: Mapped[str] = mapped_column(primary_key=True)
    swap_token: Mapped[str] = mapped_column(ForeignKey('song_swaps.token', ondelete='CASCADE'), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    event: Mapped[str]
    state: Mapped[str] = mapped_column(default='queued')
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    attempted_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class SocialReport(Base):
    __tablename__ = 'social_reports'
    token: Mapped[str] = mapped_column(primary_key=True)
    reporter_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    target_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    swap_token: Mapped[str | None] = mapped_column(ForeignKey('song_swaps.token', ondelete='SET NULL'))
    reason: Mapped[str]
    evidence_note: Mapped[str] = mapped_column(default='')
    state: Mapped[str] = mapped_column(default='open')
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


def token_valid(token):
    return isinstance(token, str) and bool(re.fullmatch(r'[A-Za-z0-9_-]{32}', token))


async def user_id(session, telegram_id):
    value = await session.scalar(select(User.id).where(User.telegram_user_id == telegram_id))
    if value is None:
        raise CardError('social_unavailable')
    return value


async def blocked(session, first, second):
    pair = ((SocialBlock.owner_id == first) & (SocialBlock.target_id == second)) | ((SocialBlock.owner_id == second) & (SocialBlock.target_id == first))
    return bool(await session.scalar(select(SocialBlock.owner_id).where(pair).limit(1)) or
                await session.scalar(select(SocialSettings.user_id).where(SocialSettings.user_id.in_([first, second]), SocialSettings.suspended.is_(True)).limit(1)))


async def consent(session, token, actor):
    row = await session.get(ComparisonInvitation, token) if token_valid(token) else None
    if row is None or actor not in {row.sender_id, row.recipient_id}:
        raise CardError('social_unavailable')
    if await invitation_state(session, row) != 'consented' or await blocked(session, row.sender_id, row.recipient_id):
        raise CardError('social_unavailable')
    return row


def comparison(first, second):
    """Only consented selections; absence means not selected, never not rated."""
    left = {song['id']: song for song in first['songs']}
    right = {song['id']: song for song in second['songs']}
    artists_left = {normalize_name(song['artist']): song['artist'] for song in left.values()}
    artists_right = {normalize_name(song['artist']): song['artist'] for song in right.values()}
    project = lambda songs: [{k: song[k] for k in ['artist', 'title']} for song in songs]
    return dict(sparse=min(len(left), len(right)) < 3, minimum=3,
                shared_songs=project(left[k] for k in sorted(left.keys() & right.keys())),
                shared_artists=[artists_left[k] for k in sorted(artists_left.keys() & artists_right.keys())],
                only_first=project(left[k] for k in sorted(left.keys() - right.keys())),
                only_second=project(right[k] for k in sorted(right.keys() - left.keys())))


async def notice(session, swap, user, event):
    await session.execute(insert(SocialNotice).values(token=secrets.token_urlsafe(24), swap_token=swap.token,
        user_id=user, event=event, state='queued').on_conflict_do_nothing(index_elements=['swap_token','user_id','event']))


async def stop_interactions(session, first, second=None):
    pair = ((SongSwap.sender_id == first) | (SongSwap.recipient_id == first))
    invites = ((ComparisonInvitation.sender_id == first) | (ComparisonInvitation.recipient_id == first))
    if second is not None:
        pair &= ((SongSwap.sender_id == second) | (SongSwap.recipient_id == second))
        invites &= ((ComparisonInvitation.sender_id == second) | (ComparisonInvitation.recipient_id == second))
    await session.execute(update(SocialNotice).where(SocialNotice.swap_token.in_(select(SongSwap.token).where(pair)),
        SocialNotice.state == 'queued').values(state='cancelled'))
    await session.execute(update(SongSwap).where(pair, SongSwap.state.in_(['draft','sent'])).values(state='cancelled', note=''))
    await session.execute(update(ComparisonInvitation).where(invites,
        ComparisonInvitation.state.in_(['pending','consented'])).values(state='revoked', sender_snapshot={}, recipient_snapshot={}))


async def stop_invitation_swaps(session, invitations):
    swaps=select(SongSwap.token).where(SongSwap.invitation.in_(invitations))
    await session.execute(update(SocialNotice).where(SocialNotice.swap_token.in_(swaps),SocialNotice.state=='queued').values(state='cancelled'))
    await session.execute(update(SongSwap).where(SongSwap.invitation.in_(invitations),SongSwap.state.in_(['draft','sent'])).values(state='cancelled',note=''))


async def remove_saved(session,actor,track_id):
    await session.execute(delete(SavedSong).where(SavedSong.user_id==actor,SavedSong.track_id==track_id))
    swaps=select(SongSwap.token).where(SongSwap.recipient_id==actor,SongSwap.track_id==track_id)
    await session.execute(update(SocialNotice).where(SocialNotice.swap_token.in_(swaps),SocialNotice.event=='saved',SocialNotice.state=='queued').values(state='cancelled'))
    await session.execute(update(SongSwap).where(SongSwap.recipient_id==actor,SongSwap.track_id==track_id).values(saved=False))


class Social:
    def __init__(self, database): self.database = database

    async def cleanup(self, telegram_id):
        async with self.database.write() as session:
            actor=await user_id(session,telegram_id)
            own=(SongSwap.sender_id==actor)|(SongSwap.recipient_id==actor)
            await session.execute(update(SongSwap).where(own,SongSwap.expires_at<=utc_now()).values(note=''))
            await session.execute(delete(SongSwap).where(own,SongSwap.expires_at<utc_now()-timedelta(days=7)))
            await session.execute(delete(SocialReport).where(SocialReport.created_at<utc_now()-timedelta(days=90)))

    async def compare(self, telegram_id, token):
        async with self.database.sessions() as session:
            actor = await user_id(session, telegram_id)
            row = await consent(session, token, actor)
            first = row.sender_snapshot if actor == row.sender_id else row.recipient_snapshot
            second = row.recipient_snapshot if actor == row.sender_id else row.sender_snapshot
            return dict(token=token, you=public_snapshot(first), other=public_snapshot(second), **comparison(first, second))

    async def choices(self, telegram_id, invitation, reply_to=None):
        async with self.database.sessions() as session:
            actor = await user_id(session, telegram_id)
            row = await consent(session, invitation, actor)
            if reply_to:
                original = await self._swap(session, actor, reply_to)
                if original.recipient_id != actor or original.invitation != invitation:
                    raise CardError('social_unavailable')
            snapshot = row.sender_snapshot if actor == row.sender_id else row.recipient_snapshot
            return [dict(id=song['id'], artist=song['artist'], title=song['title']) for song in snapshot['songs']]

    async def draft(self, telegram_id, invitation, track_id, reply_to=None):
        if type(track_id) is not int or (reply_to is not None and not token_valid(reply_to)):
            raise CardError('social_invalid')
        async with self.database.write() as session:
            actor = await user_id(session, telegram_id)
            row = await consent(session, invitation, actor)
            snapshot = row.sender_snapshot if actor == row.sender_id else row.recipient_snapshot
            if track_id not in {song['id'] for song in snapshot['songs']}:
                raise CardError('social_unavailable')
            if reply_to:
                original = await self._swap(session, actor, reply_to)
                if original.recipient_id != actor or original.invitation != invitation:
                    raise CardError('social_unavailable')
            recipient = row.recipient_id if actor == row.sender_id else row.sender_id
            existing = await session.scalar(select(SongSwap).where(SongSwap.sender_id == actor, SongSwap.invitation == invitation,
                SongSwap.track_id == track_id, SongSwap.reply_to == reply_to, SongSwap.state == 'draft', SongSwap.expires_at > utc_now()))
            if existing: return await self._projection(session, actor, existing)
            count = await session.scalar(select(func.count()).select_from(SongSwap).where(SongSwap.sender_id == actor, SongSwap.created_at > utc_now()-timedelta(days=1)))
            if count >= 10: raise CardError('social_limit')
            swap = SongSwap(token=secrets.token_urlsafe(24), invitation=invitation, sender_id=actor, recipient_id=recipient,
                track_id=track_id, reply_to=reply_to, state='draft', note='', loved=False, saved=False, expires_at=row.expires_at)
            session.add(swap);await session.flush()
            return await self._projection(session, actor, swap)

    async def _swap(self, session, actor, token, *, draft=False):
        row = await session.get(SongSwap, token) if token_valid(token) else None
        if row is None or actor not in {row.sender_id, row.recipient_id} or row.expires_at <= utc_now():
            raise CardError('social_unavailable')
        if row.state != 'sent' and not (draft and row.sender_id == actor and row.state == 'draft'):
            raise CardError('social_unavailable')
        await consent(session, row.invitation, actor)
        return row

    async def _projection(self, session, actor, row):
        track = await session.get(Track, row.track_id)
        card = await session.get(TasteCard, row.recipient_id if actor == row.sender_id else row.sender_id)
        return dict(token=row.token, invitation=row.invitation, role='sender' if actor == row.sender_id else 'recipient',
            state=row.state, song=dict(id=track.id, artist=track.display_artist or track.artist, title=track.display_title or track.title),
            partner=card.nickname if card else '', note=row.note, saved=row.saved, loved=row.loved,
            reply_to=row.reply_to, expires_at=row.expires_at.isoformat())

    async def read(self, telegram_id, token):
        async with self.database.sessions() as session:
            actor = await user_id(session, telegram_id)
            row = await self._swap(session, actor, token, draft=True)
            return await self._projection(session, actor, row)

    async def act(self, telegram_id, token, action, note_text=''):
        if not isinstance(action,str) or action not in {'note','send','save','unsave','love','cancel','delete','remind'}:
            raise CardError('social_invalid')
        if not isinstance(note_text, str) or len(note_text) > 240 or any(ord(c)<32 and c not in '\n\t' for c in note_text):
            raise CardError('social_invalid')
        async with self.database.write() as session:
            actor = await user_id(session, telegram_id)
            row = await self._swap(session, actor, token, draft=True)
            sender = actor == row.sender_id
            if action in {'note','send','cancel','remind'} and not sender:
                raise CardError('social_unavailable')
            if action in {'save','unsave','love'} and (sender or row.state != 'sent'):
                raise CardError('social_unavailable')
            if action == 'note':
                if row.state != 'draft': raise CardError('social_unavailable')
                from .taste_cards import clean_text
                row.note = clean_text(note_text,240)
            elif action == 'send':
                if row.state == 'draft':
                    row.state = 'sent';row.sent_at = utc_now()
                    await notice(session, row, row.recipient_id, 'pick')
            elif action == 'save':
                await session.execute(insert(SavedSong).values(user_id=actor, track_id=row.track_id).on_conflict_do_nothing())
                if not row.saved:
                    row.saved = True;await notice(session, row, row.sender_id, 'saved')
            elif action == 'unsave':
                await remove_saved(session,actor,row.track_id)
            elif action == 'love':
                if not row.loved:
                    row.loved = True
                    await session.execute(insert(Rating).values(user_id=actor, track_id=row.track_id, value='love')
                        .on_conflict_do_update(index_elements=['user_id','track_id'], set_=dict(value='love', updated_at=utc_now())))
                    await notice(session, row, row.sender_id, 'loved')
            elif action in {'cancel','delete'}:
                row.state = 'cancelled' if action == 'cancel' else 'deleted';row.note = ''
                await session.execute(update(SocialNotice).where(SocialNotice.swap_token == row.token, SocialNotice.state == 'queued').values(state='cancelled'))
                return dict(token=row.token, state=row.state)
            else:
                if row.state != 'sent' or row.saved or row.loved or row.sent_at > utc_now()-timedelta(hours=24):
                    raise CardError('social_limit')
                old = (await session.scalars(select(SocialNotice).where(SocialNotice.swap_token == row.token, SocialNotice.event.like('reminder%')))).all()
                if len(old) >= 2 or any(n.created_at > utc_now()-timedelta(hours=24) for n in old):
                    raise CardError('social_limit')
                await notice(session, row, row.recipient_id, 'reminder'+str(len(old)+1))
            await session.flush()
            return await self._projection(session, actor, row)

    async def inbox(self, telegram_id):
        await self.cleanup(telegram_id)
        async with self.database.sessions() as session:
            actor = await user_id(session, telegram_id)
            rows = (await session.scalars(select(SongSwap).where((SongSwap.sender_id == actor) | (SongSwap.recipient_id == actor),
                SongSwap.state.in_(['draft','sent']), SongSwap.expires_at > utc_now()).order_by(SongSwap.created_at.desc()).limit(40))).all()
            values = []
            for row in rows:
                if row.state == 'draft' and row.sender_id != actor: continue
                try: await self._swap(session, actor, row.token, draft=True)
                except CardError: continue
                values.append(await self._projection(session, actor, row))
            return values

    async def remove_save(self,telegram_id,track_id):
        if type(track_id) is not int: raise CardError('social_invalid')
        async with self.database.write() as session:
            actor=await user_id(session,telegram_id)
            await remove_saved(session,actor,track_id)
            return dict(removed=True)

    async def settings(self, telegram_id, notifications=None):
        if notifications is not None and type(notifications) is not bool: raise CardError('social_invalid')
        await self.cleanup(telegram_id)
        async with self.database.write() as session:
            actor = await user_id(session, telegram_id)
            row = await session.get(SocialSettings, actor)
            if row is None: row=SocialSettings(user_id=actor,notifications=False,suspended=False);session.add(row)
            if notifications is not None:
                row.notifications = notifications
                if not notifications:
                    await session.execute(update(SocialNotice).where(SocialNotice.user_id == actor, SocialNotice.state == 'queued').values(state='cancelled'))
            blocks = (await session.scalars(select(SocialBlock).where(SocialBlock.owner_id == actor).limit(100))).all()
            result=[]
            for item in blocks:
                # Own block records expose only a chosen label and an opaque owner-bound handle.
                result.append(dict(handle=item.handle,nickname=item.label))
            return dict(notifications=row.notifications, suspended=row.suspended, blocks=result)

    async def relationship(self, telegram_id, invitation, action, reason='spam', swap_token=None):
        if not isinstance(action,str) or not isinstance(reason,str) or action not in {'block','unblock','report'} or reason not in {'spam','harassment','unsafe','other'}:
            raise CardError('social_invalid')
        async with self.database.write() as session:
            actor=await user_id(session,telegram_id)
            if action=='unblock':
                item=await session.scalar(select(SocialBlock).where(SocialBlock.owner_id==actor,SocialBlock.handle==invitation))
                if item is None: raise CardError('social_unavailable')
                await session.delete(item)
                return dict(state='unblock')
            row=await session.get(ComparisonInvitation,invitation) if token_valid(invitation) else None
            if row is None or actor not in {row.sender_id,row.recipient_id}: raise CardError('social_unavailable')
            target=row.recipient_id if row.sender_id==actor else row.sender_id
            if swap_token:
                swap=await session.get(SongSwap,swap_token) if token_valid(swap_token) else None
                if swap is None or swap.invitation!=invitation or actor not in {swap.sender_id,swap.recipient_id}: raise CardError('social_unavailable')
            if action=='block':
                snapshot=row.recipient_snapshot if row.sender_id==actor else row.sender_snapshot
                await session.execute(insert(SocialBlock).values(owner_id=actor,target_id=target,label=snapshot.get('nickname','')).on_conflict_do_nothing())
                await stop_interactions(session,actor,target)
            else:
                count=await session.scalar(select(func.count()).select_from(SocialReport).where(SocialReport.reporter_id==actor,SocialReport.created_at>utc_now()-timedelta(days=1)))
                if count>=5: raise CardError('social_limit')
                duplicate=await session.scalar(select(SocialReport).where(SocialReport.reporter_id==actor,SocialReport.target_id==target,SocialReport.swap_token==swap_token,SocialReport.state=='open'))
                if duplicate: return dict(state='reported')
                session.add(SocialReport(token=secrets.token_urlsafe(24),reporter_id=actor,target_id=target,swap_token=swap_token,reason=reason,evidence_note=swap.note if swap_token else ''))
            return dict(state='reported' if action=='report' else action)

    async def moderate(self, telegram_id, moderators, report=None, action=None):
        if telegram_id not in moderators: raise CardError('social_unavailable')
        async with self.database.write() as session:
            await session.execute(delete(SocialReport).where(SocialReport.created_at<utc_now()-timedelta(days=90)))
            if report:
                row=await session.get(SocialReport,report) if token_valid(report) else None
                if row is None or action not in {'dismiss','suspend'}: raise CardError('social_invalid')
                if row.state=='open':
                    row.state=action;row.resolved_at=utc_now()
                    if action=='suspend':
                        await session.execute(insert(SocialSettings).values(user_id=row.target_id,notifications=False,suspended=True)
                            .on_conflict_do_update(index_elements=['user_id'],set_=dict(notifications=False,suspended=True)))
                        await stop_interactions(session,row.target_id)
                return dict(state=row.state)
            rows=(await session.scalars(select(SocialReport).where(SocialReport.state=='open').order_by(SocialReport.created_at).limit(30))).all()
            values=[]
            for row in rows:
                swap=await session.get(SongSwap,row.swap_token) if row.swap_token else None
                values.append(dict(token=row.token,reason=row.reason,note=row.evidence_note,state=row.state))
            return dict(reports=values)

    async def flush_notices(self, bot):
        """Durable at-most-once attempts. Ambiguous Telegram failures are never replayed."""
        try:
            async with asyncio.timeout(8):
                await self._flush_notices(bot)
        except TimeoutError:
            pass  # Already claimed attempts remain non-retryable; the inbox still works.

    async def _flush_notices(self, bot):
        if bot is None: return
        async with self.database.sessions() as session:
            tokens=list((await session.scalars(select(SocialNotice.token).where(SocialNotice.state=='queued').order_by(SocialNotice.created_at).limit(20))).all())
        from .i18n import language, tr
        from .preferences import UserPreferences
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
        for token in tokens:
            async with self.database.write() as session:
                row=await session.get(SocialNotice,token)
                if row is None or row.state!='queued': continue
                settings=await session.get(SocialSettings,row.user_id)
                swap=await session.get(SongSwap,row.swap_token)
                try:
                    if settings is None or not settings.notifications or settings.suspended: raise CardError('social_unavailable')
                    await self._swap(session,row.user_id,row.swap_token)
                except CardError:
                    row.state='cancelled';continue
                count=await session.scalar(select(func.count()).select_from(SocialNotice).where(SocialNotice.user_id==row.user_id,SocialNotice.attempted_at>utc_now()-timedelta(days=1)))
                if count>=3: row.state='capped';continue
                row.state='attempted';row.attempted_at=utc_now()
                user=await session.get(User,row.user_id)
                prefs=await session.get(UserPreferences,row.user_id)
                destination=user.telegram_user_id;locale=prefs.language if prefs else user.language_code
                event=row.event;swap_token=row.swap_token
                projection=await self._projection(session,row.user_id,swap)
            context=language.set(locale or 'en')
            try:
                rows=[[InlineKeyboardButton(text=tr('social_open'),callback_data='ss:view:'+swap_token)]]
                text=tr('social_notice_'+('reminder' if event.startswith('reminder') else event))
                song=projection['song'];identity=song['artist'][:70]+' — '+song['title'][:90]
                if event=='pick':
                    text=tr('social_from',name=projection['partner'])+'\n\n'+identity
                    if projection['note']: text+='\n\n'+projection['note']
                    rows=[[
                        InlineKeyboardButton(text=tr('social_save'),callback_data='ss:save:'+swap_token),
                        InlineKeyboardButton(text=tr('social_love'),callback_data='ss:love:'+swap_token),
                        InlineKeyboardButton(text=tr('social_reply'),callback_data='ss:reply:'+swap_token)],
                        [InlineKeyboardButton(text=tr('social_block'),callback_data='sc:block:'+projection['invitation']),
                         InlineKeyboardButton(text=tr('social_report'),callback_data='ss:report:'+swap_token)],*rows]
                elif event in {'saved','loved'}:
                    text=tr('social_'+event+'_by',name=projection['partner'])+'\n\n'+identity
                await bot.send_message(destination,text,reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),parse_mode=None)
                state='sent'
            except Exception:
                state='uncertain'  # Inbox is authoritative; no automatic network retry.
            finally: language.reset(context)
            async with self.database.write() as session:
                row=await session.get(SocialNotice,token)
                if row is not None: row.state=state
