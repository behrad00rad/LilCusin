"""Bulk data loading and display-batch persistence; no network or scoring."""

import json
from collections import defaultdict, deque

from sqlalchemy import func, or_, select, tuple_
from sqlalchemy.dialects.sqlite import insert

from ..matching import comparison_text, identity_key
from ..models import AudioAnalysis, Rating, RecommendationHistory, SimilarTrack, Track, TrackExternalID, TrackTag, User, UserTrackSignal, utc_now
from ..providers.common import TrackCandidate
from . import settings as S
from .scoring import tag_weight
from .types import Item, Profile, Recommendation, RecommendationResult, Seed


def aliases(metadata):
    keys = {("name", identity_key(metadata.artist, metadata.title))}
    keys.update(("id", provider, value) for provider, value in metadata.external_ids.items() if value)
    return keys


def from_track(track):
    return Item(TrackCandidate(track.display_title or track.title, track.display_artist or track.artist,
                               track.metadata_source, track.album, track.artwork_url, track.duration), track.id)


async def load_items(session, tracks):
    result = {track.id: from_track(track) for track in tracks}
    if not result:
        return result
    ids = list(result)
    for row in await session.scalars(select(TrackExternalID).where(TrackExternalID.track_id.in_(ids))):
        result[row.track_id].metadata.external_ids[row.provider] = row.external_identifier
    for row in await session.scalars(select(TrackTag).where(TrackTag.track_id.in_(ids))):
        name = comparison_text(row.name)
        weight = tag_weight(row.weight)
        if name and weight > 0:
            tags = result[row.track_id].tags
            tags[name] = max(tags.get(name, 0), weight)
    for row in await session.scalars(select(AudioAnalysis).where(
        AudioAnalysis.track_id.in_(ids), AudioAnalysis.status == "succeeded",
    ).order_by(AudioAnalysis.updated_at)):
        if isinstance(row.features, dict) and isinstance(row.features.get("sample_rate"), int):
            key = (row.analyzer_name, row.analyzer_version, row.features["sample_rate"])
            result[row.track_id].analyses[key] = row.features
    for item in result.values():
        item.identities = aliases(item.metadata)
    return result


def balanced_seeds(rows, values, maximum):
    groups = defaultdict(deque)
    for rating, track in rows:
        if rating.value in values:
            groups[comparison_text(track.artist)].append((rating, track))
    chosen = []
    while groups and len(chosen) < maximum:
        for artist in list(sorted(groups)):
            chosen.append(groups[artist].popleft())
            if not groups[artist]:
                del groups[artist]
            if len(chosen) == maximum:
                break
    return chosen


async def load_profile(session, telegram_user_id, selected_track_id=None):
    user_id = await session.scalar(select(User.id).where(User.telegram_user_id == telegram_user_id))
    if user_id is None:
        return None
    rows = (await session.execute(select(Rating, Track).join(Track).where(Rating.user_id == user_id)
                                  .order_by(Rating.track_id))).all()
    selected = await session.get(Track, selected_track_id) if selected_track_id is not None else None
    if selected_track_id is not None and selected is None:
        return None
    positives = [(rating, track) for rating, track in rows if rating.value in {"love", "like"}] if selected is None else []
    implicit = []
    if selected is None:
        implicit = (await session.execute(select(Track, func.max(UserTrackSignal.weight))
            .join(UserTrackSignal, UserTrackSignal.track_id == Track.id).where(
                UserTrackSignal.user_id == user_id, UserTrackSignal.signal_type == "playlist_channel",
                UserTrackSignal.weight > 0,
                ~Track.id.in_(select(Rating.track_id).where(Rating.user_id == user_id)))
            .group_by(Track.id).order_by(Track.id))).all()
    if not positives and not implicit and selected is None:
        return None
    negatives = balanced_seeds(rows, {"dislike"}, S.MAX_NEGATIVE_SEEDS)
    items = await load_items(session, [track for _, track in positives + negatives] + [track for track, _ in implicit]
                             + ([selected] if selected is not None else []))
    rated_aliases = set()
    for _, track in rows:
        rated_aliases.update(aliases(from_track(track).metadata))
    # All ratings exclude a song, including neutral and ratings outside seed caps.
    for provider, identifier in await session.execute(select(TrackExternalID.provider, TrackExternalID.external_identifier)
            .join(Rating, Rating.track_id == TrackExternalID.track_id).where(Rating.user_id == user_id)):
        rated_aliases.add(("id", provider, identifier))
    history_rows = (await session.execute(select(Track, func.max(RecommendationHistory.recommended_at))
        .join(RecommendationHistory).where(RecommendationHistory.user_id == user_id,
            RecommendationHistory.recommended_at > utc_now() - S.HISTORY_WINDOW).group_by(Track.id))).all()
    history = {track.id: when for track, when in history_rows}
    history_aliases = {}
    for track, when in history_rows:
        for key in aliases(from_track(track).metadata):
            history_aliases[key] = max(history_aliases.get(key, when), when)
    if history:
        for row in await session.scalars(select(TrackExternalID).where(TrackExternalID.track_id.in_(history))):
            key = ("id", row.provider, row.external_identifier)
            history_aliases[key] = max(history_aliases.get(key, history[row.track_id]), history[row.track_id])
    positive_seeds = [Seed(items[track.id], rating.value) for rating, track in positives]
    positive_seeds += [Seed(items[track.id], "playlist_channel", weight) for track, weight in implicit
                       if not items[track.id].identities & rated_aliases]
    if not positive_seeds and selected is None:
        return None
    excluded_ids = {track.id for _, track in rows}
    for track, _ in implicit:
        excluded_ids.add(track.id)
        rated_aliases.update(items[track.id].identities)
    if selected is not None:
        positive_seeds = [Seed(items[selected.id], None)]
        # Exclude the focus track and its aliases even if it has never been rated.
        excluded_ids.add(selected.id)
        rated_aliases.update(items[selected.id].identities)
    return Profile(user_id, positive_seeds,
                   [Seed(items[track.id], rating.value) for rating, track in negatives],
                   excluded_ids, rated_aliases, history, history_aliases, selected_track_id)


