# Current handoff

## Direct delivery and unseen feed refresh - local, 2026-10-21

Implementation `61150aa`: explicit signed POST /api/delivery-request validates
actor/source/grant or current swap consent, then enqueues through GetSong.request.
No second worker, polling process or chat-opening /start fallback. Existing queue
limits, recording choices, learning and delivery receipts remain. Status POST is
still read-only. Active requests deduplicate; frontend never claims Sent until a
receipt confirms an audio message. Worker/connector route allowlists updated.
Home filters swaps by the current actor's stored rating/Love and immediately
removes matching swaps after rating a recommendation. No partner rating exposed.
Pulling down at the first card keeps buffered unseen cards; only exhaustion makes
one batch request. Opt-in batch response returns up to five picks with normal
owned grants; legacy replacement still returns one. Seen picks are tracked in
this Mini App session, with bounded history/DOM and no implicit rating. Delays
show a skeleton, block underlying controls and keep the owl loading message until
the request finishes. Failure retains a usable card; navigation guards stale work.
Thirteen scoped Python API tests and ten Node scripts passed, plus syntax, Worker
build and whitespace. Initial sandbox temp/SQLite test errors were environmental;
rerun with workspace disposable databases/loopback permissions passed. Browser
inventory appeared but browser connections were unavailable; no new screenshots,
real Telegram delivery or physical swipe verification. No push/deployment.
RELEASE GATE: reconcile runtime Python changes and run scoped Linux checks; deploy
backend endpoint/batch/projection before matching UI, restart only the Mini App API
as documented, preserve the existing bot/audio worker, DB/config and rollback.
A static-assets-only release is insufficient. Unrelated dirty Mini App cover-proxy
registration and other backend work remain outside this commit.

## Feed polish deployed - 2026-10-21

Explicit user authorization deployed `b25293c` as release `96b50529b5e1cdcd`:
Saved/check animation, received swap cards and edge-to-edge artwork/title overlay.
Four UI assets updated after baseline checks, rollback backups retained. Focused
feed regression passed again. All five public UI hashes match; unsigned delivery
returns 401. Service states/PIDs, Python sources, private configuration and index
unchanged; no restart. This supersedes local-only status below. Browser/phone
visual verification remains pending; no new screenshots or Git push in this release.

## Saved feedback, Home swaps and artwork overlay - local, 2026-10-21

Add to my card now changes to Saved/checkmark after acknowledgement or an existing
stored selection, with a brief reduced-motion-aware icon animation. Failure keeps
the original action; profile updates invalidate the session cache. Home includes
up to three received sent-state swaps after the first recommendation, with sender,
song and note. Swap cards stay out of recommendation grants/rating/history caches;
opening reloads the authorized inbox and uses only a still-available fresh swap.
Artwork fills the top edge with a dark lower fade behind title/artist. Existing
viewport fitting remains; palette, whole-card/tab gestures and APIs unchanged.
Five scoped Node checks passed (feed polish, delivery, viewport, gestures, social),
plus syntax, Worker generation and whitespace. Browser inventory is empty; visual
review/screenshots and phone verification pending. No deployment or push.

## Viewport fix deployed - 2026-10-21

Explicitly authorized asset release `a90f126e622dc9f5` deployed commit `5c50070`'s
app.js/style.css after prior-hash checks; rollback copies retained. Viewport
regression passed again. All five public UI assets returned 200 with matching
hashes; unsigned delivery-status returned 401. Service states/PIDs, Python sources
and private configuration unchanged; no restart. This supersedes the pending
status below. Browser rendering and physical iPhone verification remain pending.

## Viewport overflow correction - local, 2026-10-21

User phone screenshot confirms Get song/secondary controls are hidden by navigation.
The cover now remains square but shrinks to space left after controls, hint,
Telegram safe areas and viewport height; overlay arrows follow its size. Telegram
viewport/safe-area changes refit it; active swipes/animations are excluded from
measurement. No API, palette or gesture changes. Five scoped Node checks passed
(viewport, gestures, motion, home/owl, delivery), plus JS syntax, Worker generation
and whitespace. New regression covers short/tall hosts, long content, safe areas,
repeat-fit stability and drag guards. Rendered/iPhone verification is pending:
browser access was approval-blocked in the interrupted turn and no browser is
currently connected. No new screenshots, push or deployment for this correction.

