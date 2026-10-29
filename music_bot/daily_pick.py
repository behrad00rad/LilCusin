"""One durable daily chef pick per private user; only the poller owns the loop."""
import asyncio
import logging
import json
from dataclasses import asdict
from datetime import timedelta, timezone

from aiogram import Router
from aiogram.filters import Command
from aiogram.exceptions import TelegramForbiddenError
from aiogram.types import InlineKeyboardMarkup
from sqlalchemy import ForeignKey, String, select, or_, delete
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base, ChatControl, RecommendationHistory, User, utc_now
from .preferences import UserPreferences, normalize_language
from .social import SocialSettings
from .i18n import language

logger = logging.getLogger('music_bot')
TEHRAN = timezone(timedelta(hours=3, minutes=30))
router = Router()


class DailyPickState(Base):
    __tablename__ = 'daily_pick_state'
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    enabled: Mapped[bool] = mapped_column(default=True)
    day: Mapped[str | None] = mapped_column(String(10))
    state: Mapped[str] = mapped_column(default='ready')


def copy(key, locale=None):
    fa = (locale or language.get()) == 'fa'
    return {
        'intro': ('👨‍🍳 سه انتخاب امروزِ سرآشپز مخصوص تو!\n\nبه یکی دو تا آهنگ امتیاز بده تا سلیقه‌ت رو بهتر بشناسم 🎧',
                  '👨‍🍳 Your personal chef’s three picks for today!\n\nRate a song or two—it helps me get to know your taste better 🎧'),
        'off': ('پیشنهاد روزانه خاموش شد. برای فعال‌کردن دوباره: /daily on', 'Daily picks are off. Turn them back on with /daily on.'),
        'on': ('پیشنهاد روزانه روشنه؛ هر روز ساعت ۱۸ به وقت تهران. برای قطع: /daily off', 'Daily picks are on, every day at 6 PM Tehran time. Stop with /daily off.'),
        'stop': ('پیشنهاد روزانه رو قطع کن', 'Stop daily picks'),
        'usage': ('/daily on یا /daily off', 'Use /daily on or /daily off.'),
    }[key][0 if fa else 1]


def audio_keyboard(token, locale=None):
    from .chat_ui import button
    fa = (locale or language.get()) == 'fa'
    return InlineKeyboardMarkup(inline_keyboard=[[
        button(token, 'known', 'این رو می‌شناسم' if fa else 'Already know it', 0),
        button(token, 'notforme', 'سلیقه‌م نیست' if fa else 'Not for me', 0),
        button(token, 'more', 'بیشتر شبیه این' if fa else 'More like this', 0),
    ]])


def varied_picks(rows):
    """Keep a close first pick, then favor different artists and a little exploration."""
    remaining=list(rows);picked=[];artists=set();tracks=set()
    while remaining and len(picked)<3:
        if not picked:index=0
        else:
            index=max(range(len(remaining)),key=lambda i:(remaining[i].artist.casefold() not in artists,
                bool(remaining[i].exploration) if len(picked)==2 else False,-i))
        row=remaining.pop(index)
        if row.track_id in tracks:continue
        picked.append(row);artists.add(row.artist.casefold());tracks.add(row.track_id)
    return picked


def explain_caption(fields, req, locale):
    from .i18n import localized_reason
    pick=(req.canonical_metadata or {}).get('_daily_pick') or {}
    reason=pick.get('recommendation',{}).get('reason')
    if not reason:return fields
    context=language.set(normalize_language(locale))
    try:reason=localized_reason(str(reason))
    finally:language.reset(context)
    label='چرا این آهنگ؟ ' if normalize_language(locale)=='fa' else 'Why this pick: '
    return {**fields,'caption':fields['caption']+'\n\n'+label+' '.join(reason.split())[:350]}