async def load_edges(session, seed_ids):
    ranked = select(SimilarTrack.id, func.row_number().over(
        partition_by=SimilarTrack.track_id, order_by=(SimilarTrack.score.desc(), SimilarTrack.id),
    ).label("position")).where(SimilarTrack.track_id.in_(seed_ids)).subquery()
    return (await session.scalars(select(SimilarTrack).join(ranked, ranked.c.id == SimilarTrack.id)
                                  .where(ranked.c.position <= S.MAX_EDGES_PER_SEED)
                                  .order_by(ranked.c.position, SimilarTrack.track_id)
                                  .limit(S.MAX_SIMILAR_CANDIDATES))).all()


async def local_candidates(session, profile, related_artists):
    seed_tags = set()
    for seed in profile.positives:
        seed_tags.update(sorted(seed.item.tags, key=seed.item.tags.get, reverse=True)[:S.MAX_SEED_TAGS])
    artists = {comparison_text(seed.item.metadata.artist) for seed in profile.positives}
    positive_ids = {seed.item.track_id for seed in profile.positives}
    artists.update(artist for seed_id, artist in related_artists if seed_id in positive_ids)
    artists.update(seed.item.metadata.artist.casefold() for seed in profile.positives)
    rated = select(Rating.track_id).where(Rating.user_id == profile.user_id)
    conditions = {
        "shared_tags": Track.id.in_(select(TrackTag.track_id).where(TrackTag.name.in_(seed_tags))),
        "artist_metadata": Track.artist.in_(artists),
    }
    compatible = {key for seed in profile.positives for key in seed.item.analyses}
    if compatible:
        # Actual sample-rate compatibility is checked in scoring after bulk loading.
        versions = {(name, version) for name, version, _ in compatible}
        conditions["local_audio"] = Track.id.in_(select(AudioAnalysis.track_id).where(
            AudioAnalysis.status == "succeeded",
            tuple_(AudioAnalysis.analyzer_name, AudioAnalysis.analyzer_version).in_(versions)))
    tracks, sources = {}, defaultdict(set)
    for source, condition in conditions.items():
        query = select(Track).where(~Track.id.in_(rated), condition).order_by(Track.id)
        if source in ("shared_tags", "artist_metadata"):
            partition = TrackTag.name if source == "shared_tags" else Track.artist
            ranked = select(Track.id.label("track_id"), func.row_number().over(
                partition_by=partition, order_by=Track.id).label("position"))
            if source == "shared_tags":
                ranked = ranked.join(TrackTag).where(TrackTag.name.in_(seed_tags))
            ranked = ranked.where(~Track.id.in_(rated), condition).subquery()
            # Round-robin tags/artists before applying the local source cap.
            query = select(Track).join(ranked, ranked.c.track_id == Track.id).group_by(Track.id).order_by(func.min(ranked.c.position), Track.id)
        rows = await session.scalars(query.limit(S.MAX_LOCAL_PER_SOURCE))
        for track in rows:
            tracks[track.id] = track
            sources[track.id].add(source)
    items = await load_items(session, list(tracks.values()))
    for key, item in items.items():
        item.sources.update(sources[key])
    return list(items.values())


async def resolve_tracks(session, candidates):
    """Match a bounded set of external candidates in two batched SELECTs."""
    names = {(comparison_text(c.metadata.artist), comparison_text(c.metadata.title)) for c in candidates}
    names.update((c.metadata.artist.casefold(), c.metadata.title.casefold()) for c in candidates)
    external = {(p, value) for c in candidates for p, value in c.metadata.external_ids.items()}
    external_rows = (await session.scalars(select(TrackExternalID).where(
        tuple_(TrackExternalID.provider, TrackExternalID.external_identifier).in_(external)))).all() if external else []
    by_external = {(row.provider, row.external_identifier): row.track_id for row in external_rows}
    ids = {row.track_id for row in external_rows} | {c.track_id for c in candidates if c.track_id is not None}
    tracks = (await session.scalars(select(Track).where(or_(Track.id.in_(ids), tuple_(Track.artist, Track.title).in_(names))))).all()
    by_name = {identity_key(track.display_artist or track.artist, track.display_title or track.title): track.id for track in tracks}
    resolved = {}
    for index, item in enumerate(candidates):
        matches = {by_external[(p, value)] for p, value in item.metadata.external_ids.items() if (p, value) in by_external}
        if len(matches) > 1:
            resolved[index] = -1  # Conflicting provider identities; skip safely.
        else:
            resolved[index] = next(iter(matches), item.track_id or by_name.get(identity_key(item.metadata.artist, item.metadata.title)))
    return resolved, tracks


