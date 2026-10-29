"""Explicit owner-bound discovery after strict automatic matching cannot verify a source."""
import asyncio
import math
from datetime import timedelta
from uuid import uuid4
from sqlalchemy import select, func, or_
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from .bot_copy import text as copy
from .fetch_models import AudioRequest, FetchJob, AudioSelection
from .models import User, Track, utc_now
from .workflow import FlowError
from .youtube_fetch import FetchError, VIDEO, version_words
from .recording_metadata import canonical_snapshot, result_metadata, label_credit

REASONS = {'no_matching_candidate', 'search_unavailable', 'recording_discovery_empty', 'recording_discovery_unavailable'}

def available(metadata):
    return metadata.get('failure_phase') == 'search' and metadata.get('failure_reason') in REASONS


def keyboard(request_id, existing=None):
    rows = [[InlineKeyboardButton(text=copy('choose_recording'), callback_data='pickreq:'+request_id)]]
    if existing is not None:
        rows += existing.inline_keyboard
    return InlineKeyboardMarkup(inline_keyboard=rows)


def choices(track, candidates, maximum, rejected=()):
    """Retain source metadata; automatic_match separately gates implicit selection."""
    rows, seen = [], set(rejected)
    for candidate in candidates:
        video = candidate.external_ids.get('youtube', '')
        duration = candidate.duration
        if (not isinstance(video,str) or not VIDEO.fullmatch(video) or video in seen
                or isinstance(duration,bool) or not isinstance(duration,(int,float)) or not math.isfinite(duration) or not 0 < duration <= maximum):
            continue
        clean = result_metadata(candidate)
        snapshot = canonical_snapshot(candidate)
        editions = set(candidate.recording_metadata.get('flags',())) | version_words(candidate.title or '')
        if candidate.source != 'youtube_music':
            # Raw uploader credits grant no artist proof. Keep the catalogue identity.
            artist = track.display_artist or track.artist
            proven = track.metadata_source not in {'youtube_recording','youtube'} and not label_credit(artist)
            snapshot.update(artist=artist if proven else '',title=track.display_title or track.title,
                album=track.album if proven and not editions else None,
                artwork_url=track.artwork_url if proven and not editions else None)
        snapshot['flags'] = sorted(editions)
        rows.append(dict(id=video,title=clean.title,artist=clean.artist,duration=duration,
            version=sorted(editions),exact=False,score=0,recording_title=clean.title,
            source_policy='explicit-discovery-v1',canonical_metadata=snapshot))
        seen.add(video)
        if len(rows) == 3:
            break
    return rows


def automatic_match(track, row):
    """Relax duration/provenance friction, never a known artist or edition conflict."""
    from .youtube_fetch import artist_key
    from .recording_resolver import title_key
    artist=track.display_artist or track.artist
    title=track.display_title or track.title
    return bool(artist_key(artist) and not label_credit(artist)
        and artist_key(artist)==artist_key(row.get('artist') or '')
        and title_key(title,artist)==title_key(row.get('title') or '',row.get('artist') or '')
        and (version_words(title)-{'music_video'})==(set(row.get('version') or [])-{'music_video'})
        and (not track.duration or abs(track.duration-row['duration'])<=max(45,track.duration*.25)))


async def automatic(service, job_id):
    """Try the top discovered recording once before showing a failed-search button."""
    async with service.db.write() as session:
        job=await session.get(FetchJob,job_id)
        if job is None or job.video_id or job.metadata_json.get('force_choice') or job.metadata_json.get('auto_discovery_attempted'):
            return False
        requests=list(await session.scalars(select(AudioRequest).where(AudioRequest.job_id==job_id,AudioRequest.state=='pending')))
        if not requests:return False
        track=await session.get(Track,job.track_id)
        rejected=set()
        for req in requests:
            selection=await session.scalar(select(AudioSelection).where(AudioSelection.user_id==req.user_id,AudioSelection.track_id==track.id))
            if selection:rejected.update(selection.rejected_ids)
        token=uuid4().hex
        job.metadata_json={**job.metadata_json,'auto_discovery_attempted':True,'auto_lookup_token':token}
    provider=getattr(service.fetcher,'recording_search',None)
    candidates=[]
    try:
        if provider is not None:
            async with asyncio.timeout(12):
                candidates,_=await provider.search(' '.join((track.display_artist or track.artist,track.display_title or track.title)))
    except asyncio.CancelledError:
        raise
    except Exception:
        return False
    rows=choices(track,candidates,service.settings.max_duration,rejected)
    if not rows:return False
    selected=rows[0] if automatic_match(track,rows[0]) else None
    async with service.db.write() as session:
        job=await session.get(FetchJob,job_id)
        current=list(await session.scalars(select(AudioRequest).where(AudioRequest.job_id==job_id,AudioRequest.state=='pending')))
        if job is None or job.metadata_json.get('auto_lookup_token')!=token or not current:
            return False
        # Requests and corrections may change while discovery is in flight.
        for req in current:
            selection=await session.scalar(select(AudioSelection).where(AudioSelection.user_id==req.user_id,AudioSelection.track_id==track.id))
            if selection and (rows[0]['id'] in selection.rejected_ids or (selection.video_id and selection.video_id!=rows[0]['id'])):
                return False
        if selected:
            job.state,job.video_id,job.candidates='queued',selected['id'],rows
            job.metadata_json={**selected,'source_policy':'automatic-first-v1','auto_discovery_attempted':True}
            for req in current:
                daily={key:value for key,value in (req.canonical_metadata or {}).items() if key.startswith('_daily')}
                req.canonical_metadata={**selected['canonical_metadata'],**daily}
        else:
            job.state,job.candidates='choice',rows
            job.metadata_json={**job.metadata_json,'force_choice':True}
    if not selected:
        await service.offer(job_id,rows)
    return True


