"""Durable human-triggered game alerts. Ambiguous sends are never replayed."""
import asyncio
import secrets
from datetime import datetime, timedelta
from urllib.parse import urlsplit, urlencode

from sqlalchemy import ForeignKey, UniqueConstraint, CheckConstraint, Index, select, delete, func
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base, User, UTCDateTime, utc_now
from .guess_game import enabled, allow_guess
from .guess_service import GuessError, relationship, answers, group, NEED, TEHRAN
from .social import SocialSettings
from .comparison_invitations import ComparisonInvitation
from .preferences import UserPreferences, normalize_language
from .i18n import language, tr


class GuessAlertSettings(Base):
    __tablename__ = 'guess_alert_settings'
    __table_args__ = (CheckConstraint('quiet_start BETWEEN 0 AND 23 AND quiet_end BETWEEN 0 AND 23 AND quiet_start != quiet_end'),)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    alerts: Mapped[bool] = mapped_column(default=True)
    quiet_start: Mapped[int] = mapped_column(default=22)
    quiet_end: Mapped[int] = mapped_column(default=8)


class GuessPair(Base):
    __tablename__ = 'guess_pairs'
    guesser_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    target_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    last_nudge: Mapped[datetime | None] = mapped_column(UTCDateTime())
    last_finish_attempt: Mapped[datetime | None] = mapped_column(UTCDateTime())
    muted: Mapped[bool] = mapped_column(default=False)


class GuessNotice(Base):
    __tablename__ = 'guess_notices'
    __table_args__ = (UniqueConstraint('guesser_id', 'target_id', 'kind', 'day'),
                     CheckConstraint("kind IN ('finish','nudge')"),
                     Index('ix_guess_notices_due','state','due_at'))
    token: Mapped[str] = mapped_column(primary_key=True, default=lambda: secrets.token_urlsafe(24))
    guesser_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    target_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    invitation: Mapped[str] = mapped_column(ForeignKey('comparison_invitations.token', ondelete='CASCADE'))
    kind: Mapped[str]
    day: Mapped[str]
    score: Mapped[int] = mapped_column(default=0)
    games: Mapped[int] = mapped_column(default=1)
    remaining: Mapped[int] = mapped_column(default=0)
    state: Mapped[str] = mapped_column(default='queued')
    due_at: Mapped[datetime] = mapped_column(UTCDateTime())
    attempted_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


async def purge(session, first, second=None):
    for model in (GuessNotice, GuessPair):
        where = (model.guesser_id == first) | (model.target_id == first)
        if second is not None:
            where &= (model.guesser_id == second) | (model.target_id == second)
        await session.execute(delete(model).where(where))


async def connection(session, actor, target):
    await relationship(session, actor, target=target)
    rows = await session.scalars(select(ComparisonInvitation).where(
        ComparisonInvitation.state == 'consented',
        ((ComparisonInvitation.sender_id == actor) & (ComparisonInvitation.recipient_id == target)) |
        ((ComparisonInvitation.sender_id == target) & (ComparisonInvitation.recipient_id == actor))))
    from .comparison_invitations import is_friendship
    return next(row for row in rows if is_friendship(row))


async def enqueue_finish(session, game):
    now = utc_now(); day = now.astimezone(TEHRAN).date().isoformat()
    row = await session.scalar(select(GuessNotice).where(GuessNotice.guesser_id == game.guesser_id,
        GuessNotice.target_id == game.target_id, GuessNotice.kind == 'finish', GuessNotice.day == day))
    if row:
        if row.state == 'queued':
            row.score = game.score; row.games += 1
        return
    friend = await connection(session, game.guesser_id, game.target_id)
    session.add(GuessNotice(guesser_id=game.guesser_id, target_id=game.target_id,
        invitation=friend.token, kind='finish', day=day, score=game.score, due_at=now+timedelta(minutes=2)))


async def nudged(session, actor, target):
    pair = await session.get(GuessPair, (actor, target))
    return bool(pair and pair.last_nudge and pair.last_nudge > utc_now()-timedelta(days=3))


