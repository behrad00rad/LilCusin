"""Verified future-only playlist ingestion using the official Bot API."""

import asyncio
import hashlib
import re
import secrets
from datetime import timedelta

from sqlalchemy import delete, func, or_, select, update

from .models import ChannelConnectionCode, ChannelPost, ChatControl, PlaylistChannel, SongSubmission, User, UserTrackSignal, utc_now
from .workflow import FlowError

CODE_TTL = timedelta(minutes=10)
MAX_CHANNELS = 10


def code_hash(code):
    return hashlib.sha256(code.encode()).hexdigest()


class ChannelService:
    def __init__(self, database, workflow):
        self.database, self.workflow = database, workflow

    async def initialize(self):
        async with self.database.write() as session:
            await session.execute(update(ChannelPost).where(ChannelPost.status == 'processing').values(status='review'))

    async def new_code(self, telegram_user_id):
        code = 'PL-' + secrets.token_hex(24)
        async with self.database.write() as session:
            user_id = await session.scalar(select(User.id).where(User.telegram_user_id == telegram_user_id))
            if user_id is None:
                raise FlowError('stale')
            await session.execute(delete(ChannelConnectionCode).where(or_(ChannelConnectionCode.user_id == user_id,
                                                                          ChannelConnectionCode.expires_at <= utc_now())))
            session.add(ChannelConnectionCode(code_hash=code_hash(code), user_id=user_id, expires_at=utc_now() + CODE_TTL))
        return code

    async def connect(self, message, bot):
        code = (message.text or '').strip()
        if message.chat.type != 'channel' or not re.fullmatch(r'PL-[a-f0-9]{48}', code):
            return None
        digest = code_hash(code)
        async with self.database.sessions() as session:
            pending = await session.get(ChannelConnectionCode, digest)
            user = await session.get(User, pending.user_id) if pending else None
        if user is None:
            return None
        outcome = 'expired' if pending.expires_at <= utc_now() else 'connected'
        if outcome == 'connected':
            try:
                async with asyncio.timeout(8):
                    own = await bot.get_chat_member(message.chat.id, bot.id)
                    owner = await bot.get_chat_member(message.chat.id, user.telegram_user_id)
                if own.status != 'administrator':
                    outcome = 'permissions'
                elif owner.status not in {'creator', 'administrator'}:
                    outcome = 'not_admin'
            except Exception:
                # No exception body, code, API URL or identity is logged.
                return user.telegram_user_id, 'permissions'
        async with self.database.write() as session:
            pending = await session.get(ChannelConnectionCode, digest)
            if pending is None:  # Consumed concurrently, cancelled, or forgotten.
                return None
            if pending.expires_at <= utc_now():
                outcome = 'expired'
            await session.delete(pending)
            if outcome == 'connected':
                channel = await session.scalar(select(PlaylistChannel).where(PlaylistChannel.telegram_chat_id == message.chat.id))
                if channel and channel.user_id != user.id:
                    outcome = 'in_use'
                elif channel and channel.status == 'connected':
                    outcome = 'already'
                else:
                    count = await session.scalar(select(func.count()).select_from(PlaylistChannel).where(PlaylistChannel.user_id == user.id))
                    if channel is None and count >= MAX_CHANNELS:
                        outcome = 'limit'
                    else:
                        if channel is None:
                            channel = PlaylistChannel(user_id=user.id, telegram_chat_id=message.chat.id)
                            session.add(channel)
                        channel.title = (message.chat.title or '')[:200]
                        channel.status, channel.connected_at, channel.after_message_id = 'connected', message.date, message.message_id
        return user.telegram_user_id, outcome

    async def ingest(self, message):
        if message.chat.type != 'channel' or message.audio is None:
            return None
        async with self.database.write() as session:
            channel = await session.scalar(select(PlaylistChannel).where(PlaylistChannel.telegram_chat_id == message.chat.id,
                                                                         PlaylistChannel.status == 'connected'))
            if (channel is None or message.message_id <= channel.after_message_id or message.date < channel.connected_at):
                return None
            audio = message.audio
            duplicate = await session.scalar(select(ChannelPost.id).where(ChannelPost.channel_id == channel.id,
                or_(ChannelPost.message_id == message.message_id, ChannelPost.file_unique_id == audio.file_unique_id)))
            if duplicate is not None:
                return None
            owner = await session.get(User, channel.user_id)
            submission = SongSubmission(user_id=owner.id, submission_type='telegram_audio',
                parsed_artist=audio.performer, parsed_title=audio.title, file_id=audio.file_id,
                file_unique_id=audio.file_unique_id, original_filename=audio.file_name,
                mime_type=audio.mime_type, file_size=audio.file_size, duration=audio.duration)
            session.add(submission)
            await session.flush()
            post = ChannelPost(channel_id=channel.id, message_id=message.message_id,
                               file_unique_id=audio.file_unique_id, submission_id=submission.id)
            session.add(post)
            await session.flush()
            post_id, submission_id, user_id = post.id, submission.id, owner.telegram_user_id
        try:
            result = await self.workflow.start(submission_id, user_id)
        except FlowError:
            return None  # A concurrent /forgetme may have removed the submission.
        except Exception:
            async with self.database.write() as session:
                await session.execute(update(ChannelPost).where(ChannelPost.id == post_id).values(status='review'))
            raise
        async with self.database.write() as session:
            post = await session.get(ChannelPost, post_id)
            if post is None:
                return None
            if result.kind != 'confirmed':
                post.status = 'review'
        return user_id, result

    async def listing(self, user_id):
        async with self.database.sessions() as session:
            channels = (await session.scalars(select(PlaylistChannel).join(User).where(User.telegram_user_id == user_id)
                                              .order_by(PlaylistChannel.id).limit(MAX_CHANNELS))).all()
            ids = [row.id for row in channels]
            learned = dict((await session.execute(select(UserTrackSignal.channel_id, func.count())
                .where(UserTrackSignal.channel_id.in_(ids)).group_by(UserTrackSignal.channel_id))).all())
            review = dict((await session.execute(select(ChannelPost.channel_id, func.count())
                .where(ChannelPost.channel_id.in_(ids), ChannelPost.status.in_(['review', 'processing']))
                .group_by(ChannelPost.channel_id))).all())
        return [(row, learned.get(row.id, 0), review.get(row.id, 0)) for row in channels]

    async def control(self, token, user_id, message_id, action, index):
        async with self.database.write() as session:
            control = await session.scalar(select(ChatControl).join(User).where(
                ChatControl.token == token, User.telegram_user_id == user_id,
                ChatControl.message_id == message_id, ChatControl.expires_at > utc_now()))
            kind = 'channels' if action in {'choose', 'review'} else 'channel_disconnect'
            if control is None or control.payload['kind'] != kind or not 0 <= index < len(control.payload.get('links', [])):
                raise FlowError('stale')
            channel = await session.scalar(select(PlaylistChannel).where(PlaylistChannel.id == control.payload['links'][index],
                                                                        PlaylistChannel.user_id == control.user_id))
            key = f'{action}:{index}'
            if channel is None or key in control.payload['used']:
                raise FlowError('stale')
            control.payload = {**control.payload, 'used': [*control.payload['used'], key]}
            if action in {'keep', 'remove'}:
                await session.delete(control)
            return channel

    async def disconnect(self, user_id, channel_id, remove_signals):
        async with self.database.write() as session:
            channel = await session.scalar(select(PlaylistChannel).join(User).where(
                PlaylistChannel.id == channel_id, User.telegram_user_id == user_id))
            if channel is None:
                raise FlowError('stale')
            channel.status = 'disconnected'
            if remove_signals:
                await session.execute(delete(UserTrackSignal).where(UserTrackSignal.channel_id == channel.id))
                # Pending confirmations or a later reconnection must not restore erased signals.
                await session.execute(update(ChannelPost).where(ChannelPost.channel_id == channel.id).values(learn_allowed=False))

    async def review(self, user_id, channel_id):
        async with self.database.sessions() as session:
            submission_id = await session.scalar(select(ChannelPost.submission_id).join(PlaylistChannel).join(User)
                .where(PlaylistChannel.id == channel_id, User.telegram_user_id == user_id,
                       ChannelPost.status.in_(['review', 'processing'])).order_by(ChannelPost.id).limit(1))
        if submission_id is None:
            raise FlowError('stale')
        return await self.workflow.review_channel(submission_id, user_id)

    async def permission_change(self, chat_id, status):
        if status == 'administrator':
            return None  # A fresh code is required after removal/demotion; no backlog import.
        async with self.database.write() as session:
            channel = await session.scalar(select(PlaylistChannel).where(PlaylistChannel.telegram_chat_id == chat_id,
                                                                         PlaylistChannel.status == 'connected'))
            if channel is None:
                return None
            channel.status = 'unavailable'
            return await session.scalar(select(User.telegram_user_id).where(User.id == channel.user_id))
