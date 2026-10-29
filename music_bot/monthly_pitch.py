"""At-most-once per 30 days invitation for private users without taste history."""
import asyncio
import logging
from datetime import timedelta
from uuid import uuid4
from sqlalchemy import select
from aiogram.exceptions import TelegramForbiddenError
from aiogram.types import InlineKeyboardButton,InlineKeyboardMarkup
from .models import User,Rating,UserTrackSignal,SongSubmission,ChatControl,utc_now
from .taste_setup import TasteSetup
from .taste_learning import TasteRequest,TrackPreference
from .social import SavedSong,SocialSettings
from .preferences import normalize_language

logger=logging.getLogger('music_bot')

async def has_history(session,user_id):
    for model in (Rating,UserTrackSignal,TasteRequest,TrackPreference,SavedSong):
        if await session.scalar(select(model.user_id).where(model.user_id==user_id).limit(1)) is not None:return True
    if await session.scalar(select(SongSubmission.id).where(SongSubmission.user_id==user_id,SongSubmission.track_id.is_not(None)).limit(1)) is not None:return True
    setup=await session.get(TasteSetup,user_id)
    return bool(setup and (setup.artist or setup.style or setup.mood))

def pitch_text(locale):
    if normalize_language(locale)=='fa':
        return ('👨‍🍳 دوست دارم برات آهنگ انتخاب کنم، ولی هنوز سلیقه‌ت رو نمی‌شناسم.\n\n'
            'اگه تو تلگرام آهنگ گوش می‌دی، یه آهنگ یا لینک بفرست؛ می‌تونم آهنگ پیدا کنم، تشخیص بدم چی پخش می‌شه، متنش رو بیارم و محبوب‌هات رو تو LilCusin نگه دارم.\n\n'
            'با /rate به یکی دو تا آهنگ امتیاز بده تا کم‌کم بفهمم چی دوست داری 🎧\n\n'
            'برای قطع پیام‌های روزانه: /daily off')
    return ('👨‍🍳 I’d love to pick music for you, but I don’t know your taste yet.\n\n'
        'Already listen to music on Telegram? Send me a song or a link: I can find music, recognize what’s playing, show lyrics, and keep your favourites in LilCusin.\n\n'
        'Rate a song or two with /rate so I can learn what you love 🎧\n\n'
        '/daily off to stop these messages.')

async def send_pitch(database,bot,telegram_id,locale):
    from .daily_pick import DailyPickState
    now=utc_now()
    # Existing owner-bound, explicitly erased chat state supplies durable cooldown
    # storage without a new table. Claim before network I/O; ambiguity never replays.
    async with database.write() as session:
        user=await session.scalar(select(User).where(User.telegram_user_id==telegram_id))
        if user is None:return False
        daily=await session.get(DailyPickState,user.id)
        social=await session.get(SocialSettings,user.id)
        if daily is None or not daily.enabled or (social and (social.suspended or not social.notifications)):return False
        if await has_history(session,user.id):return False
        prior=await session.scalar(select(ChatControl.token).where(ChatControl.user_id==user.id,
            ChatControl.payload['kind'].as_string()=='monthly_pitch',ChatControl.expires_at>now).limit(1))
        if prior:return False
        token=uuid4().hex
        session.add(ChatControl(token=token,user_id=user.id,payload={'kind':'monthly_pitch','state':'attempted'},expires_at=now+timedelta(days=30)))
    fa=normalize_language(locale)=='fa'
    rows=[[InlineKeyboardButton(text='پیدا کردن آهنگ' if fa else 'Find music',callback_data='nav:search')]]
    try:
        async with asyncio.timeout(2):
            menu=await bot.get_chat_menu_button()
        if getattr(menu,'web_app',None):
            rows.append([InlineKeyboardButton(text='باز کردن LilCusin' if fa else 'Open LilCusin',web_app=menu.web_app)])
    except Exception:pass
    rows.append([InlineKeyboardButton(text='قطع این پیام‌ها' if fa else 'Stop these messages',callback_data='daily:off')])
    try:
        # Recheck preferences/history after preparing the app button.
        async with database.sessions() as session:
            daily=await session.get(DailyPickState,user.id)
            social=await session.get(SocialSettings,user.id)
            if daily is None or not daily.enabled or (social and (social.suspended or not social.notifications)) or await has_history(session,user.id):return False
        sent=await bot.send_message(telegram_id,pitch_text(locale),parse_mode=None,reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
        async with database.write() as session:
            control=await session.get(ChatControl,token)
            if control:control.message_id=sent.message_id;control.payload={'kind':'monthly_pitch','state':'sent'}
        return True
    except TelegramForbiddenError:
        async with database.write() as session:
            daily=await session.get(DailyPickState,user.id)
            if daily:daily.enabled=False
    except Exception:
        logger.warning('Monthly invitation unconfirmed; cooldown retained.')
    return False
