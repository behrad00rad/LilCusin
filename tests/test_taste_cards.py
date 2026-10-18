"""Privacy, authorization, lifecycle and chat/API parity for the taste card."""
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from aiohttp.test_utils import TestClient, TestServer
from aiogram import Bot
from aiogram.types import Update
from sqlalchemy import func, select

from music_bot.chat_service import ChatService
from music_bot.miniapp import create_app
from music_bot.models import Rating, Track, User, utc_now
from music_bot.submissions import Submitter
from music_bot.taste_cards import CardError, SignatureSong, TasteCard, TasteCards
from .support import ServiceTestCase, dispatcher
from .test_miniapp import signed, TOKEN


class TasteCardTests(ServiceTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.chat = ChatService(self.database, AsyncMock())
        await self.chat.ensure_user(Submitter(123, 'private_contact', 'Private full name'))
        await self.chat.ensure_user(Submitter(456))
        async with self.database.write() as session:
            rows = [Track(artist=f'Artist {i}', title=f'Song {i}', metadata_source='fixture') for i in range(7)]
            session.add_all(rows)
            await session.flush()
            self.ids = [row.id for row in rows]
            user_id = await session.scalar(select(User.id).where(User.telegram_user_id == 123))
            session.add(Rating(user_id=user_id, track_id=rows[-1].id, value='dislike'))
        self.grant = await self.chat.create_control(123, tracks=self.ids, kind='miniapp')
        self.cards = TasteCards(self.database)

    async def change(self, action, **fields):
        owner = await self.cards.owner(123)
        return await self.cards.update(123, dict(action=action, revision=owner['revision'], **fields))

    async def ready(self):
        await self.change('edit', nickname='نام من', bio='A deliberately chosen bio')
        return await self.change('add', track_id=self.ids[0], token=self.grant)

    async def test_private_default_and_public_projection_never_exposes_private_fields(self):
        card = await self.ready()
        self.assertFalse(card['shared'])
        self.assertIsNone(card['share_token'])
        published = await self.cards.sharing(123, 'publish', card['revision'])
        public = await self.cards.view(published['share_token'])
        self.assertEqual(set(public), {'taste_id', 'nickname', 'bio', 'songs', 'current'})
        self.assertEqual(set(public['songs'][0]), {'artist', 'title', 'artwork'})
        self.assertNotIn('private_contact', str(public))
        self.assertNotIn('Private full name', str(public))
        self.assertNotIn('Song 6', str(public))
        async with self.database.sessions() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(Rating)), 1)

    async def test_expiry_rotation_hide_and_stable_taste_id(self):
        card = await self.ready()
        first = await self.cards.sharing(123, 'publish', card['revision'])
        second = await self.cards.sharing(123, 'rotate', first['revision'])
        self.assertEqual(first['taste_id'], second['taste_id'])
        with self.assertRaisesRegex(CardError, 'card_unavailable'):
            await self.cards.view(first['share_token'])
        await self.cards.view(second['share_token'])
        async with self.database.write() as session:
            row = await session.scalar(select(TasteCard).where(TasteCard.share_token == second['share_token']))
            row.share_expires_at = utc_now() - timedelta(seconds=1)
        with self.assertRaisesRegex(CardError, 'card_unavailable'):
            await self.cards.view(second['share_token'])
        third = await self.cards.sharing(123, 'publish', second['revision'])
        self.assertNotEqual(third['share_token'], second['share_token'])
        await self.cards.sharing(123, 'hide', third['revision'])
        with self.assertRaisesRegex(CardError, 'card_unavailable'):
            await self.cards.view(third['share_token'])

    async def test_forged_cross_owner_expired_and_wrong_kind_grants_cannot_select(self):
        other = await self.chat.create_control(456, tracks=self.ids, kind='miniapp')
        wrong = await self.chat.create_control(123, tracks=self.ids, kind='forget')
        for token, track in [(other, self.ids[0]), (wrong, self.ids[0]), ('forged', self.ids[0]), (self.grant, 999999)]:
            with self.subTest(token=token == self.grant), self.assertRaisesRegex(CardError, 'card_stale'):
                await self.change('add', track_id=track, token=token)
        from music_bot.models import ChatControl
        async with self.database.write() as session:
            (await session.get(ChatControl, self.grant)).expires_at = utc_now() - timedelta(seconds=1)
        with self.assertRaisesRegex(CardError, 'card_stale'):
            await self.change('add', track_id=self.ids[0], token=self.grant)

    async def test_cap_duplicate_selection_removal_and_current_are_consistent(self):
        for track_id in self.ids[:5]:
            await self.change('add', track_id=track_id, token=self.grant)
        duplicate = await self.change('add', track_id=self.ids[0], token=self.grant)
        self.assertEqual(len(duplicate['songs']), 5)
        with self.assertRaisesRegex(CardError, 'card_full'):
            await self.change('add', track_id=self.ids[5], token=self.grant)
        await self.change('current', track_id=self.ids[0])
        removed = await self.change('remove', track_id=self.ids[0])
        self.assertIsNone(removed['current'])
        replacement = await self.change('add', track_id=self.ids[5], token=self.grant)
        self.assertEqual(len(replacement['songs']), 5)
        with self.assertRaisesRegex(CardError, 'card_stale'):
            await self.change('current', track_id=self.ids[6])

    async def test_concurrent_edits_reject_stale_revision(self):
        import asyncio
        card = await self.cards.owner(123)
        results = await asyncio.gather(*(self.cards.update(123, dict(action='edit', revision=card['revision'],
            nickname=name, bio='')) for name in ['First', 'Second']), return_exceptions=True)
        self.assertEqual(sum(isinstance(result, CardError) for result in results), 1)
        self.assertIn((await self.cards.owner(123))['nickname'], {'First', 'Second'})

    async def test_invalid_input_and_incomplete_publishing(self):
        card = await self.cards.owner(123)
        for payload in [dict(action=[], revision=0), dict(action='edit', revision=True, nickname='n', bio=''),
                        dict(action='edit', revision=0, nickname='x' * 41, bio=''),
                        dict(action='edit', revision=0, nickname='n', bio='x' * 241),
                        dict(action='add', revision=0, track_id=True, token=self.grant),
                        dict(action='edit', revision=0, nickname='n', bio='', user_id=456)]:
            with self.assertRaises(CardError):
                await self.cards.update(123, payload)
        with self.assertRaisesRegex(CardError, 'card_incomplete'):
            await self.cards.sharing(123, 'publish', card['revision'])
        edited = await self.change('edit', nickname='Hi\u202e', bio='<script>example</script>')
        self.assertEqual(edited['nickname'], 'Hi')

    async def test_card_delete_and_forget_revoke_without_deleting_shared_tracks(self):
        card = await self.ready()
        public = await self.cards.sharing(123, 'publish', card['revision'])
        await self.cards.sharing(123, 'delete', public['revision'])
        with self.assertRaises(CardError):
            await self.cards.view(public['share_token'])
        async with self.database.sessions() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(SignatureSong)), 0)
            self.assertEqual(await session.scalar(select(func.count()).select_from(Rating)), 1)
        replacement = await self.ready()
        public = await self.cards.sharing(123, 'publish', replacement['revision'])
        await self.chat.forget(123)
        with self.assertRaises(CardError):
            await self.cards.view(public['share_token'])
        async with self.database.sessions() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(TasteCard)), 0)
            self.assertEqual(await session.scalar(select(func.count()).select_from(Track)), 7)

    async def test_additive_initialize_preserves_existing_ratings(self):
        # Initialize an existing database a second time: no destructive upgrade.
        before = await self.ready()
        await self.database.initialize()
        self.assertEqual((await self.cards.owner(123))['taste_id'], before['taste_id'])
        async with self.database.sessions() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(Rating)), 1)

    async def test_upgrade_database_without_social_tables_preserves_existing_users_and_ratings(self):
        async with self.database.engine.begin() as connection:
            await connection.run_sync(lambda conn: SignatureSong.__table__.drop(conn))
            await connection.run_sync(lambda conn: TasteCard.__table__.drop(conn))
        await self.database.initialize()
        async with self.database.sessions() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(User)), 2)
            self.assertEqual(await session.scalar(select(func.count()).select_from(Rating)), 1)
        self.assertFalse((await self.cards.owner(123))['shared'])

    async def test_api_owner_auth_projection_and_conflict(self):
        client = TestClient(TestServer(create_app(TOKEN, self.chat, self.workflow, bot_username='LilCusinTestBot')))
        await client.start_server()
        try:
            self.assertEqual((await client.get('/api/taste-card')).status, 401)
            owner = await self.ready()
            headers = {'X-Telegram-Init-Data': signed()}
            response = await client.post('/api/taste-card/share', json={'action': 'publish', 'revision': owner['revision']}, headers=headers)
            published = await response.json()
            self.assertEqual(response.status, 200)
            self.assertTrue(published['share_url'].startswith('https://t.me/LilCusinTestBot?start=taste_'))
            response = await client.post('/api/taste-card/view', json={'token': published['share_token']}, headers={'X-Telegram-Init-Data': signed(456)})
            self.assertEqual(set(await response.json()), {'taste_id', 'nickname', 'bio', 'songs', 'current'})
            response = await client.post('/api/taste-card/update', json=dict(action='edit', revision=owner['revision'], nickname='overwrite', bio=''), headers=headers)
            self.assertEqual(response.status, 409)
            response = await client.get('/api/taste-card', headers={'X-Telegram-Init-Data': signed(456)})
            self.assertFalse((await response.json())['shared'])
            response = await client.post('/api/taste-card/view', json={'token': 'invalid'}, headers=headers)
            self.assertEqual(response.status, 404)
        finally:
            await client.close()

    async def test_chat_commands_search_and_deep_link_use_same_card(self):
        bot = Bot(TOKEN)
        sequence = 0
        async def send(text):
            nonlocal sequence
            sequence += 1
            update = Update.model_validate({'update_id': sequence, 'message': {'message_id': sequence,
                'date': 1700000000, 'chat': {'id': 123, 'type': 'private'},
                'from': {'id': 123, 'is_bot': False, 'first_name': 'Test'}, 'text': text}})
            await dispatcher.feed_update(bot, update, chat_service=self.chat, workflow=self.workflow)
        from music_bot.providers.common import TrackCandidate
        try:
            with patch('aiogram.types.Message.answer', new_callable=AsyncMock) as answer:
                answer.return_value = SimpleNamespace(message_id=100)
                await send('/cardname My name')
                await send('/cardbio My music')
                self.assertEqual((await self.cards.owner(123))['nickname'], 'My name')
                with patch.object(self.workflow, 'search_title', new_callable=AsyncMock,
                    return_value=([TrackCandidate('New', 'Band', 'fixture')], False)):
                    await send('/cardsearch Band - New')
                self.assertTrue(answer.call_args.kwargs['reply_markup'].inline_keyboard[0][0].callback_data.startswith('tc:add:'))
                owner = await self.change('add', track_id=self.ids[0], token=self.grant)
                await send('/cardshare')
                self.assertIn('My name', answer.call_args.args[0])
                self.assertIn('My music', answer.call_args.args[0])
                self.assertFalse((await self.cards.owner(123))['shared'])
                public = await self.cards.sharing(123, 'publish', owner['revision'])
                await send('/start taste_' + public['share_token'])
                self.assertIn('My name', answer.call_args.args[0])
                self.assertNotIn('private_contact', answer.call_args.args[0])
                await send('/cardhide')
                await send('/start taste_' + public['share_token'])
                self.assertIn('no longer available', answer.call_args.args[0])
        finally:
            await bot.session.close()

    async def test_chat_callback_selection_publish_replay_hide_and_nonowner(self):
        bot = Bot(TOKEN)
        grant = await self.chat.create_control(123, tracks=[self.ids[0]], kind='tastecard')
        await self.chat.bind_control(grant, 100)
        async def click(data, user_id=123, message_id=100):
            update = Update.model_validate({'update_id': 1, 'callback_query': {'id': 'fixture', 'chat_instance': 'fixture',
                'from': {'id': user_id, 'is_bot': False, 'first_name': 'Test'}, 'data': data,
                'message': {'message_id': message_id, 'date': 1700000000,
                    'chat': {'id': user_id, 'type': 'private'}, 'text': 'fixture'}}})
            await dispatcher.feed_update(bot, update, chat_service=self.chat)
        try:
            with patch('aiogram.types.Message.answer', new_callable=AsyncMock) as answer, \
                    patch('aiogram.types.CallbackQuery.answer', new_callable=AsyncMock), \
                    patch.object(bot, 'me', new_callable=AsyncMock, return_value=SimpleNamespace(username='LilCusinTestBot')):
                await click(f'tc:add:{grant}:{self.ids[0]}', user_id=456)
                self.assertEqual((await self.cards.owner(456))['songs'], [])
                await click(f'tc:add:{grant}:{self.ids[0]}', message_id=999)
                self.assertEqual((await self.cards.owner(123))['songs'], [])
                await click(f'tc:add:{grant}:{self.ids[0]}')
                await click(f'tc:add:{grant}:{self.ids[0]}')
                self.assertEqual(len((await self.cards.owner(123))['songs']), 1)
                card = await self.change('edit', nickname='Selected name', bio='')
                await click(f"tc:publish:0:{card['revision']}")
                public = await self.cards.owner(123)
                self.assertTrue(public['shared'])
                await self.cards.view(public['share_token'])
                await click(f"tc:publish:0:{card['revision']}")
                self.assertIn('changed in another view', answer.call_args.args[0])
                await click(f"tc:hide:0:{public['revision']}")
                with self.assertRaises(CardError):
                    await self.cards.view(public['share_token'])
        finally:
            await bot.session.close()
