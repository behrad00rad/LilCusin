"""Canonical tracks and provider identifiers; callers own the write transaction."""

from sqlalchemy import or_, select
from sqlalchemy.dialects.sqlite import insert

from .matching import comparison_text
from .models import Track, TrackExternalID, TrackTag, normalize_name


class IdentityConflict(ValueError):
    pass


async def attach_ids(session, track_id, identifiers):
    for provider, identifier in identifiers.items():
        if provider not in ("lastfm", "musicbrainz") or not identifier:
            continue
        # An identifier already attached elsewhere is never reassigned.
        await session.execute(insert(TrackExternalID).values(
            track_id=track_id, provider=provider, external_identifier=identifier,
        ).on_conflict_do_nothing(index_elements=["provider", "external_identifier"]))


async def canonical_track(session, candidate):
    clauses = [
        (TrackExternalID.provider == provider) & (TrackExternalID.external_identifier == value)
        for provider, value in candidate.external_ids.items()
    ]
    ids = set((await session.scalars(select(TrackExternalID.track_id).where(or_(*clauses)))).all()) if clauses else set()
    if len(ids) > 1:
        raise IdentityConflict("Conflicting existing identifiers")
    track = await session.get(Track, ids.pop()) if ids else None
    if track is None:
        track = await session.scalar(select(Track).where(
            Track.artist.in_([normalize_name(candidate.artist), comparison_text(candidate.artist)]),
            Track.title.in_([normalize_name(candidate.title), comparison_text(candidate.title)]),
        ))
    if track is None:
        track = Track(
            artist=comparison_text(candidate.artist), title=comparison_text(candidate.title),
            display_artist=candidate.artist, display_title=candidate.title,
            album=candidate.album, artwork_url=candidate.artwork_url, duration=candidate.duration,
            metadata_source=candidate.source,
        )
        session.add(track)
        await session.flush()
    await attach_ids(session, track.id, candidate.external_ids)
    return track


async def save_tags(session, track_id, tags):
    merged = {}
    for tag in tags:
        if not isinstance(tag.name, str) or not tag.name.strip():
            continue
        name = comparison_text(tag.name)
        if not name:
            continue
        key = (name, tag.source)
        previous = merged.get(key)
        if previous is None or (tag.weight or 0) > (previous.weight or 0):
            merged[key] = tag
    for (name, source), tag in merged.items():
        values = dict(display_name=tag.name.strip(), weight=tag.weight)
        await session.execute(insert(TrackTag).values(
            track_id=track_id, name=name, source=source, **values,
        ).on_conflict_do_update(index_elements=["track_id", "name", "source"], set_=values))