async def nudge(database, telegram_id, friend_id):
    async with database.write() as session:
        actor = await session.scalar(select(User.id).where(User.telegram_user_id == telegram_id))
        target = await relationship(session, actor, friend_id=friend_id)
        safe, _ = await answers(session, target)
        have = len({group(item) for item in safe.values()})
        if have >= NEED:
            raise GuessError('guess_invalid', 409)
        if await nudged(session, actor, target):
            raise GuessError('guess_nudge_limit', 429)
        pair = await session.get(GuessPair, (actor, target))
        if pair is None:
            pair = GuessPair(guesser_id=actor, target_id=target); session.add(pair)
        now = utc_now(); pair.last_nudge = now
        session.add(GuessNotice(guesser_id=actor, target_id=target, invitation=friend_id,
            kind='nudge', day=now.astimezone(TEHRAN).date().isoformat(), remaining=NEED-have, due_at=now))
    return {'nudged': True}


async def settings(database, telegram_id, values=None):
    if not enabled(): raise GuessError('guess_unavailable')
    if values is not None and (set(values) != {'alerts','quiet_start','quiet_end'} or
            type(values['alerts']) is not bool or any(type(values[k]) is not int or not 0 <= values[k] <= 23 for k in ['quiet_start','quiet_end']) or values['quiet_start'] == values['quiet_end']):
        raise GuessError('guess_invalid', 400)
    async with database.write() as session:
        actor = await session.scalar(select(User.id).where(User.telegram_user_id == telegram_id))
        if actor is None: raise GuessError('guess_unavailable')
        row = await session.get(GuessAlertSettings, actor)
        if row is None:
            row = GuessAlertSettings(user_id=actor, alerts=True, quiet_start=22, quiet_end=8); session.add(row)
        if values:
            for key, value in values.items(): setattr(row,key,value)
            if not row.alerts:
                await session.execute(delete(GuessNotice).where(GuessNotice.target_id==actor,GuessNotice.state=='queued'))
        return dict(alerts=row.alerts,quiet_start=row.quiet_start,quiet_end=row.quiet_end)


def quiet_until(now, start=22, end=8):
    local = now.astimezone(TEHRAN)
    quiet = start <= local.hour < end if start < end else local.hour >= start or local.hour < end
    if not quiet: return None
    until = local.replace(hour=end,minute=0,second=0,microsecond=0)
    return until + timedelta(days=1) if until <= local else until


async def permitted(session, row):
    if not enabled(): return False
    try: await relationship(session,row.guesser_id,target=row.target_id)
    except GuessError: return False
    social = await session.get(SocialSettings,row.target_id)
    prefs = await session.get(GuessAlertSettings,row.target_id)
    pair = await session.get(GuessPair,(row.guesser_id,row.target_id))
    return bool(social and social.notifications and not social.suspended and
                (prefs is None or prefs.alerts) and (pair is None or not pair.muted))


def app_url(origin, token):
    parsed = urlsplit(origin)
    if parsed.scheme != 'https' or not parsed.netloc or parsed.username or parsed.password: return None
    return origin.split('?',1)[0].split('#',1)[0].rstrip('/')+'/?'+urlencode({'guess':token})


