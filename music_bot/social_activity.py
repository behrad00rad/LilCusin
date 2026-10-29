"""Friend acceptance alerts; swap activity reuses the existing notice records."""
from datetime import timedelta, datetime
from sqlalchemy import ForeignKey, select, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.sqlite import insert
from .models import Base, User, UTCDateTime, utc_now
from .taste_cards import CardError

class FriendNotice(Base):
    __tablename__='friend_notices'
    invitation: Mapped[str]=mapped_column(ForeignKey('comparison_invitations.token',ondelete='CASCADE'),primary_key=True)
    user_id: Mapped[int]=mapped_column(ForeignKey('users.id',ondelete='CASCADE'),index=True)
    state: Mapped[str]=mapped_column(default='queued')
    created_at: Mapped[datetime]=mapped_column(UTCDateTime(),default=utc_now)
    attempted_at: Mapped[datetime|None]=mapped_column(UTCDateTime())

async def accepted(session, invitation):
    await session.execute(insert(FriendNotice).values(invitation=invitation.token,user_id=invitation.sender_id,state='queued').on_conflict_do_nothing())

async def attempts(session, actor):
    from .social import SocialNotice
    cutoff=utc_now()-timedelta(days=1)
    return sum([await session.scalar(select(func.count()).select_from(model).where(model.user_id==actor,model.attempted_at>cutoff)) for model in (SocialNotice,FriendNotice)])

async def activity(database, telegram_id):
    from .social import Social, SocialNotice, consent, user_id
    result=[];service=Social(database)
    async with database.sessions() as session:
        actor=await user_id(session,telegram_id)
        rows=await session.scalars(select(FriendNotice).where(FriendNotice.user_id==actor).order_by(FriendNotice.created_at.desc()).limit(10))
        for row in rows:
            try:connection=await consent(session,row.invitation,actor)
            except CardError:continue
            result.append(dict(event='accepted',name=connection.recipient_snapshot.get('nickname',''),invitation=row.invitation,at=row.created_at.isoformat()))
        rows=await session.scalars(select(SocialNotice).where(SocialNotice.user_id==actor,SocialNotice.event.in_(['pick','saved','loved'])).order_by(SocialNotice.created_at.desc()).limit(15))
        for row in rows:
            try:
                swap=await service._swap(session,actor,row.swap_token)
                projection=await service._projection(session,actor,swap)
            except CardError:continue
            if row.event=='saved' and not swap.saved:continue
            result.append(dict(event=row.event,name=projection['partner'],song=projection['song']['title'],swap=row.swap_token,at=row.created_at.isoformat()))
    return sorted(result,key=lambda item:item['at'],reverse=True)[:15]

async def flush(database, bot):
    if bot is None:return
    from .social import SocialSettings, consent
    from .taste_cards import CardError
    from .preferences import UserPreferences
    from .i18n import language,tr
    from .invitation_chat import exchanges_button
    from aiogram.types import InlineKeyboardMarkup
    async with database.sessions() as session:
        tokens=list(await session.scalars(select(FriendNotice.invitation).where(FriendNotice.state=='queued').limit(20)))
    for token in tokens:
        async with database.write() as session:
            row=await session.get(FriendNotice,token)
            if row is None or row.state!='queued':continue
            settings=await session.get(SocialSettings,row.user_id)
            try:connection=await consent(session,token,row.user_id)
            except CardError:row.state='cancelled';continue
            if settings is None or not settings.notifications or settings.suspended:row.state='cancelled';continue
            if await attempts(session,row.user_id)>=3:row.state='capped';continue
            row.state='attempted';row.attempted_at=utc_now()
            user=await session.get(User,row.user_id);prefs=await session.get(UserPreferences,row.user_id)
            destination=user.telegram_user_id;locale=prefs.language if prefs else user.language_code
            name=connection.recipient_snapshot.get('nickname','')
        context=language.set(locale or 'en')
        try:
            await bot.send_message(destination,tr('activity_accepted',name=name),parse_mode=None,reply_markup=InlineKeyboardMarkup(inline_keyboard=[[exchanges_button()]]))
            state='sent'
        except Exception:state='uncertain'
        finally:language.reset(context)
        async with database.write() as session:
            row=await session.get(FriendNotice,token)
            if row is not None:row.state=state
