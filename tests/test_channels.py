"""Six focused connection, ingestion, preference and privacy scenarios."""

import asyncio
from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from aiogram.types import Message
from sqlalchemy import func, select, update

from music_bot.channel_handlers import channel_post
from music_bot.channels import ChannelService, code_hash
from music_bot.chat_service import ChatService
from music_bot.models import ChannelConnectionCode, ChannelPost, PlaylistChannel, Rating, Track, UserTrackSignal, utc_now
from music_bot.recommendations import RecommendationService
from music_bot.recommendations.repository import load_profile
from music_bot.submissions import Submitter
from music_bot.workflow import FlowError
from tests.support import ServiceTestCase
from tests.test_workflow import EXACT


class ChannelTests(ServiceTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.chat = ChatService(self.database, RecommendationService(self.database))
        await self.chat.ensure_user(self.user)
        self.channels = ChannelService(self.database, self.workflow)
        self.bot = AsyncMock()
        self.bot.id = 777
        self.bot.get_chat_member.return_value = SimpleNamespace(status='administrator')
        self.providers.call.return_value = [EXACT]
        self.enrichment = Mock()

    def post(self, number=10, channel=-100123, **fields):
        return Message.model_validate({'message_id': number, 'date': int(utc_now().timestamp()),
            'chat': {'id': channel, 'type': 'channel', 'title': 'Test playlist'}, **fields})

    def audio(self, number=11, unique='one', channel=-100123):
        return self.post(number, channel, audio={'file_id': 'fixture-file', 'file_unique_id': unique,
            'duration': 120, 'performer': 'Artist', 'title': 'Song'})

    async def connect(self, channel=-100123, user=123, number=10):
        code = await self.channels.new_code(user)
        return await self.channels.connect(self.post(number, channel, text=code), self.bot)

    async def count(self, model):
        async with self.database.sessions() as session:
            return await session.scalar(select(func.count()).select_from(model))

    async def test_connect_hash_admin_and_single_use(self):
        code = await self.channels.new_code(123)
        async with self.database.sessions() as session:
            stored = await session.scalar(select(ChannelConnectionCode))
            self.assertEqual(stored.code_hash, code_hash(code))
            self.assertNotEqual(stored.code_hash, code)
        message = self.post(text=code)
        self.assertEqual(await self.channels.connect(message, self.bot), (123, 'connected'))
        self.assertIsNone(await self.channels.connect(message, self.bot))
        self.assertEqual(await self.count(PlaylistChannel), 1)
        self.assertEqual(await self.count(ChannelConnectionCode), 0)
        self.assertEqual([call.args for call in self.bot.get_chat_member.call_args_list], [(-100123, 777), (-100123, 123)])
        await self.chat.ensure_user(Submitter(999))
        self.assertEqual(await self.connect(user=999, number=20), (999, 'in_use'))
        async with self.database.sessions() as session:
            self.assertEqual((await session.scalar(select(PlaylistChannel))).after_message_id, 10)

    async def test_expired_and_non_admin_rejected(self):
        code = await self.channels.new_code(123)
        async with self.database.write() as session:
            await session.execute(update(ChannelConnectionCode).values(expires_at=utc_now() - timedelta(seconds=1)))
        self.assertEqual(await self.channels.connect(self.post(text=code), self.bot), (123, 'expired'))
        self.bot.get_chat_member.assert_not_awaited()
        self.bot.get_chat_member.side_effect = [SimpleNamespace(status='administrator'), SimpleNamespace(status='member')]
        self.assertEqual(await self.connect(), (123, 'not_admin'))
        self.assertEqual(await self.count(PlaylistChannel), 0)
        self.bot.get_chat_member.side_effect = [SimpleNamespace(status='member'), SimpleNamespace(status='creator')]
        self.assertEqual(await self.connect(), (123, 'permissions'))
        self.assertEqual(await self.count(PlaylistChannel), 0)

    async def test_new_audio_dedup_weak_signal_no_public_reply_or_history(self):
        await self.connect()
        self.assertIsNone(await self.channels.ingest(self.audio(number=9)))
        await channel_post(self.audio(), self.bot, self.channels, self.workflow, self.enrichment, self.chat)
        await asyncio.gather(self.channels.ingest(self.audio()), self.channels.ingest(self.audio(number=12)))
        self.assertEqual(await self.count(ChannelPost), 1)
        self.assertEqual(await self.count(UserTrackSignal), 1)
        self.assertEqual(await self.count(Rating), 0)
        await self.channels.ingest(self.audio(number=13, unique='different-upload'))
        self.assertEqual(await self.count(ChannelPost), 2)
        self.assertEqual(await self.count(UserTrackSignal), 1)
        self.bot.send_message.assert_not_awaited()
        self.bot.download.assert_not_awaited()
        async with self.database.sessions() as session:
            signal = await session.scalar(select(UserTrackSignal))
            post = await session.get(ChannelPost, signal.channel_post_id)
            self.assertEqual(signal.weight, .25)
            self.assertEqual(post.status, 'identified')
            self.assertEqual(post.message_id, 11)
            self.assertEqual(post.track_id, signal.track_id)

    async def test_ambiguous_private_confirmation_before_signal(self):
        await self.connect()
        self.providers.call.return_value = [replace(EXACT, title='Song remix', external_ids={})]
        private = Message.model_validate({'message_id': 99, 'date': int(utc_now().timestamp()),
            'chat': {'id': 123, 'type': 'private'}})
        self.bot.send_message.return_value = private
        with patch('aiogram.types.Message.answer', new_callable=AsyncMock) as answer:
            await channel_post(self.audio(), self.bot, self.channels, self.workflow, self.enrichment, self.chat)
            self.assertTrue(answer.call_args.kwargs['reply_markup'].inline_keyboard[0][0].callback_data.startswith('c:'))
        self.assertEqual(self.bot.send_message.call_args.args[0], 123)
        self.assertEqual(await self.count(UserTrackSignal), 0)
        async with self.database.sessions() as session:
            post = await session.scalar(select(ChannelPost))
            self.assertEqual(post.status, 'review')
            from music_bot.models import IdentificationFlow
            flow = await session.get(IdentificationFlow, post.submission_id)
        with self.assertRaises(FlowError):
            await self.workflow.select(post.submission_id, 999, flow.revision, 0)
        await self.workflow.select(post.submission_id, 123, flow.revision, 0)
        self.assertEqual(await self.count(UserTrackSignal), 1)
        self.assertEqual(await self.count(Rating), 0)

    async def test_explicit_ratings_override_channel_seed(self):
        await self.connect()
        await self.channels.ingest(self.audio())
        async with self.database.write() as session:
            session.add(Track(artist='Artist', title='Next song', metadata_source='fixture'))
            post = await session.scalar(select(ChannelPost))
        weak = await self.chat.recommendations.recommend_for_user(123)
        self.assertEqual(weak.status, 'ok')
        self.assertIn('playlist', weak.recommendations[0].reason)
        for value in ('neutral', 'dislike'):
            await self.workflow.rate(post.submission_id, 123, value)
            self.assertEqual((await self.chat.recommendations.recommend_for_user(123)).status, 'insufficient_preferences')
        await self.workflow.rate(post.submission_id, 123, 'like')
        liked = await self.chat.recommendations.recommend_for_user(123)
        self.assertGreater(liked.recommendations[0].score, weak.recommendations[0].score)
        async with self.database.sessions() as session:
            profile = await load_profile(session, 123)
            self.assertEqual(len(profile.positives), 1)
            self.assertEqual(profile.positives[0].rating, 'like')
        similar = await self.chat.recommendations.recommend_similar_to_track(123, post.track_id)
        self.assertEqual(similar.status, 'ok')

    async def test_disconnect_choices_and_forget_isolation(self):
        await self.connect()
        await self.channels.ingest(self.audio())
        await self.chat.ensure_user(Submitter(999))
        await self.connect(channel=-100999, user=999)
        await self.channels.ingest(self.audio(channel=-100999))
        async with self.database.sessions() as session:
            channel = await session.scalar(select(PlaylistChannel).where(PlaylistChannel.telegram_chat_id == -100123))
            post = await session.scalar(select(ChannelPost).where(ChannelPost.channel_id == channel.id))
        await self.channels.disconnect(123, channel.id, False)
        self.assertEqual(await self.count(UserTrackSignal), 2)
        self.assertIsNone(await self.channels.ingest(self.audio(number=20, unique='new')))
        with self.assertRaises(FlowError):
            await self.channels.disconnect(999, channel.id, True)
        await self.channels.disconnect(123, channel.id, True)
        self.assertEqual(await self.count(UserTrackSignal), 1)
        await self.workflow.rate(post.submission_id, 123, 'neutral')
        self.assertEqual(await self.count(UserTrackSignal), 1)  # Old confirmations cannot restore removed imports.
        await self.channels.new_code(123)
        await self.chat.forget(123)
        self.assertEqual(await self.count(ChannelConnectionCode), 0)
        self.assertEqual(await self.count(PlaylistChannel), 1)
        self.assertEqual(await self.count(ChannelPost), 1)
        self.assertEqual(await self.count(UserTrackSignal), 1)
        self.assertEqual(await self.count(Track), 1)
