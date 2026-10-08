"""Developer-only live checks: python -m music_bot.validate_sources."""

import argparse
import asyncio
import os

import aiohttp

from .__main__ import configure_logging
from .config import ConfigError, load_environment, required_variable
from .providers.common import ProviderError, TrackCandidate
from .providers.lastfm import LastFMClient
from .providers.musicbrainz import MusicBrainzClient

# Easy to edit; repeat --song ARTIST TITLE to supply your own Unicode samples.
DEFAULT_SONGS = [("Radiohead", "Creep"), ("گوگوش", "من آمده‌ام")]


def report(value: str) -> None:
    for name in ("TELEGRAM_BOT_TOKEN", "LASTFM_API_KEY"):
        if secret := os.environ.get(name, "").strip():
            value = value.replace(secret, "[redacted]")
    print(" ".join(value.split()))


def describe(provider: str, track: TrackCandidate | None) -> None:
    if track is None:
        report(f"  {provider}: provider available; track not found")
        return
    report(f"  {provider}: provider available; track found: {track.artist or '?'} - {track.title or '?'}"[:350])
    if track.missing_metadata:
        report("    incomplete metadata: " + ", ".join(track.missing_metadata))
    else:
        report("    metadata: title, artist, album, duration and identifiers present")


async def validate(songs: list[tuple[str, str]]) -> int:
    load_environment()
    status = 0
    try:
        key = required_variable("LASTFM_API_KEY")
    except ConfigError as error:
        report(str(error))
        key = None
        status = 2
    async with aiohttp.ClientSession() as session:
        lastfm = LastFMClient(session, key) if key else None
        musicbrainz = MusicBrainzClient(session)
        for artist, title in songs:
            report(f"Sample: {artist} - {title}")
            if lastfm:
                try:
                    matches = await lastfm.search_tracks(artist, title)
                    report(f"  Last.fm search: provider available; {len(matches)} candidates")
                    # Direct lookup also runs when search has no matches.
                    track = await lastfm.get_track_info(artist, title)
                    describe("Last.fm metadata", track)
                    tags = await lastfm.get_top_tags(artist, title)
                    similar = await lastfm.get_similar_tracks(artist, title)
                    report(f"    tags: {len(tags)}; similar tracks: {len(similar)}")
                except ProviderError as error:
                    report(f"  Last.fm: provider/request failure ({error.reason.value})")
                    status = max(status, 1)
            try:
                matches = await musicbrainz.search_recordings(artist, title)
                report(f"  MusicBrainz search: provider available; {len(matches)} candidates")
                if not matches:
                    describe("MusicBrainz", None)
                else:
                    candidate = matches[0]
                    mbid = candidate.external_ids.get("musicbrainz")
                    track = await musicbrainz.get_recording(mbid) if mbid else candidate
                    describe("MusicBrainz metadata", track)
            except ProviderError as error:
                report(f"  MusicBrainz: provider/request failure ({error.reason.value})")
                status = max(status, 1)
    return status


def run() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--song", nargs=2, action="append", metavar=("ARTIST", "TITLE"))
    args = parser.parse_args()
    configure_logging()
    try:
        return asyncio.run(validate(args.song or DEFAULT_SONGS))
    except KeyboardInterrupt:
        return 130
    except Exception:
        report("Validation failed unexpectedly; details omitted for privacy.")
        return 1


if __name__ == "__main__":
    raise SystemExit(run())
