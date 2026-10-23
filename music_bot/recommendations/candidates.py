"""Bounded, cache-first candidates and identity merging."""

import asyncio
import logging
from collections import defaultdict, deque
from dataclasses import replace

from sqlalchemy import select

from ..cache import cache_key, decode
from ..matching import comparison_text, decode_track
from ..models import ProviderCache, utc_now
from ..providers.common import ProviderError, TrackCandidate
from . import settings as S
from .repository import aliases, load_edges, load_items, local_candidates, resolve_tracks
from .scoring import clamp, evidence, seed_weight, tag_weight
from .types import Item

logger = logging.getLogger(__name__)


async def guess_pool(session, profile, *, limit=600):
    """Cache/local candidates only; no taste mutations or external requests.

    The caller must apply its stricter, lifetime game exclusions. Popularity is
    used only to order the bounded same-language fallback, never returned.
    """
    from sqlalchemy import func
    from ..models import Rating, Track
    primary = await local_candidates(session, profile, {})
    edges = await load_edges(session, [seed.item.track_id for seed in profile.positives])
    cached = []
    for edge in edges:
        try:
            item = candidate_item(decode_track(edge.candidate))
        except (ValueError, KeyError, TypeError):
            continue
        if item is not None:
            cached.append(item)
    resolved, tracks = await resolve_tracks(session, cached)
    canonical = await load_items(session, tracks)
    primary.extend(canonical[key] for key in resolved if key in canonical)
    popular = select(Rating.track_id, func.count().label('popularity')).where(
        Rating.value.in_(['love', 'like'])).group_by(Rating.track_id).subquery()
    tracks = list(await session.scalars(select(Track).outerjoin(popular, popular.c.track_id == Track.id)
        .order_by(popular.c.popularity.desc().nullslast(), Track.id).limit(limit)))
    fallback = await load_items(session, tracks)
    return deduplicate(primary), list(fallback.values())


def candidate_item(metadata):
    if not isinstance(metadata, TrackCandidate) or not metadata.artist or not metadata.title:
        return None
    if not comparison_text(metadata.artist) or not comparison_text(metadata.title):
        return None
    item = Item(metadata, identities=aliases(metadata))
    for tag in metadata.tags:
        name, weight = comparison_text(tag.name), tag_weight(tag.weight)
        if name and weight > 0:
            item.tags[name] = max(item.tags.get(name, 0), weight)
    return item


def merge(left, right):
    """Keep display metadata from the canonical track when one exists."""
    if left.track_id is None and right.track_id is not None:
        left, right = right, left
    a, b = left.metadata, right.metadata
    left.metadata = replace(a, album=a.album or b.album, artwork_url=a.artwork_url or b.artwork_url,
                            duration=a.duration if a.duration is not None else b.duration,
                            external_ids={**b.external_ids, **a.external_ids})
    for name, weight in right.tags.items():
        left.tags[name] = max(left.tags.get(name, 0), weight)
    for seed_id, score in right.links.items():
        previous = left.links.get(seed_id)
        left.links[seed_id] = max(previous, score) if previous is not None and score is not None else previous if previous is not None else score
    left.sources.update(right.sources)
    left.identities.update(right.identities)
    if left.track_id is not None:
        left.identities.add(("track", left.track_id))
    return left


def deduplicate(items):
    # Union every overlapping group, including transitive ID/name aliases.
    groups, lookup, counter = {}, {}, 0
    for item in items:
        if item.track_id is not None:
            item.identities.add(("track", item.track_id))
        overlapping = sorted({lookup[key] for key in item.identities if key in lookup})
        for group in overlapping:
            item = merge(groups.pop(group), item)
        group = counter
        counter += 1
        groups[group] = item
        for key in item.identities:
            lookup[key] = group
    return list(groups.values())


def bound_relationships(relationships, positive_ids):
    bounded = defaultdict(list)
    for positive in (True, False):
        seed_ids = sorted(key for key in relationships if (key in positive_ids) == positive)
        count = 0
        for position in range(S.MAX_EDGES_PER_SEED):
            for seed_id in seed_ids:
                if position < len(relationships[seed_id]) and count < S.MAX_SIMILAR_CANDIDATES:
                    bounded[seed_id].append(relationships[seed_id][position])
                    count += 1
            if count == S.MAX_SIMILAR_CANDIDATES:
                break
    return bounded


