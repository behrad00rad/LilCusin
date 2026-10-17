# View-aware discovery and spelling recovery — 2026-10-17 (Asia/Tehran)

The user correctly challenged the previous fallback: a popular video can be absent
from a bounded store/catalogue title search, and `prayer kendick` should not require
perfect spelling. The previous artist-refinement UI did not address either gap.

## Implemented behavior

Short Telegram title queries (one to eight words) now run bounded catalogue search
and public YouTube metadata discovery concurrently. The existing extractor lists
at most twenty entries with `--flat-playlist --skip-download`. Conventional song
labels must match the query, including bounded one-character spelling errors or
adjacent transpositions. Known reaction/instrumental/cover/remix labels are excluded
unless requested. Up to three hints are independently checked against catalogues;
unvalidated uploads never become canonical suggestions. No audio is downloaded,
fingerprinted, automatically selected or rated.

Observed upload view counts rank validated discovery suggestions, which precede
the remaining catalogue matches. Repeated uploads are not summed: the highest
observed matching upload is used. Counts are labelled YouTube views in the bot;
they are not song-wide plays, monthly listeners or Deezer popularity ranks.
Missing/invalid counts remain unknown. Discovery-only fuzzy matching does not
change persisted identity keys or automatic confirmation thresholds.

Discovery admits at most two concurrent queries, deduplicates identical requests,
caches successful results for fifteen minutes and empty results for one minute,
and bounds its in-memory cache to 128 hashed query keys. Catalogue validation has
a 1.8-second per-call budget; discovery has a six-second total budget within the
existing seven-second chat search deadline. Cancellation drains the subprocess
and removes the temporary directory. A failed discovery backs off for a minute;
catalogue results remain usable. Turning discovery off preserves the local fast
path. Rating uploads continue to avoid automatic fingerprinting/downloads.

## Live metadata evidence

Using the actual discovery and catalogue pipeline, disposable data and no Last.fm:

| Query | Expected identity | Position | Elapsed |
| --- | --- | --- | --- |
| prayer | Kendrick Lamar — Prayer | 1 | 5.55 s |
| prayer kendick | Kendrick Lamar — Prayer | 1 | 4.17 s |
| prayer kendick, repeated | Same cached result | 1 | 0.08 s |

The matched upload reported 3,879,049 views at inspection. Counts can change. These
are individual live metadata probes, not playback verification, global popularity
statistics or latency guarantees. Broad discovery is bounded and service/network
availability can change; other artists and typos are not universally guaranteed.
YouTube Music search probes returned no entries in this environment, so the working
regular-video metadata adapter was used. Mini App UI/assets/Worker and production
are outside scope. Existing unrelated edits remain separate.

## Verification and runtime

The initial discovery/lyrics/title/popularity run passed 45 tests in 64.009
seconds. The final identity/provider/flow/cancellation run passed 80 tests in
184.071 seconds. A separate final cache/resource compatibility run passed 20 tests
in 24.705 seconds; three focused presentation and existing artist-hint checks
passed in 9.098 seconds. Counts overlap and are not a full repository-suite claim.
Coverage includes view provenance, failed validation, no fabricated counts,
short-word typo exclusions, cache sharing, bounded concurrent extraction, cleanup
on cancellation, operator off mode, existing owner checks and optional ratings.
Compilation and scoped whitespace checks passed.

Only the idle isolated local test bot was restarted. Read-only checks confirmed
the expected test identity, polling and registered commands with Mini App disabled
on build `chat-7794021096e0`. Its configured discovery provider is YouTube. Actual
phone rendering, user selection and playback of these new results remain unverified.
