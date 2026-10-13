"""Same-origin Telegram Mini App API. No browser-supplied user IDs are trusted."""

import asyncio
import hashlib
import hmac
import json
import time
from pathlib import Path
from urllib.parse import parse_qsl

from aiohttp import web
from sqlalchemy import select

from .catalog import canonical_track, IdentityConflict
from .chat_ui import safe_url
from .models import ChatControl, User, utc_now
from .providers.common import ProviderError
from .submissions import Submitter, parse_song, InvalidSubmission
from .workflow import RATINGS, save_rating

ASSETS = Path(__file__).with_name('web')


def validate_init_data(raw, bot_token, *, now=None):
    try:
        pairs = parse_qsl(raw, strict_parsing=True, max_num_fields=30)
        fields = dict(pairs)
        if not raw or len(raw) > 12000 or len(fields) != len(pairs):
            raise ValueError
        signature = fields.pop('hash')
        secret = hmac.digest(b'WebAppData', bot_token.encode(), 'sha256')
        check = '\n'.join(f'{key}={value}' for key, value in sorted(fields.items()))
        expected = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError
        age = (time.time() if now is None else now) - int(fields['auth_date'])
        if not -30 <= age <= 3600:
            raise ValueError
        user = json.loads(fields['user'])
        if type(user['id']) is not int or user['id'] <= 0:
            raise ValueError
        return user
    except (ValueError, KeyError, TypeError):
        raise web.HTTPUnauthorized(text='Open Lil Cusin again from Telegram.') from None


def track_json(track, reason=None):
    return dict(id=track.track_id if hasattr(track, 'track_id') else track.id,
                title=getattr(track, 'display_title', None) or track.title,
                artist=getattr(track, 'display_artist', None) or track.artist,
                artwork=safe_url(track.artwork_url, artwork=True), reason=reason)


def create_app(token, chat, workflow):
    # Limit simultaneous provider work; SQLite writes already serialize.
    capacity = asyncio.Semaphore(4)

    @web.middleware
    async def security(request, handler):
        try:
            if request.path.startswith('/api/'):
                user = validate_init_data(request.headers.get('X-Telegram-Init-Data', ''), token)
                request['user'] = user
                await chat.ensure_user(Submitter(user['id'], user.get('username'),
                                                user.get('first_name'), user.get('language_code')))
            response = await handler(request)
        except web.HTTPException as error:
            response = web.json_response({'error': error.text}, status=error.status) if request.path.startswith('/api/') else error
        except (ProviderError, TimeoutError):
            response = web.json_response({'error': 'Music search is unavailable. Please try again.'}, status=503)
        except Exception:
            # Never echo request data, provider errors or secrets.
            response = web.json_response({'error': 'Something went wrong. Please try again.'}, status=500)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['X-Robots-Tag'] = 'noindex, nofollow'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' https://telegram.org; style-src 'self'; img-src 'self' https://lastfm.freetls.fastly.net https://lastfm-img2.akamaized.net; connect-src 'self'; object-src 'none'; base-uri 'none'"
        return response

    async def body(request):
        try:
            value = await request.json()
            if not isinstance(value, dict):
                raise ValueError
            return value
        except (ValueError, TypeError):
            raise web.HTTPBadRequest(text='Invalid request.') from None

    async def bundle(user_id, tracks, status='ok'):
        grant = await chat.create_control(user_id, tracks=[t['id'] for t in tracks], kind='miniapp')
        return web.json_response(dict(tracks=tracks, token=grant, status=status))

    async def recommendations(request):
        async with capacity:
            result = await chat.recommendations.recommend_for_user(request['user']['id'])
        return await bundle(request['user']['id'], [track_json(row, row.reason) for row in result.recommendations], result.status)

    async def search(request):
        data = await body(request)
        query = data.get('query')
        if not isinstance(query, str) or not 3 <= len(query) <= 240:
            raise web.HTTPBadRequest(text='Enter Artist - Song title (up to 240 characters).')
        try:
            artist, title = parse_song(query)
        except InvalidSubmission:
            raise web.HTTPBadRequest(text='Use Artist - Song title.') from None
        async with capacity:
            candidates, failed = await workflow.search(artist, title)
        if failed and not candidates:
            raise web.HTTPServiceUnavailable(text='Music search is unavailable. Try again shortly.')
        tracks = []
        async with chat.database.write() as session:
            for candidate in candidates:
                try:
                    tracks.append(track_json(await canonical_track(session, candidate)))
                except IdentityConflict:
                    continue
        return await bundle(request['user']['id'], tracks)

    async def rate(request):
        data = await body(request)
        if (type(data.get('track_id')) is not int or not isinstance(data.get('value'), str)
                or data['value'] not in RATINGS or not isinstance(data.get('token'), str)):
            raise web.HTTPBadRequest(text='Choose a song and a rating.')
        async with chat.database.write() as session:
            grant = await session.scalar(select(ChatControl).join(User).where(
                ChatControl.token == data['token'], User.telegram_user_id == request['user']['id'],
                ChatControl.expires_at > utc_now()))
            if grant is None or grant.payload.get('kind') != 'miniapp' or data['track_id'] not in grant.payload.get('tracks', []):
                raise web.HTTPForbidden(text='Refresh this song list before rating.')
            await save_rating(session, grant.user_id, data['track_id'], data['value'])
        return web.json_response({'saved': True})

    async def profile(request):
        summary = await chat.taste_summary(request['user']['id'])
        return web.json_response(dict(name=request['user'].get('first_name', 'friend'),
            counts=summary['counts'], songs=summary['songs'], channels=summary['channels'],
            artists=[row[0] or row[1] for row in summary['artists']],
            tags=[row[0] or row[1] for row in summary['tags']]))

    async def asset(request):
        name = request.match_info.get('name', 'index.html')
        if name not in {'index.html', 'app.js', 'style.css'}:
            raise web.HTTPNotFound()
        return web.FileResponse(ASSETS / name)

    app = web.Application(middlewares=[security], client_max_size=16384)
    app.router.add_get('/', asset)
    app.router.add_get('/{name:index.html|app.js|style.css}', asset)
    app.router.add_get('/api/profile', profile)
    app.router.add_post('/api/recommendations', recommendations)
    app.router.add_post('/api/search', search)
    app.router.add_post('/api/rate', rate)
    return app


async def start_server(token, chat, workflow, host, port):
    runner = web.AppRunner(create_app(token, chat, workflow), access_log=None)
    await runner.setup()
    try:
        await web.TCPSite(runner, host, port).start()
    except BaseException:
        await runner.cleanup()
        raise
    return runner
