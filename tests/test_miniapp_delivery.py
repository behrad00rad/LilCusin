from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from aiohttp.test_utils import TestClient, TestServer
from aiogram import Bot
from aiogram.types import Update

from music_bot.chat_service import ChatService
from music_bot.miniapp import create_app
from music_bot.models import ChatControl, Track, utc_now
from music_bot.submissions import Submitter
from .support import ServiceTestCase, dispatcher
from .test_miniapp import TOKEN, signed


class MiniAppDeliveryTests(ServiceTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.chat = ChatService(self.database, AsyncMock())
        await self.chat.ensure_user(Submitter(123))
        await self.chat.ensure_user(Submitter(456))
        async with self.database.write() as session:
            row = Track(artist='Artist', title='Song', metadata_source='fixture')
            session.add(row)
            await session.flush()
            self.track_id = row.id
        self.bot = Bot(TOKEN)
        self.delivery = AsyncMock()

    async def asyncTearDown(self):
        await self.bot.session.close()
        await super().asyncTearDown()

    async def start(self, payload, user_id=123):
        update = Update.model_validate({'update_id': 1, 'message': {'message_id': 1, 'date': 1700000000,
            'chat': {'id': user_id, 'type': 'private'}, 'from': {'id': user_id, 'is_bot': False, 'first_name': 'Test'},
            'text': '/start ' + payload}})
        await dispatcher.feed_update(self.bot, update, chat_service=self.chat, get_song=self.delivery)

    async def test_api_song_link_enters_existing_delivery_for_selected_track(self):
        self.chat.recommendations.recommend_for_user.return_value = SimpleNamespace(
            recommendations=[SimpleNamespace(track_id=self.track_id, artist='Artist', title='Song', artwork_url=None, reason='Fixture')], status='ok')
        client = TestClient(TestServer(create_app(TOKEN, self.chat, self.workflow, bot_username='LilCusinTestBot')))
        await client.start_server()
        try:
            response = await client.post('/api/recommendations', json={}, headers={'X-Telegram-Init-Data': signed()})
            result = await response.json()
            url = result['tracks'][0]['get_song_url']
            self.assertEqual(url, f"https://t.me/LilCusinTestBot?start=get_{result['token']}_{self.track_id}")
            self.assertLessEqual(len(url.split('start=')[1]), 64)
            with patch('aiogram.types.Message.answer', new_callable=AsyncMock):
                await self.start(url.split('start=')[1])
            self.delivery.begin.assert_awaited_once()
            self.assertEqual(self.delivery.begin.call_args.args[1:], (123, self.track_id))
        finally:
            await client.close()

    async def test_foreign_forged_wrong_kind_and_ungranted_tracks_cannot_download(self):
        token = await self.chat.create_control(123, tracks=[self.track_id], kind='miniapp')
        other_kind = await self.chat.create_control(123, tracks=[self.track_id], kind='forget')
        with patch('aiogram.types.Message.answer', new_callable=AsyncMock):
            for payload, user_id in [(f'get_{token}_{self.track_id}',456), (f'get_{token}_999999',123),
                                     (f'get_{other_kind}_{self.track_id}',123), ('get_invalid',123)]:
                await self.start(payload, user_id)
        self.delivery.begin.assert_not_awaited()

    async def test_expired_links_fail_without_queuing_delivery(self):
        token = await self.chat.create_control(123, tracks=[self.track_id], kind='miniapp')
        async with self.database.write() as session:
            (await session.get(ChatControl, token)).expires_at = utc_now() - timedelta(seconds=1)
        with patch('aiogram.types.Message.answer', new_callable=AsyncMock) as answer:
            await self.start(f'get_{token}_{self.track_id}')
            self.assertIn('expired', answer.call_args.args[0])
        self.delivery.begin.assert_not_awaited()
