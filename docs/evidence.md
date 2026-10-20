# Recognition and search evidence

## 2026-10-20 - Recommendation loop deployed

Release `4835ec7d93767fb4`, code `cbad204`, deployed after explicit approval.
Both exact Git and production-preserving candidates passed 183 isolated Linux
tests each. Consistent backup, 22 live hashes, four additive tables, active bot/API
and polling verified; unrelated source/configuration and Nginx PID preserved.
Existing dependency preflight gaps remain unchanged; no real Telegram receipt
claimed. See [deployment checkpoint](recommendation-loop-2026-10-19.md).

## 2026-10-19 - Private recommendation loop

185 distinct affected Windows fixture tests passed in the final sequential
nine-module run (260.772 s); 24 monitored source/test hashes stayed unchanged.
Coverage includes private request/save learning, queue persistence/concurrency,
feedback/ownership, bilingual copy, reset/forget and delivery/channel/social-save
compatibility. Shutdown scenarios additionally passed seven repeated executions.
All 16 chat cases passed again after final copy-only changes. Details are in the [resumable verification
record](recommendation-loop-2026-10-19.md), which retains earlier non-green runs.
Code committed/pushed as `cbad204`, remote SHA matched. Exact staged snapshot:
183 Windows tests passed; two unrelated working-tree cases excluded. Deployment
source transfer was blocked by automatic review, after safe staging/hash guards;
no live writes or service changes. See the same checkpoint for approval/resume.
No live Telegram/provider or phone claim.

## 2026-10-19 - Recommendation recovery

26 isolated recommendation tests passed on Windows, including two new regressions
for For You artist recovery and cooldown-aware online refill. In-memory syntax
and scoped whitespace checks passed. Initial permission/iteration failures are
retained in the [verification record](recommendation-recovery-2026-10-19.md).
User-approved release `27ccddcae8221606` deployed: 26 tests also passed in isolated
Linux staging, deployed SHA-256 matches the tested module, bot active and polling.
Unrelated sources/configuration and Mini App API PID unchanged. Initial deployment
rolled back safely; full preflight remains blocked by pre-existing missing
`packaging`, with identical old/new baseline and separate runtime imports passing.
Actual Telegram recommendation receipt remains unverified.

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

## 2026-10-17 â€” Release verification

Recognition and social/search regression: 28 tests passed. Python compilation,
dependency compatibility and staged whitespace checks passed. Broader discovery
and delivery runs were stopped after extended waits; no complete-suite pass is
claimed for this release. Earlier live checks above were not repeated.

The release includes the recognition/discovery changes and these study records.
Pre-existing Worker, deployment-note and recommendation-test edits remain outside
the commit. Production was not deployed. Commit and push identity are recorded
in the local Work Journal after remote verification.


## 2026-10-17 â€” Local UX audit

Completed a code-based review of chat navigation, Mini App parity, search and delivery critical paths. Findings and proposed priorities: [UX audit](ux-audit-2026-10-17.md). No application changes, live Telegram checks, latency measurements, or test runs in this audit; implementation and deployment remain unverified. Existing user edits were preserved. Recommendations have not been accepted as implementation decisions.

## 2026-10-17 â€” Approved local chat phases 1â€“3

The user approved runtime identity, chat-flow improvements, and performance work, while explicitly deferring the Mini App. Implemented details, rationale, measured offline comparisons, and verification status are maintained in [local bot flow results](bot-flow-results-2026-10-17.md). The current changes remain uncommitted; production and pre-existing Worker edits are outside this work.

## 2026-10-17 â€” Reported recording failures

Investigated the user's reported source-search and recognition failures and implemented guarded candidate recovery, metadata-aware audio routing, and duration-aware fingerprint sampling. Findings, authorization limits and validation status: [recording recovery](recording-recovery-2026-10-17.md). Candidate recovery is distinct from verified audio delivery; the Mini App and production remain outside this change.

## 2026-10-17 â€” Rating intent and native bot controls

The user explicitly requested rating uploads without automatic recognition, compact Details controls, colors and Close on search results. Implemented changes and verification status: [rating and UI follow-up](rating-ui-2026-10-17.md). This supersedes automatic fingerprinting of untagged song uploads; recognition is explicit for audio files. Production and Mini App are outside this change.
# 2026-10-17 â€” Local search fallback recovery

75 relevant regressions passed in 162.447 seconds; a separate focused 27-test run
passed. Public-sample bounded lookup with rejected primary returned five matches
in 1.51 seconds. Only the isolated local bot restarted. No private query replay,
production deployment, or Mini App changes. Last.fm credential remains invalid.
See [report](search-fallback-2026-10-17.md).

