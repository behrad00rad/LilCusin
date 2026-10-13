import hashlib
import hmac
import json
from urllib.parse import urlencode
from unittest import TestCase
from unittest.mock import AsyncMock

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from sqlalchemy import select

from music_bot.chat_service import ChatService
from music_bot.miniapp import create_app, validate_init_data
from music_bot.models import Rating, Track
from music_bot.submissions import Submitter
from .support import ServiceTestCase

TOKEN = '123456:test-token'


def signed(user_id=123, date=None):
    import time
    fields = {'auth_date': str(int(time.time()) if date is None else date),
              'user': json.dumps({'id': user_id, 'first_name': 'Test'})}
    secret = hmac.digest(b'WebAppData', TOKEN.encode(), 'sha256')
    fields['hash'] = hmac.new(secret, '\n'.join(f'{k}={v}' for k, v in sorted(fields.items())).encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


class AuthenticationTests(TestCase):
    def test_signed_user(self):
        self.assertEqual(validate_init_data(signed(date=1000), TOKEN, now=1001)['id'], 123)

    def test_tampered_expired_future_and_duplicate_data(self):
        for raw in [signed(date=1000).replace('Test', 'Other'), signed(date=-3000),
                    signed(date=10000), signed(date=1000) + '&auth_date=1000', '']:
            with self.subTest(raw=raw), self.assertRaises(web.HTTPUnauthorized):
                validate_init_data(raw, TOKEN, now=1001)


class MiniAppTests(ServiceTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.chat = ChatService(self.database, AsyncMock())
        await self.chat.ensure_user(Submitter(123))
        async with self.database.write() as session:
            track = Track(artist='Test', title='Song', metadata_source='lastfm')
            session.add(track)
            await session.flush()
            self.track_id = track.id
        self.client = TestClient(TestServer(create_app(TOKEN, self.chat, self.workflow)))
        await self.client.start_server()

    async def asyncTearDown(self):
        await self.client.close()
        await super().asyncTearDown()

    async def test_api_requires_auth_but_preview_is_public(self):
        response = await self.client.get('/api/profile')
        self.assertEqual(response.status, 401)
        self.assertEqual((await self.client.get('/')).status, 200)

    async def test_rating_owner_and_display_grant(self):
        grant = await self.chat.create_control(123, tracks=[self.track_id], kind='miniapp')
        payload = dict(token=grant, track_id=self.track_id, value='love')
        response = await self.client.post('/api/rate', json=payload,
                                          headers={'X-Telegram-Init-Data': signed(456)})
        self.assertEqual(response.status, 403)
        response = await self.client.post('/api/rate', json={**payload, 'track_id': 999},
                                          headers={'X-Telegram-Init-Data': signed()})
        self.assertEqual(response.status, 403)
        response = await self.client.post('/api/rate', json=payload,
                                          headers={'X-Telegram-Init-Data': signed()})
        self.assertEqual(response.status, 200)
        async with self.database.sessions() as session:
            self.assertEqual(await session.scalar(select(Rating.value)), 'love')

    async def test_bad_json_and_search_query(self):
        for value in [[], {'query': 'no separator'}, {'query': 5}]:
            response = await self.client.post('/api/search', json=value,
                                              headers={'X-Telegram-Init-Data': signed()})
            self.assertEqual(response.status, 400)
