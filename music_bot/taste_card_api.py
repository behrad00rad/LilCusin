"""Authenticated owner operations and deliberately shared card projections."""
from aiohttp import web
import asyncio
import base64
from .taste_cards import TasteCards, CardError
from .comparison_invitations import ComparisonInvitations


def register_taste_card_api(app, chat, body, *, bot_username=None):
    cards = TasteCards(chat.database)

    async def handle(request, operation):
        try:
            result = await operation()
            if result.get('share_token') and bot_username:
                result['share_url'] = f"https://t.me/{bot_username}?start=taste_{result['share_token']}"
            return web.json_response(result)
        except CardError as error:
            code = str(error)
            status = (404 if code in {'card_unavailable', 'invite_unavailable'} else
                      409 if code in {'card_conflict', 'invite_stale'} else
                      429 if code == 'invite_limit' else 403 if code == 'card_stale' else 400)
            return web.json_response({'error': code}, status=status)

    async def owner(request):
        return await handle(request, lambda: cards.owner(request['user']['id']))

    async def update(request):
        data = await body(request)
        return await handle(request, lambda: cards.update(request['user']['id'], data))

    async def sharing(request):
        data = await body(request)
        if set(data) != {'action', 'revision'}:
            raise web.HTTPBadRequest(text='card_invalid')
        return await handle(request, lambda: cards.sharing(request['user']['id'], data['action'], data['revision']))

    async def view(request):
        data = await body(request)
        if set(data) != {'token'}:
            raise web.HTTPBadRequest(text='card_invalid')
        return await handle(request, lambda: cards.view(data['token']))

    async def image(request):
        data = await body(request)
        if data:
            raise web.HTTPBadRequest(text='card_invalid')
        from .taste_card_image import portrait, small_preview
        from .i18n import language
        card = await cards.owner(request['user']['id'])
        preview = await portrait(card, language.get())
        preview = await asyncio.to_thread(small_preview, preview)
        return web.json_response({'image': 'data:image/jpeg;base64,'+base64.b64encode(preview).decode()})

    invites = ComparisonInvitations(chat.database)

    async def invitation_list(request):
        return web.json_response({'invitations': await invites.listing(request['user']['id'])})

    async def invitation_create(request):
        data = await body(request)
        if set(data) != {'card_token', 'sender_revision', 'recipient_revision'}:
            raise web.HTTPBadRequest(text='invite_invalid')
        return await handle(request, lambda: invites.create(request['user']['id'], **data))

    async def invitation_action(request):
        data = await body(request)
        if set(data) != {'token', 'action'}:
            raise web.HTTPBadRequest(text='invite_invalid')
        return await handle(request, lambda: invites.decide(request['user']['id'], data['token'], data['action']))

    app.router.add_get('/api/taste-card', owner)
    app.router.add_post('/api/taste-card/update', update)
    app.router.add_post('/api/taste-card/share', sharing)
    app.router.add_post('/api/taste-card/view', view)
    app.router.add_post('/api/taste-card/image', image)
    app.router.add_get('/api/comparison-invitations', invitation_list)
    app.router.add_post('/api/comparison-invitations/create', invitation_create)
    app.router.add_post('/api/comparison-invitations/decide', invitation_action)
