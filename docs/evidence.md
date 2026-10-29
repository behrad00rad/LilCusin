# Recognition and search evidence

## 2026-10-29 - Scoped Git publication preparation

Reconciled published main history with the local committed history in an isolated
checkout. Prepared session features, required delivery/metadata/search support and
only session-authored documentation sections; unrelated dirty Mini App, admin
console and game work in the original checkout were not staged. Newer remote
source-validation guards were retained and extended for the explicitly approved
automatic-first and owner-selected discovery policies. Initial clean-checkout
validation found a missing bilingual recovery key; supporting keys were added
before final validation. Publication does not redeploy this reconciled candidate.

Publication validation: monthly/daily, lifetime and varied-pick cases passed
in the isolated checkout. Recovery/caption/link regressions passed through scoped
reruns after adding missing edition copy and photo-link/cancellation prerequisites;
the final 13-case link suite passed. Four existing original-source rejection
cases, two owner-bound saved-rating recall cases, startup imports, explicit-policy
checks and whitespace checks passed. No full-suite or redeployment claim. The
original checkout's unrelated uncommitted files are preserved.



## 2026-10-29 - Monthly invitation and daily rating reminder

User subsequently confirmed the combined monthly invitation and three-song
preview as “perfect.” The preview used recipient-owned cached audio and did not
consume scheduled daily eligibility or the monthly cooldown. This confirms the
message/file presentation, not fresh-source or unattended scheduled delivery.


At the user's subsequent request, the verified private recipient received one
monthly-template preview and three acknowledged audio presentation tests with
one chef greeting, rating encouragement, per-file test explanations and the
existing feedback controls. Only recipient-owned previously delivered tracks were
used, explicitly labelled as a preview rather than new personal recommendations.
The durable test receipt verified all three audio sends and unchanged scheduled
daily state; no monthly cooldown marker was created. No second poller or live
source fetch. User playback/button/phone acceptance is not inferred from receipts.

User explicitly authorized the monthly pitch after asking for a gentle rating
reminder in daily recommendations. Release `ed4489f150a08894` changes the daily
module and its existing fixture, adds `monthly_pitch.py` and focused monthly tests.
One reminder appears in the chef intro, not repeatedly under three songs:
“Rate a song or two—it helps me get to know your taste better 🎧”; natural Persian
copy explains the same music-taste benefit.

Before reserving recommendations, the daily loop checks recorded ratings, signals,
requests, track preferences, saves, identified submissions and artist/style/mood
setup. No history routes to the invitation; history with an empty pool does not.
No last-activity inference is made. Pitch copy describes available music search,
recognition, lyrics, favourites and /rate, with Search and opt-out actions plus
the real configured WebApp button when obtainable. No fabricated app URL.

A private `monthly_pitch` ChatControl row claims the 30-day window before sending.
The existing writer transaction serializes duplicate claims. Expiry survives
restarts and generic browsing cleanup; account removal explicitly deletes it.
Opt-out/history/suspension are rechecked before send. Telegram forbidden disables
future daily outreach; uncertain sends retain the cooldown instead of replaying.
Daily opt-out and social notification opt-out suppress the pitch. No schema change
or new timer; the existing 18:00–22:00 Tehran daily loop performs eligibility checks.

Exact staged Linux artifact passed 24 cases (27.590s) and poller imports: 30-day
boundary, repeated attempts, setup history/opt-out, ambiguous send, /forgetme,
EN/FA copy, all existing daily delivery/feedback/lifecycle cases, five caption-link
cases and three varied-pick/reason cases. Scoped syntax/whitespace passed.
Deployment preserved all protected source/config hashes, unchanged schema and
Mini App/nginx/connector. Four installed hashes, initialized/stable bot, exactly
one poller, public home 200 and unsigned auth 401 verified; private code rollback
retained. No commit/push, live test message or phone/provider/retention claim.

## 2026-10-29 - Three daily chef picks

User explicitly requested deploying three daily music picks before any monthly
invitation or broader engagement system. Release `5f0ef9e9b04e44ba` changes only
the daily module, its audio-caption integration and focused tests. Select up to
three from five eligible queue rows: retain the close first pick, favor different
artists next, then supported exploration. Explanations use the actual recommender
reason/localization; no invented mood or music attributes. Captions retain the
icon link row and append the reason. One durable daily intro claim avoids repeating
the chef message for each file. Automated requests do not learn positive intent.
Sequential bounded waiting uses the existing media worker and queue quotas.

