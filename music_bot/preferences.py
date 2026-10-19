"""Per-user language and first-visit guide state; removed with the user account."""
from sqlalchemy import ForeignKey, select
from sqlalchemy.orm import Mapped, mapped_column
from .models import Base, User
from .submissions import Submitter

LANGUAGES = {'en':'English','fa':'فارسی','ar':'العربية','tr':'Türkçe','ru':'Русский','es':'Español','fr':'Français','de':'Deutsch'}


def normalize_language(value):
    code = str(value or '').lower().split('-')[0].split('_')[0]
    return code if code in LANGUAGES else 'en'


class UserPreferences(Base):
    __tablename__ = 'user_preferences'
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    language: Mapped[str | None]
    bot_guide_seen: Mapped[bool] = mapped_column(default=False)
    ui_guide_done: Mapped[bool] = mapped_column(default=False)


async def preferences(database, telegram_id, fallback=None, *, language=None, bot_seen=None, ui_done=None):
    async with database.write() as session:
        user = await session.scalar(select(User).where(User.telegram_user_id == telegram_id))
        if user is None:
            raise ValueError('User must exist before preferences are accessed')
        row = await session.get(UserPreferences, user.id)
        if row is None:
            row = UserPreferences(user_id=user.id, bot_guide_seen=False, ui_guide_done=False)
            session.add(row)
        if language is not None:
            if language not in LANGUAGES:
                raise ValueError('Unsupported language')
            row.language = language
        if bot_seen is not None: row.bot_guide_seen = bot_seen
        if ui_done is not None: row.ui_guide_done = ui_done
        result=dict(language=row.language or normalize_language(fallback or user.language_code),
                    bot_guide_seen=row.bot_guide_seen, ui_guide_done=row.ui_guide_done)
    from .taste_setup import needed
    result['taste_setup_done']=not await needed(database,telegram_id)
    return result
