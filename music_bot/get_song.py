"""Bounded durable worker; transport is injected, fetching returns a local artifact.

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
from time import monotonic
from dataclasses import dataclass
from datetime import timedelta, datetime
from pathlib import Path
from uuid import uuid4

from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError, TelegramForbiddenError
from aiogram.types import FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import delete, func, select
from sqlalchemy.exc import SQLAlchemyError
from .fetch_models import FetchJob, AudioRequest, AudioDelivery, AudioSource, AudioSelection
from .models import Track, User, utc_now
from .youtube_fetch import FetchError, YouTubeFetcher, confident, VIDEO, approved_source, SOURCE_POLICIES
from .workflow import FlowError
from .lilbro_fetch import LilBroFetcher, configured_fetcher
from .audio_artwork import artwork_key, prepare as prepare_artwork, tag_metadata
from .bot_copy import text as copy
from .i18n import language

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
    workers: int = 2

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
        if (values['max_bytes'] > 49_000_000 or values['disk_bytes'] < 2 * values['max_bytes']
                or values['workers'] > 4):
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
        self.jobs = {}
        self.recognizer = None
        self.art_attempted = set()
        self.metadata_cache = {}
        self.receipt_recovery = {}
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
        album_tasks = list(getattr(self, "album_tasks", {}).values())
        for task in album_tasks:task.cancel()
        await asyncio.gather(*album_tasks, return_exceptions=True)
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
        for task in self.jobs.values():
            task.cancel()
        await asyncio.gather(*self.jobs.values(), return_exceptions=True)
        self.jobs.clear()

    async def begin(self, message, user_id, track_id, *, other_versions=False):
        """Attach one durable status, including when the request already exists."""
        from .chat_ui import cancel_keyboard
        # Retire previous terminal status messages before creating another job UI.
        async with self.db.sessions() as session:
            old = (await session.execute(select(AudioRequest.id, AudioRequest.status_message_id).join(User).where(
                User.telegram_user_id == user_id, AudioRequest.state.in_(['failed', 'cancelled', 'done']),
                AudioRequest.status_message_id.is_not(None)).order_by(AudioRequest.created_at.desc()).limit(20))).all()
        for rid, mid in old:
            try:
                await self.bot.delete_message(user_id, mid)
                async with self.db.write() as session:
                    row = await session.get(AudioRequest, rid)
                    if row:
                        row.status_message_id = None
            except Exception:
                pass
        pending = await message.answer(copy('queued'), reply_markup=cancel_keyboard())
        try:
            request_id = await self.request(user_id, track_id, other_versions=other_versions)
            if not other_versions:
                await self.cached_request(user_id, request_id)
            await self.bind_status(user_id, request_id, pending.message_id)
            return request_id
        except FetchError:
            token, keyboard = await self.retry_keyboard(user_id, track_id)
            await pending.edit_text(copy('failed'), reply_markup=keyboard)
            from .chat_service import ChatService
            await ChatService(self.db, None).bind_control(token, pending.message_id)
            return None

    async def cached_request(self, user_id, request_id):
        async with self.db.sessions() as session:
            req = await session.scalar(select(AudioRequest).join(User).where(
                AudioRequest.id == request_id, User.telegram_user_id == user_id, AudioRequest.state == 'pending'))
            if req is None:
                return
            job = await session.get(FetchJob, req.job_id)
            track = await session.get(Track, job.track_id)
        if not job.metadata_json.get('force_choice') or job.video_id:
            await self.deliver_cached(job, track)

    async def retry_keyboard(self, user_id, track_id):
        from .chat_service import ChatService
        from .chat_ui import button
        controls = ChatService(self.db, None)
        token = await controls.create_control(user_id, tracks=[track_id], kind='card')
        return token, InlineKeyboardMarkup(inline_keyboard=[[
            button(token, 'get', copy('retry'), 0), button(token, 'versions', copy('versions'), 0)]])

    async def bind_status(self, user_id, request_id, message_id):
        async with self.delivery_locks.setdefault(user_id, asyncio.Lock()):
            async with self.db.write() as session:
                req = await session.scalar(select(AudioRequest).join(User).where(
                    AudioRequest.id == request_id, User.telegram_user_id == user_id))
                if req is None:
                    raise FlowError('stale')
                old = req.status_message_id
                req.status_message_id = message_id
                state, job_id = req.state, req.job_id
            if old and old != message_id:
                try:
                    await self.bot.delete_message(user_id, old)
                except Exception:
                    pass
            if state == 'choice':
                async with self.db.sessions() as session:
                    job = await session.get(FetchJob, job_id)
                await self.show_choices(req, user_id, job.candidates)
            else:
                key = {'pending': 'queued', 'sending': 'sending', 'done': 'delivered',
                       'cancelled': 'cancelled', 'failed': 'failed', 'uncertain': 'uncertain'}.get(state, 'queued')
                await self.progress(request_id, key, locked=True)

    async def progress(self, request_id, key, keyboard=None, *, locked=False):
        if not locked:
            async with self.db.sessions() as session:
                user_id = await session.scalar(select(User.telegram_user_id).join(AudioRequest).where(AudioRequest.id == request_id))
            if user_id is None:
                return
            async with self.delivery_locks.setdefault(user_id, asyncio.Lock()):
                return await self.progress(request_id, key, keyboard, locked=True)
        from .preferences import preferences
        from .chat_service import ChatService
        from .chat_ui import cancel_keyboard, card_keyboard
        async with self.db.sessions() as session:
            result = (await session.execute(select(AudioRequest, User.telegram_user_id, FetchJob.track_id, FetchJob.metadata_json)
                .join(User, User.id == AudioRequest.user_id).join(FetchJob, FetchJob.id == AudioRequest.job_id)
                .where(AudioRequest.id == request_id))).first()
        if not result or not result[0].status_message_id:
            return
        req, user_id, track_id, job_metadata = result
        if key == 'delivered':
            try:
                await self.bot.delete_message(user_id, req.status_message_id)
                async with self.db.write() as session:
                    row = await session.get(AudioRequest, request_id)
                    if row:
                        row.status_message_id = None
            except Exception:
                pass
            return
        # Late worker updates must not resurrect cancelled/failed requests.
        if req.state in {'cancelled', 'failed', 'uncertain', 'done'} and key not in {'cancelled', 'failed', 'uncertain', 'delivered'}:
            return
        context = None
        token = None
        try:
            prefs = await preferences(self.db, user_id)
            context = language.set(prefs['language'])
            async with self.db.sessions() as session:
                track = await session.get(Track, track_id)
            heading = copy('song', artist=track.display_artist or track.artist, title=track.display_title or track.title)
            if keyboard is None:
                if key in {'queued', 'searching', 'recordings_searching', 'fetching', 'sending'}:
                    keyboard = cancel_keyboard(request_id)
                elif key in {'failed', 'uncertain'}:
                    token, keyboard = await self.retry_keyboard(user_id, track_id)
            if token:
                await ChatService(self.db, None).bind_control(token, req.status_message_id)
            status_key = key
            if key == 'failed' and job_metadata.get('failure_phase') in {'search', 'download', 'prepare', 'send', 'choice'}:
                status_key = ('failed_no_match' if job_metadata.get('failure_reason') == 'no_matching_candidate'
                              else 'failed_' + job_metadata['failure_phase'])
            from .recording_fallback import available, keyboard as recording_keyboard
            if key == 'failed' and available(job_metadata):
                keyboard = recording_keyboard(request_id,keyboard)
                if job_metadata.get('recording_discovery'):
                    status_key = 'recordings_unavailable' if job_metadata.get('failure_reason') == 'recording_discovery_unavailable' else 'recordings_empty'
            async with asyncio.timeout(4):
                await self.bot.edit_message_text(heading + '\n\n' + copy(status_key), chat_id=user_id, message_id=req.status_message_id, reply_markup=keyboard)
        except Exception:
            pass  # Presentation failure must not fail or repeat audio delivery.
        finally:
            if context is not None:
                language.reset(context)

    async def choice_language(self, user_id):
        from .preferences import preferences
        try:
            async with asyncio.timeout(1):
                return (await preferences(self.db, user_id))['language']
        except Exception as error:
            logger.warning('Choice language lookup failed (%s); defaulting to English.', type(error).__name__)
            return 'en'

    async def show_choices(self, req, user_id, rows):
        if (req.canonical_metadata or {}).get('_daily_pick'):
            await self.request_state(req.id, 'failed')
            return  # A daily pick must not become a recording-choice notification.
        context = language.set(await self.choice_language(user_id))
        try:
            details = [copy('choice_unverified' if any(r.get('source_policy') == 'explicit-discovery-v1' for r in rows) else 'choice')]
            buttons = []
            for i, row in enumerate(rows):
                duration = int(row['duration'])
                from .recording_metadata import edition_label
                edition = edition_label(row.get('version', []), language.get()) or ('بدون برچسب نسخه' if language.get() == 'fa' else 'Unlabelled version')
                details.append(f"{i + 1}. {row['title']}\n{row.get('artist', '')} · {duration // 60}:{duration % 60:02d} · {edition}")
                if row.get('duration_mismatch'):
                    details.append('⚠ مدت متفاوت است' if language.get() == 'fa' else '⚠ Duration differs from the catalogue')
                if row.get('title_mismatch'):
                    details.append('⚠ املای عنوان متفاوت است؛ پیش از انتخاب بررسی کن' if language.get() == 'fa' else '⚠ Title spelling differs; check before choosing')
                label = 'دریافت' if language.get() == 'fa' else 'Get'
                buttons.append([InlineKeyboardButton(text=f"{label} {i + 1} · {duration // 60}:{duration % 60:02d} · {edition}", callback_data=f'g:{req.id}:{i}')])
            choice_text = '\n\n'.join(details)
            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
            keyboard.inline_keyboard.extend([
                [InlineKeyboardButton(text=copy('versions'), callback_data=f'v:{req.id}')],
                [InlineKeyboardButton(text=copy('close'), callback_data=f'closereq:{req.id}')]])
            async with asyncio.timeout(4):
                if req.status_message_id:
                    try:
                        await self.bot.edit_message_text(choice_text, chat_id=user_id,
                            message_id=req.status_message_id, reply_markup=keyboard)
                        message_id = req.status_message_id
                    except TelegramBadRequest as error:
                        if 'message is not modified' in error.message.lower():
                            message_id = req.status_message_id
                        else:
                            sent = await self.bot.send_message(user_id, choice_text, reply_markup=keyboard)
                            message_id = sent.message_id
                else:
                    sent = await self.bot.send_message(user_id, choice_text, reply_markup=keyboard)
                    message_id = sent.message_id
            persisted = False
            async with self.db.write() as session:
                current = await session.get(AudioRequest, req.id)
                if current and current.state in {'pending', 'choice'}:
                    current.message_id, current.state = message_id, 'choice'
                    if req.status_message_id:
                        current.status_message_id = message_id
                    persisted = True
            if not persisted:
                try:
                    async with asyncio.timeout(2):
                        await self.bot.edit_message_reply_markup(chat_id=user_id, message_id=message_id, reply_markup=None)
                except Exception:
                    pass
            return persisted
        finally:
            language.reset(context)

    async def request(self, user_id, track_id, *, other_versions=False, learn=True, daily_pick=None):
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
            selection = await s.scalar(select(AudioSelection).where(AudioSelection.user_id == user.id,
                                                                  AudioSelection.track_id == track_id))
            if previous and selection and selection.video_id and not other_versions:
                previous_job = await s.get(FetchJob, previous.job_id)
                if previous_job.video_id != selection.video_id and previous.state != 'sending':
                    previous.state = 'cancelled'
                    previous = None
            if previous and not other_versions:
                if daily_pick:
                    return None  # Preserve a user's existing foreground request.
                return previous.id
            await self.check_limits(s, user.id)
            preferred = selection.video_id if selection else None
            key = (f'{track_id}:{preferred}' if preferred else
                   f'{track_id}:search:{user.id}' if selection else f'{track_id}:search')
            metadata = {}
            if preferred:
                source = await s.scalar(select(AudioSource).where(AudioSource.track_id == track_id,
                                                                  AudioSource.video_id == preferred))
                metadata = source.fetch_metadata if source else {}
                if isinstance(self.fetcher, YouTubeFetcher) and not approved_source(metadata, alternatives=True):
                    # Legacy manual choices did not establish recording provenance.
                    selection.video_id = preferred = None
                    key = f'{track_id}:search:{user.id}'
                    metadata = {'force_choice': True}
            elif selection:
                metadata = {'force_choice': True}
            if other_versions:
                key, preferred = f'{track_id}:versions:{user.id}', None
                metadata = {'force_choice': True, 'other_versions': True}
                existing = await s.scalar(select(AudioRequest).join(FetchJob).where(
                    AudioRequest.user_id == user.id, FetchJob.key == key,
                    AudioRequest.state.in_(('pending', 'choice', 'sending'))))
                if existing:
                    return existing.id
            job = await s.scalar(select(FetchJob).where(FetchJob.key == key))
            if job is None:
                job = FetchJob(id=uuid4().hex, track_id=track_id, key=key,
                               video_id=preferred, metadata_json=metadata)
                s.add(job)
                await s.flush()
            elif job.state not in ACTIVE:
                job.state, job.candidates, job.video_id = 'queued', [], preferred
                job.metadata_json = metadata or (job.metadata_json if preferred else {})
            snapshot = dict(selection.canonical_metadata or {}) if selection and preferred and not other_versions else {}
            if daily_pick:
                snapshot['_daily_pick'] = daily_pick
            req = AudioRequest(id=uuid4().hex, user_id=user.id, job_id=job.id, canonical_metadata=snapshot)
            s.add(req)
            await s.flush()
            if not other_versions and learn and not daily_pick:
                from .taste_learning import record_request
                await record_request(s, user.id, track_id, req.id)
            request_id = req.id
        recommendations = getattr(self, 'recommendations', None)
        if recommendations is not None:
            recommendations.queue.warm(user_id)
        return request_id

    async def request_recognized(self, user_id, artist, title, *, artwork_url=None, album=None):
        """Queue an identified recording without inventing ratings or submissions."""
        if not self.settings.enabled:
            raise FetchError('Get song is disabled. The operator must configure source permissions first.')
        from sqlalchemy.dialects.sqlite import insert
        from .catalog import canonical_track
        from .providers.common import TrackCandidate
        from .chat_ui import safe_url
        async with self.db.write() as session:
            await session.execute(insert(User).values(telegram_user_id=user_id)
                .on_conflict_do_nothing(index_elements=['telegram_user_id']))
            track = await canonical_track(session, TrackCandidate(artist=artist, title=title, source='shazam',
                artwork_url=safe_url(artwork_url, artwork=True), album=album))
            track_id = track.id
        return await self.request(user_id, track_id)

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
            chosen = dict(job.candidates[index])
            if job.metadata_json.get('other_versions'):
                chosen['source_policy'] = 'explicit-alternative-v1'
            elif isinstance(self.fetcher, YouTubeFetcher) and not approved_source(chosen, alternatives=True):
                raise FlowError('stale')
            job.candidates = [chosen if i == index else row for i, row in enumerate(job.candidates)]
            video = job.candidates[index]['id']
            if not isinstance(video, str) or not VIDEO.fullmatch(video):
                raise FlowError('stale')
            target_track_id = job.track_id
            if job.metadata_json.get('other_versions'):
                from .catalog import canonical_track
                from .providers.common import TrackCandidate
                from .youtube_fetch import without_artist_credit
                original = await s.get(Track, job.track_id)
                row = job.candidates[index]
                artist = original.display_artist or original.artist
                title = row.get('recording_title') or without_artist_credit(row['title'], artist)
                import re
                title = re.sub(r'\s*[\[(](?:official\s+)?(?:audio|video|lyrics?)[\])]\s*', ' ', title, flags=re.I).strip()
                target = await canonical_track(s, TrackCandidate(artist=artist, title=title,
                    duration=row['duration'], source='youtube'))
                target_track_id = target.id
            selection = await s.scalar(select(AudioSelection).where(AudioSelection.user_id == req.user_id,
                                                                  AudioSelection.track_id == target_track_id))
            if selection and video in selection.rejected_ids:
                raise FlowError('stale')
            if selection is None:
                selection = AudioSelection(user_id=req.user_id, track_id=target_track_id, rejected_ids=[])
                s.add(selection)
            from .recording_metadata import canonical_snapshot
            from .providers.common import TrackCandidate
            row = job.candidates[index]
            target = await s.get(Track, target_track_id)
            searched_artist = target.display_artist or target.artist if target.metadata_source != 'youtube_recording' else None
            snapshot = canonical_snapshot(TrackCandidate(row.get('recording_title') or row['title'],
                row.get('artist') or '',
                'youtube_music' if row.get('source_policy') == 'catalogue-music-v1' else 'youtube_recording',
                duration=row.get('duration'),
                external_ids={'youtube':video}), searched_artist=searched_artist)
            from .recording_metadata import snapshot_metadata
            proposed = row.get('canonical_metadata')
            if row.get('source_policy') == 'explicit-discovery-v1' and snapshot_metadata(proposed,video) is not None:
                snapshot = dict(proposed)
            selection.canonical_metadata = snapshot
            req.canonical_metadata = snapshot
            selection.video_id, selection.updated_at = video, utc_now()
            key = f'{target_track_id}:{video}'
            selected = await s.scalar(select(FetchJob).where(FetchJob.key == key))
            if selected is None:
                selected = FetchJob(id=uuid4().hex, key=key, track_id=target_track_id, video_id=video,
                                    candidates=[], metadata_json=job.candidates[index])
                s.add(selected)
                await s.flush()
            elif selected.state not in ACTIVE:
                selected.state = 'queued'
                selected.metadata_json = job.candidates[index]
            req.job_id, req.state = selected.id, 'pending'

    async def other_versions(self, user_id, request_id, message_id):
        async with self.db.sessions() as session:
            req = await session.scalar(select(AudioRequest).join(User).where(
                AudioRequest.id == request_id, User.telegram_user_id == user_id,
                AudioRequest.message_id == message_id, AudioRequest.state.in_(('choice', 'done', 'reported')),
                AudioRequest.created_at > utc_now() - timedelta(days=self.settings.retention_days)))
            if req is None:
                raise FlowError('stale')
            track_id = (await session.get(FetchJob, req.job_id)).track_id
        return await self.request(user_id, track_id, other_versions=True)

    async def bind_recognition_versions(self, user_id, request_id, message):
        from .chat_service import ChatService
        from .chat_ui import button
        async with self.db.sessions() as session:
            request = await session.scalar(select(AudioRequest).join(User).where(
                AudioRequest.id == request_id, User.telegram_user_id == user_id))
            if request is None:
                raise FlowError('stale')
            track_id = (await session.get(FetchJob, request.job_id)).track_id
        controls = ChatService(self.db, None)
        token = await controls.create_control(user_id, tracks=[track_id], kind='card')
        await message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            button(token, 'versions', 'Find other versions', 0)]]))
        await controls.bind_control(token, message.message_id)

    async def shazam_artwork(self, track, path, directory, alive, *, force=False):
        """Identify downloaded audio for artwork when catalogue enrichment is missing."""
        from .recognition import ffmpeg_executable
        from .chat_ui import safe_url
        from .artwork import matches_artwork
        try:
            if len(self.art_attempted) >= 500:
                self.art_attempted.pop()
            self.art_attempted.add(track.id)
            sample = Path(directory) / 'artwork-sample.wav'
            await self.fetcher.process([ffmpeg_executable(), '-nostdin', '-v', 'error', '-y',
                '-i', str(path), '-t', '12', '-vn', '-ac', '1', '-ar', '22050',
                '-codec:a', 'pcm_s16le', str(sample)], directory, alive)
            result = await self.recognizer.recognize(sample)
            artist, title = track.display_artist or track.artist, track.display_title or track.title
            if (not result or not safe_url(result.artwork_url, artwork=True)
                    or not matches_artwork(artist, title, result)):
                return
            async with self.db.write() as session:
                current = await session.get(Track, track.id)
                if current and (force or not artwork_key(current)):
                    current.artwork_url = result.artwork_url
                    if not current.album:
                        current.album = result.album
                    track.artwork_url, track.album = current.artwork_url, current.album
        except asyncio.CancelledError:
            raise
        except Exception:
            pass  # Artwork is optional; never replace audio delivery with an art error.
        finally:
            (Path(directory) / 'artwork-sample.wav').unlink(missing_ok=True)

    async def cancel(self, user_id, forget=False):
        task = getattr(self, "album_tasks", {}).pop(user_id, None)
        if task:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        # Serialize with the final ownership check and Telegram send, avoiding post-forget delivery.
        cancelled = []
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
                        cancelled.append(req.id)
            for request_id in cancelled:
                await self.progress(request_id, 'cancelled', locked=True)

    async def cancel_request(self, user_id, request_id, message_id):
        async with self.delivery_locks.setdefault(user_id, asyncio.Lock()):
            async with self.db.write() as session:
                req = await session.scalar(select(AudioRequest).join(User).where(
                    AudioRequest.id == request_id, User.telegram_user_id == user_id,
                    AudioRequest.status_message_id == message_id, AudioRequest.state.in_(('pending', 'choice'))))
                if req is None:
                    raise FlowError('stale')
                req.state = 'cancelled'
            await self.progress(request_id, 'cancelled', locked=True)

    async def alive(self, job_id):
        async with self.db.sessions() as s:
            return bool(await s.scalar(select(AudioRequest.id).where(AudioRequest.job_id == job_id, AudioRequest.state == 'pending')))

    async def maintenance(self):
        # Retain acknowledged receipts through a temporary database outage.
        # Missing/deleted requests are never recreated by persist_receipt.
        for request_id, args in list(self.receipt_recovery.items()):
            try:
                await self.persist_receipt(*args)
            except SQLAlchemyError:
                continue
            self.receipt_recovery.pop(request_id, None)
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
                for job_id, task in list(self.jobs.items()):
                    if task.done():
                        await asyncio.gather(task, return_exceptions=True)
                        self.jobs.pop(job_id)
                await self.maintenance()
                async with self.db.sessions() as s:
                    jobs = (await s.scalars(select(FetchJob).where(FetchJob.state.in_(('queued', 'choice', 'done')),
                        FetchJob.id.not_in(list(self.jobs)),
                        select(AudioRequest.id).where(AudioRequest.job_id == FetchJob.id, AudioRequest.state == 'pending').exists())
                        .order_by(FetchJob.created_at).limit(max(0, self.settings.workers - len(self.jobs))))).all()
                if self.settings.enabled:
                    for job in jobs:
                        self.jobs[job.id] = asyncio.create_task(self.execute(job.id))
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
        phase = 'search'
        try:
            if job.metadata_json.get('recording_discovery') and not job.video_id:
                from .recording_fallback import finish
                await finish(self,job_id)
                return
            if (isinstance(self.fetcher, YouTubeFetcher) and job.video_id
                    and not approved_source(job.metadata_json, alternatives=True)):
                job.video_id, job.candidates = None, []
                await self.state(job_id, 'running', video_id=None, candidates=[])
            if not job.metadata_json.get('force_choice') or job.video_id:
                await self.deliver_cached(job, track)
            if not await self.alive(job_id):
                await self.state(job_id, 'done')
                return
            for req, _ in await self.requests(job_id):
                await self.progress(req.id, 'searching')
            with tempfile.TemporaryDirectory(dir=self.root, prefix='job-') as directory:
                if shutil.disk_usage(directory).free < self.settings.disk_bytes:
                    raise FetchError('Temporary storage unavailable.')
                if not job.video_id:
                    search_track = track
                    if job.metadata_json.get('other_versions'):
                        from types import SimpleNamespace
                        from .youtube_fetch import base_title
                        search_track = SimpleNamespace(artist=track.display_artist or track.artist,
                            title=base_title(track.display_title or track.title), duration=None, allow_versions=True)
                    rows = job.candidates
                    if isinstance(self.fetcher, YouTubeFetcher) and not job.metadata_json.get('other_versions'):
                        rows = [row for row in rows if approved_source(row)]
                    if not rows:
                        try:
                            rows = await self.fetcher.search(search_track, directory, lambda: self.alive(job_id))
                        except FetchError:
                            if not await self.alive(job_id):
                                return
                            logger.warning('Audio source search failed; retrying once.')
                            await asyncio.sleep(.5)
                            rows = await self.fetcher.search(search_track, directory, lambda: self.alive(job_id))
                    if isinstance(self.fetcher, YouTubeFetcher) and not job.metadata_json.get('other_versions'):
                        rows = [row for row in rows if approved_source(row)]
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
                phase = 'download'
                for req, _ in await self.requests(job_id):
                    await self.progress(req.id, 'fetching')
                if isinstance(self.fetcher, LilBroFetcher):
                    async def persist(fields):
                        job.metadata_json = {**job.metadata_json, **fields}
                        await self.state(job_id, 'running', metadata_json=job.metadata_json)
                    path = await self.fetcher.fetch_selected(job.video_id, directory, lambda: self.alive(job_id),
                                                            job.metadata_json, persist)
                else:
                    try:
                        path = await self.fetcher.fetch(job.video_id, directory, lambda: self.alive(job_id))
                    except FetchError:
                        if not await self.alive(job_id):
                            return
                        logger.warning('Audio source download failed; retrying once.')
                        await asyncio.sleep(.5)
                        path = await self.fetcher.fetch(job.video_id, directory, lambda: self.alive(job_id))
                phase = 'prepare'
                from types import SimpleNamespace
                pending = await self.requests(job_id)
                snapshot = pending[0][0].canonical_metadata if pending else None
                metadata = await self.delivery_metadata(track, snapshot=snapshot, video=job.video_id)
                from .recording_metadata import snapshot_metadata
                canonical_art = snapshot_metadata(snapshot,job.video_id) is not None
                art_track = (SimpleNamespace(id=track.id, title=metadata.title, artist=metadata.artist,
                    display_title=None, display_artist=None, duration=track.duration,
                    album=metadata.album, artwork_url=metadata.artwork_url or track.artwork_url)
                    if canonical_art else track)
                thumbnail, cover_key = None, None
                try:
                    async with asyncio.timeout(8):
                        if self.artwork_loader and not canonical_art and not artwork_key(track):
                            await self.artwork_loader.load(track.id)
                            async with self.db.sessions() as s:
                                track = await s.get(Track, track.id)
                                art_track = track
                        if self.recognizer and not artwork_key(art_track):
                            await self.shazam_artwork(art_track, path, directory, lambda: self.alive(job_id))
                        thumbnail, cover_key = await prepare_artwork(self.fetcher, art_track, path, directory,
                                                                    lambda: self.alive(job_id))
                        if not thumbnail and self.recognizer and track.id not in self.art_attempted:
                            await self.shazam_artwork(art_track, path, directory, lambda: self.alive(job_id), force=True)
                            thumbnail, cover_key = await prepare_artwork(self.fetcher, art_track, path, directory,
                                                                        lambda: self.alive(job_id))
                except TimeoutError:
                    logger.warning('Artwork preparation timed out after 8 seconds; sending audio without artwork.')
                except Exception:
                    logger.warning('Artwork preparation failed; sending audio without artwork. Details omitted for privacy.')
                async with self.db.write() as s:
                    previous_source = await s.scalar(select(AudioSource).where(AudioSource.track_id == track.id, AudioSource.video_id == job.video_id))
                    previous = previous_source.fetch_metadata if previous_source else {}
                    await s.execute(delete(AudioSource).where(AudioSource.track_id == track.id, AudioSource.video_id == job.video_id))
                    s.add(AudioSource(track_id=track.id, video_id=job.video_id,
                        fetch_metadata={**previous, **{k: v for k, v in job.metadata_json.items() if not k.startswith('lilbro_')},
                                        'bytes': path.stat().st_size, 'container': path.suffix,
                                        'provider': 'youtube',
                                        'fetcher': 'lilbro' if isinstance(self.fetcher, LilBroFetcher) else 'yt-dlp'}))
                phase = 'send'
                await self.deliver(job, track, path, thumbnail, cover_key)
                await self.state(job_id, 'done')
        except asyncio.CancelledError:
            raise
        except Exception as error:
            logger.warning('Audio delivery failed at %s (%s); details omitted for privacy.', phase, type(error).__name__)
            if isinstance(error, FetchError):
                known = {'Audio source unavailable.': 'source_unavailable', 'Request cancelled.': 'cancelled',
                         'No suitable source found.': 'no_matching_candidate',
                         'Source search unavailable.': 'search_unavailable',
                         'Source metadata unavailable.': 'invalid_source_metadata',
                         'Audio unavailable or too large.': 'file_limit',
                         'Fetched media is unsupported or exceeds limits.': 'validation',
                         'Temporary storage limit reached.': 'storage_limit'}
                logger.warning('Audio delivery failure category: %s.', known.get(str(error), 'other'))
            reason = ('no_matching_candidate' if isinstance(error, FetchError) and str(error) == 'No suitable source found.'
                      else 'search_unavailable' if phase == 'search' else phase + '_failed')
            if (phase == 'search' and isinstance(error, FetchError) and not job.video_id
                    and str(error) in {'No suitable source found.', 'Source search unavailable.',
                                       'Audio source unavailable.', 'Source metadata unavailable.'}):
                from .recording_fallback import automatic
                try:
                    if await automatic(self, job_id):
                        return
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.warning('Automatic recording lookup unavailable; retaining recovery choice.')
            job.metadata_json = {**job.metadata_json, 'failure_phase': phase, 'failure_reason': reason}
            await self.state(job_id, 'failed', metadata_json=job.metadata_json)
            await self.fail(job_id, phase=phase)

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
                try:
                    await self.show_choices(current, user_id, rows)
                except Exception as error:
                    ambiguous = isinstance(error, (TimeoutError, TelegramNetworkError, SQLAlchemyError))
                    category = ('unconfirmed' if ambiguous else 'forbidden' if isinstance(error, TelegramForbiddenError)
                                else 'rejected' if isinstance(error, TelegramBadRequest) else 'presentation')
                    logger.warning('Choice prompt failed (%s, %s); provider details omitted.', category, type(error).__name__)
                    async with self.db.write() as session:
                        job = await session.get(FetchJob, job_id)
                        if job:
                            job.metadata_json = {**job.metadata_json, 'failure_phase': 'choice',
                                'failure_reason': 'choice_prompt_failed', 'choice_failure_category': category}
                    changed = await self.request_state(req.id, 'uncertain' if ambiguous else 'failed', locked=True)
                    if changed and not current.status_message_id and not ambiguous:
                        await self.choice_recovery(req.id, user_id, job.track_id)

    async def choice_recovery(self, request_id, user_id, track_id):
        context = language.set(await self.choice_language(user_id))
        try:
            token, keyboard = await self.retry_keyboard(user_id, track_id)
            # Keep recovery controls compatible with the basic Telegram keyboard schema.
            keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text=button.text, callback_data=button.callback_data)
                for button in row] for row in keyboard.inline_keyboard])
            async with asyncio.timeout(4):
                sent = await self.bot.send_message(user_id, copy('failed_choice'), reply_markup=keyboard)
            from .chat_service import ChatService
            await ChatService(self.db, None).bind_control(token, sent.message_id)
            async with self.db.write() as session:
                req = await session.get(AudioRequest, request_id)
                if req and req.state == 'failed':
                    req.status_message_id = sent.message_id
        except Exception as error:
            logger.warning('Choice recovery failed (%s); retry remains available in the app.', type(error).__name__)
        finally:
            language.reset(context)

    async def request_state(self, request_id, state, *, locked=False):
        async with self.db.write() as s:
            req = await s.get(AudioRequest, request_id)
            if req and req.state not in {'done', 'cancelled', 'expired', 'failed', 'uncertain'}:
                req.state = state
            else:
                return False
        if state in {'failed', 'uncertain'}:
            await self.progress(request_id, state, locked=locked)
        return True

    async def delivery_metadata(self, track, *, snapshot=None, video=None):
        from .recording_metadata import resolve_metadata, snapshot_metadata
        canonical = snapshot_metadata(snapshot, video)
        key = (track.id, track.display_artist or track.artist, track.display_title or track.title,
               track.metadata_source, track.duration, canonical, track.album, track.artwork_url)
        cached = self.metadata_cache.get(key)
        if cached and monotonic() - cached[0] < 300:
            return cached[1]
        providers = getattr(self.artwork_loader, 'providers', None)
        metadata = await resolve_metadata(track, providers, canonical=canonical)
        if len(self.metadata_cache) >= 128:
            self.metadata_cache.pop(next(iter(self.metadata_cache)))
        self.metadata_cache[key] = (monotonic(), metadata)
        return metadata

    @staticmethod
    def metadata_key(metadata):
        return hashlib.sha256(repr((metadata.title, metadata.artist, metadata.album)).encode()).hexdigest()

    async def send(self, req, user_id, job, track, audio, thumbnail=None, cover_key=None):
        started = monotonic()
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
            if not isinstance(audio, str):
                await self.progress(req.id, 'sending', locked=True)
            try:
                extra = {'thumbnail': FSInputFile(thumbnail)} if thumbnail else {}
                from .rating_links import audio_caption
                from .preferences import preferences
                locale = 'en'
                try:
                    async with asyncio.timeout(1):
                        locale = (await preferences(self.db, user_id))['language']
                except Exception:
                    pass  # Caption localization must not block audio delivery.
                from .recording_metadata import telegram_fields
                metadata = await self.delivery_metadata(track, snapshot=req.canonical_metadata, video=job.video_id)
                fields = telegram_fields(metadata)
                daily = bool((req.canonical_metadata or {}).get('_daily_pick'))
                if daily:
                    from .daily_pick import prepare_audio
                    keyboard = await prepare_audio(self, req, user_id, track.id, locale)
                    if keyboard is None:
                        await self.request_state(req.id, 'cancelled', locked=True)
                        return
                    extra['reply_markup'] = keyboard
                    extra.update(await audio_caption(self.bot, track.id, locale=locale, compact=True))
                    from .daily_pick import explain_caption
                    extra.update(explain_caption(extra,req,locale))
                else:
                    extra.update(await audio_caption(self.bot, track.id, locale=locale))
                sent = await self.bot.send_audio(user_id, audio=audio, request_timeout=self.settings.timeout,
                    **fields, **extra)
            except TelegramForbiddenError:
                await self.request_state(req.id, 'uncertain', locked=True)
                if (req.canonical_metadata or {}).get('_daily_pick'):
                    from .daily_pick import setting
                    await setting(self.db, user_id, False)
                return
            except TelegramBadRequest:
                await self.request_state(req.id, 'pending', locked=True)
                raise
            except Exception:
                await self.request_state(req.id, 'uncertain', locked=True)
                return
            args = (req, job, track, sent, cover_key, fields)
            self.receipt_recovery[req.id] = args
            # Shield the acknowledged receipt from foreground cancellation.
            task = asyncio.create_task(self.recover_receipt(args))
            try:
                persisted = await asyncio.shield(task)
            except asyncio.CancelledError:
                await task
                raise
            if not persisted:
                return
            await self.progress(req.id, 'delivered', locked=True)
            logger.info('Audio delivered: cached=%s in %.0f ms.', isinstance(audio, str), (monotonic() - started) * 1000)

    async def recover_receipt(self, args):
        req = args[0]
        for attempt in range(3):
            try:
                await self.persist_receipt(*args)
                self.receipt_recovery.pop(req.id, None)
                return True
            except SQLAlchemyError:
                logger.warning('Audio receipt persistence failed (attempt %s).', attempt + 1)
                await asyncio.sleep(.1 * (attempt + 1))
        try:
            await self.request_state(req.id, 'uncertain', locked=True)
        except SQLAlchemyError:
            pass  # Maintenance retries the acknowledged receipt after DB recovery.
        return False

    async def persist_receipt(self, req, job, track, sent, cover_key, fields):
        async with self.db.write() as s:
            current = await s.get(AudioRequest, req.id)
            if current:
                current.state = 'done'
                current.message_id, current.delivered_video_id = sent.message_id, job.video_id
                if (req.canonical_metadata or {}).get('_daily_pick'):
                    from .daily_pick import acknowledge_audio
                    await acknowledge_audio(s, req, track, sent)
                await s.execute(delete(AudioDelivery).where(AudioDelivery.user_id == req.user_id,
                    AudioDelivery.track_id == track.id, AudioDelivery.video_id == job.video_id))
                s.add(AudioDelivery(user_id=req.user_id, track_id=track.id, video_id=job.video_id,
                    file_id=sent.audio.file_id, message_id=sent.message_id, artwork_key=cover_key, send_args=fields))

    async def deliver_cached(self, job, track):
        for req, user_id in await self.requests(job.id):
            async with self.db.sessions() as s:
                query = select(AudioDelivery).where(AudioDelivery.user_id == req.user_id, AudioDelivery.track_id == track.id)
                if isinstance(self.fetcher, YouTubeFetcher):
                    policies = (SOURCE_POLICIES if job.video_id and
                        job.metadata_json.get('source_policy') in {'explicit-alternative-v1','explicit-discovery-v1'}
                        else {'catalogue-original-v1','catalogue-music-v1','automatic-first-v1'})
                    query = query.join(AudioSource, (AudioSource.track_id == AudioDelivery.track_id)
                        & (AudioSource.video_id == AudioDelivery.video_id)).where(
                            AudioSource.fetch_metadata['source_policy'].as_string().in_(policies))
                selection = await s.scalar(select(AudioSelection).where(AudioSelection.user_id == req.user_id,
                                                                      AudioSelection.track_id == track.id))
                if selection:
                    query = query.where(AudioDelivery.video_id.not_in(selection.rejected_ids))
                    if selection.video_id:
                        query = query.where(AudioDelivery.video_id == selection.video_id)
                if job.video_id:
                    query = query.where(AudioDelivery.video_id == job.video_id)
                cached = await s.scalar(query.order_by(AudioDelivery.created_at.desc()))
            if cached and track.metadata_source in {'youtube_recording', 'youtube_music'}:
                metadata = await self.delivery_metadata(track, snapshot=req.canonical_metadata, video=cached.video_id)
                async with self.db.sessions() as session:
                    source = await session.scalar(select(AudioSource).where(AudioSource.track_id == track.id,
                        AudioSource.video_id == cached.video_id))
                try:
                    since = datetime.fromisoformat(source.fetch_metadata.get('audio_tags_since') or source.fetched_at.isoformat()) if source else None
                except (TypeError, ValueError):
                    since = None
                if (source is None or source.fetch_metadata.get('tags_embedded') is not True
                        or source.fetch_metadata.get('audio_tags_v1') != self.metadata_key(metadata)
                        or since is None or cached.created_at < since):
                    continue  # Refresh old upload tags once; no canonical/rating identity rewrite.
            if cached and not cached.artwork_key:
                if not artwork_key(track) and self.artwork_loader:
                    try:
                        async with asyncio.timeout(2):
                            await self.artwork_loader.load(track.id)
                    except Exception:
                        pass
                    async with self.db.sessions() as session:
                        track = await session.get(Track, track.id)
                if artwork_key(track):
                    # Telegram file_id retains old tags: fetch/tag a fresh upload once.
                    continue
            if cached:
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
                metadata = await self.delivery_metadata(track, snapshot=req.canonical_metadata, video=job.video_id)
                tagged = await tag_metadata(self.fetcher, metadata, path, path.parent, lambda: self.alive(job.id))
                async with self.db.write() as session:
                    source = await session.scalar(select(AudioSource).where(AudioSource.track_id == track.id, AudioSource.video_id == job.video_id))
                    if source:
                        previous = source.fetch_metadata
                        profile = self.metadata_key(metadata)
                        since = previous.get('audio_tags_since') if previous.get('audio_tags_v1') == profile else None
                        source.fetch_metadata = {**previous,'audio_tags_v1':profile if tagged else None,
                            'audio_tags_since':(since or utc_now().isoformat()) if tagged else None, 'tags_embedded':tagged}
                await self.send(req, user_id, job, track, FSInputFile(path), thumbnail, cover_key)
            except TelegramBadRequest:
                await self.request_state(req.id, 'failed')

    async def fail(self, job_id, alternatives=False, phase=None):
        async with self.db.sessions() as s:
            job = await s.get(FetchJob, job_id)
            video = job.video_id if job else None
        keyboard = None
        if isinstance(video, str) and VIDEO.fullmatch(video):
            keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
                text='Listen on YouTube', url='https://www.youtube.com/watch?v=' + video)]])
        for req, user_id in await self.requests(job_id):
            async with self.delivery_locks.setdefault(user_id, asyncio.Lock()):
                if not await self.request_state(req.id, 'failed', locked=True):
                    continue
                if (req.canonical_metadata or {}).get('_daily_pick'):
                    continue  # Failed daily sources do not send an empty card or error.
                async with self.db.sessions() as session:
                    current = await session.get(AudioRequest, req.id)
                if current is None or current.status_message_id:
                    continue
                from .recording_fallback import available, keyboard as recording_keyboard
                request_keyboard = recording_keyboard(req.id,keyboard) if job and available(job.metadata_json) else keyboard
                try:
                    sent = await self.bot.send_message(user_id,
                        ('No other matching recordings were found. Try Get song again later.' if alternatives else
                         copy('failed_no_match' if job and job.metadata_json.get('failure_reason') == 'no_matching_candidate' else 'failed_search') if phase == 'search' else
                         'Could not fetch this recording. Try Get song again later.') +
                        (' You can still listen using the link below.' if keyboard else ''),
                        reply_markup=request_keyboard)
                    if request_keyboard is not None:
                        async with self.db.write() as session:
                            current = await session.get(AudioRequest,req.id)
                            if current and current.state == 'failed':
                                current.message_id = sent.message_id
                except Exception:
                    pass