Expanded-tag follow-up: the user-specified Starting Over / LSD and the Search for
God match was present in iTunes and absent from MusicBrainz's first 100 title
results. Bounded recovery returned the exact candidate in 0.80 seconds. This was
metadata-only verification, not recognition, download, or user-confirmed playback.
# 2026-10-17 â€” Follow-up search cases

The bounded live workflow surfaced the censored joint-artist Paris recording at
position 5 in 2.44 seconds and qualified Kendrick Lamar / Prayer in 1.30 seconds.
Title-only Prayer did not include Kendrick in the inspected provider windows.
These are metadata probes, not playback or universal unreleased-song coverage.
See [full verification](search-aliases-2026-10-17.md).
# 2026-10-17 â€” Prayer popularity and typo probes

Actual metadata-only discovery returned Kendrick Lamar / Prayer first for prayer
(5.55 s) and prayer kendick (4.17 s), then repeated the typo query from cache in
0.08 s. The matched upload reported 3,879,049 views. No media was downloaded and
these samples are not total-song popularity or a latency SLA. See
[regressions, architecture and limitations](discovery-popularity-2026-10-17.md).

## 2026-10-17 â€” Selected-track sparse pool patch (local only)

Added regression cases for DNA with no ratings and an empty similarity response,
seed/unrelated-artist exclusion, expanded similarity parameters and artist request
shape. Python AST checks passed for five touched files; git diff --check passed.
Full recommendation/provider tests and focused tests stalled, as did a standalone
asyncio smoke check; no passing test result is claimed. Default Python lacks
SQLAlchemy/aiohttp; project environment was used for subsequent attempts.
No deployment or live DNA reproduction verified. Existing test connection cleanup,
worker/artwork and deployment-document edits predated this session and were kept.

## 2026-10-17 â€” Social product planning artifact

Created [social-product-vision.md](social-product-vision.md) from the user's
requested vision and this conversation's source/API research. Inspected the
current model classes and Mini App routes to distinguish existing taste features
from unimplemented social features. The document contains tasks T00â€“T21,
acceptance criteria, dependencies, commercial assumptions and open decisions.
Documentation checks cover task IDs, internal links and scoped whitespace.
No social feature, payment route, deployment or new runtime test is claimed;
existing source and documentation edits were preserved.


## Deployment reliability audit - 2026-10-18

Inspected current entry point, runtime imports, dependency files, Get Song/artwork/
YouTube code, recent commits and scoped staged/unstaged status. The source checkout
at 27c12a2 contains Get Song; the separate D-drive checkout at e15cc38 lacks it.
Existing unrelated edits were preserved. No tracked systemd unit/deployment shell
script was present; operational service details are historical documentation.

Final focused suite: 62 tests passed on Windows/Python 3.12.10 (artwork, preflight,
Get Song), with seven preflight tests passing again after final configuration-order
changes. Initial new test-fixture mistakes were corrected before the passing run.
Declared-version/import checks, pip check, yt-dlp --version (2026.08.19), compileall
and scoped git diff --check passed. A separate synthetic M4A/JPEG round trip verified
actual atomic metadata/artwork embedding; temporary media was removed. MP3 tags were
round-tripped in tests, M4A assignments and Telegram thumbnail forwarding also mocked.

No real configuration file or database was opened during verification. No Telegram,
YouTube or production services were contacted. Existing-environment verification is
not a clean-install proof: a disposable Python 3.12 install and isolated-tool download
both failed at package download timeouts. Python 3.13/Debian 13 clean install, full
repository suite, full preflight against real service configuration and live delivery
were not verified. Changes are uncommitted and undeployed. See DEPLOYMENT.md for the
operator's preservation, clean install, offline checks, stopped-service switch and
rollback procedure.


## 2026-10-18 â€” Verified VPS connection and scoped release baseline

SSH with the saved trusted host key succeeded. The bot service was active/running,
Python 3.13.5, branch codex/safe-publish at 27c12a2, with one existing tracked Get
Song modification. Normalized source hashes expose differences from the local
checkout. Initial async tests stalled in Windows event-loop creation before
application setup; the unrestricted rerun passed all 40 recommendation/provider
tests in 101.341 seconds. Scoped documentation whitespace checks passed. No production mutation,
restart, live conversation or social implementation is claimed. See
[verification and boundaries](social-release-baseline-2026-10-18.md).


## 2026-10-18 — Taste-card implementation, local verification

Added separate card/song tables, signed owner/view API routes, bot editing/deep
links and English/Persian Mini App editing, preview and revocable sharing. All
33 distinct scoped Python tests passed (12 new card tests and 21 existing
regressions/cancellation checks); six Worker/UI scripts passed on the final build.
Phone/desktop visual inspection and computed-width checks found no overflow.
Initial Worker POST test failure was corrected with explicit streaming duplex.
Uncommitted/undeployed; pre-existing and concurrent work was preserved. No actual
private-bot/provider journey or production change. See
[full evidence and migration boundaries](taste-card-release-2026-10-18.md).


