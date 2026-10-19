"""Owner-bound Mini App song links enter the existing bot delivery workflow."""
import re
from sqlalchemy import select
from .models import ChatControl, User, utc_now
from .i18n import tr


async def start_delivery(message, chat, get_song, payload):
    match = re.fullmatch(r'get_([a-f0-9]{32})_([1-9][0-9]{0,17})', payload)
    if match is None:
        await message.answer(tr('get_song_stale'))
        return
    token, track_id = match[1], int(match[2])
    async with chat.database.sessions() as session:
        grant = await session.scalar(select(ChatControl).join(User).where(
            ChatControl.token == token, User.telegram_user_id == message.from_user.id,
            ChatControl.expires_at > utc_now()))
        if grant is None or grant.payload.get('kind') != 'miniapp' or track_id not in grant.payload.get('tracks', []):
            await message.answer(tr('get_song_stale'))
            return
    if get_song is None:
        await message.answer(tr('get_song_unavailable'))
        return
    await get_song.begin(message, message.from_user.id, track_id)
