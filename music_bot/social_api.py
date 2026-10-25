"""Authenticated social endpoints. Actor identity always comes from initData."""
from aiohttp import web
from .social import Social
from .taste_cards import CardError


def register_social_api(app, chat, body, *, bot_username=None):
    service=Social(chat.database)
    async def run(request, operation):
        try: return web.json_response(await operation())
        except CardError as error:
            code=str(error)
            return web.json_response({'error':code},status=429 if code=='social_limit' else 400 if code=='social_invalid' else 404)

    async def data(request, required, optional=()):
        result=await body(request)
        if not set(required)<=set(result) or set(result)-set(required)-set(optional):
            raise web.HTTPBadRequest(text='social_invalid')
        return result

    async def home(request):
        async def operation():
            swaps=await service.inbox(request['user']['id'])
            async with chat.database.sessions() as session:
                from sqlalchemy import select, func
                from .social import SavedSong, user_id
                from .models import Track
                actor=await user_id(session,request['user']['id'])
                rows=(await session.scalars(select(Track).join(SavedSong).where(SavedSong.user_id==actor).order_by(SavedSong.created_at.desc()).limit(50))).all()
                saved_count=await session.scalar(select(func.count()).select_from(SavedSong).where(SavedSong.user_id==actor))
                saves=[dict(id=row.id,artist=row.display_artist or row.artist,title=row.display_title or row.title) for row in rows]
            from .social_activity import activity
            updates=await activity(chat.database,request['user']['id'])
            settings=await service.settings(request['user']['id'])
            return dict(swaps=swaps,saves=saves,saved_count=saved_count,activity=updates,notifications=settings['notifications'])
        return await run(request,operation)

    async def thread(request):
        fields=await data(request,['invitation'],['before'])
        return await run(request,lambda:service.thread(request['user']['id'],**fields))

    async def compare(request):
        fields=await data(request,['token'])
        return await run(request,lambda:service.compare(request['user']['id'],fields['token']))

    async def choices(request):
        fields=await data(request,['invitation'],['reply_to'])
        async def operation(): return dict(songs=await service.choices(request['user']['id'],**fields))
        return await run(request,operation)

    async def draft(request):
        fields=await data(request,['invitation','track_id'],['reply_to','source_token'])
        return await run(request,lambda:service.draft(request['user']['id'],**fields))

    async def act(request):
        fields=await data(request,['token','action'],['note_text'])
        async def operation():
            result=await service.act(request['user']['id'],**fields)
            await service.flush_notices(getattr(chat,'social_bot',None))
            return result
        return await run(request,operation)

    async def settings(request):
        fields=await data(request,['notifications']) if request.method=='POST' else {}
        return await run(request,lambda:service.settings(request['user']['id'],**fields))

    async def relationship(request):
        fields=await data(request,['invitation','action'],['reason','swap_token','details'])
        return await run(request,lambda:service.relationship(request['user']['id'],**fields))

    async def get_song(request):
        fields=await data(request,['token'])
        async def operation():
            swap=await service.read(request['user']['id'],fields['token'])
            if swap['state']!='sent': raise CardError('social_unavailable')
            if not bot_username: raise CardError('social_unavailable')
            # The bot revalidates this swap when opening the link, including block/revocation.
            return dict(url=f"https://t.me/{bot_username}?start=swap_{swap['token']}")
        return await run(request,operation)

    async def unsave(request):
        fields=await data(request,['track_id'])
        return await run(request,lambda:service.remove_save(request['user']['id'],fields['track_id']))

    app.router.add_get('/api/social',home)
    app.router.add_post('/api/social/thread',thread)
    app.router.add_post('/api/social/compare',compare)
    app.router.add_post('/api/social/choices',choices)
    app.router.add_post('/api/social/draft',draft)
    app.router.add_post('/api/social/action',act)
    app.router.add_get('/api/social/settings',settings)
    app.router.add_post('/api/social/settings/update',settings)
    app.router.add_post('/api/social/relationship',relationship)
    app.router.add_post('/api/social/get-song',get_song)
    app.router.add_post('/api/social/unsave',unsave)