Read-only investigation found the requested recipient's October 28 state was
`sent`, with an acknowledged completed manual test request. That test consumed
the scheduled day. Future presentation tests carry `test: true` and do not update
the scheduled daily state. The test helper no longer sets the recipient's day.

Exact staged release: ten caption/variety/EN/FA audio checks passed (4.418s),
poller imports passed, and a separate mock integration verified three distinct
numbered requests, no taste learning and lease release. Private code backup,
four installed hashes, protected sources/config, unchanged schema, initialized
stable bot, one poller, unchanged Mini App/nginx/connector and home 200/auth 401
verified. Deployment completion and receipt/hashes/services were read back again
at the user's explicit deploy request. No commit/push or live test messages.
Source/provider failures, sparse pools, quotas and restart mid-batch can yield
fewer than three deliveries; real scheduled three-file acceptance remains open.
Monthly invitations, inactive-user pitches and new eligibility rules are not live.

## 2026-10-28 - Link recognition, search lifetime and recording recovery

User requested recognition directly from pasted links, minimal icon-only captions,
longer-lived result buttons, and automatic delivery of the first suitable recording
instead of the failed-match -> Select recording -> first result sequence.

`954741c9af055267` reconciles seven installed runtime files: `link_download.py`,
`rating_links.py`, `workflow.py`, `chat_service.py`, `album_search.py`, `get_song.py`
and `recording_fallback.py`, plus five focused test files. Existing dirty user work
was present and preserved; deployment was assembled from fetched production files
and only scoped functions/snippets, not wholesale source-checkout synchronization.
No commit/push, configuration, dependencies, schema or Mini App assets changed.

The new link action retains original owner/message/15-minute-choice checks and
one-use per action. It releases the shared admission lock before calling real
Recognition.submit; tests exercise that path to prevent re-entrant deadlock.
No original video/audio/media delivery is required. Recognition still privately
fetches bounded audio to fingerprint and retains its existing source/provider
limits and identified-song delivery behavior. EN/FA action copy uses the current
language context. Video/audio/picture download choices remain separate.

Song result binding and safe card/list/rating controls now use 24-hour expiry;
control retention is capped at 100 per user. Artist/album/query controls use 24h
but still live in the existing bounded 100-entry in-process cache: restart or
capacity eviction can invalidate them earlier. Short confirmation/control kinds
keep 30 minutes. Owner, message, revision, cancellation and account checks remain.

On eligible strict-source failures, one 12-second broader lookup considers the
first playable non-rejected result. Auto delivery requires a nonempty/non-label
artist match, exact normalized title, compatible edition and duration difference
within max(45 seconds, 25%). Music-video packaging is permitted; known cover/live/
other artist or large-duration conflicts retain direct recording choices. This
deliberately relaxes the earlier strict duration/original-upload gate per the
user's friction report; it is not new proof of an official/original upload.
Source metadata is tagged `automatic-first-v1`; canonical selection snapshots
and daily presentation metadata are retained. No new request, positive feedback,
quota bypass or extra media worker is created. Explicit Other versions is not
auto-selected. Cancellation/new source rejection is rechecked after lookup.
Metadata outages/empty results keep the existing recoverable failure path.

Verification: exact staged Linux artifact passed 24 cases (20.814s) and poller
imports. Includes the real recognition-admission path, wrong owner/message/expiry,
no prerequisite media sends, Unicode icon links, EN/FA daily audio, 24h expiry and
short confirmations, retention past 20 cards, top-result auto delivery after
strict no-match, cancellation, late rejection, outage/one-attempt bounds, edition/
artist/duration conflicts, daily metadata, cache delivery and quota/correction
regressions. Local checks: 21 caption/link cases, 10 lifetime/initial-auto cases,
then nine existing manual-fallback/strict-resolver regressions passed. The added
late-rejection case passed in the final Linux artifact. Mock tagging warnings
were emitted without failed checks. Scoped syntax/whitespace passed; no full suite.

Both deployment locks, original/staged/installed hashes and protected config/code
guards passed. Code rollback copies retained; only the bot restarted. Initialized
polling, stable service/PID/restart counts, one poller, unchanged Mini App/nginx/
connector/schema, public home 200 and unsigned delivery-status 401 verified.
Real pasted-link/Shazam/provider, specific-song or phone acceptance remains open.
An attempted in-place update of the earlier authorized test song could not be
completed: Telegram returned “message to edit not found.” No new test audio or
recognition message was sent, and this is not counted as live caption success
for this release. New sends use the tested minimal icon caption.

## 2026-10-28 - Daily chef picks

### Approved audio layout and caption follow-ups

