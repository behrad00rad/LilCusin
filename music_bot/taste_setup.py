"""First picks are stated preferences, never fabricated song ratings."""
from sqlalchemy import ForeignKey, select
from sqlalchemy.orm import Mapped, mapped_column
from .models import Base, User

STYLES = ('pop','rock','indie','hiphop','electronic','jazz','classical','persian')
MOODS = ('calm','energetic','mixed')
ARTISTS = {
    'pop': ('Billie Eilish','Dua Lipa'), 'rock': ('Radiohead','Muse'),
    'indie': ('Beach House','Arctic Monkeys'), 'hiphop': ('Mac Miller','Kendrick Lamar'),
    'electronic': ('Nils Frahm','Daft Punk'), 'jazz': ('Bill Evans','John Coltrane'),
    'classical': ('Frédéric Chopin','Ludwig van Beethoven'), 'persian': ('Mohammad Reza Shajarian','Hayedeh'),
}

class TasteSetup(Base):
    __tablename__ = 'taste_setup'
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id',ondelete='CASCADE'),primary_key=True)
    style: Mapped[str | None]
    mood: Mapped[str | None]
    artist: Mapped[str | None]
    completed: Mapped[bool] = mapped_column(default=False)
    step: Mapped[int] = mapped_column(default=0)

async def read_setup(database,telegram_id):
    async with database.sessions() as session:
        row=await session.scalar(select(TasteSetup).join(User).where(User.telegram_user_id==telegram_id))
        return dict(style=row.style,mood=row.mood,artist=row.artist,completed=row.completed,step=row.step) if row else dict(style=None,mood=None,artist=None,completed=False,step=0)

async def save_setup(database,telegram_id,*,style=None,mood=None,artist=None,completed=True,step=3):
    if style is not None and style not in STYLES:raise ValueError('Choose a music style.')
    if mood is not None and mood not in MOODS:raise ValueError('Choose a mood.')
    if artist is not None and (not isinstance(artist,str) or len(artist)>80):raise ValueError('Use an artist name up to 80 characters.')
    async with database.write() as session:
        user=await session.scalar(select(User).where(User.telegram_user_id==telegram_id))
        if user is None:raise ValueError('User unavailable.')
        row=await session.get(TasteSetup,user.id)
        if row is None:row=TasteSetup(user_id=user.id);session.add(row)
        row.style,row.mood,row.artist=style,mood,(artist.strip() or None) if artist else None
        row.completed,row.step=completed,step
        from .taste_learning import invalidate
        await invalidate(session,user.id)

async def needed(database,telegram_id):
    from .models import Rating,UserTrackSignal
    async with database.sessions() as session:
        user=await session.scalar(select(User.id).where(User.telegram_user_id==telegram_id))
        row=await session.get(TasteSetup,user) if user else None
        if row:return not row.completed
        return not (await session.scalar(select(Rating.id).where(Rating.user_id==user).limit(1)) or
                    await session.scalar(select(UserTrackSignal.id).where(UserTrackSignal.user_id==user).limit(1)))
