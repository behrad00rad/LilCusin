"""Single durable worker; transport is injected, fetching returns only a local artifact.

Run one bot/worker per database. Sending is at-most-once after an ambiguous restart:
Telegram sendAudio has no idempotency key, so interrupted sends require a new tap.
"""
import asyncio
import os
import logging
import shutil
import tempfile
import weakref
import hashlib
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import delete, func, select
from .fetch_models import FetchJob, AudioRequest, AudioDelivery, AudioSource, AudioSelection
from .models import Track, User, utc_now
from .youtube_fetch import FetchError, YouTubeFetcher, confident, VIDEO
from .workflow import FlowError
from .lilbro_fetch import LilBroFetcher, configured_fetcher
from .audio_artwork import artwork_key, prepare as prepare_artwork

logger = logging.getLogger('music_bot')

ACTIVE = ('queued', 'running', 'choice')

@dataclass(frozen=True)
class FetchSettings:
    enabled: bool = False
    per_hour: int = 5
    queue_limit: int = 20
    per_user_queue: int = 2
    max_duration: int = 900
    max_bytes: int = 45_000_000
    timeout: int = 180
    disk_bytes: int = 150_000_000
    retention_days: int = 7

    @classmethod
    def environment(cls):
        values = {}
        for name in cls.__dataclass_fields__:
            if name == 'enabled':
                continue
            try:
                values[name] = int(os.getenv('GET_SONG_' + name.upper(), str(getattr(cls(), name))))
                if values[name] <= 0:
                    raise ValueError
            except ValueError:
                from .config import ConfigError
                raise ConfigError('Invalid Get song limit: ' + name) from None
        if values['max_bytes'] > 49_000_000 or values['disk_bytes'] < 2 * values['max_bytes']:
            from .config import ConfigError
            raise ConfigError('Get song file/disk limits are incompatible.')
        return cls(enabled=os.getenv('GET_SONG_ENABLED', 'false').lower() == 'true', **values)

