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
from .scoring import clamp, evidence, tag_weight
from .types import Item

logger = logging.getLogger(__name__)


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
    left.analyses.update({key: value for key, value in right.analyses.items() if key not in left.analyses})
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


async def generate(database, profile, providers, limit):
    now = utc_now()
    seeds = profile.positives + profile.negatives
    positive_ids = {seed.item.track_id for seed in profile.positives}
    keys = {seed.item.track_id: cache_key("lastfm", "get_similar_tracks",
            (seed.item.metadata.artist, seed.item.metadata.title)) for seed in seeds}
    relationships, fresh, related_artists = defaultdict(list), set(), {}
    async with database.sessions() as session:
        edges = await load_edges(session, list(keys))
        cached = {row.key: row for row in await session.scalars(select(ProviderCache).where(ProviderCache.key.in_(keys.values())))}
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
    available = [item for item in deduplicate(local + available) if not item.identities & profile.rated_aliases]
    if providers is not None and len(available) < limit:
        calls = 0
        for seed in profile.positives:
            seed_id = seed.item.track_id
            if seed_id in fresh or calls >= S.MAX_PROVIDER_CALLS:
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
    for item in candidates:
        for key in sorted(item.identities):
            for seed_id, score in negative_links[key].items():
                previous = item.links.get(seed_id)
                item.links[seed_id] = max(previous, score) if previous is not None and score is not None else previous if previous is not None else score

    # Cap fairly across dominant seed patterns, not by most recent submission.
    groups = defaultdict(list)
    for item in candidates:
        scores = [(evidence(seed, item, related_artists)[0] * S.RATING_WEIGHTS[seed.rating], seed.item.track_id)
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