async def prepare_audio(delivery, req, telegram_id, track_id, locale):
    """Present only a ready file, inside the existing durable sending claim."""
    from .chat_service import ChatService
    from .fetch_models import AudioRequest
    payload = dict(req.canonical_metadata or {})
    pick = payload['_daily_pick']
    now = utc_now().astimezone(TEHRAN)
    if pick['day'] != now.date().isoformat() or now.hour >= 22:
        return None
    async with delivery.db.sessions() as session:
        settings = await session.get(DailyPickState, req.user_id)
        social = await session.get(SocialSettings, req.user_id)
        if settings is None or not settings.enabled or (social and social.suspended):
            return None
    token = payload.get('_daily_control')
    if not token:
        token = await ChatService(delivery.db, None).create_control(telegram_id, tracks=[track_id], kind='card')
    async with delivery.db.write() as session:
        current = await session.get(AudioRequest, req.id)
        if current is None or current.state != 'sending':
            return None
        payload = dict(current.canonical_metadata)
        state=await session.get(DailyPickState,req.user_id)
        intro = not payload.get('_daily_intro_attempted') and (pick.get('test') or state.state not in {'introduced','sent'})
        if intro and not pick.get('test'):state.state='introduced'
        payload.update(_daily_control=token, _daily_intro_attempted=True)
        current.canonical_metadata = payload
        control = await session.get(ChatControl, token)
        control.payload = {**control.payload, 'daily': True}
        control.expires_at = utc_now() + timedelta(days=2)
    req.canonical_metadata = payload
    if intro:
        await delivery.bot.send_message(telegram_id, copy('intro', locale), parse_mode=None)
    return audio_keyboard(token, locale)


async def acknowledge_audio(session, req, track, sent):
    """Save feedback binding and history with the acknowledged audio receipt."""
    from .recommendations.queue import QueuedRecommendation
    payload = req.canonical_metadata or {}
    pick = payload.get('_daily_pick')
    if not pick:
        return
    token = payload.get('_daily_control')
    control = await session.get(ChatControl, token) if token else None
    if control:
        control.message_id = sent.message_id
    row = pick['recommendation']
    await session.execute(insert(RecommendationHistory).values(
        user_id=req.user_id, track_id=track.id, batch_id='daily_' + req.id,
        position=1, ranking_score=row['score'], reason=row['reason'], recommended_at=utc_now(),
        source=json.dumps({'sources': row['sources'], 'exploration': row.get('exploration', False), 'daily': True})
    ).on_conflict_do_nothing(index_elements=['user_id', 'batch_id', 'track_id']))
    from .admin_tracking import stage
    await stage(session, req.user_id, 'first_recommendation_shown')
    await session.execute(delete(QueuedRecommendation).where(
        QueuedRecommendation.user_id == req.user_id, QueuedRecommendation.track_id == track.id))
    state = await session.get(DailyPickState, req.user_id)
    if state and state.day == pick['day'] and not pick.get('test'):
        state.state = 'sent'


async def setting(database, telegram_id, enabled=None):
    async with database.write() as session:
        user = await session.scalar(select(User).where(User.telegram_user_id == telegram_id))
        if user is None:
            return False
        row = await session.get(DailyPickState, user.id)
        if row is None:
            row = DailyPickState(user_id=user.id, enabled=True)
            session.add(row)
        if enabled is not None:
            row.enabled = enabled
        return row.enabled


@router.message(Command('daily'))
async def daily_command(message, chat_service):
    if message.chat.type != 'private' or message.from_user.is_bot:
        return
    args = (message.text or '').split()[1:]
    if args and args not in (['on'], ['off']):
        await message.answer(copy('usage'))
        return
    active = await setting(chat_service.database, message.from_user.id,
                           args[0] == 'on' if args else None)
    await message.answer(copy('on' if active else 'off'))


@router.callback_query(lambda query: query.data == 'daily:off')
async def daily_off(query, chat_service):
    if not query.message or query.message.chat.type != 'private' or query.message.chat.id != query.from_user.id:
        await query.answer()
        return
    await setting(chat_service.database, query.from_user.id, False)
    await query.answer(copy('off'))


