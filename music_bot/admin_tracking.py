"""Bounded first-occurrence funnel events and daily operational counters."""
import functools
import logging
import time
from datetime import timedelta
from sqlalchemy import delete
from sqlalchemy.dialects.sqlite import insert
from .admin_models import AdminMetric, AdminStage
from .models import utc_now

STAGES = ('onboarding_started', 'artist_selection_completed', 'onboarding_completed',
          'first_recommendation_shown', 'first_recommendation_liked')


async def stage(session, user_id, name):
    if name not in STAGES:
        raise ValueError('Unknown onboarding stage')
    await session.execute(insert(AdminStage).values(user_id=user_id, stage=name, source='first_party',
        occurred_at=utc_now()).on_conflict_do_nothing(index_elements=['user_id', 'stage', 'source']))


async def metric(database, kind, duration_ms=0):
    # Telemetry must not turn a working recommendation/search into a failure.
    try:
        async with database.write() as session:
            await session.execute(delete(AdminMetric).where(AdminMetric.day < (utc_now()-timedelta(days=180)).date().isoformat()))
            stmt = insert(AdminMetric).values(day=utc_now().date().isoformat(), source='first_party',
                                              kind=kind, count=1, duration_ms=max(0, int(duration_ms)))
            await session.execute(stmt.on_conflict_do_update(index_elements=['day', 'source', 'kind'],
                set_={'count': AdminMetric.count + 1, 'duration_ms': AdminMetric.duration_ms + stmt.excluded.duration_ms}))
    except Exception:
        logging.getLogger('music_bot').warning('Owner analytics counter unavailable.')


def observe_recommendation(method):
    @functools.wraps(method)
    async def wrapped(self, *args, **kwargs):
        started = time.monotonic()
        kind = 'recommendation_failure'
        try:
            result = await method(self, *args, **kwargs)
            kind = 'recommendation_ok' if result.recommendations else 'recommendation_empty'
            return result
        finally:
            await metric(self.database, kind, (time.monotonic() - started) * 1000)
    return wrapped
