# Recognition and search evidence

## Verification during this session

- Initial inspection recorded pre-existing Worker/deployment changes and a
  recommendation-test cleanup; those are outside this release.
- The user confirmed actual test-bot recognition responds correctly. Telegram
  verified the configured local identity as @testlilcuhbot; the user confirmed it
  after initially naming a different username.
- A public ShazamIO fixture was recognized as Gloria Gaynor - I Will Survive.
  Real Telegram audio/voice/video transport tests passed using synthetic inbound
  updates and actual downloads, recognition requests and result messages.
- Live recognition-to-full-song delivery reached done after a tester selected an
  offered recording. A later source-search issue was traced to using normalized
  database titles; searches now preserve catalogue punctuation. An intermittent
  download cause remained uncertain, but final delivery succeeded. Added bounded
  retries and fixed failure categories rather than exposing provider errors.
- Live Shazam artwork delivery returned a Telegram audio thumbnail and recorded
  successful cover embedding. Plain Get song also obtained a Shazam cover with
  Last.fm excluded from the live test.
- A live other-versions search offered original/unlabelled, live and remaster
  categories. It was cancelled without another live alternate-version download.
  Separate identity, owner/message checks and selection are tested locally.
- Live deftones search returned Deftones tracks. Someday kanye returned Kanye West
  - Ghost Town through discovery and independent catalogue matching.
- The user supplied a TikTok post. Initial extraction failed; installing the
  supported curl-cffi transport enabled download and recognition as The Smiths -
  Back to the Old House. No raw post URL is published here.

## Automated checks

Recorded regression runs passed 87 tests for delivery/search/recognition/chat
controls and 86 tests for search/providers/recognition/Mini App. Focused checks
passed after final changes, including 32 workflow tests, artwork replacement,
version selection and control authorization. Counts overlap; do not sum them.
Compilation, dependency compatibility and whitespace checks passed. A final
release test result is recorded separately when available.

## Limits and release scope

Actual posts from Instagram/Pinterest/X/SoundCloud/Vimeo were not live-tested.
Private, blocked or image-only posts can fail; source labels and Shazam matching
are not guarantees of recording identity. User confirmation of the latest button
UX is pending. Earlier Telegram messages are unchanged. Only the isolated local
test bot was restarted; this session did not deploy to the production VPS.
Local QA evidence stays ignored and contains no published credentials or chat IDs.

## 2026-10-17 — Release verification

Recognition and social/search regression: 28 tests passed. Python compilation,
dependency compatibility and staged whitespace checks passed. Broader discovery
and delivery runs were stopped after extended waits; no complete-suite pass is
claimed for this release. Earlier live checks above were not repeated.

The release includes the recognition/discovery changes and these study records.
Pre-existing Worker, deployment-note and recommendation-test edits remain outside
the commit. Production was not deployed. Commit and push identity are recorded
in the local Work Journal after remote verification.


## 2026-10-17 — Local UX audit

Completed a code-based review of chat navigation, Mini App parity, search and delivery critical paths. Findings and proposed priorities: [UX audit](ux-audit-2026-10-17.md). No application changes, live Telegram checks, latency measurements, or test runs in this audit; implementation and deployment remain unverified. Existing user edits were preserved. Recommendations have not been accepted as implementation decisions.

## 2026-10-17 — Approved local chat phases 1–3

The user approved runtime identity, chat-flow improvements, and performance work, while explicitly deferring the Mini App. Implemented details, rationale, measured offline comparisons, and verification status are maintained in [local bot flow results](bot-flow-results-2026-10-17.md). The current changes remain uncommitted; production and pre-existing Worker edits are outside this work.

## 2026-10-17 — Reported recording failures

Investigated the user's reported source-search and recognition failures and implemented guarded candidate recovery, metadata-aware audio routing, and duration-aware fingerprint sampling. Findings, authorization limits and validation status: [recording recovery](recording-recovery-2026-10-17.md). Candidate recovery is distinct from verified audio delivery; the Mini App and production remain outside this change.

## 2026-10-17 — Rating intent and native bot controls

The user explicitly requested rating uploads without automatic recognition, compact Details controls, colors and Close on search results. Implemented changes and verification status: [rating and UI follow-up](rating-ui-2026-10-17.md). This supersedes automatic fingerprinting of untagged song uploads; recognition is explicit for audio files. Production and Mini App are outside this change.
# 2026-10-17 — Local search fallback recovery

75 relevant regressions passed in 162.447 seconds; a separate focused 27-test run
passed. Public-sample bounded lookup with rejected primary returned five matches
in 1.51 seconds. Only the isolated local bot restarted. No private query replay,
production deployment, or Mini App changes. Last.fm credential remains invalid.
See [report](search-fallback-2026-10-17.md).

Expanded-tag follow-up: the user-specified Starting Over / LSD and the Search for
God match was present in iTunes and absent from MusicBrainz's first 100 title
results. Bounded recovery returned the exact candidate in 0.80 seconds. This was
metadata-only verification, not recognition, download, or user-confirmed playback.
# 2026-10-17 — Follow-up search cases

The bounded live workflow surfaced the censored joint-artist Paris recording at
position 5 in 2.44 seconds and qualified Kendrick Lamar / Prayer in 1.30 seconds.
Title-only Prayer did not include Kendrick in the inspected provider windows.
These are metadata probes, not playback or universal unreleased-song coverage.
See [full verification](search-aliases-2026-10-17.md).
# 2026-10-17 — Prayer popularity and typo probes

Actual metadata-only discovery returned Kendrick Lamar / Prayer first for prayer
(5.55 s) and prayer kendick (4.17 s), then repeated the typo query from cache in
0.08 s. The matched upload reported 3,879,049 views. No media was downloaded and
these samples are not total-song popularity or a latency SLA. See
[regressions, architecture and limitations](discovery-popularity-2026-10-17.md).