async def flush(database, bot, origin):
    if bot is None or not enabled(): return
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
    async with database.sessions() as session:
        tokens = list(await session.scalars(select(GuessNotice.token).where(GuessNotice.state=='queued',GuessNotice.due_at<=utc_now()).limit(20)))
    for token in tokens:
        async with database.write() as session:
            row = await session.get(GuessNotice,token)
            if row is None or row.state != 'queued': continue
            if not await permitted(session,row): row.state='suppressed';continue
            prefs = await session.get(GuessAlertSettings,row.target_id)
            until = quiet_until(utc_now(),prefs.quiet_start if prefs else 22,prefs.quiet_end if prefs else 8)
            if until: row.due_at=until;continue
            midnight=utc_now().astimezone(TEHRAN).replace(hour=0,minute=0,second=0,microsecond=0)
            pair=await session.get(GuessPair,(row.guesser_id,row.target_id))
            if row.kind=='finish' and pair and pair.last_finish_attempt and pair.last_finish_attempt>=midnight:
                row.state='capped';continue
            attempted=select(GuessNotice).where(GuessNotice.target_id==row.target_id,GuessNotice.attempted_at>=midnight)
            if row.kind=='finish' and await session.scalar(attempted.where(GuessNotice.guesser_id==row.guesser_id,GuessNotice.kind=='finish').limit(1)):
                row.state='capped';continue
            own=await session.scalar(select(func.count()).select_from(GuessNotice).where(GuessNotice.target_id==row.target_id,GuessNotice.attempted_at>utc_now()-timedelta(days=1)))
            if own>=3: row.state='capped';continue
            url = app_url(origin,row.invitation)
            if not url: continue  # Missing app configuration leaves the queue pending.
            row.state='attempted';row.attempted_at=utc_now()
            if row.kind=='finish':
                if pair is None:
                    pair=GuessPair(guesser_id=row.guesser_id,target_id=row.target_id);session.add(pair)
                pair.last_finish_attempt=utc_now()
        # Claim is durable before the network call. Hold the second writer lock
        # through the bounded send so a block/unfriend cannot complete before it.
        async with database.write() as session:
            row = await session.get(GuessNotice,token)
            if row is None: continue
            if not await permitted(session,row): row.state='suppressed';continue
            alerts=await session.get(GuessAlertSettings,row.target_id)
            until=quiet_until(utc_now(),alerts.quiet_start if alerts else 22,alerts.quiet_end if alerts else 8)
            if until:
                row.state='queued';row.attempted_at=None;row.due_at=until
                if row.kind=='finish':
                    pair=await session.get(GuessPair,(row.guesser_id,row.target_id))
                    if pair:pair.last_finish_attempt=None
                continue
            user = await session.get(User,row.target_id);prefs = await session.get(UserPreferences,row.target_id)
            friend = await session.get(ComparisonInvitation,row.invitation)
            snapshot = friend.sender_snapshot if friend.sender_id == row.guesser_id else friend.recipient_snapshot
            name = str(snapshot.get('nickname') or '')[:40]
            context = language.set(normalize_language((prefs.language if prefs else user.language_code) or 'en'))
            try:
                if row.kind=='nudge':
                    safe,_ = await answers(session,row.target_id);remaining=NEED-len({group(item) for item in safe.values()})
                    if remaining<=0: row.state='suppressed';continue
                    text=tr('guess_notice_nudge_one' if remaining==1 else 'guess_notice_nudge',name=name,n=remaining)
                    url=app_url(origin,row.invitation).split('?',1)[0]+'?view=search'
                else:
                    text=tr('guess_notice_finish',name=name,score=row.score)
                    if row.games>1:text+='\n'+tr('guess_notice_batch',n=row.games)
                keys=[[InlineKeyboardButton(text=tr('guess_notice_find' if row.kind=='nudge' else 'guess_notice_open'),web_app=WebAppInfo(url=url))],
                      [InlineKeyboardButton(text=tr('guess_notice_mute'),callback_data='gg:m:'+token),
                       InlineKeyboardButton(text=tr('guess_notice_stop'),callback_data='gg:s:'+token)]]
                async with asyncio.timeout(5):
                    await bot.send_message(user.telegram_user_id,text,parse_mode=None,reply_markup=InlineKeyboardMarkup(inline_keyboard=keys))
                row.state='sent'
            except Exception: row.state='uncertain'
            finally: language.reset(context)


async def callback(query,chat_service):
    if query.from_user.is_bot or not query.message or query.message.chat.type!='private' or query.message.chat.id!=query.from_user.id:
        await query.answer();return
    parts=(query.data or '').split(':')
    if len(parts)!=3 or parts[1] not in {'m','s'}: await query.answer();return
    async with chat_service.database.write() as session:
        actor=await session.scalar(select(User.id).where(User.telegram_user_id==query.from_user.id))
        row=await session.get(GuessNotice,parts[2])
        if row is None or actor!=row.target_id: await query.answer();return
        if parts[1]=='m':
            pair=await session.get(GuessPair,(row.guesser_id,actor))
            if pair is None: pair=GuessPair(guesser_id=row.guesser_id,target_id=actor);session.add(pair)
            pair.muted=True
            await session.execute(delete(GuessNotice).where(GuessNotice.guesser_id==row.guesser_id,GuessNotice.target_id==actor,GuessNotice.state=='queued'))
        else:
            prefs=await session.get(GuessAlertSettings,actor)
            if prefs is None:prefs=GuessAlertSettings(user_id=actor);session.add(prefs)
            prefs.alerts=False
            await session.execute(delete(GuessNotice).where(GuessNotice.target_id==actor,GuessNotice.state=='queued'))
    await query.answer(tr('guess_notice_muted'))


async def worker(database,bot,origin):
    while True:
        try: await flush(database,bot,origin)
        except asyncio.CancelledError: raise
        except Exception: pass  # No identities/URLs/error bodies in logs.
        await asyncio.sleep(30)