async def replay_batch(session, user_id, batch_id, rated_aliases, selected_track_id=None):
    rows = (await session.execute(select(RecommendationHistory, Track).join(Track).where(
        RecommendationHistory.user_id == user_id, RecommendationHistory.batch_id == batch_id,
    ).order_by(RecommendationHistory.position, RecommendationHistory.id))).all()
    if not rows:
        return None
    items = await load_items(session, [track for _, track in rows])
    recommendations = []
    for history, track in rows:
        item = items[track.id]
        try:
            source = json.loads(history.source or "{}")
        except ValueError:
            source = {}
        if not isinstance(source, dict):
            source = {}
        if source.get("selected_track_id") != selected_track_id:
            raise ValueError("batch_id already belongs to another recommendation mode or selected track")
        if item.identities & rated_aliases:
            continue
        recommendations.append(Recommendation(track.id, item.metadata.artist, item.metadata.title,
            track.album, track.artwork_url, item.metadata.external_ids, history.ranking_score or 0,
            history.reason or "", tuple(source.get("sources", [])), bool(source.get("exploration"))))
    return RecommendationResult("ok" if recommendations else "no_candidates", tuple(recommendations), batch_id)


async def persist_selection(database, telegram_user_id, ranked, for_display, batch_id, selected_track_id=None):
    async with database.write() as session:
        # Recheck ratings/history under the writer lock to cover concurrent calls.
        profile = await load_profile(session, telegram_user_id, selected_track_id)
        if profile is None:
            return RecommendationResult("insufficient_preferences" if selected_track_id is None else "no_candidates")
        if for_display:
            replay = await replay_batch(session, profile.user_id, batch_id, profile.rated_aliases, selected_track_id)
            if replay is not None:
                return replay
        ranked = [row for row in ranked if not row.item.identities & profile.rated_aliases]
        if for_display:
            ranked = [row for row in ranked if not any(
                profile.history_aliases.get(key, utc_now() - S.HISTORY_WINDOW) > utc_now() - S.HISTORY_COOLDOWN
                for key in row.item.identities)]
        if not ranked:
            return RecommendationResult("no_candidates", batch_id=batch_id if for_display else None)
        candidates = [row.item for row in ranked]
        resolved, existing = await resolve_tracks(session, candidates)
        new = [dict(artist=comparison_text(item.metadata.artist), title=comparison_text(item.metadata.title),
                    display_artist=item.metadata.artist, display_title=item.metadata.title,
                    album=item.metadata.album, artwork_url=item.metadata.artwork_url,
                    duration=item.metadata.duration, metadata_source=item.metadata.source,
                    created_at=utc_now(), updated_at=utc_now())
               for index, item in enumerate(candidates) if resolved[index] is None]
        if new:
            await session.execute(insert(Track).values(new).on_conflict_do_nothing(index_elements=["artist", "title"]))
            resolved, existing = await resolve_tracks(session, candidates)
        by_id = {track.id: track for track in existing}
        external, output, history_rows, used = [], [], [], set()
        for index, row in enumerate(ranked):
            track_id = resolved[index]
            if track_id in (None, -1) or track_id in used or track_id in profile.rated_ids:
                continue
            used.add(track_id)
            track = by_id[track_id]
            item = row.item
            for provider, identifier in item.metadata.external_ids.items():
                if provider in ("lastfm", "musicbrainz") and identifier:
                    external.append(dict(track_id=track_id, provider=provider, external_identifier=identifier))
            output.append(Recommendation(track_id, track.display_artist or track.artist, track.display_title or track.title,
                track.album or item.metadata.album, track.artwork_url or item.metadata.artwork_url,
                item.metadata.external_ids.copy(), row.score, row.reason, tuple(sorted(item.sources)), row.exploration))
            if for_display:
                history_rows.append(dict(user_id=profile.user_id, track_id=track_id, ranking_score=row.score,
                    reason=row.reason, source=json.dumps({"sources": sorted(item.sources), "exploration": row.exploration,
                                                         "selected_track_id": selected_track_id}),
                    batch_id=batch_id, position=len(output), recommended_at=utc_now()))
        if external:
            await session.execute(insert(TrackExternalID).values(external).on_conflict_do_nothing(index_elements=["provider", "external_identifier"]))
        if history_rows:
            await session.execute(insert(RecommendationHistory).values(history_rows).on_conflict_do_nothing(
                index_elements=["user_id", "batch_id", "track_id"]))
        return RecommendationResult("ok" if output else "no_candidates", tuple(output), batch_id if for_display else None)
