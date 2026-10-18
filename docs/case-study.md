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

## 2026-10-17 — Recovery for empty More like this results

A user reported an empty result from DNA / Kendrick Lamar. The local patch expands
the track-similarity pool and adds same-artist discovery when a selected song has
no eligible candidates, without requiring ratings. Implementation and regression
cases are present; runtime checks stalled in the local asyncio environment.
Syntax/diff checks pass. Deployment and live outcome remain unverified; see
[decision](decisions.md) and [evidence](evidence.md).

## 2026-10-17 — Proposed social direction

The user asked to document a Telegram-native community around music identity,
sharing and connection. The [vision and phased task list](social-product-vision.md)
describe profiles, song exchanges and later social features while preserving
the current bot/Mini App foundation. This is planning documentation only;
social implementation and commercial validation remain future work.


## Deployment reliability - 2026-10-18

A targeted audit found that the basic install instructions omitted the existing
optional audio requirements, Python 3.13 needed audioop compatibility, and a silent
three-second artwork budget could interrupt an eight-second image request. The
local change adds compatible dependency bounds, safe stage diagnostics, a 12-second
artwork budget and offline preflight. All 62 focused tests passed; synthetic M4A
artwork and tags also round-tripped. The deployment guide explicitly preserves
production-only changes and persistent data. These are local, uncommitted results;
clean Debian 13/Python 3.13 installation remains unverified after download timeouts,
and no production deployment or connection occurred.


## 2026-10-18 — Establishing the social-release baseline

Before adding music identity and exchange features, a read-only VPS inspection
confirmed the running service and found that identical Git revisions did not
mean identical local/deployed source. Existing edits were preserved. The first
local async-test stall was traced to event-loop initialization rather than the
recommendation code. [Baseline evidence](social-release-baseline-2026-10-18.md)
keeps service liveness, test results and future social implementation separate.


## 2026-10-18 — A deliberately selected music identity

The first implemented social slice lets someone create a private taste card and
choose exactly what to share: a nickname, bio and five songs. Short-lived links
can be hidden or replaced without exposing private ratings or Telegram contacts.
Both chat and Mini App use the same ownership rules. Local privacy/lifecycle
tests and English/Persian phone/desktop checks passed. It remains uncommitted
and undeployed; comparison and reciprocal exchanges are still future work. See
[implementation and evidence](taste-card-release-2026-10-18.md).


## 2026-10-18 — Deployed search, recognition and chat UX repairs

Artist queries were being treated mainly as titles, reversed scrobble identities entered the catalogue, and TikTok soundtrack selection differed from uploaded-video recognition. The deployed repair adds artist/alias discovery, guards and corrects reversed metadata, fingerprints embedded video audio, retains search results and sends uncluttered audio messages. Server regressions and real-provider probes verify the release; visual Telegram confirmation and a live standalone Mini App remain outside this pass. See [verified account](search-recognition-ux-2026-10-18.md).


## 2026-10-18 — Mini App Get song

The primary Mini App song action now returns to LilCusin to get audio instead of opening Lil Bro. A short-lived owner-bound grant identifies the selected song, while the existing delivery workflow handles fetching and choices. Locally tested; production delivery remains unverified.


## 2026-10-18 — Taste-card/Get Song deployment and UI brief

The selected music card and same-bot Get Song action are deployed. Restoring the inactive API/connector removed the gap between the running bot and public visual surface. A consistent backup, scoped file reconciliation, VPS staging tests and public hash/auth checks support the release. The reviewed future UI remains separate from shipped functionality. See [deployment evidence](deployment-2026-10-18.md).

## 2026-10-18 — Reducing search waiting

Search waited for old-message deletion and repeated metadata work. The deployed
performance pass acknowledges first, cleans up in the background, reuses completed
searches and appends late choices to stable buttons. In a small engine sample,
repeat queries fell from about 1.94 seconds to 57–91 ms; cold search remained
about 3.4 seconds. Real Telegram perceived latency remains unverified.
[Verified scope](search-performance-2026-10-18.md).

## 2026-10-18 — Bot onboarding, portrait and selected-song consent
The next local slice connects a short bot welcome to selected favorites, a Stories portrait and deliberate recipient-bound consent. Privacy revisions revoke stale agreements and no fake compatibility score appears. Locally tested; actual comparison, swaps and production verification remain separate. [Implementation](onboarding-portrait-consent-2026-10-18.md).

## 2026-10-19 — Recovering a rejected live performance

A Navan medley failed because upload metadata reversed its titles and added a
cover label. A narrowly scoped matcher change now offers the verified performance
with explicit selection while retaining wrong-version guards. Deployed after 18
focused passing tests; playback remains unverified. [Evidence](navan-medley-fix-2026-10-19.md).


## 2026-10-19 — A local two-way music loop

The selected card now leads to an explainable comparison and a deliberate reciprocal pick, instead of ending at a share link. Private saves remain separate from explicit ratings. Block, report and opt-in alerts accompany the interaction; no unsupported compatibility score or social count is introduced. The bilingual Mini App exposes the same state as chat. Locally verified with fictional users and scoped tests; not deployed or cohort-validated. [Release and limits](social-loop-release-2026-10-19.md).

### Navan follow-up verification limit

The first deployed matcher patch passed an idealized fixture but missed stored
identity normalization. User feedback exposed the gap. A corrected candidate now
passes stored-input tests and real temporary audio retrieval; deployment and
Telegram receipt remain pending. [Evidence](navan-medley-fix-2026-10-19.md).

Navan follow-up deployment confirmed: user-approved one-file correction deployed,
source hash verified, restart succeeded; all 20 isolated regressions passed against
the deployed module. The identical candidate retrieved/validated actual audio.
Telegram receipt/playback remains unverified; Mini App unchanged.
[Deployment evidence](navan-medley-fix-2026-10-19.md).


## 2026-10-19 — Verified release

The music-identity release now joins consented taste cards, explainable comparisons and reciprocal song exchange across chat and Mini App. It is committed and deployed, with measured staging and runtime evidence; public connectivity and real two-account delivery remain explicit validation gaps. See [release evidence](deployment-2026-10-19.md).
