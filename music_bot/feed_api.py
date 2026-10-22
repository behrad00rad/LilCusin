"""Owner-bound browsing feedback; no public feed history or taste mutation."""
import re
from aiohttp import web
from sqlalchemy import select

from .feed_history import record_event
from .models import ChatControl, User, utc_now


def register_feed_api(app, chat, body):
    async def events(request):
        data = await body(request)
        rows = data.get('events')
        if set(data) != {'events'} or not isinstance(rows, list) or not 1 <= len(rows) <= 20:
            raise web.HTTPBadRequest(text='Invalid feed events.')
        async with chat.database.write() as session:
            actor = await session.scalar(select(User.id).where(User.telegram_user_id == request['user']['id']))
            for row in rows:
                if (not isinstance(row, dict) or set(row) - {'track_id', 'token', 'swap_token', 'event', 'event_id'}
                        or type(row.get('track_id')) is not int or row['track_id'] <= 0
                        or not isinstance(row.get('token', row.get('swap_token')), str)
                        or len(row.get('token', row.get('swap_token'))) > 100
                        or not isinstance(row.get('event'), str)
                        or row['event'] not in {'seen', 'skipped', 'not_now', 'hidden'}
                        or not isinstance(row.get('event_id'), str)
                        or not re.fullmatch(r'[a-zA-Z0-9_-]{8,64}', row['event_id'])):
                    raise web.HTTPBadRequest(text='Invalid feed event.')
                if 'swap_token' in row:
                    from .social import Social
                    from .taste_cards import CardError
                    try:
                        swap = await Social(chat.database)._swap(session, actor, row['swap_token'])
                        if swap.track_id != row['track_id']:
                            raise CardError('social_unavailable')
                    except CardError:
                        raise web.HTTPForbidden(text='Refresh this song list first.') from None
                else:
                    grant = await session.scalar(select(ChatControl).where(ChatControl.user_id == actor,
                        ChatControl.token == row['token'], ChatControl.expires_at > utc_now()))
                    if (grant is None or grant.payload.get('kind') != 'miniapp'
                            or row['track_id'] not in grant.payload.get('tracks', [])):
                        raise web.HTTPForbidden(text='Refresh this song list first.')
                await record_event(session, actor, row['track_id'], row['event'], row['event_id'])
        return web.json_response({'ok': True})
    app.router.add_post('/api/feed/events', events)

    async def eligible(request):
        """Filter only IDs already owned through current incoming exchanges."""
        from .feed_history import excluded_ids
        from .social import SongSwap
        from .taste_cards import CardError
        from .social import Social
        async with chat.database.sessions() as session:
            actor = await session.scalar(select(User.id).where(User.telegram_user_id == request['user']['id']))
            excluded = await excluded_ids(session, actor)
            swaps = list(await session.scalars(select(SongSwap).where(SongSwap.recipient_id == actor,
                SongSwap.state == 'sent', SongSwap.expires_at > utc_now()).limit(40)))
            tokens = []
            for swap in swaps:
                if swap.track_id in excluded:
                    continue
                try:
                    await Social(chat.database)._swap(session, actor, swap.token)
                    tokens.append(swap.token)
                except CardError:
                    pass
        return web.json_response({'tokens': tokens})
    app.router.add_get('/api/feed/swaps', eligible)
