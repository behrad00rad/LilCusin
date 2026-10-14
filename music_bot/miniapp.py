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
from .chat_ui import safe_url, lil_bro_url
from .channels import ChannelService
from .preferences import preferences, LANGUAGES
from .i18n import language
from .models import ChatControl, Track, User, utc_now
from .artwork import ArtworkLoader
from .channel_api import register_channel_api
from .providers.common import ProviderError
from .submissions import Submitter, parse_song, InvalidSubmission
from .workflow import RATINGS, save_rating, FlowError

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
                artwork=safe_url(track.artwork_url, artwork=True), reason=reason,
                listen_url=lil_bro_url(getattr(track, 'display_artist', None) or track.artist,
                                       getattr(track, 'display_title', None) or track.title))


def create_app(token, chat, workflow):
    # Limit simultaneous provider work; SQLite writes already serialize.
    capacity = asyncio.Semaphore(4)
    channels = ChannelService(chat.database, workflow)
    artwork = ArtworkLoader(chat.database, workflow.providers)

    @web.middleware
    async def security(request, handler):
        try:
            if request.path.startswith('/api/'):
                user = validate_init_data(request.headers.get('X-Telegram-Init-Data', ''), token)
                request['user'] = user
                await chat.ensure_user(Submitter(user['id'], user.get('username'),
                                                user.get('first_name'), user.get('language_code')))
                request['preferences'] = await preferences(chat.database, user['id'], user.get('language_code'))
                locale_context = language.set(request['preferences']['language'])
                try:
                    response = await handler(request)
                finally:
                    language.reset(locale_context)
            else:
                response = await handler(request)
        except web.HTTPException as error:
            response = web.json_response({'error': error.text}, status=error.status) if request.path.startswith('/api/') else error
        except (ProviderError, TimeoutError):
            response = web.json_response({'error': 'Music search is unavailable. Please try again.'}, status=503)
        except FlowError:
            response = web.json_response({'error': 'Refresh this page and try again.'}, status=409)
        except Exception:
            # Never echo request data, provider errors or secrets.
            response = web.json_response({'error': 'Something went wrong. Please try again.'}, status=500)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['X-Robots-Tag'] = 'noindex, nofollow'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' https://telegram.org; style-src 'self'; img-src 'self' https://lastfm.freetls.fastly.net https://lastfm-img.freetls.fastly.net https://lastfm-img2.akamaized.net; connect-src 'self'; object-src 'none'; base-uri 'none'"
        return response

    async def body(request):
        try:
            value = await request.json()
            if not isinstance(value, dict):
                raise ValueError
            return value
        except (ValueError, TypeError):
            raise web.HTTPBadRequest(text='Invalid request.') from None

    async def taste_setup(request):
        from .taste_setup import read_setup,save_setup
        if request.method=='POST':
            data=await body(request)
            if any(key not in {'style','mood','artist'} for key in data):raise web.HTTPBadRequest(text='Invalid taste setup.')
            try:await save_setup(chat.database,request['user']['id'],**data)
            except (ValueError,TypeError) as error:raise web.HTTPBadRequest(text='Choose a style, mood, and artist name.') from None
        return web.json_response(await read_setup(chat.database,request['user']['id']))

    async def bundle(user_id, tracks, status='ok', visible=(), expected_token=None, links=(), extra=None):
        grant = await chat.create_control(user_id, tracks=list(dict.fromkeys([t['id'] for t in tracks] + list(visible))), kind='miniapp', expected_token=expected_token, links=links)
        for track in tracks:
            if not track.get('artwork'):artwork.schedule(track['id'])
        return web.json_response(dict(tracks=tracks, token=grant, status=status, **(extra or {})))

    async def cover_art(request):
        data=await body(request)
        ids,token=data.get('track_ids'),data.get('token')
        if (not isinstance(ids,list) or not 1<=len(ids)<=10 or any(type(i) is not int or i<=0 for i in ids) or not isinstance(token,str)):
            raise web.HTTPBadRequest(text='Choose displayed songs.')
        async with chat.database.sessions() as session:
            grant=await session.scalar(select(ChatControl).join(User).where(ChatControl.token==token,
                User.telegram_user_id==request['user']['id'],ChatControl.expires_at>utc_now()))
            if grant is None or grant.payload.get('kind')!='miniapp' or any(i not in grant.payload.get('tracks',[]) for i in ids):
                raise web.HTTPForbidden(text='Refresh this song list first.')
            rows=(await session.scalars(select(Track).where(Track.id.in_(ids)))).all()
            result={str(row.id):safe_url(row.artwork_url,artwork=True) for row in rows}
        for track_id in ids:
            if not result.get(str(track_id)):artwork.schedule(track_id)
        return web.json_response({'artwork':result})

    async def recommendations(request):
        data = await body(request)
        replace = data.get('replace', False)
        exclude = data.get('exclude', [])
        current = data.get('current', [])
        if (type(replace) is not bool or not isinstance(exclude, list) or len(exclude) > 20
                or any(type(value) is not int or value <= 0 for value in exclude)
                or not isinstance(current, list) or len(current) > 20 or (current and not replace)
                or any(not isinstance(item, dict) or type(item.get('id')) is not int
                       or not isinstance(item.get('token'), str) or item['id'] not in exclude for item in current)):
            raise web.HTTPBadRequest(text='Invalid song list.')
        # Renew only the user's still-visible, previously granted cards. This
        # keeps long rating sessions usable without extending arbitrary IDs.
        visible = []
        expected_token = None
        if current:
            async with chat.database.sessions() as session:
                for item in current:
                    grant = await session.scalar(select(ChatControl).join(User).where(
                        ChatControl.token == item['token'], User.telegram_user_id == request['user']['id'],
                        ChatControl.expires_at > utc_now()))
                    if grant is None or grant.payload.get('kind') != 'miniapp' or item['id'] not in grant.payload.get('tracks', []):
                        raise web.HTTPForbidden(text='Refresh this song list first.')
                    visible.append(item['id'])
                    expected_token = grant.token
        async with capacity:
            result = await chat.recommendations.recommend_for_user(request['user']['id'], limit=20 if replace else 5)
        rows = [track_json(row, row.reason) for row in result.recommendations if row.track_id not in exclude]
        return await bundle(request['user']['id'], rows[:1] if replace else rows, result.status, visible, expected_token)

    async def search(request):
        data = await body(request)
        query = data.get('query')
        if not isinstance(query, str) or not 3 <= len(query) <= 240:
            raise web.HTTPBadRequest(text='Enter a song title or Artist - Song title (up to 240 characters).')
        try:
            artist, title = parse_song(query)
        except InvalidSubmission:
            artist, title = None, query.strip()
            if not title or title.startswith('/'):
                raise web.HTTPBadRequest(text='Enter a song title.') from None
        async with capacity:
            candidates, failed = await (workflow.search(artist, title) if artist else workflow.search_title(title))
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

    async def similar(request):
        data = await body(request)
        if type(data.get('track_id')) is not int or not isinstance(data.get('token'), str):
            raise web.HTTPBadRequest(text='Choose a song first.')
        async with chat.database.sessions() as session:
            grant = await session.scalar(select(ChatControl).join(User).where(
                ChatControl.token == data['token'], User.telegram_user_id == request['user']['id'],
                ChatControl.expires_at > utc_now()))
            if grant is None or grant.payload.get('kind') != 'miniapp' or data['track_id'] not in grant.payload.get('tracks', []):
                raise web.HTTPForbidden(text='Refresh this song list first.')
        async with capacity:
            result = await chat.recommendations.recommend_similar_to_track(request['user']['id'], data['track_id'])
        return await bundle(request['user']['id'], [track_json(row, row.reason) for row in result.recommendations], result.status)

    async def channel_list(request):
        rows = await channels.listing(request['user']['id'])
        return web.json_response({'channels': [dict(id=row.id, title=row.title or 'Playlist channel',
            status=row.status, learned=learned, review=review) for row, learned, review in rows]})

    async def channel_connect(request):
        code = await channels.new_code(request['user']['id'])
        return web.json_response({'code': code, 'expires_in': 600})

    async def channel_disconnect(request):
        data = await body(request)
        if type(data.get('channel_id')) is not int or type(data.get('remove_signals')) is not bool:
            raise web.HTTPBadRequest(text='Choose whether to keep the channel’s learned taste.')
        await channels.disconnect(request['user']['id'], data['channel_id'], data['remove_signals'])
        return web.json_response({'saved': True})

    async def get_preferences(request):
        return web.json_response(request['preferences'])

    async def set_preferences(request):
        data = await body(request)
        if (not data or set(data) - {'language', 'ui_guide_done'}
                or ('language' in data and (not isinstance(data['language'], str) or data['language'] not in LANGUAGES))
                or ('ui_guide_done' in data and data['ui_guide_done'] is not True)):
            raise web.HTTPBadRequest(text='Invalid preferences.')
        result = await preferences(chat.database, request['user']['id'], request['user'].get('language_code'),
                                   language=data.get('language'), ui_done=data.get('ui_guide_done'))
        return web.json_response(result)

    async def asset(request):
        name = request.match_info.get('name', 'index.html')
        if name not in {'index.html', 'app.js', 'style.css', 'locales.json', 'bot-logo.jpg', 'vazirmatn.woff2', 'Vazirmatn-OFL.txt'}:
            raise web.HTTPNotFound()
        return web.FileResponse(ASSETS / name)

    app = web.Application(middlewares=[security], client_max_size=16384)
    app.on_cleanup.append(lambda app: artwork.close())
    app.router.add_get('/', asset)
    app.router.add_get('/{name:index.html|app.js|style.css|locales.json|bot-logo.jpg|vazirmatn.woff2|Vazirmatn-OFL.txt}', asset)
    app.router.add_get('/api/profile', profile)
    app.router.add_get('/api/preferences', get_preferences)
    app.router.add_post('/api/preferences/update', set_preferences)
    app.router.add_post('/api/recommendations', recommendations)
    app.router.add_post('/api/search', search)
    app.router.add_get('/api/taste-setup', taste_setup)
    app.router.add_post('/api/taste-setup/update', taste_setup)
    app.router.add_post('/api/rate', rate)
    app.router.add_post('/api/similar', similar)
    app.router.add_post('/api/artwork', cover_art)
    app.router.add_get('/api/channels', channel_list)
    app.router.add_post('/api/channels/connect', channel_connect)
    app.router.add_post('/api/channels/disconnect', channel_disconnect)
    register_channel_api(app,chat,workflow,body,bundle,track_json,capacity)
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