## Home card and owl deployed - 2026-10-20

User-authorized release `eda1f132f83ce635` deployed the tested Home card and inline
owl from `f46500d`, preserving the existing production locale preload. Four assets
updated after prior-hash checks, with rollback copies retained. All five public
HTTPS UI assets returned 200 and exact source hashes; unsigned delivery-status
returned 401. Live Persian browser preview shows owl, count, radio ratings and
card actions. Service states/PIDs, Python sources, private configuration and
social.js unchanged; no restart. Home/owl regression and syntax passed again.
This supersedes local-only status below. Physical Telegram swipes and actual
audio receipt remain unverified. No Git push performed in this deployment.

## Home card and inline owl - local, 2026-10-20

Implementation `f46500d` replaces prior Home/header polish with a square cover,
over-cover count and up/down arrows, visible radio-group ratings, reason chip,
one primary Get song action and quieter secondary controls. Whole-card vertical
swipes and horizontal tab navigation retain their existing handlers. Inline SVG
owl has CSS blink/bob, bounded RAF pupil tracking, action-only reactions and
localized tips; language selection moved into More. Quick Guide already has a
language selector. Header previously showed the brand logo/name, not a user photo.
Server dominant-color/cache work deferred by user; fixed #1f2024 fallback. Existing
provider artwork variants use 400px WebP (300px low-data); no backend changes.
Four scoped Node scripts passed: home/owl, gestures, motion and delivery; syntax,
Worker generation and whitespace passed. EN/FA checked at actual 360/390px width,
810px height: no horizontal overflow, >=44px rating targets, secondary actions
clear navigation. All eight before/after screenshots saved; capture needed retries.
Cover 360px: ~273x160 -> 283x283; 390px: ~289x148 -> 299x299 (baseline height
varies with copy). Core UI gzip estimate 112173 -> 115661 bytes, +3488 bytes;
JS/CSS raw delta +6123 bytes. Excludes unchanged assets and image/network cost.
Native Telegram touch, audio receipt, live network transfer and reduced-motion
device rendering not verified. No push or deployment. See the detailed evidence
and Persian copy review in ux-clarity-2026-10-19.md.

## Search More correction deployed - 2026-10-20

`8b779c1` corrects the cached-pool-only limitation below. More stays available at
the end of fetched results and requests a deeper batch for the same query, with
YouTube fallback. Only unseen artist/title identities and recording IDs append;
old indices remain stable. Five new songs per extension, bounded to 60 total;
explicit exhaustion keeps the displayed page instead of cycling old songs.
Seven focused tests passed locally and in isolated runtime staging. Live public
Radiohead metadata probe returned 37 unique songs, 25 beyond the initial 12.
Both deployed hashes/polling verified; API PID and configuration unchanged.
Owner/message/expiry/revision and post-provider cancellation guards retained.
Native Telegram taps and phone rendering remain unverified.

## Terminal 3 Telegram UX deployed - 2026-10-20

Search paging `1108497` deployed first: five existing results per page, More songs/
Previous in EN/FA, stable choice indices and owner/message/revision/expiry checks;
no extra provider calls. This browses the fetched result pool, not an unlimited
artist discography. Then `edf6e51` deployed direct two-column card ratings and
Get audio / دریافت فایل آهنگ labels. Existing evidence-based localized ranking
reasons retained; no invented artist attribution or AI requests.
Four pagination tests passed locally and on isolated production-source staging.
Seventeen UX/chat cases covered locally; three old row-index expectations were
corrected and rerun successfully, without repeating the whole module. Three
focused runtime rating/navigation checks passed. Both releases used exclusive
deployment locking, live-source guards, scoped backups and rollback; hashes,
polling and unchanged API PID/configuration verified. Forbidden delivery modules
untouched. No Telegram browser session was available; actual native 320/390px
layout/overflow and physical taps remain unverified. No Mini App assets changed.

## A1 deployed - 2026-10-20

UI commit `02259c0` deployed as asset release `a00194180b159c2a` after explicit
user authorization. Four frontend assets updated after prior-hash checks; rollback
copies retained. All five public HTTPS UI assets returned 200 with matching hashes;
unsigned delivery-status returned 401. Service states/PIDs, Python sources and
private configuration unchanged; no restart. Initial upload disconnected before
application; retry succeeded. Supersedes the pending status below. Physical
Telegram gestures and real delivery remain unverified. No further development.