class DailyPicks:
    def __init__(self, service, bot, delivery):
        self.service, self.database = service, service.database
        self.bot, self.delivery = bot, delivery
        self.task = None

    def start(self):
        self.task = asyncio.create_task(self.run())

    async def close(self):
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)

    async def claim(self, telegram_id, day):
        async with self.database.write() as session:
            user = await session.scalar(select(User).where(User.telegram_user_id == telegram_id))
            if user is None or telegram_id <= 0:
                return None
            social = await session.get(SocialSettings, user.id)
            if social and social.suspended:
                return None
            row = await session.get(DailyPickState, user.id)
            if row is None:
                row = DailyPickState(user_id=user.id, enabled=True)
                session.add(row)
            if not row.enabled or row.day == day:
                return None
            row.day, row.state = day, 'attempted'
            prefs = await session.get(UserPreferences, user.id)
            return (prefs.language if prefs else None) or user.language_code or 'en'

    async def finish(self, telegram_id, state, *, blocked=False):
        async with self.database.write() as session:
            internal = await session.scalar(select(User.id).where(User.telegram_user_id == telegram_id))
            row = await session.get(DailyPickState, internal) if internal else None
            if row:
                if state == 'queued' and row.state in {'sent','introduced'}:
                    return
                row.state = state
                if blocked:
                    row.enabled = False

    async def send(self, telegram_id, day):
        locale = await self.claim(telegram_id, day)
        if locale is None:
            return
        context = language.set(normalize_language(locale))
        batch = None
        try:
            async with asyncio.timeout(600):
                from .monthly_pitch import has_history,send_pitch
                async with self.database.sessions() as session:
                    internal=await session.scalar(select(User.id).where(User.telegram_user_id==telegram_id))
                    history=internal is not None and await has_history(session,internal)
                if not history:
                    await send_pitch(self.database,self.bot,telegram_id,locale)
                    await self.finish(telegram_id,'monthly_invitation')
                    return
                result = await self.service.recommendations.queue.reserve(telegram_id, limit=5, feed=True)
                batch = result.batch_id
                if not result.recommendations:
                    await self.finish(telegram_id, 'empty')
                    return
                if not await setting(self.database, telegram_id):
                    return
                if not self.delivery.settings.enabled:
                    await self.finish(telegram_id, 'unavailable')
                    return
                from .fetch_models import AudioRequest
                picks=varied_picks(result.recommendations)
                for index,row in enumerate(picks,1):
                    if not await setting(self.database,telegram_id):break
                    request_id = await self.delivery.request(telegram_id, row.track_id, learn=False,
                        daily_pick={'day': day, 'recommendation': asdict(row),'number':index,'total':3})
                    if not request_id:continue
                    await self.finish(telegram_id,'queued')
                    if index==len(picks):continue
                    # Respect the existing two-request quota; let the existing worker
                    # finish each file before adding the next, never another poller.
                    for _ in range(90):
                        async with self.database.sessions() as session:
                            request=await session.get(AudioRequest,request_id)
                            if request is None or request.state not in {'pending','sending'}:break
                        await asyncio.sleep(2)
        except TelegramForbiddenError:
            await self.finish(telegram_id, 'blocked', blocked=True)
        except Exception:
            # Network ambiguity is not safe to retry; today's durable claim remains.
            logger.warning('Daily pick unavailable; no automatic retry today.')
        finally:
            try:
                if batch:
                    await self.service.recommendations.queue.release(telegram_id, batch)
            finally:
                language.reset(context)

    async def tick(self, now=None):
        local = (now or utc_now()).astimezone(TEHRAN)
        if not 18 <= local.hour < 22:
            return  # No overnight or multi-day catch-up burst.
        cursor = 0
        while True:
            async with self.database.sessions() as session:
                ids = list(await session.scalars(select(User.telegram_user_id).outerjoin(
                    DailyPickState, DailyPickState.user_id == User.id).where(
                    User.telegram_user_id > cursor,
                    or_(DailyPickState.user_id.is_(None), DailyPickState.enabled.is_(True)),
                    or_(DailyPickState.day.is_(None), DailyPickState.day != local.date().isoformat())
                    ).order_by(User.telegram_user_id).limit(100)))
            if not ids:
                return
            for telegram_id in ids:
                if (utc_now().astimezone(TEHRAN).hour >= 22) and now is None:
                    return
                await self.send(telegram_id, local.date().isoformat())
                await asyncio.sleep(1)
            cursor = ids[-1]

    async def run(self):
        while True:
            try:
                await self.tick()
            except Exception:
                logger.warning('Daily pick cycle unavailable; will check later.')
            await asyncio.sleep(300)
