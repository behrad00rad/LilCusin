"""Two bot-first entry paths with explicit ratings and a five-song picker."""
from aiogram.types import ForceReply, InlineKeyboardButton as Button, InlineKeyboardMarkup
from sqlalchemy import ForeignKey, func, select
from sqlalchemy.orm import Mapped, mapped_column

from .i18n import tr
from .models import Base, Rating, User
from .taste_cards import TasteCards


class Onboarding(Base):
    __tablename__ = 'card_onboarding'
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    mode: Mapped[str] = mapped_column(default='pick')
    prompt_message_id: Mapped[int | None]
    active: Mapped[bool] = mapped_column(default=True)


def welcome_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [Button(text=tr('onboard_send'), callback_data='ob:send', style='primary')],
        [Button(text=tr('onboard_pick'), callback_data='ob:pick', style='primary')]])


async def set_mode(chat, telegram_id, mode, active=True):
    async with chat.database.write() as session:
        user_id = await session.scalar(select(User.id).where(User.telegram_user_id == telegram_id))
        if user_id is None:
            return
        row = await session.get(Onboarding, user_id)
        if row is None:
            row = Onboarding(user_id=user_id);session.add(row)
        row.mode, row.active, row.prompt_message_id = mode, active, None


async def ask_pick(message, chat, telegram_id):
    card = await TasteCards(chat.database).owner(telegram_id)
    count = len(card['songs'])
    if count >= 5:
        await set_mode(chat, telegram_id, 'pick', False)
        await message.answer(tr('onboard_done'))
        from .taste_card_chat import show_card
        await show_card(message, chat, telegram_id)
        await recommendations(message, chat, telegram_id, card['songs'][-1]['id'])
        return
    sent = await message.answer(tr('onboard_pick_prompt', n=count + 1),
                               reply_markup=ForceReply(selective=True, input_field_placeholder=tr('onboard_song_placeholder')))
    async with chat.database.write() as session:
        user_id = await session.scalar(select(User.id).where(User.telegram_user_id == telegram_id))
        row = await session.get(Onboarding, user_id)
        if row is not None and row.active and row.mode == 'pick':
            row.prompt_message_id = sent.message_id


async def recommendations(message, chat, telegram_id, seed=None):
    from .chat_ui import button, clean
    from . import messages
    if seed is None:
        result = await chat.recommendations.recommend_for_user(telegram_id, limit=3)
    else:
        result = await chat.recommendations.recommend_similar_to_track(telegram_id, seed, limit=3)
    if not result.recommendations:
        await message.answer(tr('onboard_no_picks'))
        return
    for row in result.recommendations[:3]:
        token = await chat.create_control(telegram_id, tracks=[row.track_id], seed=seed, kind='rating')
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            button(token, value, messages.rating_label(value, None), 0)
            for value in ['love', 'like', 'neutral', 'dislike']]])
        sent = await message.answer(f'{clean(row.title)}\n{clean(row.artist)}', parse_mode=None, reply_markup=keyboard)
        await chat.bind_control(token, sent.message_id)
        await chat.record_displayed(telegram_id, [row], token, seed)


async def start_path(message, chat, telegram_id, mode):
    await set_mode(chat, telegram_id, mode)
    if mode == 'pick':
        await ask_pick(message, chat, telegram_id)
    else:
        async with chat.database.sessions() as session:
            count = await session.scalar(select(func.count()).select_from(Rating).join(User).where(
                User.telegram_user_id == telegram_id, Rating.value.in_(['love', 'like'])))
        if count:
            await set_mode(chat, telegram_id, mode, False)
            await recommendations(message, chat, telegram_id)
        else:
            from .chat_ui import main_menu
            await message.answer(tr('onboard_send_prompt'), reply_markup=main_menu())


async def handle_reply(message, chat, workflow):
    if not message.reply_to_message:
        return False
    user_id = message.from_user.id
    async with chat.database.write() as session:
        row = await session.scalar(select(Onboarding).join(User).where(User.telegram_user_id == user_id,
            Onboarding.active.is_(True), Onboarding.mode == 'pick',
            Onboarding.prompt_message_id == message.reply_to_message.message_id))
        if row is None:
            return False
        row.prompt_message_id = None
    from .taste_card_chat import search_songs
    if not await search_songs(message, chat, workflow, message.text):
        await ask_pick(message, chat, user_id)
    return True


async def after_pick(message, chat, telegram_id):
    async with chat.database.sessions() as session:
        row = await session.scalar(select(Onboarding).join(User).where(
            User.telegram_user_id == telegram_id, Onboarding.active.is_(True), Onboarding.mode == 'pick'))
    if row is not None:
        await ask_pick(message, chat, telegram_id)
        return True
    return False


async def after_rating(message, chat, telegram_id):
    ready = False
    async with chat.database.write() as session:
        row = await session.scalar(select(Onboarding).join(User).where(
            User.telegram_user_id == telegram_id, Onboarding.active.is_(True), Onboarding.mode == 'send'))
        if row is not None:
            count = await session.scalar(select(func.count()).select_from(Rating).where(
                Rating.user_id == row.user_id, Rating.value.in_(['love', 'like'])))
            if count >= 3:
                row.active = False;ready = True
    if ready:
        await recommendations(message, chat, telegram_id)
