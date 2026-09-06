"""Developer-only recommendation evaluation. Never sends Telegram messages."""

import argparse
import asyncio
import os
from contextlib import AsyncExitStack
from pathlib import Path

import aiohttp

from . import messages
from .__main__ import configure_logging
from .cache import CachedProviders
from .config import ConfigError, load_environment, required_variable
from .database import DEFAULT_PATH, Database
from .providers.lastfm import LastFMClient
from .recommendations import RecommendationService
from .validate_sources import report


def short_metadata(value):
    # Redact before truncation so even a secret crossing the limit is removed.
    for name in ("TELEGRAM_BOT_TOKEN", "LASTFM_API_KEY"):
        if secret := os.environ.get(name, "").strip():
            value = value.replace(secret, "[redacted]")
    return " ".join(value.split())[:150]


async def evaluate(args) -> int:
    load_environment()
    database = Database(args.database)
    try:
        await database.initialize()
        async with AsyncExitStack() as stack:
            providers = None
            if args.online:
                key = required_variable("LASTFM_API_KEY")
                http = await stack.enter_async_context(aiohttp.ClientSession())
                providers = CachedProviders(database, LastFMClient(http, key), None)
            result = await RecommendationService(database, providers).recommend_for_user(
                args.telegram_user_id, args.limit, random_seed=args.seed)
            if result.status != "ok":
                report(messages.REC_INSUFFICIENT if result.status == "insufficient_preferences" else messages.REC_EMPTY)
            for index, row in enumerate(result.recommendations, 1):
                report(f"{index}. {short_metadata(row.artist)} — {short_metadata(row.title)} | score={row.score:.4f} | {row.reason} | "
                       f"sources={','.join(row.sources)} | exploration={row.exploration}")
            report("Preview only: recommendation history was not recorded.")
        return 0
    finally:
        await database.close()


def run() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("telegram_user_id", type=int)
    parser.add_argument("--limit", type=int, default=5, choices=range(1, 21))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--database", type=Path, default=DEFAULT_PATH)
    parser.add_argument("--online", action="store_true", help="Allow bounded cached Last.fm fallback for a sparse pool")
    args = parser.parse_args()
    if args.telegram_user_id <= 0:
        parser.error("Telegram user ID must be positive")
    configure_logging()
    try:
        return asyncio.run(evaluate(args))
    except ConfigError as error:
        report(str(error))
        return 2
    except KeyboardInterrupt:
        return 130
    except Exception:
        report("Recommendation evaluation failed; details omitted for privacy.")
        return 1


if __name__ == "__main__":
    raise SystemExit(run())