The user rejected the initial card/button density and requested a chef intro,
the actual music file, `/rate /lyrics` and only Already know it / Not for me /
More like this. Release `16b4948428fec88d` moved presentation to the existing
durable audio-send boundary, tagged automated requests without positive taste
intent, and bound compact controls/history to the acknowledged audio receipt.
Source search/download produces no chef message. Daily source failures and
unconfident recording choices stay quiet. Existing normal delivery is preserved.
Invalid cached references can retry without repeating the intro; ambiguous sends
are not automatically replayed. An audio-send network failure after the intro
can still leave the intro alone; this is not an atomic Telegram message pair.

Exact staged artifact: 16 Linux tests passed (11.895s), normal/compact caption
smoke checks and poller imports passed. The initial Linux selection referenced
an absent caption test module; the final suite used the available four existing
delivery checks and 12 new daily cases. Initial Windows daily run had one test
fixture error assigning to frozen FetchSettings; the corrected fixture passed
in that Linux artifact. Three existing local caption tests and syntax/whitespace
checks passed. Five scoped files deployed with consistent stopped-writer backup,
preserved source/config hashes, unchanged schema and stable bot/API/one poller.
Public home 200 and unsigned delivery-status 401 verified.

The authorized recipient's Telegram identity was verified with getChat. The live
layout test reused only that recipient's own previously delivered audio, created
no poller/media worker and received an acknowledged audio message. It verifies
file/caption/button delivery, not a new source search or new recommendation.
The user explicitly confirmed “working perfectly.” No explicit rating or playback
measurement is inferred. The test counts as today's pick for that recipient.

User then preferred the earlier chef-emoji introduction. Copy-only release
`f0b0e64188a71930` restored EN/FA emoji copy, passed two exact layout tests and
imports, and restarted only the bot. Installed/protected hashes, unchanged schema,
unchanged Mini App/nginx/connector and public/auth health verified; no DB operation.

At the user's next request, caption release `121f3365655e919b` adds owl bot links
to known-song and extracted-audio captions and a typed `/lilcusin` welcome alias.
The final requested visible labels use `○` circles rather than slashes. Entities
use UTF-16 offsets so both owl emoji and Persian text keep accurate tap targets.
Known tracks retain song-specific rate/lyrics deep links; branding links only to
the bot, without recipient identifiers or an expiring owner token. Extracted audio
gets branding alone. Five caption/alias cases, two actual daily audio layout
cases and one existing delivery case passed on the exact Linux artifact (2.899s);
poller imports passed. Eight local caption cases and the existing audio-only link
download case passed. An earlier staged alias fixture lacked the bot argument;
it was corrected before release. A dropped staging connection was reconciled by
reading the remote result and verifying unchanged production hashes before retry.
Five scoped files deployed with private code backup, unchanged schema, protected
source/config hashes, stable bot/one poller, unchanged Mini App/nginx/connector
and public home 200/auth 401. No commit/push or full-suite claim.
The already-authorized test audio's caption was then edited in place, without
sending another song. Telegram returned the exact circle-style text, all three
expected text-link URLs and the existing one-row/three-button keyboard. This
verifies caption/entity installation, not a forwarded-message click on a device.

User clarified the intended circle as filled `●`, requested all links on the
same line and warmer copy. Final release `fc199e0f751fcfd3` uses
“A little treat for your ears 🎧  ● rate  ● lyrics  🦉 ● lilcusin” and natural
Persian “اینم برای تو، با عشق 🎧” before the same link row. No forced newlines;
Unicode link offsets include the greeting's headphone emoji. Seven exact staged
caption/EN/FA audio-layout tests passed (2.214s), poller imports passed and three
existing local caption tests passed. Three scoped files deployed with code backup,
protected source/config hashes, unchanged schema/Mini App/nginx/connector,
initialized/stable bot and one poller, public home 200/auth 401. The intermediate
filled-symbol-only artifact was staged, never deployed. No additional song send.

### Initial implementation and first test (superseded layout)

Implemented and deployed `5360607dd36a585b`: new `daily_pick.py`, scoped integration
into poller startup/cleanup, database registration, command menu and `GetSong.request`
(`learn=False` only for automatic delivery). Existing dirty work was present before
this session and was preserved. Production's four integration files were fetched
and patched independently; the release also contains the new module and its tests.
No commit or push. No Mini App asset or private configuration changes.

