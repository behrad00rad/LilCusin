from unittest.mock import AsyncMock
from aiohttp.test_utils import TestClient,TestServer
from sqlalchemy import select
from music_bot.chat_service import ChatService
from music_bot.miniapp import create_app
from music_bot.models import ChannelPost,PlaylistChannel,SongSubmission,Track,Rating,User,UserTrackSignal,utc_now
from music_bot.artwork import ArtworkLoader
from music_bot.providers.common import TrackCandidate
from .support import ServiceTestCase
from .test_miniapp import TOKEN,signed


class ChannelLibraryTests(ServiceTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.chat=ChatService(self.database,AsyncMock())
        await self.chat.ensure_user(self.user)
        async with self.database.write() as session:
            user=await session.scalar(select(User).where(User.telegram_user_id==123))
            self.internal=user.id
            channel=PlaylistChannel(user_id=user.id,telegram_chat_id=-100123,title='My channel',connected_at=utc_now(),after_message_id=1)
            track=Track(artist='Artist',title='Song',metadata_source='lastfm')
            session.add_all([channel,track]);await session.flush()
            self.channel_id,self.track_id=channel.id,track.id
            for i in range(2):
                submission=SongSubmission(user_id=user.id,submission_type='telegram_audio',file_id='private-file',
                    parsed_artist='Artist' if i==0 else None,parsed_title='Song' if i==0 else None,
                    track_id=track.id if i==0 else None,identification_status='confirmed' if i==0 else 'pending')
                session.add(submission);await session.flush()
                post=ChannelPost(channel_id=channel.id,message_id=i+2,file_unique_id=str(i),submission_id=submission.id,
                    track_id=track.id if i==0 else None,status='identified' if i==0 else 'review')
                session.add(post);await session.flush()
                if i==1:self.post_id=post.id
        self.headers={'X-Telegram-Init-Data':signed()}
        self.client=TestClient(TestServer(create_app(TOKEN,self.chat,self.workflow)))
        await self.client.start_server()

    async def asyncTearDown(self):
        await self.client.close();await super().asyncTearDown()

    async def page(self,**extra):
        response=await self.client.post('/api/channels/songs',json={'channel_id':self.channel_id,**extra},headers=self.headers)
        self.assertEqual(response.status,200,await response.text());return await response.json()

    async def test_owner_scoped_songs_explicit_rating_and_unrated_filter(self):
        page=await self.page()
        self.assertEqual([s['id'] for s in page['tracks']],[self.track_id])
        self.assertIsNone(page['tracks'][0]['rating'])
        async with self.database.sessions() as session:self.assertIsNone(await session.scalar(select(Rating)))
        response=await self.client.post('/api/rate',json={'token':page['token'],'track_id':self.track_id,'value':'love'},headers=self.headers)
        self.assertEqual(response.status,200)
        self.assertEqual((await self.page())['tracks'][0]['rating'],'love')
        self.assertEqual((await self.page(filter='unrated'))['tracks'],[])
        response=await self.client.post('/api/channels/songs',json={'channel_id':self.channel_id},headers={'X-Telegram-Init-Data':signed(456)})
        self.assertEqual(response.status,403)

    async def test_review_manual_correction_confirmation_and_rating_in_app(self):
        page=await self.page(filter='review')
        self.assertEqual([i['id'] for i in page['items']],[self.post_id])
        self.assertNotIn('private-file',str(page))
        data={'channel_id':self.channel_id,'post_id':self.post_id,'token':page['token'],'action':'open'}
        response=await self.client.post('/api/channels/review',json=data,headers=self.headers)
        self.assertEqual(response.status,200);review=await response.json()
        self.assertEqual(review['kind'],'missing')
        self.providers.call.return_value=[TrackCandidate(title='Song',artist='Artist',source='lastfm')]
        response=await self.client.post('/api/channels/review',json={**data,'action':'search','token':review['token'],
            'revision':review['revision'],'query':'Artist - Song'},headers=self.headers)
        self.assertEqual(response.status,200);confirmed=await response.json()
        self.assertEqual(confirmed['kind'],'confirmed')
        self.assertEqual((await self.page(filter='review'))['items'],[])
        async with self.database.sessions() as session:
            self.assertIsNotNone(await session.scalar(select(UserTrackSignal)))
            self.assertIsNone(await session.scalar(select(Rating)))
        response=await self.client.post('/api/rate',json={'token':confirmed['token'],'track_id':confirmed['tracks'][0]['id'],'value':'like'},headers=self.headers)
        self.assertEqual(response.status,200)

    async def test_review_rejects_other_users_posts_and_stale_revisions(self):
        page=await self.page(filter='review')
        data={'channel_id':self.channel_id,'post_id':self.post_id,'token':page['token'],'action':'open'}
        response=await self.client.post('/api/channels/review',json=data,headers={'X-Telegram-Init-Data':signed(456)})
        self.assertEqual(response.status,403)
        response=await self.client.post('/api/channels/review',json={**data,'post_id':self.post_id+999},headers=self.headers)
        self.assertEqual(response.status,403)
        review=await (await self.client.post('/api/channels/review',json=data,headers=self.headers)).json()
        response=await self.client.post('/api/channels/review',json={**data,'token':review['token'],'action':'search','revision':review['revision']+10,'query':'Artist - Song'},headers=self.headers)
        self.assertEqual(response.status,409)

    async def test_artwork_requires_a_displayed_owned_song(self):
        page=await self.page()
        data={'token':page['token'],'track_ids':[self.track_id]}
        self.assertEqual((await self.client.post('/api/artwork',json=data,headers=self.headers)).status,200)
        self.assertEqual((await self.client.post('/api/artwork',json=data,headers={'X-Telegram-Init-Data':signed(456)})).status,403)
        self.assertEqual((await self.client.post('/api/artwork',json={**data,'track_ids':[99999]},headers=self.headers)).status,403)
        self.assertEqual((await self.client.post('/api/artwork',json={**data,'track_ids':[True]},headers=self.headers)).status,400)

    async def test_replacement_stays_in_channel_and_excludes_visible(self):
        page=await self.page()
        result=await self.page(filter='unrated',replace=True,exclude=[self.track_id],current=[{'id':self.track_id,'token':page['token']}])
        self.assertEqual(result['tracks'],[])
        response=await self.client.post('/api/rate',json={'token':result['token'],'track_id':self.track_id,'value':'like'},headers=self.headers)
        self.assertEqual(response.status,200)

    async def test_artwork_identity_validation_and_cache(self):
        loader=ArtworkLoader(self.database,self.providers)
        self.providers.call.return_value=TrackCandidate(title='Wrong',artist='Other',source='lastfm',artwork_url='https://lastfm.freetls.fastly.net/wrong.jpg')
        await loader.load(self.track_id)
        async with self.database.sessions() as session:self.assertIsNone((await session.get(Track,self.track_id)).artwork_url)
        self.providers.call.return_value=TrackCandidate(title='Song',artist='Artist',source='lastfm',artwork_url='https://lastfm.freetls.fastly.net/right.jpg')
        await loader.load(self.track_id)
        async with self.database.sessions() as session:self.assertEqual((await session.get(Track,self.track_id)).artwork_url,'https://lastfm.freetls.fastly.net/right.jpg')
        await loader.close()

    async def test_telegram_review_button_can_open_the_next_review(self):
        from music_bot.channels import ChannelService
        service=ChannelService(self.database,self.workflow)
        token=await self.chat.create_control(123,kind='channels',links=[self.channel_id])
        await self.chat.bind_control(token,77)
        for _ in range(2):
            channel=await service.control(token,123,77,'review',0)
            self.assertEqual(channel.id,self.channel_id)

    async def test_channel_pages_have_stable_cursors_and_no_duplicate_tracks(self):
        async with self.database.write() as session:
            for i in range(12):
                track=Track(artist='Artist',title='Track '+str(i),metadata_source='lastfm')
                session.add(track);await session.flush()
                submission=SongSubmission(user_id=self.internal,submission_type='text',parsed_artist='Artist',
                    parsed_title=track.title,track_id=track.id,identification_status='confirmed')
                session.add(submission);await session.flush()
                session.add(ChannelPost(channel_id=self.channel_id,message_id=50+i,file_unique_id='page-'+str(i),
                    submission_id=submission.id,track_id=track.id,status='identified'))
        first=await self.page();second=await self.page(cursor=first['next_cursor'])
        self.assertEqual(len(first['tracks']),10)
        self.assertEqual(len(second['tracks']),3)
        self.assertIsNone(second['next_cursor'])
        self.assertFalse({t['id'] for t in first['tracks']} & {t['id'] for t in second['tracks']})
        replacement=await self.page(filter='unrated',replace=True,cursor=first['next_cursor'],
            exclude=[s['id'] for s in first['tracks']],current=[{'id':s['id'],'token':first['token']} for s in first['tracks'][1:]])
        remaining=await self.page(cursor=replacement['next_cursor'])
        self.assertFalse({s['id'] for s in first['tracks']+replacement['tracks']} & {s['id'] for s in remaining['tracks']})

    async def test_existing_canonical_song_keeps_new_cover_metadata(self):
        from music_bot.catalog import canonical_track
        async with self.database.write() as session:
            candidate=TrackCandidate(title='Song',artist='Artist',source='lastfm',album='Album',
                artwork_url='https://lastfm.freetls.fastly.net/album.jpg')
            track=await canonical_track(session,candidate)
            self.assertEqual(track.id,self.track_id)
            self.assertEqual(track.album,'Album')
            self.assertEqual(track.artwork_url,candidate.artwork_url)

    async def test_main_search_finds_title_without_artist(self):
        self.providers.call.return_value=[
            TrackCandidate(title='Space Song',artist='Beach House',source='lastfm'),
            TrackCandidate(title='Unrelated Track',artist='Other',source='lastfm'),
        ]
        response=await self.client.post('/api/search',json={'query':'Space Song'},headers=self.headers)
        self.assertEqual(response.status,200,await response.text())
        self.assertEqual([(t['artist'],t['title']) for t in (await response.json())['tracks']],
                         [('Beach House','Space Song')])
        self.providers.call.assert_any_await('musicbrainz','search_titles','Space Song')

    async def test_hello_search_through_real_provider_cache(self):
        from music_bot.cache import CachedProviders
        lastfm, musicbrainz = AsyncMock(), AsyncMock()
        musicbrainz.search_titles.return_value = [TrackCandidate(title='Hello, Hello, Hello',artist='New England',source='musicbrainz'),
            TrackCandidate(title='Hello',artist='Adele',source='musicbrainz'),
            TrackCandidate(title='Say Hello to Heaven',artist='Temple of the Dog',source='musicbrainz'),
            TrackCandidate(title='Hello',artist='Adele',source='musicbrainz',external_ids={'musicbrainz':'duplicate-recording'}),
            TrackCandidate(title='Goodbye',artist='Other',source='musicbrainz')]
        lastfm.search_tracks.return_value = []
        lastfm.search_titles.return_value = []
        lastfm.get_track_info.return_value = None
        self.workflow.providers = CachedProviders(self.database,lastfm,musicbrainz)
        response=await self.client.post('/api/search',json={'query':'hello'},headers=self.headers)
        self.assertEqual(response.status,200,await response.text())
        songs=(await response.json())['tracks']
        self.assertEqual(songs[0]['artist'],'Adele')
        self.assertEqual({s['title'] for s in songs},{'Hello','Hello, Hello, Hello','Say Hello to Heaven'})
        musicbrainz.search_titles.assert_awaited_once_with('hello')

    async def test_local_title_matches_survive_provider_failure(self):
        from music_bot.providers.common import ProviderError,Failure
        async with self.database.write() as session:
            session.add(Track(artist='Local artist',title='Hello from the Other Side',display_title='Hello from the Other Side',metadata_source='fixture'))
        self.providers.call.side_effect=ProviderError(Failure.NETWORK)
        response=await self.client.post('/api/search',json={'query':'hello'},headers=self.headers)
        self.assertEqual(response.status,200)
        self.assertEqual((await response.json())['tracks'][0]['title'],'Hello from the Other Side')

    async def test_actual_lastfm_cover_host_is_allowed(self):
        from music_bot.chat_ui import safe_url
        url='https://lastfm-img.freetls.fastly.net/i/u/300x300/cover.png'
        self.assertEqual(safe_url(url,artwork=True),url)
        self.assertIsNone(safe_url('https://other.example/cover.png',artwork=True))
        self.assertIsNone(safe_url('https://lastfm-img.freetls.fastly.net/i/u/300x300/2a96cbd8b46e442fc41c2b86b821562f.png',artwork=True))

    async def test_placeholder_is_replaced_with_real_album_art(self):
        async with self.database.write() as session:
            (await session.get(Track,self.track_id)).artwork_url='https://lastfm-img.freetls.fastly.net/i/u/300x300/2a96cbd8b46e442fc41c2b86b821562f.png'
        self.providers.call.return_value=TrackCandidate(title='Song',artist='Artist',source='lastfm',artwork_url='https://lastfm-img.freetls.fastly.net/i/u/300x300/real.png')
        loader=ArtworkLoader(self.database,self.providers)
        await loader.load(self.track_id)
        async with self.database.sessions() as session:
            self.assertTrue((await session.get(Track,self.track_id)).artwork_url.endswith('/real.png'))
        await loader.close()