## A1 UI polish - 2026-10-20

Completed whole-card swipe and tab animations with reduced-motion support,
compact Home/Search layouts, five-slot Taste Card placeholders and clearer
exchange filters/actions. Existing palette, consent, delivery and backend APIs
are preserved. Eight scoped Node checks, two translation tests, JS syntax and
Worker generation passed; the final four affected Node checks passed again.
EN/FA browser layouts checked at 320px/390px and desktop, including long titles,
missing artwork and safe-area geometry. Physical Telegram touch and real delivery
remain unverified; screenshot capture was unreliable. A1 deployment is pending:
the existing three-asset release procedure needs four-asset reconciliation.
Production remains on swipe asset release `28bb9f95e81cc9ab`. Development stopped
at the user's request; unrelated changes preserved.

## UI release - 2026-10-19

User-approved UI commit `cdcc4d2` is pushed to `codex/safe-publish` and deployed
to the existing direct VPS Mini App origin. This supersedes the local-only UI
status below. The scoped file update preserves production hosting differences
and unrelated concurrent work. Mini App API active; bot PID, Nginx and inactive
connector unchanged during the successful application. Five public UI assets
returned HTTPS 200 with exact source hashes; unsigned delivery-status returned 401.
31 affected tests passed in isolated Linux staging against the reconciled runtime.
No schema/configuration changes or full-checkout synchronization. Real Telegram
delivery and physical swipe remain unverified. See [UI evidence](ux-clarity-2026-10-19.md).

## Active local task - recommendation loop

Items 1-3 are implemented locally: weak request learning, the existing private
saved library as a stronger signal, durable leased For You refill and owner-bound
Save/known/not-for-me/Next controls. Pause/reset/library management are available
in /taste. 185 affected tests passed with monitored source hashes unchanged;
all 16 chat cases passed again after final copy changes. See [resumable checkpoint and
limits](recommendation-loop-2026-10-19.md). Code committed/pushed as `cbad204`;
remote SHA verified. Exact staged snapshot: 183 Windows tests passed. Deployed
on 2026-10-20 as release `4835ec7d93767fb4` after explicit upload/deployment approval.
Both exact Git and reconciled runtime snapshots passed 183 Linux tests each.
Bot polling and Mini App API active; 22 source hashes and four additive tables
verified. Existing dependency gaps remain; real Telegram receipt is unverified.
Friends' taste remains a consent-scoped design, not an implemented recommender.

## Recommendation recovery - 2026-10-19

Approved one-file release `27ccddcae8221606` deployed; source hash verified,
bot active and polling. Recently displayed songs no longer suppress refill;
empty For You pools recover using positive artists. 26 recommendation tests
passed on Windows and again in isolated Linux staging. Unrelated runtime sources,
configuration and Mini App API PID unchanged. Existing missing `packaging` blocks
full preflight; baseline unchanged, runtime imports passed. Actual Telegram
recommendation receipt remains unverified. See [evidence](recommendation-recovery-2026-10-19.md).

Updated: 2026-10-19 (Asia/Tehran). Release committed, pushed and deployed.

## Latest verified release

See [deployment evidence and limits](deployment-2026-10-19.md). Runtime commit
`f7f0739` is deployed on the VPS; all three services are active, the verified
moderator is configured, and local authentication gates reject unsigned requests.
Cloudflare accepted the new frozen Worker. Public URL checks encountered connection
errors/403; actual two-account Telegram delivery remains unverified. Concurrent
recording-search edits are preserved outside the release. 424 distinct Linux
staging cases passed cumulatively, plus five Node checks.

The following sections retain historical local-slice observations; the release
record above supersedes their undeployed/uncommitted status.

## Current implementation

Steps 5–8 now add selected-song comparisons, draft/send/save/Love/reciprocal picks,
block/report/notification controls, an operator review command and a Mini App loop
with Home/card/comparisons/swaps. **60 distinct scoped Python tests passed**, with
final targeted checks and five Node checks. English/Persian desktop/phone flows
were exercised using fictional users. See [release contract and limits](social-loop-release-2026-10-19.md).
An accountable moderator must be configured before launch; deployment and actual
two-account Telegram delivery remain unverified. There is no production change.

Earlier October 18 slice:

Bot onboarding, full-size portrait cards, recipient-bound mutual-consent
invitations and Mini App review/preview are implemented locally. 42 scoped Python
tests and relevant Worker checks passed. English/Persian phone/desktop fixtures
were checked in the browser. See [scope, consent contract and proof](onboarding-portrait-consent-2026-10-18.md).
No commit, push, second poller or production change was performed in this slice.
The user confirmed preceding Get Song verification with “1 is ok”; no new live
delivery was observed by the agent. Comparison and swaps were still open at that earlier milestone.

The sections below retain the earlier documentation-baseline observations.

## Verified in this session

- Application Git root is `source/`, HEAD `27c12a2`. It has substantial pre-existing
  tracked and untracked application/test/documentation changes. HEAD is not the
  complete local build or a reliable production identity. No commit/push performed.
- A separate dirty checkout exists at `D:/lilcusin/LilCusin`; it was not reconciled.
- Existing product vision, decision history and dated release records are retained.
  Workflow checks cover documentation only; no application suite or live checks ran.

## Latest recorded release (not reverified live here)

[October 18 deployment](deployment-2026-10-18.md) records taste cards and Mini App
Get Song deployed, 32 isolated staging tests, Worker checks, deployed asset hashes,
authentication rejection and running services. Local changes remain uncommitted.
It supersedes the deployment status in the earlier
[taste-card slice](taste-card-release-2026-10-18.md) and
[baseline](social-release-baseline-2026-10-18.md), not their historical evidence.
Actual Telegram audio receipt/playback and source availability were not retested.

## Blockers and uncertainties

- Source/runtime parity and outstanding baseline flags need fresh scoped evidence
  before another release. Preserve the reconciled production Get Song behavior.
- A genuine signed Telegram card/share/delivery journey remains a verification gap.
- The new local comparison/swap/control implementation is not deployed. Configure
  an accountable moderator and complete the real Telegram loop before a cohort.
- Earlier Windows async checks stalled during event-loop setup; see the baseline
  for evidence. A stall must not be reported as a product failure or a passing test.

## Next task

Prepare both locally tested slices for an explicitly authorized deployment, including
the new image dependencies/font and additive tables. Then verify a two-account
Telegram onboarding/image/invitation/comparison/swap journey and configured operator review. Retain the broader P0 gaps in
[TASKS](TASKS.md); user confirmation of Get Song does not close every live journey.
Do not automatically begin implementation from this handoff.

## Keep this useful

Replace current status after a material change; link detailed evidence in dated
records. Leave history there. At handoff, record what changed, checks with outcomes,
remaining gaps and one next task. Never copy secrets or personal records here.

## Search performance release — 2026-10-18

Release `e62d51a326501d2ee357` is deployed and polling: 128 isolated affected regression
tests passed. Cleanup no longer blocks acknowledgement; complete-result caching
and progressive stable search choices are enabled. Engine samples: cold 3.43 s,
cached 57–91 ms; Telegram round-trip/real presentation remain unverified. Six-file
production-based patch excludes concurrent invitation/onboarding work; local work
is uncommitted. See [scope and evidence](search-performance-2026-10-18.md).

## Navan live-medley fix — 2026-10-19

Approved one-file matcher fix deployed; source hash verified, bot active/running.
18 focused tests passed; deployed fixture accepts Montreal and rejects NYC.
Actual Telegram download/playback remains unverified. No Mini App changes.
See [deployment evidence](navan-medley-fix-2026-10-19.md).

### Navan follow-up — initial patch insufficient

User reported continued failure. Stored identity punctuation and 220/272-second
duration mismatch reproduced. Corrected one-file candidate passes 20 isolated VPS
tests and retrieves/validates real audio (4,398,625 bytes); not yet deployed.
See [updated evidence](navan-medley-fix-2026-10-19.md). Telegram receipt unverified.

Navan follow-up deployment confirmed: user-approved one-file correction deployed,
source hash verified, restart succeeded; all 20 isolated regressions passed against
the deployed module. The identical candidate retrieved/validated actual audio.
Telegram receipt/playback remains unverified; Mini App unchanged.
[Deployment evidence](navan-medley-fix-2026-10-19.md).

## Home card stability - step 1 - 2026-10-21