Eight isolated Windows cases passed (52.235s); exact Linux staged artifact passed
12 cases (18.700s) and poller imports. Coverage: concurrent/restart daily cap,
next day, opt-out/on, EN/FA, empty pool, ambiguous send, Telegram block, cascading
account deletion, actual authorized rating persistence, scheduling/cancellation,
automatic versus explicit taste requests, cached delivery, deduplicated jobs,
quotas/cancel and wrong-recording limits. Restricted Windows sockets initially
blocked testing; successful rerun used the normal host environment. First Linux
selection included a nonexistent production test name; final 12-case run passed.
Mock audio tagging warnings did not fail existing delivery checks.

Two established deployment locks and source/config hashes guarded the release.
Both writers stopped for a private SQLite backup (`quick_check=ok`). The first
attempt's early schema check found no new table and rolled code back; original
hashes, service health and public endpoints were verified. A separate second
attempt retained the identical tested files and waited up to 90 seconds for
migration. It verified all six installed hashes, protected sources/config,
existing schema unchanged plus only `daily_pick_state`, stable bot/API, exactly
one poller, public home 200 and unsigned delivery-status 401. Private receipts and
code/database recovery copies retained; no old database restored.

Default sends start at 18:00 Tehran; scheduler checks every five minutes until
22:00, processes sequentially at one user per second, skips opted-out/suspended
users and disables future sends on Telegram forbidden errors. Missing candidates
produce no reminder. Durable claims favor missed sends over duplicate sends on
network ambiguity. Existing provider confidence, delivery choices/quotas and
source availability still apply; audio may fail or need a recording choice.
Daily controls last up to two days subject to the existing 20-control cap.
Supported chef copy is English/Persian; other languages fall back to English.
Real-user daily audio/rating journey and retention impact remain unverified.

User-authorized single-recipient live test: Telegram `getChat` verified the
requested existing private recipient before sending. Daily chef message and
rating controls were acknowledged as sent; the production audio worker accepted
the automatic request but failed during source search, with zero candidates and
no delivered audio message. No second poller/media worker was started. The test
counts as that recipient's daily attempt; it will not send another evening pick.
No playback or explicit rating was confirmed. Default/English/Persian `/daily`
registration was independently verified through Telegram `getMyCommands`.


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

## 2026-10-20 - Vigen/Sogand Get song correction, deployed

Read-only deployed-job metadata confirmed the wrong 175-second Sam H candidate.
The corrected matcher passed 24 focused tests and found the 288-second Viguen
Topic recording in a live VPS metadata-only run in memory. The user-approved
one-file release has a verified deployed hash and active bot process; later SSH
timeouts blocked post-restart polling/live-lookup checks. Uncommitted; no audio
or Telegram verification. [Details](vigen-get-song-fix-2026-10-20.md).

### 2026-10-20 - Dele Divaneh follow-up, local

Stored source metadata confirmed the unlabelled Sam Shirazi upload was offered
for Vigen's Dele Divaneh; instrumental content is user-reported. The stricter
candidate passed 78 distinct affected cases across runs and returned only
catalogue-attributed Topic releases for both reported songs in live metadata
checks. A three-file patch passes production apply checking but is not deployed.
No download/playback verification. [Evidence and limits](strict-original-get-song-2026-10-20.md).

## 2026-10-20 - A2/A3 measured Mini App performance release

Integrated Terminal 1 A1 before measuring current public/runtime responses.
14 local and 14 isolated runtime HTTP/API checks plus 13 Node scripts pass.
English static body budget falls 74.5%; a controlled 300 ms response-delay
fixture reached the first song heading at 1,065.5 -> 725.5 ms. EN/FA phone
geometry/actions checked; screenshot/physical-device and signed-network timings
remain unavailable. [Full measurements](performance-2026-10-20.md). Deployed as `dbd57299600da7b3` from pushed commit `dafc654`; exact public hashes,
gzip/304/immutable headers and unchanged protected services verified. Live public
EN/FA preview loaded WebP; signed Telegram remains unverified.

## 2026-10-21 - Search/artwork recovery

Five live search failures, an offline timeout-to-empty reproduction and a slow
cover sample motivated scoped fixes. Artifact `ab739eac183fff74` deployed after
83 isolated Python checks and the local Node lifecycle regression. Public app
hash/gzip/304, immutable cover headers, bot polling/API health and protected
source/configuration verified. No signed Telegram receipt or physical-network
claim. [Full evidence and rollback detail](search-cover-recovery-2026-10-21.md).

## 2026-10-22 - Early search receipts

Current source inspection identified pre-acknowledgement database/queue/reply work.
Eight local and 45 distinct cumulative staging cases verify receipt ordering,
reuse, cancellation/error cleanup and chat/search compatibility. Artifact
`a5f28398fa68d32c` deployed; polling/hashes and unchanged API/Nginx/connector
verified. Existing catalogue parity failure retained; real user round-trip open.
[Full evidence](search-ack-2026-10-22.md).

