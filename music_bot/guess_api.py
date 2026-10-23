"""Routes inherit the Mini App's initData authentication and no-store headers."""
from aiohttp import web
from .guess_service import GuessError, GuessService


def register_guess_api(app, chat, body):
    service = GuessService(chat.database)

    async def run(operation):
        try:
            return web.json_response(await operation())
        except GuessError as error:
            return web.json_response({'error': str(error), **error.details}, status=error.status)

    async def status(request):
        if list(request.query) != ['friend_id'] or len(request.query.getall('friend_id')) != 1:
            raise web.HTTPBadRequest(text='guess_invalid')
        return await run(lambda: service.status(request['user']['id'], request.query['friend_id']))

    async def start(request):
        data = await body(request)
        if set(data) != {'friend_id'}:
            raise web.HTTPBadRequest(text='guess_invalid')
        return await run(lambda: service.start(request['user']['id'], data['friend_id']))

    async def answer(request):
        data = await body(request)
        if set(data) != {'idx', 'recording_id'}:
            raise web.HTTPBadRequest(text='guess_invalid')
        return await run(lambda: service.answer(request['user']['id'], request.match_info['id'], **data))

    app.router.add_get('/api/guess/status', status)
    app.router.add_post('/api/guess/start', start)
    app.router.add_post('/api/guess/{id}/answer', answer)