async def generate(database, profile, providers, limit):
    now = utc_now()
    seeds = profile.positives + profile.negatives
    positive_ids = {seed.item.track_id for seed in profile.positives}
    keys = {seed.item.track_id: cache_key("lastfm", "get_similar_tracks",
            (seed.item.metadata.artist, seed.item.metadata.title)) for seed in seeds}
    relationships, fresh, related_artists = defaultdict(list), set(), {}
    async with database.sessions() as session:
        edges = await load_edges(session, sorted(positive_ids))
        edges += await load_edges(session, sorted(set(keys) - positive_ids))
        cached = {row.key: row for row in await session.scalars(select(ProviderCache)
                  .where(ProviderCache.key.in_(keys.values())).order_by(ProviderCache.key).limit(S.MAX_CACHED_SEEDS))}
    for edge in edges:
        if edge.provider != "lastfm" or edge.updated_at + S.RELATIONSHIP_TTL + S.RELATIONSHIP_GRACE <= now:
            continue
        try:
            metadata = replace(decode_track(edge.candidate), score=edge.score)
        except (KeyError, TypeError, ValueError):
            continue
        relationships[edge.track_id].append(metadata)
        if edge.updated_at + S.RELATIONSHIP_TTL > now:
            fresh.add(edge.track_id)
    for seed_id, key in keys.items():
        record = cached.get(key)
        if record and record.expires_at + S.RELATIONSHIP_GRACE > now:
            try:
                values = decode(record.payload)
            except (KeyError, TypeError, ValueError):
                continue
            if isinstance(values, list):
                if record.expires_at > now:
                    fresh.add(seed_id)
                    relationships[seed_id] = values[:S.MAX_EDGES_PER_SEED]
                elif values and seed_id not in fresh:
                    relationships[seed_id] = values[:S.MAX_EDGES_PER_SEED]

    relationships = bound_relationships(relationships, positive_ids)

    def related():
        result = {}
        for seed_id, values in relationships.items():
            for metadata in values:
                if metadata.artist and (score := clamp(metadata.score)) is not None and score > 0:
                    key = (seed_id, comparison_text(metadata.artist))
                    result[key] = max(result.get(key, 0), score)
        return result

    related_artists = related()
    async with database.sessions() as session:
        local = await local_candidates(session, profile, related_artists)

    # Only fill a sparse pool. Fresh empty caches also prevent another request.
    available = [item for values in (relationships[seed_id] for seed_id in positive_ids)
                 for metadata in values if (item := candidate_item(metadata)) is not None]
    available = [item for item in deduplicate(local + available)
                 if item.track_id not in profile.rated_ids and not item.identities & profile.rated_aliases
                 and not any(profile.history_aliases.get(key, now - S.HISTORY_WINDOW) > now - S.HISTORY_COOLDOWN
                             for key in item.identities)]
    calls = 0
    if providers is not None and len(available) < limit:
        artist_seeds = defaultdict(deque)
        for seed in profile.positives:
            artist_seeds[comparison_text(seed.item.metadata.artist)].append(seed)
        online_seeds = []
        while artist_seeds:
            for artist in list(artist_seeds):
                online_seeds.append(artist_seeds[artist].popleft())
                if not artist_seeds[artist]:
                    del artist_seeds[artist]
        for seed in online_seeds:
            seed_id = seed.item.track_id
            if seed_id in fresh or calls >= max(0, S.MAX_PROVIDER_CALLS - 1):
                continue
            calls += 1
            try:
                async with asyncio.timeout(S.PROVIDER_TIMEOUT):
                    values = await providers.call("lastfm", "get_similar_tracks", seed.item.metadata.artist, seed.item.metadata.title)
                if isinstance(values, list):
                    relationships[seed_id] = values[:S.MAX_EDGES_PER_SEED]
            except (ProviderError, TimeoutError):
                # Do not log exception bodies, identities, URLs or provider payloads.
                logger.warning("Recommendation provider unavailable; using cached/local candidates.")
        relationships = bound_relationships(relationships, positive_ids)
        related_artists = related()
        async with database.sessions() as session:
            local = await local_candidates(session, profile, related_artists)

    candidates, negative_links = list(local), defaultdict(dict)
    for seed_id, values in relationships.items():
        for metadata in values:
            item = candidate_item(metadata)
            if item is None:
                continue
            score = clamp(metadata.score)
            if seed_id in positive_ids:
                item.links[seed_id] = score
                item.sources.add("lastfm_similar")
                candidates.append(item)
            else:
                for key in item.identities:
                    negative_links[key][seed_id] = score
    candidates = deduplicate(candidates)
    async with database.sessions() as session:
        resolved, tracks = await resolve_tracks(session, candidates)
        canonical = await load_items(session, tracks)
    merged = []
    for index, item in enumerate(candidates):
        track_id = resolved[index]
        if track_id == -1:
            continue
        if track_id is not None:
            item = merge(canonical[track_id], item)
        merged.append(item)
    candidates = deduplicate(merged)
    candidates = [item for item in candidates if item.track_id not in profile.rated_ids and not item.identities & profile.rated_aliases]
    candidates = [item for item in candidates if not any(
        profile.history_aliases.get(key, now - S.HISTORY_WINDOW) > now - S.HISTORY_COOLDOWN
        for key in item.identities)]
    fallback_artists = {}
    for positive in sorted(profile.positives, key=seed_weight, reverse=True):
        artist = positive.item.metadata.artist
        fallback_artists.setdefault(comparison_text(artist), artist)
    for artist in list(fallback_artists.values())[:S.MAX_PROVIDER_CALLS]:
        if providers is None or candidates or calls >= S.MAX_PROVIDER_CALLS:
            break
        calls += 1
        try:
            async with asyncio.timeout(S.PROVIDER_TIMEOUT):
                values = await providers.call("lastfm", "get_artist_top_tracks", artist)
            fallback = [item for metadata in values[:S.MAX_EDGES_PER_SEED] if (item := candidate_item(metadata)) is not None
                        and comparison_text(metadata.artist) == comparison_text(artist)] if isinstance(values, list) else []
            async with database.sessions() as session:
                resolved, tracks = await resolve_tracks(session, fallback)
                canonical = await load_items(session, tracks)
            for index, item in enumerate(fallback):
                track_id = resolved[index]
                if track_id == -1:
                    continue
                if track_id is not None:
                    item = merge(canonical[track_id], item)
                if item.track_id in profile.rated_ids or item.identities & profile.rated_aliases:
                    continue
                if any(profile.history_aliases.get(key, now - S.HISTORY_WINDOW) > now - S.HISTORY_COOLDOWN
                       for key in item.identities):
                    continue
                item.sources.add("artist_top_tracks")
                candidates.append(item)
            candidates = deduplicate(candidates)
        except (ProviderError, TimeoutError):
            logger.warning("Recommendation artist fallback unavailable.")
    for item in candidates:
        for key in sorted(item.identities):
            for seed_id, score in negative_links[key].items():
                previous = item.links.get(seed_id)
                item.links[seed_id] = max(previous, score) if previous is not None and score is not None else previous if previous is not None else score

    # Cap fairly across dominant seed patterns, not by most recent submission.
    groups = defaultdict(list)
    for item in candidates:
        scores = [(evidence(seed, item, related_artists)[0] * seed_weight(seed), seed.item.track_id)
                  for seed in profile.positives]
        affinity, seed_id = max(scores, key=lambda pair: (pair[0], -pair[1]))
        if affinity > 0:
            groups[seed_id].append((affinity, item))
    queues = {key: deque(item for _, item in sorted(rows, key=lambda row: (-row[0], comparison_text(row[1].metadata.artist), comparison_text(row[1].metadata.title))))
              for key, rows in groups.items()}
    bounded = []
    while queues and len(bounded) < S.MAX_CANDIDATES:
        for key in sorted(list(queues)):
            bounded.append(queues[key].popleft())
            if not queues[key]:
                del queues[key]
            if len(bounded) == S.MAX_CANDIDATES:
                break
    return bounded, related_artists
