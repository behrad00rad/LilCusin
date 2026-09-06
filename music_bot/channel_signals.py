"""Attach provenance-based signals inside the existing confirmation transaction."""

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert

from .models import ChannelPost, UserTrackSignal, utc_now
from .recommendations.settings import PLAYLIST_CHANNEL_WEIGHT


async def learn_confirmed_channel_track(session, submission):
    post = await session.scalar(select(ChannelPost).where(ChannelPost.submission_id == submission.id))
    if post is None:
        return
    post.track_id, post.status = submission.track_id, "identified"
    if post.learn_allowed:
        await session.execute(insert(UserTrackSignal).values(
            user_id=submission.user_id, track_id=submission.track_id, channel_id=post.channel_id,
            channel_post_id=post.id, signal_type="playlist_channel", weight=PLAYLIST_CHANNEL_WEIGHT,
            created_at=utc_now(),
        ).on_conflict_do_nothing(index_elements=["user_id", "track_id", "channel_id"]))
