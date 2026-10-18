"""Remove only known transient UI messages, never delivered audio or a chat sweep."""
from datetime import timedelta
from sqlalchemy import select
from .models import ChatControl, IdentificationFlow, SongSubmission, User, utc_now
from .fetch_models import AudioRequest


async def clear_previous_search(message, database):
    user_id = message.from_user.id
    cutoff = utc_now() - timedelta(hours=47)
    async with database.sessions() as session:
        owner = await session.scalar(select(User.id).where(User.telegram_user_id == user_id))
        if owner is None:
            return
        controls = (await session.scalars(select(ChatControl).where(ChatControl.user_id == owner,
            ChatControl.expires_at > cutoff).order_by(ChatControl.expires_at.desc()).limit(40))).all()
        flows = (await session.scalars(select(IdentificationFlow).join(SongSubmission).where(
            SongSubmission.user_id == owner, IdentificationFlow.expires_at > cutoff)
            .order_by(IdentificationFlow.expires_at.desc()).limit(40))).all()
        requests = (await session.scalars(select(AudioRequest).where(AudioRequest.user_id == owner,
            AudioRequest.state.in_(['failed', 'cancelled', 'done']), AudioRequest.created_at > cutoff)
            .order_by(AudioRequest.created_at.desc()).limit(40))).all()
    ids = {c.message_id for c in controls if c.payload.get('kind') in {'card', 'rating', 'list'}}
    ids.update(f.prompt_message_id for f in flows)
    ids.update(r.status_message_id for r in requests)
    removed = set()
    # Capture only messages older than the incoming query. A background cleanup
    # must never remove the new acknowledgement or results created meanwhile.
    for mid in sorted(i for i in ids if i and i < message.message_id)[-40:]:
        try:
            await message.model_copy(update={'message_id': mid}).delete()
            removed.add(mid)
        except Exception:
            pass  # Old Telegram messages may no longer be deletable.
    if removed:
        async with database.write() as session:
            for token in [c.token for c in controls if c.message_id in removed]:
                row = await session.get(ChatControl, token)
                if row and row.message_id in removed:
                    row.message_id = None
            for req in requests:
                if req.status_message_id in removed:
                    row = await session.get(AudioRequest, req.id)
                    if row and row.status_message_id in removed:
                        row.status_message_id = None
            for flow in flows:
                if flow.prompt_message_id in removed:
                    row = await session.get(IdentificationFlow, flow.submission_id)
                    if row and row.prompt_message_id in removed:
                        row.prompt_message_id = None