class GetSong:
    def __init__(self, database, bot, settings=None, fetcher=None, artwork_loader=None):
        self.db, self.bot = database, bot
        self.settings = settings or FetchSettings.environment()
        self.fetcher = fetcher or configured_fetcher(self.settings, bot)
        self.artwork_loader = artwork_loader
        self.task = None
        self.delivery_locks = weakref.WeakValueDictionary()
        self.root = Path(tempfile.gettempdir()) / ('lilcusin-fetch-' + hashlib.sha256(str(database.engine.url).encode()).hexdigest()[:16])

    async def start(self):
        # Only this application's generated directory is cleared, before starting its sole worker.
        self.root.mkdir(parents=True, exist_ok=True)
        for entry in self.root.iterdir():
            if entry.is_dir() and not entry.is_symlink() and entry.name.startswith('job-'):
                shutil.rmtree(entry)
        async with self.db.write() as s:
            for job in (await s.scalars(select(FetchJob).where(FetchJob.state == 'running'))).all():
                job.state = 'queued'
            for req in (await s.scalars(select(AudioRequest).where(AudioRequest.state == 'sending'))).all():
                req.state = 'uncertain'
            for req in (await s.scalars(select(AudioRequest).where(AudioRequest.state == 'choice', AudioRequest.message_id.is_(None)))).all():
                req.state = 'failed'
            if not self.settings.enabled:
                for req in (await s.scalars(select(AudioRequest).where(AudioRequest.state.in_(('pending', 'choice'))))).all():
                    req.state = 'cancelled'
        self.task = asyncio.create_task(self.run())

    async def close(self):
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)

    async def request(self, user_id, track_id):
        if not self.settings.enabled:
            raise FetchError('Get song is disabled. The operator must configure source permissions first.')
        async with self.db.write() as s:
            user = await s.scalar(select(User).where(User.telegram_user_id == user_id))
            track = await s.get(Track, track_id)
            if user is None or track is None:
                raise FlowError('stale')
            if track.duration and track.duration > self.settings.max_duration:
                raise FetchError('This song exceeds the duration limit.')
            previous = await s.scalar(select(AudioRequest).join(FetchJob).where(AudioRequest.user_id == user.id,
                FetchJob.track_id == track_id, AudioRequest.state.in_(('pending', 'choice', 'sending'))))
            if previous:
                return previous.id
            await self.check_limits(s, user.id)
            selection = await s.scalar(select(AudioSelection).where(AudioSelection.user_id == user.id,
                                                                  AudioSelection.track_id == track_id))
            preferred = selection.video_id if selection else None
            key = (f'{track_id}:{preferred}' if preferred else
                   f'{track_id}:search:{user.id}' if selection else f'{track_id}:search')
            metadata = {}
            if preferred:
                source = await s.scalar(select(AudioSource).where(AudioSource.track_id == track_id,
                                                                  AudioSource.video_id == preferred))
                metadata = source.fetch_metadata if source else {}
            elif selection:
                metadata = {'force_choice': True}
            job = await s.scalar(select(FetchJob).where(FetchJob.key == key))
            if job is None:
                job = FetchJob(id=uuid4().hex, track_id=track_id, key=key,
                               video_id=preferred, metadata_json=metadata)
                s.add(job)
                await s.flush()
            elif job.state not in ACTIVE:
                job.state, job.candidates, job.video_id = 'queued', [], preferred
                job.metadata_json = metadata or (job.metadata_json if preferred else {})
            req = AudioRequest(id=uuid4().hex, user_id=user.id, job_id=job.id)
            s.add(req)
            await s.flush()
            return req.id

    async def check_limits(self, s, user_id):
        count = await s.scalar(select(func.count()).select_from(AudioRequest).where(AudioRequest.user_id == user_id,
            AudioRequest.created_at > utc_now() - timedelta(hours=1)))
        pending = await s.scalar(select(func.count()).select_from(AudioRequest).where(
            AudioRequest.state.in_(('pending', 'choice', 'sending'))))
        own = await s.scalar(select(func.count()).select_from(AudioRequest).where(AudioRequest.user_id == user_id,
            AudioRequest.state.in_(('pending', 'choice', 'sending'))))
        if count >= self.settings.per_hour or pending >= self.settings.queue_limit or own >= self.settings.per_user_queue:
            raise FetchError('Request limit reached. Please try later.')

    async def wrong(self, user_id, request_id, message_id):
        """Validate the delivered message, reject only this user's source, queue alternatives."""
        if not self.settings.enabled:
            raise FlowError('stale')
        async with self.delivery_locks.setdefault(user_id, asyncio.Lock()):
            async with self.db.write() as s:
                req = await s.scalar(select(AudioRequest).join(User).where(AudioRequest.id == request_id,
                    User.telegram_user_id == user_id, AudioRequest.message_id == message_id,
                    AudioRequest.state.in_(('done', 'reported')),
                    AudioRequest.created_at > utc_now() - timedelta(days=self.settings.retention_days)))
                if req is None or not req.delivered_video_id or not VIDEO.fullmatch(req.delivered_video_id):
                    raise FlowError('stale')
                original = await s.get(FetchJob, req.job_id)
                key = f'{original.track_id}:correction:{req.id}'
                if req.state == 'reported':
                    existing = await s.scalar(select(AudioRequest).join(FetchJob).where(
                        FetchJob.key == key, AudioRequest.user_id == req.user_id,
                        AudioRequest.state.in_(('pending', 'choice', 'sending'))))
                    if existing:
                        return existing.id
                    raise FlowError('stale')
                active = await s.scalar(select(AudioRequest.id).join(FetchJob).where(
                    AudioRequest.user_id == req.user_id, FetchJob.track_id == original.track_id,
                    AudioRequest.state.in_(('pending', 'choice', 'sending'))))
                if active:
                    raise FetchError('A request for this song is already active. Use /cancel first.')
                await self.check_limits(s, req.user_id)
                selection = await s.scalar(select(AudioSelection).where(AudioSelection.user_id == req.user_id,
                    AudioSelection.track_id == original.track_id))
                if selection is None:
                    selection = AudioSelection(user_id=req.user_id, track_id=original.track_id, rejected_ids=[])
                    s.add(selection)
                selection.rejected_ids = list(dict.fromkeys([*selection.rejected_ids, req.delivered_video_id]))[-64:]
                selection.video_id, selection.updated_at = None, utc_now()
                await s.execute(delete(AudioDelivery).where(AudioDelivery.user_id == req.user_id,
                    AudioDelivery.track_id == original.track_id, AudioDelivery.video_id == req.delivered_video_id))
                req.state = 'reported'
                job = FetchJob(id=uuid4().hex, track_id=original.track_id, key=key,
                               metadata_json={'force_choice': True})
                s.add(job)
                await s.flush()
                retry = AudioRequest(id=uuid4().hex, user_id=req.user_id, job_id=job.id)
                s.add(retry)
                await s.flush()
                return retry.id

    async def choose(self, user_id, request_id, message_id, index):
        if not self.settings.enabled:
            raise FlowError('stale')
        async with self.db.write() as s:
            req = await s.scalar(select(AudioRequest).join(User).where(AudioRequest.id == request_id,
                User.telegram_user_id == user_id, AudioRequest.state == 'choice', AudioRequest.message_id == message_id,
                AudioRequest.created_at > utc_now() - timedelta(minutes=30)))
            if req is None:
                raise FlowError('stale')
            job = await s.get(FetchJob, req.job_id)
            if not 0 <= index < len(job.candidates):
                raise FlowError('stale')
            video = job.candidates[index]['id']
            if not isinstance(video, str) or not VIDEO.fullmatch(video):
                raise FlowError('stale')
            selection = await s.scalar(select(AudioSelection).where(AudioSelection.user_id == req.user_id,
                                                                  AudioSelection.track_id == job.track_id))
            if selection and video in selection.rejected_ids:
                raise FlowError('stale')
            if selection is None:
                selection = AudioSelection(user_id=req.user_id, track_id=job.track_id, rejected_ids=[])
                s.add(selection)
            selection.video_id, selection.updated_at = video, utc_now()
            key = f'{job.track_id}:{video}'
            selected = await s.scalar(select(FetchJob).where(FetchJob.key == key))
            if selected is None:
                selected = FetchJob(id=uuid4().hex, key=key, track_id=job.track_id, video_id=video,
                                    candidates=[], metadata_json=job.candidates[index])
                s.add(selected)
                await s.flush()
            elif selected.state not in ACTIVE:
                selected.state = 'queued'
                selected.metadata_json = job.candidates[index]
            req.job_id, req.state = selected.id, 'pending'

    async def cancel(self, user_id, forget=False):
        # Serialize with the final ownership check and Telegram send, avoiding post-forget delivery.
        async with self.delivery_locks.setdefault(user_id, asyncio.Lock()):
            async with self.db.write() as s:
                ids = select(User.id).where(User.telegram_user_id == user_id)
                if forget:
                    await s.execute(delete(AudioRequest).where(AudioRequest.user_id.in_(ids)))
                    await s.execute(delete(AudioDelivery).where(AudioDelivery.user_id.in_(ids)))
                    await s.execute(delete(AudioSelection).where(AudioSelection.user_id.in_(ids)))
                else:
                    for req in (await s.scalars(select(AudioRequest).where(AudioRequest.user_id.in_(ids),
                            AudioRequest.state.in_(('pending', 'choice'))))).all():
                        req.state = 'cancelled'

    async def alive(self, job_id):
        async with self.db.sessions() as s:
            return bool(await s.scalar(select(AudioRequest.id).where(AudioRequest.job_id == job_id, AudioRequest.state == 'pending')))

    async def maintenance(self):
        async with self.db.write() as s:
            cutoff = utc_now() - timedelta(days=self.settings.retention_days)
            await s.execute(delete(AudioDelivery).where(AudioDelivery.created_at < cutoff))
            await s.execute(delete(AudioSource).where(AudioSource.fetched_at < cutoff))
            await s.execute(delete(AudioSelection).where(AudioSelection.updated_at < cutoff))
            await s.execute(delete(AudioRequest).where(AudioRequest.created_at < cutoff))
            for req in (await s.scalars(select(AudioRequest).where(AudioRequest.state == 'choice',
                    AudioRequest.created_at < utc_now() - timedelta(minutes=30)))).all():
                req.state = 'expired'
            orphan = ~select(AudioRequest.id).where(AudioRequest.job_id == FetchJob.id,
                        AudioRequest.state.in_(('pending', 'choice', 'sending'))).exists()
            for job in (await s.scalars(select(FetchJob).where(orphan, FetchJob.state.in_(ACTIVE)))).all():
                job.state = 'cancelled'
            await s.execute(delete(FetchJob).where(FetchJob.created_at < cutoff,
                ~select(AudioRequest.id).where(AudioRequest.job_id == FetchJob.id).exists()))

    async def run(self):
        while True:
            try:
                await self.maintenance()
                async with self.db.sessions() as s:
                    job = await s.scalar(select(FetchJob).where(FetchJob.state.in_(('queued', 'choice', 'done')),
                        select(AudioRequest.id).where(AudioRequest.job_id == FetchJob.id, AudioRequest.state == 'pending').exists())
                        .order_by(FetchJob.created_at))
                if job and self.settings.enabled:
                    await self.execute(job.id)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.error('Audio worker iteration failed; details omitted for privacy.')
            await asyncio.sleep(.5)

    async def state(self, job_id, state, **fields):
        async with self.db.write() as s:
            job = await s.get(FetchJob, job_id)
            if job:
                job.state, job.updated_at = state, utc_now()
                for k, v in fields.items():
                    setattr(job, k, v)

    async def execute(self, job_id):
        async with self.db.sessions() as s:
            job = await s.get(FetchJob, job_id)
            track = await s.get(Track, job.track_id)
        await self.state(job_id, 'running')
        try:
            if self.artwork_loader and not artwork_key(track):
                await self.artwork_loader.load(track.id)
                async with self.db.sessions() as s:
                    track = await s.get(Track, track.id)
            if not job.metadata_json.get('force_choice') or job.video_id:
                await self.deliver_cached(job, track)
            if not await self.alive(job_id):
                await self.state(job_id, 'done')
                return
            with tempfile.TemporaryDirectory(dir=self.root, prefix='job-') as directory:
                if shutil.disk_usage(directory).free < self.settings.disk_bytes:
                    raise FetchError('Temporary storage unavailable.')
                if not job.video_id:
                    rows = job.candidates or await self.fetcher.search(track, directory, lambda: self.alive(job_id))
                    async with self.db.sessions() as s:
                        selections = (await s.scalars(select(AudioSelection).where(AudioSelection.user_id.in_(
                            select(AudioRequest.user_id).where(AudioRequest.job_id == job_id,
                                                              AudioRequest.state == 'pending')),
                            AudioSelection.track_id == track.id))).all()
                    rejected = {video for selection in selections for video in selection.rejected_ids}
                    rows = [row for row in rows if row['id'] not in rejected]
                    if not rows:
                        if job.metadata_json.get('force_choice'):
                            await self.state(job_id, 'failed')
                            await self.fail(job_id, alternatives=True)
                            return
                        raise FetchError('No suitable source found.')
                    if job.metadata_json.get('force_choice') or not confident(rows):
                        await self.state(job_id, 'choice', candidates=rows)
                        await self.offer(job_id, rows)
                        return
                    job.video_id, job.metadata_json = rows[0]['id'], rows[0]
                    await self.state(job_id, 'running', video_id=job.video_id, metadata_json=rows[0])
                if isinstance(self.fetcher, LilBroFetcher):
                    async def persist(fields):
                        job.metadata_json = {**job.metadata_json, **fields}
                        await self.state(job_id, 'running', metadata_json=job.metadata_json)
                    path = await self.fetcher.fetch_selected(job.video_id, directory, lambda: self.alive(job_id),
                                                            job.metadata_json, persist)
                else:
                    path = await self.fetcher.fetch(job.video_id, directory, lambda: self.alive(job_id))
                thumbnail, cover_key = await prepare_artwork(self.fetcher, track, path, directory,
                                                            lambda: self.alive(job_id))
                async with self.db.write() as s:
                    await s.execute(delete(AudioSource).where(AudioSource.track_id == track.id, AudioSource.video_id == job.video_id))
                    s.add(AudioSource(track_id=track.id, video_id=job.video_id,
                        fetch_metadata={**{k: v for k, v in job.metadata_json.items() if not k.startswith('lilbro_')},
                                        'bytes': path.stat().st_size, 'container': path.suffix,
                                        'provider': 'youtube',
                                        'fetcher': 'lilbro' if isinstance(self.fetcher, LilBroFetcher) else 'yt-dlp'}))
                await self.deliver(job, track, path, thumbnail, cover_key)
                await self.state(job_id, 'done')
        except asyncio.CancelledError:
            raise
        except Exception:
            await self.state(job_id, 'failed')
            await self.fail(job_id)

    async def requests(self, job_id):
        async with self.db.sessions() as s:
            return (await s.execute(select(AudioRequest, User.telegram_user_id).join(User).where(
                AudioRequest.job_id == job_id, AudioRequest.state == 'pending'))).all()

    async def offer(self, job_id, rows):
        for req, user_id in await self.requests(job_id):
            async with self.delivery_locks.setdefault(user_id, asyncio.Lock()):
                async with self.db.write() as s:
                    current = await s.get(AudioRequest, req.id)
                    if current is None or current.state != 'pending':
                        continue
                    current.state = 'choice'
                try:
                    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(text=f"{i+1}. {r['title'][:45]} — {r.get('artist', '')[:25]} ({int(r['duration'])}s)" +
                            (' ⚠ duration differs' if r.get('duration_mismatch') else ''),
                            callback_data=f'g:{req.id}:{i}')]
                        for i, r in enumerate(rows)])
                    sent = await self.bot.send_message(user_id, 'Choose the recording you want, or /cancel.',
                                                       reply_markup=keyboard)
                    async with self.db.write() as s:
                        current = await s.get(AudioRequest, req.id)
                        if current:
                            current.message_id = sent.message_id
                except Exception:
                    await self.request_state(req.id, 'failed')

    async def request_state(self, request_id, state):
        async with self.db.write() as s:
            req = await s.get(AudioRequest, request_id)
            if req:
                req.state = state

    async def send(self, req, user_id, job, track, audio, thumbnail=None, cover_key=None):
        async with self.delivery_locks.setdefault(user_id, asyncio.Lock()):
            async with self.db.write() as s:
                current = await s.get(AudioRequest, req.id)
                if current is None or current.state != 'pending':
                    return
                selection = await s.scalar(select(AudioSelection).where(AudioSelection.user_id == req.user_id,
                                                                      AudioSelection.track_id == track.id))
                if selection and job.video_id in selection.rejected_ids:
                    current.state = 'failed'
                    return
                current.state = 'sending'
            try:
                extra = {'thumbnail': FSInputFile(thumbnail)} if thumbnail else {}
                sent = await self.bot.send_audio(user_id, audio=audio, title=track.display_title or track.title,
                    performer=track.display_artist or track.artist, request_timeout=self.settings.timeout,
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
                        text='Wrong song', callback_data=f'w:{req.id}')]]), **extra)
            except TelegramBadRequest:
                await self.request_state(req.id, 'pending')
                raise
            except Exception:
                await self.request_state(req.id, 'uncertain')
                return
            async with self.db.write() as s:
                current = await s.get(AudioRequest, req.id)
                if current:
                    current.state = 'done'
                    current.message_id, current.delivered_video_id = sent.message_id, job.video_id
                    await s.execute(delete(AudioDelivery).where(AudioDelivery.user_id == req.user_id,
                        AudioDelivery.track_id == track.id, AudioDelivery.video_id == job.video_id))
                    s.add(AudioDelivery(user_id=req.user_id, track_id=track.id, video_id=job.video_id,
                        file_id=sent.audio.file_id, message_id=sent.message_id, artwork_key=cover_key))

    async def deliver_cached(self, job, track):
        for req, user_id in await self.requests(job.id):
            async with self.db.sessions() as s:
                query = select(AudioDelivery).where(AudioDelivery.user_id == req.user_id, AudioDelivery.track_id == track.id)
                selection = await s.scalar(select(AudioSelection).where(AudioSelection.user_id == req.user_id,
                                                                      AudioSelection.track_id == track.id))
                if selection:
                    query = query.where(AudioDelivery.video_id.not_in(selection.rejected_ids))
                    if selection.video_id:
                        query = query.where(AudioDelivery.video_id == selection.video_id)
                if job.video_id:
                    query = query.where(AudioDelivery.video_id == job.video_id)
                cached = await s.scalar(query.order_by(AudioDelivery.created_at.desc()))
            if cached:
                if artwork_key(track) and cached.artwork_key != artwork_key(track):
                    continue  # Upgrade an old coverless file once; subsequent sends reuse it.
                cached_job = FetchJob(id=job.id, track_id=track.id, video_id=cached.video_id)
                try:
                    await self.send(req, user_id, cached_job, track, cached.file_id, cover_key=cached.artwork_key)
                except TelegramBadRequest as error:
                    # Only a definite invalid reference authorizes fetching a replacement.
                    message = error.message.lower()
                    if any(part in message for part in ('wrong file identifier', 'file reference', 'file_id', 'file identifier')):
                        async with self.db.write() as s:
                            await s.execute(delete(AudioDelivery).where(AudioDelivery.id == cached.id))
                    else:
                        await self.request_state(req.id, 'failed')

    async def deliver(self, job, track, path, thumbnail=None, cover_key=None):
        for req, user_id in await self.requests(job.id):
            try:
                await self.send(req, user_id, job, track, FSInputFile(path), thumbnail, cover_key)
            except TelegramBadRequest:
                await self.request_state(req.id, 'failed')

    async def fail(self, job_id, alternatives=False):
        async with self.db.sessions() as s:
            job = await s.get(FetchJob, job_id)
            video = job.video_id if job else None
        keyboard = None
        if isinstance(video, str) and VIDEO.fullmatch(video):
            keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
                text='Listen on YouTube', url='https://www.youtube.com/watch?v=' + video)]])
        for req, user_id in await self.requests(job_id):
            async with self.delivery_locks.setdefault(user_id, asyncio.Lock()):
                await self.request_state(req.id, 'failed')
                try:
                    await self.bot.send_message(user_id,
                        ('No other matching recordings were found. Try Get song again later.' if alternatives else
                         'Could not fetch this recording. Try Get song again later.') +
                        (' You can still listen using the link below.' if keyboard else ''),
                        reply_markup=keyboard)
                except Exception:
                    pass