Implemented locally; not deployed. Get song uses fixed-size in-button Requesting/Try again/Sent states, with an off-layout aria-live region and no delivery-triggered deck fitting. Cover arrows are grouped as three 44px counter zones; the first previous control stays disabled. Artwork has a minimum 4:3 shape, metadata clamps at two lines, the redundant bottom hint is removed and a one-time owl tip replaces it. EN/FA owl lines shortened. Friend send becomes a 44px cover action alongside the existing privacy lock in the current working-tree integration. Whole-card vertical swipes/tab gestures and rating/delivery APIs preserved.

Focused Node delivery check passed against both the current working tree and an isolated commit candidate, including pending/confirmed/error button states, no delivery resize callback, cover dimensions and bilingual caption lengths. Existing Exchanges Node check, JS syntax and whitespace passed. Chrome became available: actual CSS 390px English and 360px Persian layouts visually inspected; zero horizontal overflow and both captions fit, with a roughly square English cover. Four caption encoding errors found and corrected; native-Persian regression assertion added. Lock-on/requesting visuals, friend thread and real Telegram receipt/haptics not verified. No old screenshots regenerated. Step 2 (Love-only friend visibility and lock animation) and step 3 (friend threads) remain untouched. The currently deployed lock differs: it uses a separate per-song privacy record and opt-in Like/Love sharing, rather than a rating visibility enum.

Commit scope: independent Home core/CSS/copy/test changes and the cover-send helper; the one-line integration with the pre-existing uncommitted friendship implementation remains uncommitted to avoid absorbing that older work. Do not deploy from the isolated commit alone as a replacement for the current dirty runtime.

Persian copy for review: «در حال درخواست…»، «دوباره امتحان کن»، «به تلگرامت فرستاده شد»، «بزن تا یه نکته بگم»، «امتیاز بده، بهترش کنم»، «آهنگ بعدیت رو پیدا کن»، «برای دوستت آهنگ بفرست»، «پنج آهنگ، کارتِ تو»، «بازم از اینا میارم»، «از اینا کمتر میارم»، «دارم آهنگ بعدی رو میارم»، «کارت رو بالا یا پایین بکش»، «پنج آهنگ بچین و بفرست».

## Private Love - step 2 - 2026-10-22

Implemented/tested locally; not deployed. Only Love ratings are eligible for friend discovery; Like/Neutral/Dislike remain private. Owner-facing visibility is derived as `private|friends` from the existing persisted rating, per-song lock and sharing opt-in; no schema migration. Current locks/aliases filter friend comparison/list snapshots as well as feed discovery. Existing explicitly selected/shared songs remain separate from rating visibility. API unlock requires `confirm_shared:true`; Mini App unlock, Undo and private-library restore ask first. Sharing remains off by default and enabling it asks explicitly. Previously delivered messages/images cannot be recalled; already-rendered friend screens update on their next request.

Open gray lock, purple closed lock/Private pill and Love privately label/icon; 280ms shackle/pulse, guarded haptics, one-time tooltip, confirmed Undo, 1.1s purple evil owl plus truthful unlock copy. Reduced-motion rules disable transitions/pulse. Native Telegram unlock controls retain their existing explicit-action behavior; the new confirmation is enforced in Mini App API/UI. Ten affected Python privacy cases and focused Node lock/delivery checks passed; JS syntax passed. Phone/haptics checks pending. Commit includes the already-live uncommitted privacy prerequisites and in-scope friendship projection code after review; unrelated source is unstaged. Future deployment must preserve the newer live artwork loader noted above, and deploy API confirmation semantics with matching UI.

Persian review: privacy_tooltip = خصوصی؛ فقط خودت می‌بینیش.; privacy_pill = خصوصی; privacy_love = عاشقشم، خصوصی; privacy_confirm_share = این علاقه رو با دوستات شریک می‌شی؟ تنظیم اشتراک‌گذاری‌ات هم باید روشن باشه.; privacy_confirm_enable = دوستات آهنگ‌های محبوب فعلی و بعدیت رو ببینن؟ بقیهٔ امتیازها خصوصی می‌مونن.; privacy_now_private = حالا خصوصیه; privacy_undo = برگردون; privacy_now_shared = دوستات دوباره می‌تونن ببیننش.; owl_evil = هیس! بین خودمون بمونه.; owl_shared = دوستات دوباره می‌بیننش.; owl_unlocked = قفل بازه؛ چیزی شریک نشد.