# 2026-10-24 - Project overview and recent updates

Added a public-facing LilCusin introduction and linked it from the repository
README. The overview gathers the documented discovery, recognition, Get song,
ratings, recommendations, Mini App, channel, social sharing and privacy
capabilities in one place.

The recent-update summary reflects the checkout handoff: artwork/startup
performance and slow-source recovery are documented as deployed; early private
text-search acknowledgement and bounded cancellation are documented as
deployed; the stricter catalogue-attributed original-source policy remains local
and undeployed. The checkout contains pre-existing unrelated dirty code; this
documentation task did not modify it. No application tests were run. Documentation
links, scoped diff and whitespace were inspected locally. GitHub could not be
reached from this environment, so remote state and publication are unverified.

## Recent runtime changes summarized

- Public Mini App assets reuse available artwork variants and support compression
  and cache validation to reduce repeat transfer cost.
- Slow source-search failures remain distinct from a clean no-match; Get song
  reports bounded progress and retains cancellation. Cover retries have bounded
  waits and leave a placeholder when unavailable.
- Private text searches receive an early acknowledgement before setup or queued
  action waits; progress, failure and cancellation are surfaced in that status.
- Persian Get song matching was corrected to require artist evidence and use
  unambiguous recording aliases. A stricter catalogue-attributed original-source
  policy is a separate local-only change and is not described as deployed.

Evidence and limitations: the dated [STATE handoff](STATE.md), linked release
evidence therein, and the relevant [decision history](decisions.md) record
targeted checks and guarded runtime verification. Physical mobile behavior,
signed Telegram round trips, and playback are not established by those checks.
This overview is documentation, not a new runtime release.

## 2026-10-23 — Guess game step 1

Ten scoped SQLite/settings/forgetme cases passed (8 cases in 109.806s, settings in 31.095s, forgetme in 32.816s), with mocked bot and no provider calls. First sandbox fixture setup failed on temporary-directory permissions; reruns outside sandbox passed. JS/Worker syntax, Worker regeneration and scoped whitespace passed. No game UI, visuals, deployment or real Telegram verification. [Files and remaining work](guess-game.md).

## 2026-10-23 — Guess game service/API verification

Eleven initial isolated service/API cases passed in 198.839s; the added concurrent-start/wrong-score/unfinished-history case and affected daily-limit case passed in 141.877s. Twelve unique service/API cases total. Three connector cases and Worker/proxy/bridge checks passed. Signed auth/no-store exercised in-process; providers/bot mocked, no external calls. Existing dirty checkout; unrelated changes excluded from commit. No browser, deployment or real Telegram acceptance. [Step handoff](guess-game.md#step-2--server-rules-and-apis-2026-10-23).

The exact staged database/API registration passed the signed-auth API case again (29.312s); the exact staged Worker passed the guess routing fixture. This checks the selectively staged prerequisites without claiming a wholly clean checkout run.


## 2026-10-24 ? Guess game screens

Local UI state fixture, JS syntax and affected signed-auth API case (14.039s) passed. Browser inventory was empty; in-app browser open returned unavailable, so no phone/visual claim. Existing dirty edits preserved. [Evidence/limits](guess-game.md#step-3--game-screens-2026-10-24).


## 2026-10-24 - Guess game alerts

The combined 32-case run had one Persian-copy encoding failure. After UTF-8 correction, eight notice cases passed (37.417s), then the quiet-race/batch case passed (18.289s). Thirty-three unique related Python cases passed across scoped runs; UI/Unicode and Worker/bridge fixtures pass. Sends/providers mocked; no browser/live acceptance. [Details and limitations](guess-game.md#step-4---nudges-and-notifications-2026-10-24).


Exact staged database/API registration passed the batch/quiet-race and signed-auth API checks (2 cases, 3.983s). Exact staged Worker routes, JS syntax and all Persian game-string Unicode assertions passed.


## 2026-10-25 - main and safe-publish integration

Integrated the reviewed safe-publish history with the current GitHub main history
in an isolated clean worktree. The integration retains main-only Mini App cover
proxy registration and documentation along with the safe-publish feed, delivery,
social and Guess Game work. The deployed Loved-sharing and alert defaults are
represented as on for missing preferences while saved opt-outs and song privacy
locks remain honored. Updated the README and feature/status documentation.
Focused checks and final remote ref verification are recorded in the release
summary; local tests do not establish real-user acceptance.