## 2026-10-18 — Deployed search, recognition and chat UX repairs

Release `40536cae008786406bcf`: 195 isolated server tests passed, Node navigation/recovery checks passed, live artist probes returned the intended artists, and the supplied TikTok was identified as Mac DeMarco — Another One through the real recognition pipeline with a fake chat sink. Deployed source hashes, polling readiness, corrected metadata and database integrity were verified. One short-readiness rollback was verified before the successful retry. No user-facing test messages were sent. See [full verification and boundaries](search-recognition-ux-2026-10-18.md).


## 2026-10-18 — Mini App Get song

Mini App Get Song integration: 18 focused Python tests passed (59.829 s), including generated-link delivery and rejection of forged, cross-owner, expired and ungranted selections. Four Worker/UI scripts passed, including renewed-grant and preview-isolation checks. English/Persian phone preview inspected without horizontal overflow. Compilation/syntax and scoped whitespace checks passed. Uncommitted/undeployed; no actual Telegram audio download or production restart. Existing changes preserved.


## 2026-10-18 — Taste-card/Get Song deployment and UI brief

Published Worker 2ff6bdc7-7cda-4a91-8bac-07dd901a3cef after 32 passing VPS staging tests. Final served HTML/JS/translations matched release hashes; both public signed API gates returned 401 for invalid auth. Bot/API/connector were active with zero restarts; deployed/protected file hashes and additive tables verified. Persian live-site preview had no 390px overflow. No actual Telegram audio receipt was tested. See [release and limits](deployment-2026-10-18.md).

## 2026-10-18 — Search performance deployed

Release `e62d51a326501d2ee357`: 128 isolated regressions passed; staged/deployed source
hashes match; service active and polling; configuration preserved. Public artist
probe in a synthetic database: 3430 ms cold, 57/91 ms cached with zero provider
calls. Excludes Telegram round-trip; no real chat message or visual test.
[Details and limitations](search-performance-2026-10-18.md).

## 2026-10-18 — Bot onboarding, portrait and selected-song consent
42 distinct isolated Python tests passed; scoped Worker/UI/bridge checks and syntax passed. English/Persian 390px phone and 1440px desktop fixtures fit the viewport, with retained screenshots. User confirmed preceding Get Song verification; no new live journey observed. Uncommitted, undeployed. [Detailed evidence](onboarding-portrait-consent-2026-10-18.md).

## 2026-10-19 — Navan live-medley fix deployed

18 focused tests passed on local and production-based code; deployed hash and
active service verified. Production fixture accepted Montreal and rejected NYC;
actual media delivery not tested. [Full scoped record](navan-medley-fix-2026-10-19.md).


## 2026-10-19 — Local comparison/swap/control loop

60 distinct scoped Python tests passed across a 57-test regression batch and final targeted checks (overlaps excluded). Five Node checks, compilation, syntax and scoped whitespace passed. Fictional signed browser users completed Save → reciprocal note/send → receipt/Love; sender save feedback and Home's pending strip were visible. English/Persian phone/desktop widths fit. No production change or live Telegram send; moderator configuration and real two-account release checks remain. [Evidence and screenshots](social-loop-release-2026-10-19.md).

### Navan correction: stored-track integration gap

Initial patch did not resolve user-reported delivery. Follow-up candidate: 20
isolated VPS tests passed; real metadata search and temporary 4,398,625-byte audio
retrieval/validation succeeded. Not yet deployed; Telegram receipt unverified.
[Updated evidence](navan-medley-fix-2026-10-19.md).

Navan follow-up deployment confirmed: user-approved one-file correction deployed,
source hash verified, restart succeeded; all 20 isolated regressions passed against
the deployed module. The identical candidate retrieved/validated actual audio.
Telegram receipt/playback remains unverified; Mini App unchanged.
[Deployment evidence](navan-medley-fix-2026-10-19.md).


## 2026-10-19 — Verified release

Runtime f7f0739 pushed and deployed; 424 cumulative Linux staging cases and five Node checks passed. VPS hashes/services/moderator/auth gates verified; Cloudflare publication confirmed. Public retrieval and real Telegram journeys remain unverified. See [release evidence](deployment-2026-10-19.md).

## 2026-10-20 - A2/A3 measured Mini App performance candidate

Integrated Terminal 1 A1 before measuring current public/runtime responses.
14 local and 14 isolated runtime HTTP/API checks plus 13 Node scripts pass.
English static body budget falls 74.5%; a controlled 300 ms response-delay
fixture reached the first song heading at 1,065.5 -> 725.5 ms. EN/FA phone
geometry/actions checked; screenshot/physical-device and signed-network timings
remain unavailable. [Full measurements](performance-2026-10-20.md). Not deployed yet.
