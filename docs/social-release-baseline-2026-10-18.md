# Social-release baseline â€” 2026-10-18 (Asia/Tehran)

## Scope and outcome

The user authorized starting the baseline audit before the first social release,
and supplied an SSH credential file to inspect the deployed VPS. SSH succeeded
using the existing trusted host key. Credentials were read in memory and excluded
from output and documentation. No production files, configuration or data were
changed; the bot was not restarted and no second poller was started.

## Deployed source versus local source

- The systemd bot service was active/running at inspection, using Python 3.13.5.
  Service liveness does not prove a successful Telegram recommendation journey.
- Both inspected checkouts report branch `codex/safe-publish`, HEAD `27c12a2`.
- The deployed checkout has one tracked modification: `music_bot/get_song.py`.
  Preserve and reconcile it before any deployment; do not overwrite the tree.
- The local checkout already contained uncommitted deployment/audio/provider/
  recommendation changes and documentation. These predate this audit and were
  not implemented by this session.
- SHA-256 comparisons after normalizing Windows/Linux line endings show equal
  `models.py` and `database.py`, but differing `miniapp.py`, recommendation
  `candidates.py`, provider `lastfm.py` and `get_song.py`. A matching HEAD alone
  is therefore insufficient to establish release parity. This check compares
  source files on disk, not code already imported by the running process.
- The deployed source lacks `docs/social-product-vision.md`. Public social
  profiles and reciprocal exchanges are not evidenced by the inspected models
  or Mini App routes.

## Discovery verification

The initial local async suite stalled. A bounded traceback located the stall in
Python's Windows asyncio event-loop creation, specifically socketpair/accept,
before the first async test setup. This is an execution restriction, not evidence
of a recommendation deadlock. The focused rerun outside that restriction passed all 40 recommendation/provider
tests in 101.341 seconds, including the DNA empty-similarity fallback. These
use isolated fixtures and mocks, not live-provider or deployed-bot verification.

## Remaining release gates

T00 remains partial: runtime feature flags and the Mini App serving path were not
inspected. T01 remains open until cancellation checks and a representative private-bot
journey are verified; the recommendation/provider suite now passes. No live user queries, private configuration,
production database or message history were inspected. No recommendation-quality,
visual, deployment or social-release success is claimed.
