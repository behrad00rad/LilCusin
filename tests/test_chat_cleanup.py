from unittest.mock import patch
from aiogram.types import Message
from sqlalchemy import select
from tests.support import ServiceTestCase
from music_bot.chat_cleanup import clear_previous_search
from music_bot.chat_service import ChatService
from music_bot.models import ChatControl
from music_bot.submissions import Submitter

class CleanupTests(ServiceTestCase):
    async def test_background_cleanup_preserves_new_or_rebound_messages(self):
        chat = ChatService(self.database, None)
        await chat.ensure_user(self.user)
        old = await chat.create_control(123, kind='card')
        fresh = await chat.create_control(123, kind='card')
        await chat.bind_control(old, 10)
        await chat.bind_control(fresh, 60)
        source = Message.model_validate({'message_id': 50, 'date': 1, 'text': 'new search',
            'chat': {'id': 123, 'type': 'private'}, 'from': {'id': 123, 'is_bot': False, 'first_name': 'Test'}})
        removed = []
        async def delete(message):
            removed.append(message.message_id)
            await chat.bind_control(old, 70)
        with patch('aiogram.types.Message.delete', new=delete):
            await clear_previous_search(source, self.database)
        self.assertEqual(removed, [10])
        async with self.database.sessions() as session:
            self.assertEqual((await session.get(ChatControl, old)).message_id, 70)
            self.assertEqual((await session.get(ChatControl, fresh)).message_id, 60)

    async def test_only_owners_transient_controls_are_deleted_once(self):
        chat = ChatService(self.database, None)
        await chat.ensure_user(self.user)
        await chat.ensure_user(Submitter(456))
        mine = await chat.create_control(123, kind='card')
        theirs = await chat.create_control(456, kind='card')
        await chat.bind_control(mine, 10)
        await chat.bind_control(theirs, 20)
        source = Message.model_validate({'message_id': 50, 'date': 1, 'text': 'new search',
            'chat': {'id': 123, 'type': 'private'}, 'from': {'id': 123, 'is_bot': False, 'first_name': 'Test'}})
        removed = []
        async def delete(message):removed.append(message.message_id)
        with patch('aiogram.types.Message.delete', new=delete):
            await clear_previous_search(source, self.database)
            await clear_previous_search(source, self.database)
        self.assertEqual(removed, [10])
        async with self.database.sessions() as session:
            self.assertIsNone((await session.get(ChatControl, mine)).message_id)
            self.assertEqual((await session.get(ChatControl, theirs)).message_id, 20)
