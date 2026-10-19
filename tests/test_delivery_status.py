from datetime import timedelta
from unittest.mock import AsyncMock, patch
from aiohttp.test_utils import TestClient, TestServer
from sqlalchemy import select, func
from music_bot.chat_service import ChatService
from music_bot.miniapp import create_app
from music_bot.models import Track, User, ChatControl, utc_now
from music_bot.fetch_models import FetchJob, AudioRequest
from music_bot.submissions import Submitter
from .support import ServiceTestCase
from .test_miniapp import TOKEN, signed


class DeliveryStatusTests(ServiceTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.chat = ChatService(self.database, AsyncMock())
        for actor in [123,456]: await self.chat.ensure_user(Submitter(actor))
        async with self.database.write() as session:
            track=Track(artist='Fixture',title='Song',metadata_source='fixture');session.add(track);await session.flush();self.track_id=track.id
            self.owner=await session.scalar(select(User.id).where(User.telegram_user_id==123))
            self.foreign=await session.scalar(select(User.id).where(User.telegram_user_id==456))
            session.add(FetchJob(id='job',track_id=self.track_id,key='fixture-job',state='ready'))
        self.token=await self.chat.create_control(123,tracks=[self.track_id],kind='miniapp')
        self.client=TestClient(TestServer(create_app(TOKEN,self.chat,self.workflow)))
        await self.client.start_server()

    async def asyncTearDown(self):
        await self.client.close()
        await super().asyncTearDown()

    async def call(self, extra=None, actor=123, source=None):
        return await self.client.post('/api/delivery-status',json={'track_id':self.track_id,**({'token':self.token} if source is None else source),**(extra or {})},headers={'X-Telegram-Init-Data':signed(actor)})

    async def add_request(self,state='pending',message=None,owner=None,old=False):
        async with self.database.write() as session:
            session.add(AudioRequest(id='request',user_id=owner or self.owner,job_id='job',state=state,message_id=message,created_at=utc_now()-timedelta(minutes=20) if old else utc_now()))

    async def test_unsigned_foreign_expired_and_ungranted_access_is_rejected(self):
        self.assertEqual((await self.client.post('/api/delivery-status',json={})).status,401)
        self.assertEqual((await self.call(actor=456)).status,403)
        self.assertEqual((await self.call({'track_id':999999})).status,403)
        async with self.database.write() as session:(await session.get(ChatControl,self.token)).expires_at=utc_now()-timedelta(seconds=1)
        self.assertEqual((await self.call()).status,403)

    async def test_status_is_read_only_and_does_not_claim_old_delivery(self):
        await self.add_request('done',message=80,old=True)
        result=await (await self.call()).json();self.assertEqual(result['state'],'waiting')
        self.assertIsNone(result['request_id'])
        async with self.database.sessions() as session:self.assertEqual(await session.scalar(select(func.count(AudioRequest.id))),1)

    async def test_active_request_remains_observable_after_completion(self):
        await self.add_request(old=True)
        first=await (await self.call()).json();self.assertEqual(first['state'],'pending')
        async with self.database.write() as session:
            row=await session.get(AudioRequest,'request');row.state='done';row.message_id=1234
        result=await (await self.call({'after':first['after'],'request_id':first['request_id']})).json()
        self.assertEqual(result['state'],'done')
        self.assertNotIn('message_id',result)

    async def test_done_without_confirmed_message_is_uncertain_and_failure_is_visible(self):
        await self.add_request('done')
        result=await (await self.call({'after':(utc_now()-timedelta(minutes=1)).isoformat()})).json();self.assertEqual(result['state'],'uncertain')
        async with self.database.write() as session:(await session.get(AudioRequest,'request')).state='failed'
        result=await (await self.call({'request_id':'request'})).json();self.assertEqual(result['state'],'failed')

    async def test_receipt_ids_cannot_read_another_actors_delivery(self):
        await self.add_request('done',message=10,owner=self.foreign)
        result=await (await self.call({'request_id':'request'})).json();self.assertEqual(result['state'],'waiting');self.assertIsNone(result['request_id'])

    async def test_invalid_markers_ids_and_actor_overrides_are_rejected(self):
        for extra in [{'track_id':True},{'after':'bad'},{'after':utc_now().replace(tzinfo=None).isoformat()},{'request_id':True},{'user_id':456},{'after':(utc_now()-timedelta(days=1)).isoformat()}]:
            self.assertEqual((await self.call(extra)).status,400)

    async def test_swap_source_revalidates_actor_and_song_state(self):
        with patch('music_bot.social.Social.read',new_callable=AsyncMock) as read:
            read.return_value={'state':'sent','song':{'id':self.track_id}}
            self.assertEqual((await self.call(source={'swap_token':'fixture'})).status,200)
            read.assert_awaited_with(123,'fixture')
            read.return_value={'state':'draft','song':{'id':self.track_id}}
            self.assertEqual((await self.call(source={'swap_token':'fixture'})).status,403)
            read.return_value={'state':'sent','song':{'id':999}}
            self.assertEqual((await self.call(source={'swap_token':'fixture'})).status,403)
