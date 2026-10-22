import hashlib
import hmac
import json
from urllib.parse import urlencode
from unittest import TestCase
from unittest.mock import AsyncMock
from types import SimpleNamespace

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from sqlalchemy import select

from music_bot.chat_service import ChatService
from music_bot.miniapp import create_app, validate_init_data
from music_bot.models import Rating, Track, User, PlaylistChannel, ChannelConnectionCode, utc_now
from music_bot.miniapp import track_json
from music_bot.chat_ui import lil_bro_url
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
    async def test_explicit_batch_returns_up_to_five_with_one_provider_call(self):
        async with self.database.write() as session:
            rows=[Track(artist='Fixture',title=f'Buffered {i}',metadata_source='fixture') for i in range(6)]
            session.add_all(rows);await session.flush();ids=[row.id for row in rows]
        self.chat.recommendations.recommend_for_user.return_value=SimpleNamespace(status='ok',recommendations=[SimpleNamespace(track_id=value,artist='Fixture',title='Song',artwork_url=None,reason='Similar') for value in ids])
        response=await self.client.post('/api/recommendations',json={'replace':True,'batch':True},headers={'X-Telegram-Init-Data':signed()})
        self.assertEqual(response.status,200);result=await response.json();self.assertEqual(len(result['tracks']),5)
        self.chat.recommendations.recommend_for_user.assert_awaited_once_with(123,limit=20)
        for value in [ids[0],ids[4]]:
            self.assertEqual((await self.client.post('/api/rate',json={'token':result['token'],'track_id':value,'value':'neutral'},headers={'X-Telegram-Init-Data':signed()})).status,200)
        for payload in [{'batch':True},{'replace':True,'batch':'yes'}]:
            self.assertEqual((await self.client.post('/api/recommendations',json=payload,headers={'X-Telegram-Init-Data':signed()})).status,400)

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.chat = ChatService(self.database, AsyncMock())
        async def queued(user, limit=5, *, feed=False):
            return await self.chat.recommendations.recommend_for_user(user, limit=limit)
        self.chat.recommendations.queue.reserve.side_effect = queued
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

    async def test_preferences_are_user_scoped_and_validate_language(self):
        headers = {'X-Telegram-Init-Data': signed()}
        response = await self.client.post('/api/preferences/update', json={'language': 'fa', 'ui_guide_done': True}, headers=headers)
        self.assertEqual(response.status, 200)
        self.assertEqual((await response.json())['language'], 'fa')
        response = await self.client.get('/api/preferences', headers={'X-Telegram-Init-Data': signed(456)})
        self.assertEqual((await response.json())['language'], 'en')
        for payload in [{'language': 'xx'}, {'language': ['fa']}, {'user_id': 456, 'language': 'de'}, {'ui_guide_done': False}]:
            response = await self.client.post('/api/preferences/update', json=payload, headers=headers)
            self.assertEqual(response.status, 400)

    async def test_replacement_excludes_visible_songs_and_grants_only_replacement(self):
        async with self.database.write() as session:
            next_track = Track(artist='Another', title='Next song', metadata_source='lastfm')
            session.add(next_track)
            await session.flush()
            next_id = next_track.id
        rows = [SimpleNamespace(track_id=value, title='Song', artist='Artist', artwork_url=None, reason='Similar')
                for value in [self.track_id, next_id]]
        self.chat.recommendations.recommend_for_user.return_value = SimpleNamespace(recommendations=rows, status='ok')
        headers = {'X-Telegram-Init-Data': signed()}
        response = await self.client.post('/api/recommendations', json={'replace': True, 'exclude': [self.track_id]}, headers=headers)
        self.assertEqual(response.status, 200)
        result = await response.json()
        self.assertEqual([song['id'] for song in result['tracks']], [next_id])
        self.chat.recommendations.recommend_for_user.assert_awaited_once_with(123, limit=20)
        response = await self.client.post('/api/rate', json={'token': result['token'], 'track_id': self.track_id, 'value': 'like'}, headers=headers)
        self.assertEqual(response.status, 403)
        for payload in [{'replace': 'yes'}, {'exclude': [True]}, {'exclude': list(range(1, 23))}]:
            response = await self.client.post('/api/recommendations', json=payload, headers=headers)
            self.assertEqual(response.status, 400)
        old = await self.chat.create_control(123, tracks=[self.track_id], kind='miniapp')
        request = {'replace': True, 'exclude': [self.track_id], 'current': [{'id': self.track_id, 'token': old}]}
        response = await self.client.post('/api/recommendations', json=request, headers={'X-Telegram-Init-Data': signed(456)})
        self.assertEqual(response.status, 403)
        response = await self.client.post('/api/recommendations', json=request, headers=headers)
        renewed = (await response.json())['token']
        response = await self.client.post('/api/rate', json={'token': renewed, 'track_id': self.track_id, 'value': 'like'}, headers=headers)
        self.assertEqual(response.status, 200)

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
        for value in [[], {'query': 'h'}, {'query': '/start'}, {'query': 5}]:
            response = await self.client.post('/api/search', json=value,
                                              headers={'X-Telegram-Init-Data': signed()})
            self.assertEqual(response.status, 400)

    async def test_listen_uses_existing_message_link(self):
        async with self.database.sessions() as session:
            track = await session.get(Track, self.track_id)
            self.assertEqual(track_json(track)['listen_url'], lil_bro_url(track.display_artist or track.artist, track.display_title or track.title))

    async def test_similar_requires_owned_displayed_song_without_rating(self):
        grant = await self.chat.create_control(123, tracks=[self.track_id], kind='miniapp')
        payload = dict(token=grant, track_id=self.track_id)
        self.chat.recommendations.recommend_similar_to_track.return_value = type('Result', (), {'recommendations': [], 'status': 'no_candidates'})()
        for user, track, status in [(456, self.track_id, 403), (123, 999, 403), (123, self.track_id, 200)]:
            response = await self.client.post('/api/similar', json={**payload, 'track_id': track},
                                             headers={'X-Telegram-Init-Data': signed(user)})
            self.assertEqual(response.status, status)
        self.chat.recommendations.recommend_similar_to_track.assert_awaited_once_with(123, self.track_id)
        async with self.database.sessions() as session:
            self.assertIsNone(await session.scalar(select(Rating.value)))

    async def test_channels_owned_listing_disconnect_and_connection_code(self):
        async with self.database.write() as session:
            user = await session.scalar(select(User).where(User.telegram_user_id == 123))
            channel = PlaylistChannel(user_id=user.id, telegram_chat_id=-100123, title='My playlist',
                                      status='connected', connected_at=utc_now(), after_message_id=1)
            session.add(channel)
            await session.flush()
            channel_id = channel.id
        headers = {'X-Telegram-Init-Data': signed()}
        response = await self.client.get('/api/channels', headers=headers)
        self.assertEqual((await response.json())['channels'][0]['title'], 'My playlist')
        response = await self.client.get('/api/channels', headers={'X-Telegram-Init-Data': signed(456)})
        self.assertEqual((await response.json())['channels'], [])
        payload = dict(channel_id=channel_id, remove_signals=False)
        response = await self.client.post('/api/channels/disconnect', json=payload,
                                         headers={'X-Telegram-Init-Data': signed(456)})
        self.assertEqual(response.status, 409)
        response = await self.client.post('/api/channels/disconnect', json={**payload, 'remove_signals': 'false'}, headers=headers)
        self.assertEqual(response.status, 400)
        response = await self.client.post('/api/channels/disconnect', json=payload, headers=headers)
        self.assertEqual(response.status, 200)
        response = await self.client.post('/api/channels/connect', json={}, headers=headers)
        code = (await response.json())['code']
        self.assertRegex(code, r'^PL-[a-f0-9]{48}$')
        async with self.database.sessions() as session:
            self.assertEqual((await session.get(PlaylistChannel, channel_id)).status, 'disconnected')
            pending = await session.scalar(select(ChannelConnectionCode))
            self.assertNotEqual(pending.code_hash, code)
