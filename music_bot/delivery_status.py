"""Read-only, signed delivery receipts; opening the UI never queues audio."""
from datetime import datetime
from aiohttp import web
from sqlalchemy import select, or_
from .models import ChatControl, User, utc_now
from .fetch_models import AudioRequest, FetchJob


def register_delivery_status(app, chat):
    async def status(request):
        try:
            data = await request.json()
            if not isinstance(data, dict) or set(data) - {'track_id', 'token', 'swap_token', 'after', 'request_id'}:
                raise ValueError
            track_id = data.get('track_id')
            if type(track_id) is not int or track_id <= 0:
                raise ValueError
            request_id = data.get('request_id')
            if request_id is not None and (not isinstance(request_id, str) or not 1 <= len(request_id) <= 80):
                raise ValueError
            after = datetime.fromisoformat(data['after']) if 'after' in data else None
            if after is not None and (after.tzinfo is None or not -30 <= (utc_now() - after).total_seconds() <= 900):
                raise ValueError
        except (ValueError, TypeError, KeyError):
            raise web.HTTPBadRequest(text='Invalid delivery status request.') from None
        actor = request['user']['id']
        if 'swap_token' in data:
            if 'token' in data or not isinstance(data['swap_token'], str):
                raise web.HTTPBadRequest(text='Choose one song source.')
            from .social import Social
            from .taste_cards import CardError
            try:
                swap = await Social(chat.database).read(actor, data['swap_token'])
                if swap['state'] != 'sent' or swap['song']['id'] != track_id:
                    raise web.HTTPForbidden(text='Refresh this song first.')
            except CardError:
                raise web.HTTPForbidden(text='Refresh this song first.') from None
        else:
            if not isinstance(data.get('token'), str):
                raise web.HTTPBadRequest(text='Choose a displayed song.')
            async with chat.database.sessions() as session:
                grant = await session.scalar(select(ChatControl).join(User).where(
                    ChatControl.token == data['token'], User.telegram_user_id == actor,
                    ChatControl.expires_at > utc_now()))
                if grant is None or grant.payload.get('kind') != 'miniapp' or track_id not in grant.payload.get('tracks', []):
                    raise web.HTTPForbidden(text='Refresh this song first.')
        marker = after or utc_now()
        async with chat.database.sessions() as session:
            conditions = [User.telegram_user_id == actor, FetchJob.track_id == track_id]
            active = AudioRequest.state.in_(['pending', 'choice', 'sending'])
            if request_id is not None:
                conditions.append(AudioRequest.id == request_id)
            else:
                conditions.append(or_(AudioRequest.created_at >= marker, active) if after else active)
            row = await session.scalar(select(AudioRequest).join(User).join(FetchJob, AudioRequest.job_id == FetchJob.id)
                                       .where(*conditions).order_by(AudioRequest.created_at.desc(), AudioRequest.id.desc()).limit(1))
            state = row.state if row else 'waiting'
            if state == 'done' and row.message_id is None:
                state = 'uncertain'
            if state not in {'waiting', 'pending', 'choice', 'sending', 'done', 'failed', 'cancelled', 'uncertain'}:
                state = 'uncertain'
        return web.json_response(dict(after=marker.isoformat(), state=state, request_id=row.id if row else None))
    app.router.add_post('/api/delivery-status', status)
