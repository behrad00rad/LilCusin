from unittest.mock import AsyncMock,patch
from aiohttp.test_utils import TestClient,TestServer
from aiogram.types import CallbackQuery
from sqlalchemy import select
from music_bot.chat_service import ChatService
from music_bot.miniapp import create_app
from music_bot.models import Rating,User,Track,ChannelPost,PlaylistChannel,SongSubmission,utc_now
from music_bot.cache import CachedProviders
from music_bot.providers.common import TrackCandidate
from music_bot.recommendations import RecommendationService
from music_bot.recommendations.repository import load_profile
from music_bot.taste_setup import TasteSetup,read_setup,save_setup
from .support import ServiceTestCase
from .test_miniapp import TOKEN,signed

class TasteSetupTests(ServiceTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.lastfm,self.mb=AsyncMock(),AsyncMock()
        self.lastfm.get_track_info.return_value=None
        self.mb.search_recordings.return_value=[TrackCandidate(title='Hello',artist='Adele',source='musicbrainz')]
        providers=CachedProviders(self.database,self.lastfm,self.mb)
        self.workflow.providers=providers
        self.chat=ChatService(self.database,RecommendationService(self.database,providers))
        await self.chat.ensure_user(self.user)
        self.client=TestClient(TestServer(create_app(TOKEN,self.chat,self.workflow)));await self.client.start_server()
        self.headers={'X-Telegram-Init-Data':signed()}

    async def asyncTearDown(self):
        await self.client.close();await super().asyncTearDown()

    async def test_setup_drives_real_first_recommendation_without_ratings(self):
        prefs=await (await self.client.get('/api/preferences',headers=self.headers)).json()
        self.assertFalse(prefs['taste_setup_done'])
        response=await self.client.post('/api/taste-setup/update',json={'style':'pop','mood':'calm','artist':'Adele'},headers=self.headers)
        self.assertEqual(response.status,200)
        result=await (await self.client.post('/api/recommendations',json={},headers=self.headers)).json()
        self.assertEqual(result['tracks'][0]['title'],'Hello')
        self.mb.search_recordings.assert_awaited_once_with('Adele','')
        async with self.database.sessions() as session:self.assertIsNone(await session.scalar(select(Rating)))
        self.assertTrue((await (await self.client.get('/api/preferences',headers=self.headers)).json())['taste_setup_done'])

    async def test_setup_validation_owner_isolation_and_forget(self):
        for payload in [{'style':'nonsense'},{'mood':[]},{'artist':'x'*81},{'user_id':456}]:
            response=await self.client.post('/api/taste-setup/update',json=payload,headers=self.headers)
            self.assertEqual(response.status,400)
        await save_setup(self.database,123,style='rock',mood='energetic',artist='Muse')
        other=await (await self.client.get('/api/taste-setup',headers={'X-Telegram-Init-Data':signed(456)})).json()
        self.assertFalse(other['completed']);self.assertIsNone(other['artist'])
        await self.chat.forget(123)
        async with self.database.sessions() as session:self.assertIsNone(await session.scalar(select(TasteSetup)))

    async def test_telegram_three_questions_and_stale_callbacks(self):
        from music_bot.taste_setup_bot import setup_callback
        def query(data):return CallbackQuery.model_validate({'id':'q','from':{'id':123,'is_bot':False,'first_name':'Test'},'chat_instance':'x','data':data,'message':{'message_id':5,'date':1700000000,'chat':{'id':123,'type':'private'},'text':'setup'}})
        with patch('aiogram.types.CallbackQuery.answer',new_callable=AsyncMock),patch('aiogram.types.Message.edit_text',new_callable=AsyncMock),patch('music_bot.chat_ui.show_recommendations',new_callable=AsyncMock) as show:
            for value in ['taste:style:rock','taste:mood:energetic','taste:artist:1']:
                await setup_callback(query(value),self.chat)
            state=await read_setup(self.database,123)
            self.assertEqual((state['style'],state['mood'],state['artist']),('rock','energetic','Muse'))
            self.assertTrue(state['completed']);show.assert_awaited_once()
            await setup_callback(query('taste:style:pop'),self.chat)
            self.assertEqual((await read_setup(self.database,123))['style'],'rock')

    async def test_channel_songs_excluded_even_in_more_like_without_implicit_seed(self):
        async with self.database.write() as session:
            user=await session.scalar(select(User).where(User.telegram_user_id==123))
            seed=Track(artist='Adele',title='Hello',metadata_source='fixture');known=Track(artist='Adele',title='Someone Like You',metadata_source='fixture')
            channel=PlaylistChannel(user_id=user.id,telegram_chat_id=-100555,title='Music',connected_at=utc_now(),after_message_id=0)
            session.add_all([seed,known,channel]);await session.flush()
            submission=SongSubmission(user_id=user.id,submission_type='text',track_id=known.id,identification_status='confirmed')
            session.add(submission);await session.flush()
            session.add(ChannelPost(channel_id=channel.id,message_id=1,file_unique_id='known',submission_id=submission.id,track_id=known.id,status='identified'))
            seed_id,known_id=seed.id,known.id
        async with self.database.sessions() as session:
            profile=await load_profile(session,123,seed_id)
            self.assertIn(known_id,profile.rated_ids)
            self.assertTrue(any(key[0]=='name' for key in profile.rated_aliases))
