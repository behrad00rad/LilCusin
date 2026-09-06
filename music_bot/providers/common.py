import math
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import aiohttp

TIMEOUT = aiohttp.ClientTimeout(total=20, connect=5, sock_read=10)


class Failure(StrEnum):
    NETWORK = "network or timeout"
    RATE_LIMIT = "rate limited"
    UNAVAILABLE = "service unavailable"
    INVALID_RESPONSE = "malformed response"
    REQUEST = "request rejected"
    AUTH = "API key rejected"


class ProviderError(Exception):
    """Contains only a fixed category, never URLs, credentials or response text."""

    def __init__(self, reason: Failure):
        self.reason = reason
        super().__init__(reason.value)


@dataclass(frozen=True)
class Tag:
    name: str
    source: str
    weight: float | None = None


@dataclass(frozen=True)
class Release:
    title: str | None
    source: str
    external_id: str | None = None
    date: str | None = None
    country: str | None = None


@dataclass(frozen=True)
class TrackCandidate:
    title: str | None
    artist: str | None
    source: str
    album: str | None = None
    artwork_url: str | None = None
    duration: float | None = None  # Seconds, consistently across providers.
    external_ids: dict[str, str] = field(default_factory=dict)
    tags: tuple[Tag, ...] = ()
    score: float | None = None
    releases: tuple[Release, ...] = ()

    @property
    def missing_metadata(self) -> tuple[str, ...]:
        # Optional fields indicate coverage, not a failed request.
        return tuple(
            name for name in ("title", "artist", "album", "duration", "external_ids")
            if not getattr(self, name)
        )


def text(value: Any) -> str | None:
    if isinstance(value, str):
        return value.strip() or None
    return None


def number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
        return result if math.isfinite(result) and result >= 0 else None
    except (TypeError, ValueError):
        return None


def items(value: Any) -> list[dict]:
    if value is None or value == "":
        return []
    if isinstance(value, dict):
        return [value] if value else []
    if isinstance(value, list) and all(isinstance(item, dict) for item in value):
        return value
    raise ProviderError(Failure.INVALID_RESPONSE)


async def request_json(session: aiohttp.ClientSession, url: str, **kwargs) -> dict:
    try:
        async with session.get(
            url, timeout=TIMEOUT, allow_redirects=False, **kwargs
        ) as response:
            if response.status == 429:
                raise ProviderError(Failure.RATE_LIMIT)
            if response.status >= 500:
                raise ProviderError(Failure.UNAVAILABLE)
            if response.status in (401, 403):
                raise ProviderError(Failure.AUTH)
            if response.status != 200:
                raise ProviderError(Failure.REQUEST)
            payload = await response.json(content_type=None)
    except (aiohttp.ClientError, TimeoutError, OSError):
        raise ProviderError(Failure.NETWORK) from None
    except (ValueError, UnicodeError):
        raise ProviderError(Failure.INVALID_RESPONSE) from None
    if not isinstance(payload, dict):
        raise ProviderError(Failure.INVALID_RESPONSE)
    return payload
