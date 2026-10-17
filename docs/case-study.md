# From unknown recordings to playable songs

LilCusin previously identified songs from title/artist metadata. The user requested
recognition from recordings and shared links, then asked for playable audio rather
than only a song title and Shazam link.

The implementation uses ShazamIO for bounded fingerprint recognition and connects
matches to the existing Get song worker. It preserves source-selection controls,
request limits, cancellation and Telegram file caching. Shazam covers now feed the
normal embedded artwork/thumbnail pipeline, including for ordinary Get song
requests when Last.fm artwork is missing or unavailable.

A live recognition of a live edition exposed the need to choose a different
recording. Find other versions now browses alternate editions while keeping the
original recognition and storing each selected edition separately. Covers/karaoke
are excluded and source labels remain best-effort.

Search feedback exposed two gaps: artist matches were discarded by title filtering,
and two-word lyric hints never reached discovery. Both paths were corrected and
independent catalogue fallback added. The user's Deftones and short Kanye hint
examples returned useful results live, without hard-coded song mappings.

Public social-post adapters share the recognition pipeline. The supplied TikTok
post was verified after adding its missing supported downloader transport. Other
platform adapters have local bounds/security checks but still need actual-post
verification. Earlier audio messages are unchanged and external sources can fail.

The isolated local test bot has been updated and live transport/artwork checks
passed. Production deployment is outside this session. See decisions.md and
evidence.md for the architecture, evidence and remaining limits.

Release preparation on 2026-10-17 verified 28 recognition/social-search tests,
compilation and dependency compatibility. Broader test runs did not complete;
production and remaining live-platform limitations above still apply.


## 2026-10-17 — Local UX audit

Completed a code-based review of chat navigation, Mini App parity, search and delivery critical paths. Findings and proposed priorities: [UX audit](ux-audit-2026-10-17.md). No application changes, live Telegram checks, latency measurements, or test runs in this audit; implementation and deployment remain unverified. Existing user edits were preserved. Recommendations have not been accepted as implementation decisions.

## 2026-10-17 — Approved local chat phases 1–3

The user approved runtime identity, chat-flow improvements, and performance work, while explicitly deferring the Mini App. Implemented details, rationale, measured offline comparisons, and verification status are maintained in [local bot flow results](bot-flow-results-2026-10-17.md). The current changes remain uncommitted; production and pre-existing Worker edits are outside this work.

## 2026-10-17 — Reported recording failures

Investigated the user's reported source-search and recognition failures and implemented guarded candidate recovery, metadata-aware audio routing, and duration-aware fingerprint sampling. Findings, authorization limits and validation status: [recording recovery](recording-recovery-2026-10-17.md). Candidate recovery is distinct from verified audio delivery; the Mini App and production remain outside this change.

## 2026-10-17 — Rating intent and native bot controls

The user explicitly requested rating uploads without automatic recognition, compact Details controls, colors and Close on search results. Implemented changes and verification status: [rating and UI follow-up](rating-ui-2026-10-17.md). This supersedes automatic fingerprinting of untagged song uploads; recognition is explicit for audio files. Production and Mini App are outside this change.
# 2026-10-17 — Search resilience correction

A partial metadata-provider failure incorrectly appeared as an outage when an
uploaded file had no usable match. The local bot now distinguishes healthy misses
from total failures and runs independent fallbacks together. Rating uploads with
unmatched tags request corrected names. Verified with 75 regressions and one
public live sample; Last.fm authentication itself remains unresolved.

The subsequent exact-song diagnosis exposed expanded performer credits as the
remaining retrieval issue. Title-only recovery now offers plausible exact-title
matches for confirmation. iTunes supplied the user's expected song in a live
metadata check; MusicBrainz's first title page did not.
# 2026-10-17 — Search aliases and refinement

User-reported omissions exposed censored catalogue spelling and provider ranking
that suppressed unknown-popularity exact matches. Search now supports bounded
masked-title aliases and catalogue diversity. Common-title results can be refined
directly with an artist; unreleased catalogue entries remain eligible, while
intended-artist inference and universal coverage are not claimed.
# 2026-10-17 — Popular video discovery and forgiving search

The user's typo and unreleased-song feedback showed catalogue-only ranking was
insufficient. Bounded metadata discovery now supplies validated song suggestions
with observed video-view provenance and small spelling-error recovery. Both live
reported Prayer queries returned the expected song first, while repeat search
used cache. This remains explicit discovery/selection, not automatic recognition.
