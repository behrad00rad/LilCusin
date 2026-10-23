"""Routes inherit the Mini App's initData authentication and no-store headers."""
from aiohttp import web
from .guess_service import GuessError, GuessService


def register_guess_api(app, chat, body, *, bot_username=None):
    service = GuessService(chat.database)

    async def run(operation):
        try:
            return web.json_response(await operation())
        except GuessError as error:
            return web.json_response({'error': str(error), **error.details}, status=error.status)

    async def status(request):
        if list(request.query) != ['friend_id'] or len(request.query.getall('friend_id')) != 1:
            raise web.HTTPBadRequest(text='guess_invalid')
        async def operation():
            result = await service.status(request['user']['id'], request.query['friend_id'])
            if result.get('permitted'):
                from sqlalchemy import select
                from .models import User
                from .comparison_invitations import ComparisonInvitation
                async with chat.database.sessions() as session:
                    actor = await session.scalar(select(User.id).where(User.telegram_user_id == request['user']['id']))
                    friend = await session.get(ComparisonInvitation, request.query['friend_id'])
                    mine, theirs = (friend.sender_snapshot, friend.recipient_snapshot) if friend.sender_id == actor else (friend.recipient_snapshot, friend.sender_snapshot)
                    result['your_name'] = str(mine.get('nickname') or '')[:40]
                    result['target_name'] = str(theirs.get('nickname') or '')[:40]
                import re
                if bot_username and re.fullmatch(r'[A-Za-z0-9_]{5,32}', bot_username):
                    result['share_url'] = 'https://t.me/' + bot_username
                    result['challenge_url'] = result['share_url'] + '?startapp=guess_' + request.query['friend_id']
            return result
        return await run(operation)

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