async def start(service, user_id, request_id, message_id):
    if not service.settings.enabled:
        raise FlowError('stale')
    async with service.delivery_locks.setdefault(user_id,asyncio.Lock()):
        async with service.db.write() as s:
            req = await s.scalar(select(AudioRequest).join(User).where(AudioRequest.id==request_id,
                User.telegram_user_id==user_id,AudioRequest.state=='failed',
                or_(AudioRequest.status_message_id==message_id,AudioRequest.message_id==message_id),
                AudioRequest.created_at>utc_now()-timedelta(minutes=30)))
            if req is None:
                raise FlowError('stale')
            original = await s.get(FetchJob,req.job_id)
            if not available(original.metadata_json):
                raise FlowError('stale')
            active = await s.scalar(select(AudioRequest.id).join(FetchJob).where(
                AudioRequest.user_id==req.user_id,FetchJob.track_id==original.track_id,
                AudioRequest.state.in_(('pending','choice','sending'))))
            if active:
                raise FlowError('stale')
            own = await s.scalar(select(func.count()).select_from(AudioRequest).where(
                AudioRequest.user_id==req.user_id,AudioRequest.state.in_(('pending','choice','sending'))))
            total = await s.scalar(select(func.count()).select_from(AudioRequest).where(AudioRequest.state.in_(('pending','choice','sending'))))
            if own>=service.settings.per_user_queue or total>=service.settings.queue_limit:
                raise FetchError('Request limit reached. Please try later.')
            key = f'{original.track_id}:recording-choice:{req.id}'
            job = await s.scalar(select(FetchJob).where(FetchJob.key==key))
            if job is None:
                job = FetchJob(id=uuid4().hex,key=key,track_id=original.track_id)
                s.add(job)
                await s.flush()
            job.state,job.video_id,job.candidates = 'running',None,[]
            job.updated_at = utc_now()
            job.metadata_json = {'force_choice':True,'recording_discovery':True,'lookup_token':uuid4().hex}
            req.job_id,req.state,req.status_message_id = job.id,'pending',message_id
            req.message_id,req.canonical_metadata = None,{}
            job_id = job.id
    await service.progress(request_id,'recordings_searching')
    await finish(service,job_id)


async def finish(service, job_id):
    async with service.db.sessions() as s:
        job = await s.get(FetchJob,job_id)
        track = await s.get(Track,job.track_id)
        token = job.metadata_json.get('lookup_token')
        req = await s.scalar(select(AudioRequest).where(AudioRequest.job_id==job_id,AudioRequest.state=='pending'))
        if req is None:
            await service.state(job_id,'done')
            return
        selection = await s.scalar(select(AudioSelection).where(AudioSelection.user_id==req.user_id,AudioSelection.track_id==track.id))
        rejected = list(selection.rejected_ids) if selection else []
    provider = getattr(service.fetcher,'recording_search',None)
    candidates,failed = [],True
    try:
        if provider is not None:
            async with asyncio.timeout(12):
                candidates,failed = await provider.search(' '.join((track.display_artist or track.artist,track.display_title or track.title)))
    except asyncio.CancelledError:
        async with service.db.write() as s:
            current = await s.get(AudioRequest,req.id)
            current_job = await s.get(FetchJob,job_id)
            if current and current.job_id==job_id and current.state=='pending':
                current.state='cancelled'
            if current_job and current_job.metadata_json.get('lookup_token')==token:
                current_job.state='done'
        raise
    except Exception:
        failed=True  # Metadata outage must not become a definitive no-match.
    rows = choices(track,candidates,service.settings.max_duration,rejected)
    async with service.db.write() as s:
        current = await s.get(AudioRequest,req.id)
        current_job = await s.get(FetchJob,job_id)
        if (current is None or current.job_id!=job_id or current.state!='pending' or current.created_at<utc_now()-timedelta(minutes=30)
                or current_job is None or current_job.metadata_json.get('lookup_token')!=token):
            if current and current.job_id==job_id and current.state=='pending' and current.created_at<utc_now()-timedelta(minutes=30):
                current.state='expired'
            if current_job and current_job.metadata_json.get('lookup_token')==token:
                current_job.state='done'
            return
        current_job.updated_at=utc_now()
        if rows:
            current_job.state,current_job.candidates='choice',rows
        else:
            current_job.state='failed'
            current_job.metadata_json={**current_job.metadata_json,'failure_phase':'search',
                'failure_reason':'recording_discovery_unavailable' if failed else 'recording_discovery_empty'}
    if rows:
        await service.offer(job_id,rows)
    else:
        await service.request_state(req.id,'failed')
