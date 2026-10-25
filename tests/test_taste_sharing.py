from datetime import timedelta
from unittest.mock import AsyncMock

from aiohttp.test_utils import TestClient, TestServer
from sqlalchemy import select, delete

from music_bot.chat_service import ChatService
from music_bot.comparison_invitations import ComparisonInvitation
from music_bot.friend_recommendations import mix_friend_songs
from music_bot.miniapp import create_app
from music_bot.models import Rating, RecommendationHistory, Track, User, utc_now
from music_bot.submissions import Submitter
from music_bot.taste_sharing import FriendTasteSharing, GuiltyPleasure, own_rating_states, save_privacy
from music_bot.workflow import save_rating
from tests.support import ServiceTestCase
from tests.test_miniapp import TOKEN, signed


class TasteSharingTests(ServiceTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.chat = ChatService(self.database, AsyncMock())
        for number in (123, 456):
            await self.chat.ensure_user(Submitter(number))
        async with self.database.write() as session:
            self.users = {user.telegram_user_id: user.id for user in await session.scalars(select(User))}
            track = Track(artist='Artist', title='Song', metadata_source='fixture')
            session.add(track)
            await session.flush()
            self.track = track.id
            session.add(ComparisonInvitation(token='f' * 32, sender_id=self.users[456], recipient_id=self.users[123],
                sender_revision=1, recipient_revision=1, card_token='c' * 32, state='consented',
                sender_snapshot={'friendship': True, 'nickname': 'Sara', 'songs': []},
                recipient_snapshot={'friendship': True, 'nickname': 'Me', 'songs': []},
                expires_at=utc_now() + timedelta(days=1), accepted_at=utc_now()))
            await save_rating(session, self.users[456], self.track, 'love')
        self.client = TestClient(TestServer(create_app(TOKEN, self.chat, self.workflow)))
        await self.client.start_server()
        self.grant = await self.chat.create_control(456, tracks=[self.track], kind='miniapp')

    async def asyncTearDown(self):
        await self.client.close()
        await super().asyncTearDown()

    async def post(self, path, data, user=456):
        return await self.client.post('/api/' + path, json=data, headers={'X-Telegram-Init-Data': signed(user)})

    async def rate(self, guilty, value='love', user=456):
        response = await self.post('rating-privacy', {'token': self.grant, 'track_id': self.track, 'private': guilty, **({'confirm_shared':True} if guilty is False else {})}, user)
        if response.status != 200:
            return response
        return await self.post('rate', {'token': self.grant, 'track_id': self.track, 'value': value}, user)

    async def test_sharing_is_opt_in_and_turning_it_off_removes_attribution(self):
        self.assertEqual(await mix_friend_songs(self.database, 123, []), [])
        self.assertEqual((await self.post('taste-sharing', {'enabled': True})).status, 200)
        rows = await mix_friend_songs(self.database, 123, [])
        self.assertEqual(rows[0]['reason'], 'Sara loved this song')
        await self.post('taste-sharing', {'enabled': False})
        async with self.database.write() as session:
            await session.execute(delete(RecommendationHistory))
        self.assertEqual(await mix_friend_songs(self.database, 123, []), [])

    async def test_guilty_is_idempotent_private_but_remains_love_for_personal_taste(self):
        await self.post('taste-sharing', {'enabled': True})
        for repeat in range(2):
            response = await self.rate(True)
            self.assertEqual(await response.json(), {'saved': True, 'guilty': True})
        self.assertEqual(await mix_friend_songs(self.database, 123, []), [])
        async with self.database.sessions() as session:
            self.assertEqual(await session.scalar(select(Rating.value).where(Rating.user_id == self.users[456])), 'love')
            self.assertIsNotNone(await session.get(GuiltyPleasure, (self.users[456], self.track)))
        rows = [{'id': self.track}]
        await own_rating_states(self.database, 456, rows)
        self.assertEqual(rows[0], {'id': self.track, 'rating': 'love', 'guilty': True,'visibility':'private'})
        await own_rating_states(self.database, 123, rows)
        self.assertEqual(rows[0], {'id': self.track, 'rating': None, 'guilty': False,'visibility':'private'})

    async def test_lock_works_for_likes_and_only_explicit_unlock_restores_sharing(self):
        await self.post('taste-sharing', {'enabled': True})
        await self.rate(True)
        await self.rate(False)
        self.assertEqual((await mix_friend_songs(self.database, 123, []))[0]['reason'], 'Sara loved this song')
        async with self.database.write() as session:
            await session.execute(delete(RecommendationHistory))
        self.assertEqual((await self.rate(True, 'like')).status, 200)
        self.assertEqual(await mix_friend_songs(self.database, 123, []), [])
        for repeat in range(2):
            self.assertFalse((await (await self.rate(False, 'like')).json())['guilty'])
        self.assertEqual(await mix_friend_songs(self.database, 123, []), [], 'Like is always private')

    async def test_telegram_lock_is_owned_idempotent_and_preserves_rating(self):
        from music_bot.chat_ui import card_keyboard, parse_control
        from music_bot.workflow import FlowError
        token = await self.chat.create_control(456, tracks=[self.track], kind='rating')
        await self.chat.bind_control(token, 80)
        with self.assertRaises(FlowError):
            await self.chat.control(token, 123, 80, 'lock', 0)
        with self.assertRaises(FlowError):
            await self.chat.control(token, 456, 81, 'lock', 0)
        for repeat in range(2):
            payload, track = await self.chat.control(token, 456, 80, 'lock', 0)
            self.assertTrue(payload['guilty'])
            self.assertEqual(payload['rating'], 'love')
        keyboard = card_keyboard(token, selected='love', rating_mode=True, guilty=True)
        self.assertEqual(parse_control(keyboard.inline_keyboard[1][-1].callback_data)[1], 'unlock')
        payload, track = await self.chat.control(token, 456, 80, 'like', 0, rating='like')
        self.assertTrue(payload['guilty'], 'ordinary ratings must not remove the lock')
        payload, track = await self.chat.control(token, 456, 80, 'unlock', 0)
        self.assertFalse(payload['guilty'])
        self.assertEqual(payload['rating'], 'like')

    async def test_lock_before_rating_never_creates_an_implicit_love(self):
        async with self.database.write() as session:
            await session.execute(delete(Rating).where(Rating.user_id == self.users[456]))
        response = await self.post('rating-privacy', {'token': self.grant, 'track_id': self.track, 'private': True})
        self.assertEqual(response.status, 200)
        async with self.database.sessions() as session:
            self.assertIsNone(await session.scalar(select(Rating).where(Rating.user_id == self.users[456])))

    async def test_privacy_changes_require_owned_fresh_grant(self):
        self.assertEqual((await self.rate(True, user=123)).status, 403)
        from music_bot.models import ChatControl
        async with self.database.write() as session:
            (await session.get(ChatControl, self.grant)).expires_at = utc_now() - timedelta(seconds=1)
        self.assertEqual((await self.rate(True)).status, 403)

    async def test_guilty_is_filtered_even_from_prior_explicit_snapshot(self):
        async with self.database.write() as session:
            invitation = await session.get(ComparisonInvitation, 'f' * 32)
            invitation.sender_snapshot = {**invitation.sender_snapshot, 'songs': [{'id': self.track}]}
            await save_privacy(session, self.users[456], self.track, 'love', True)
        self.assertEqual(await mix_friend_songs(self.database, 123, []), [])

    async def test_settings_and_private_library_are_actor_scoped(self):
        await self.rate(True)
        response = await self.client.get('/api/taste-sharing/private', headers={'X-Telegram-Init-Data': signed(123)})
        self.assertEqual((await response.json())['tracks'], [])
        response = await self.client.get('/api/taste-sharing/private', headers={'X-Telegram-Init-Data': signed(456)})
        library = await response.json()
        self.assertEqual([track['id'] for track in library['tracks']], [self.track])
        self.assertIsNotNone(library['token'])
        self.assertEqual((await self.post('taste-sharing', {'enabled': True, 'user_id': 456}, 123)).status, 400)
        self.assertEqual((await self.post('taste-sharing', {'enabled': 'true'})).status, 400)
        async with self.database.sessions() as session:
            self.assertIsNone(await session.get(FriendTasteSharing, self.users[123]))

    async def test_legacy_rating_request_does_not_silently_unhide_guilty_love(self):
        await self.rate(True)
        await self.post('rate', {'token': self.grant, 'track_id': self.track, 'value': 'love'})
        async with self.database.sessions() as session:
            self.assertIsNotNone(await session.get(GuiltyPleasure, (self.users[456], self.track)))

    async def test_private_love_hidden_from_feed_comparison_and_shared_count(self):
        from music_bot.social import Social
        from music_bot.comparison_invitations import ComparisonInvitations
        await self.post('taste-sharing',{'enabled':True})
        async with self.database.write() as session:
            row=await session.get(ComparisonInvitation,'f'*32)
            song={'id':self.track,'artist':'Artist','title':'Song'}
            row.sender_snapshot={**row.sender_snapshot,'taste_id':'sara','songs':[song]}
            row.recipient_snapshot={**row.recipient_snapshot,'taste_id':'me','songs':[song]}
        await self.rate(True)
        self.assertEqual(await mix_friend_songs(self.database,123,[]),[])
        compared=await Social(self.database).compare(123,'f'*32)
        self.assertEqual(compared['other']['songs'],[])
        self.assertEqual(compared['shared_songs'],[])
        listed=await ComparisonInvitations(self.database).read(123,'f'*32)
        self.assertEqual(listed['sender']['songs'],[])
        refused=await self.post('rating-privacy',{'token':self.grant,'track_id':self.track,'private':False})
        self.assertEqual(refused.status,409)
        confirmed=await self.post('rating-privacy',{'token':self.grant,'track_id':self.track,'private':False,'confirm_shared':True})
        self.assertEqual((await confirmed.json())['visibility'],'friends')
        self.assertTrue((await mix_friend_songs(self.database,123,[])))
