from datetime import timedelta
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from PIL import Image
from sqlalchemy import select, func

from .support import ServiceTestCase
from music_bot.chat_service import ChatService
from music_bot.submissions import Submitter
from music_bot.models import User, Track, Rating, utc_now
from music_bot.taste_cards import TasteCards, CardError
from music_bot.comparison_invitations import ComparisonInvitations, ComparisonInvitation
from music_bot import onboarding
from music_bot.taste_card_image import render, small_preview, portrait


class SocialConsentTests(ServiceTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.chat = ChatService(self.database, AsyncMock())
        self.cards = TasteCards(self.database)
        self.invites = ComparisonInvitations(self.database)
        for number in [123, 456, 789]:
            await self.chat.ensure_user(Submitter(number))
        async with self.database.write() as session:
            tracks = [Track(artist='Artist', title=f'Song {i}', metadata_source='fixture') for i in range(5)]
            session.add_all(tracks);await session.flush()
            self.ids = [track.id for track in tracks]
        self.owners = {}
        for number in [123, 456]:
            owner = await self.cards.owner(number)
            owner = await self.cards.update(number, dict(action='edit', revision=owner['revision'], nickname=f'Name {number}', bio='Private chosen bio'))
            grant = await self.chat.create_control(number, tracks=self.ids, kind='miniapp')
            owner = await self.cards.update(number, dict(action='add', revision=owner['revision'], track_id=self.ids[0], token=grant))
            self.owners[number] = owner
        self.owners[456] = await self.cards.sharing(456, 'publish', self.owners[456]['revision'])

    async def invitation(self):
        return await self.invites.create(123, self.owners[456]['share_token'], self.owners[123]['revision'], self.owners[456]['revision'])

    async def test_recipient_bound_mutual_consent_and_idempotence(self):
        invite = await self.invitation()
        self.assertEqual(invite['state'], 'pending')
        self.assertTrue(invite['sender_consented']);self.assertFalse(invite['recipient_consented'])
        self.assertEqual((await self.invitation())['token'], invite['token'])
        for operation in [lambda: self.invites.read(789, invite['token']), lambda: self.invites.decide(123, invite['token'], 'accept'), lambda: self.invites.decide(789, invite['token'], 'accept')]:
            with self.assertRaisesRegex(CardError, 'invite_unavailable'):
                await operation()
        accepted = await self.invites.decide(456, invite['token'], 'accept')
        self.assertEqual(accepted['state'], 'consented')
        self.assertEqual((await self.invites.decide(456, invite['token'], 'accept'))['state'], 'consented')
        self.assertEqual(set(accepted['sender']['songs'][0]), {'artist', 'title'})
        self.assertNotIn('bio', accepted['sender'])
        revoked = await self.invites.decide(123, invite['token'], 'revoke')
        self.assertEqual(revoked['state'], 'revoked');self.assertNotIn('sender', revoked)
        async with self.database.sessions() as session:
            self.assertEqual((await session.get(ComparisonInvitation, invite['token'])).sender_snapshot, {})

    async def test_card_edits_revoke_and_scrub(self):
        invite = await self.invitation()
        owner = await self.cards.owner(123)
        await self.cards.update(123, dict(action='edit', revision=owner['revision'], nickname='Changed', bio=''))
        self.assertEqual((await self.invites.read(456, invite['token']))['state'], 'revoked')
        with self.assertRaisesRegex(CardError, 'invite_stale'):
            await self.invites.decide(456, invite['token'], 'accept')
        async with self.database.sessions() as session:
            self.assertEqual((await session.get(ComparisonInvitation, invite['token'])).recipient_snapshot, {})

    async def test_expiry_and_self_invitation(self):
        with self.assertRaisesRegex(CardError, 'invite_self'):
            await self.invites.create(456, self.owners[456]['share_token'], self.owners[456]['revision'], self.owners[456]['revision'])
        invite = await self.invitation()
        async with self.database.write() as session:
            (await session.get(ComparisonInvitation, invite['token'])).expires_at = utc_now() - timedelta(seconds=1)
        value = await self.invites.read(456, invite['token'])
        self.assertEqual(value['state'], 'expired');self.assertNotIn('sender', value)
        with self.assertRaisesRegex(CardError, 'invite_stale'):
            await self.invites.decide(456, invite['token'], 'accept')

    async def test_hide_revokes_and_stale_revisions_fail(self):
        with self.assertRaisesRegex(CardError, 'invite_stale'):
            await self.invites.create(123, self.owners[456]['share_token'], -1, self.owners[456]['revision'])
        invite = await self.invitation()
        await self.cards.sharing(456, 'hide', self.owners[456]['revision'])
        self.assertEqual((await self.invites.read(123, invite['token']))['state'], 'revoked')

    async def test_decline_limit_and_account_deletion(self):
        for _ in range(5):
            invite = await self.invitation()
            declined = await self.invites.decide(456, invite['token'], 'decline')
            self.assertEqual(declined['state'], 'declined');self.assertNotIn('sender', declined)
        with self.assertRaisesRegex(CardError, 'invite_limit'):
            await self.invitation()
        await onboarding.set_mode(self.chat, 123, 'pick')
        await self.chat.forget(123)
        async with self.database.sessions() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(ComparisonInvitation)), 0)
            self.assertEqual(await session.scalar(select(func.count()).select_from(onboarding.Onboarding)), 0)

    async def test_picker_five_songs_does_not_fabricate_ratings(self):
        owner = self.owners[123]
        grant = await self.chat.create_control(123, tracks=self.ids, kind='miniapp')
        for track_id in self.ids[1:]:
            owner = await self.cards.update(123, dict(action='add', revision=owner['revision'], track_id=track_id, token=grant))
        message = SimpleNamespace(answer=AsyncMock())
        await onboarding.set_mode(self.chat, 123, 'pick')
        with patch('music_bot.taste_card_chat.show_card', new_callable=AsyncMock), patch.object(onboarding, 'recommendations', new_callable=AsyncMock) as recommend:
            self.assertTrue(await onboarding.after_pick(message, self.chat, 123))
            recommend.assert_awaited_once()
            self.assertFalse(await onboarding.after_pick(message, self.chat, 123))
        async with self.database.sessions() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(Rating)), 0)

    async def test_send_path_three_explicit_positives_triggers_once(self):
        await onboarding.set_mode(self.chat, 123, 'send')
        async with self.database.write() as session:
            user = await session.scalar(select(User).where(User.telegram_user_id == 123))
            session.add_all([Rating(user_id=user.id, track_id=track_id, value='like') for track_id in self.ids[:3]])
        with patch.object(onboarding, 'recommendations', new_callable=AsyncMock) as recommend:
            await onboarding.after_rating(SimpleNamespace(), self.chat, 123)
            await onboarding.after_rating(SimpleNamespace(), self.chat, 123)
            recommend.assert_awaited_once()

    async def test_picker_reply_is_owner_and_prompt_bound(self):
        message = SimpleNamespace(answer=AsyncMock(return_value=SimpleNamespace(message_id=91)))
        await onboarding.set_mode(self.chat, 123, 'pick')
        await onboarding.ask_pick(message, self.chat, 123)
        with patch('music_bot.taste_card_chat.search_songs', new_callable=AsyncMock, return_value=True) as search:
            def reply(owner, prompt):
                return SimpleNamespace(from_user=SimpleNamespace(id=owner), reply_to_message=SimpleNamespace(message_id=prompt), text='Band - Song')
            self.assertFalse(await onboarding.handle_reply(reply(456, 91), self.chat, self.workflow))
            self.assertFalse(await onboarding.handle_reply(reply(123, 92), self.chat, self.workflow))
            self.assertTrue(await onboarding.handle_reply(reply(123, 91), self.chat, self.workflow))
            self.assertFalse(await onboarding.handle_reply(reply(123, 91), self.chat, self.workflow))
            search.assert_awaited_once()

    async def test_short_recommendations_have_four_explicit_rating_buttons(self):
        rows = [SimpleNamespace(track_id=track_id, title='Song', artist='Band') for track_id in self.ids[:3]]
        self.chat.recommendations.recommend_for_user = AsyncMock(return_value=SimpleNamespace(recommendations=rows))
        message = SimpleNamespace(answer=AsyncMock(return_value=SimpleNamespace(message_id=44)))
        with patch.object(self.chat, 'record_displayed', new_callable=AsyncMock):
            await onboarding.recommendations(message, self.chat, 123)
        self.assertEqual(message.answer.await_count, 3)
        for call in message.answer.await_args_list:
            keys = call.kwargs['reply_markup'].inline_keyboard[0]
            self.assertEqual([button.callback_data.split(':')[2] for button in keys], ['love','like','neutral','dislike'])
            self.assertEqual(call.args[0], 'Song\nBand')

    async def test_authenticated_image_and_invitation_api(self):
        import base64
        from aiohttp.test_utils import TestClient, TestServer
        from music_bot.miniapp import create_app
        from .test_miniapp import signed, TOKEN
        client = TestClient(TestServer(create_app(TOKEN, self.chat, self.workflow)))
        await client.start_server()
        headers = {'X-Telegram-Init-Data': signed(123)}
        try:
            self.assertEqual((await client.post('/api/taste-card/image', json={})).status, 401)
            response = await client.post('/api/taste-card/image', json={}, headers=headers)
            self.assertEqual(response.status, 200)
            raw = await response.read();self.assertLess(len(raw), 65536)
            payload = await response.json()
            with Image.open(BytesIO(base64.b64decode(payload['image'].split(',')[1]))) as image:
                self.assertEqual(image.size, (540, 960))
            self.assertEqual((await client.post('/api/taste-card/image', json={'user_id':456}, headers=headers)).status, 400)
            invite = await self.invitation()
            response = await client.post('/api/comparison-invitations/decide', json={'token':invite['token'], 'action':'accept'}, headers=headers)
            self.assertEqual(response.status, 404)
            response = await client.get('/api/comparison-invitations', headers=headers)
            self.assertEqual((await response.json())['invitations'][0]['token'], invite['token'])
        finally:
            await client.close()

    async def test_portrait_bilingual_and_bounded_preview(self):
        card = self.owners[123]
        for language in ['en', 'fa']:
            data = render({**card, 'nickname': 'نیما / Nima', 'bio': 'موسیقی برای شب‌های آرام'}, language)
            with Image.open(BytesIO(data)) as image:
                self.assertEqual(image.size, (1080, 1920));self.assertEqual(image.format, 'JPEG')
            self.assertLessEqual(len(small_preview(data)), 45000)
        with patch('music_bot.taste_card_image.image_bytes', new_callable=AsyncMock) as fetch:
            await portrait({**card, 'songs': [{**card['songs'][0], 'artwork': 'http://127.0.0.1/private'}]})
            fetch.assert_not_awaited()
