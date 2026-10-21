# UI clarity pass — 2026-10-19 (Asia/Tehran)

## Critique from the observed UI

Search was a small utility outside the four main destinations. First entry opened
a three-step preference questionnaire, followed by a guide, before the music flow.
The home copy did not explain that Get song delivers in Telegram or that ratings
are optional. Profile put name/bio inputs before the card, then mixed signature
songs, sharing, comparison invitations, saved picks and deletion in a long page.
Empty social screens did not explain the complete path from a card to consent to
a comparison and a song exchange. Internal screens lacked a visible top return.
A preview URL requesting Persian still started in browser English.

## Implemented locally

Four primary destinations: Home, Search, Exchanges, My card. Exchanges groups Songs
and Compare tastes with an active state; nested pages retain their parent marker.
First entry opens music directly; the guide and preference setup remain available
on demand. Home gives search priority and explains Telegram delivery and optional
ratings. Channel connection and tuning remain secondary home tools.

Profile starts with visibility and the audience preview, followed by a focused
choose-song action. Name/bio editing, saved picks and advanced options use labeled
disclosures. Sharing has its own explanation and expandable visibility details;
existing confirmation/consent controls remain. Input editing updates the preview.

Empty search/exchange/comparison screens explain what to do next. Detail screens
have a top return action. Comparisons prioritize Send a song, omit empty result
sections and redundant internal IDs; pending consent still shows both song sets.
Swap copy distinguishes saving from rating and describes the Get song destination.
Exchange requests show loading and retry states with stale-response protection.
English/Persian guidance is localized; other supported languages explicitly use
English for new keys. Preview language URLs work without changing signed actor
language preference authority.

Palette variables, owl assets, fonts and existing gradient/card identity are
preserved. Layout changes reduce phone header height and prioritize actions.

## Scoped verification

Two TranslationTests passed (matching locale keys/placeholders and Telegram
language/menu behavior). Five existing Node checks passed: social routes/UI,
Get song grant renewal/preview safety, taste cards, Worker routing/auth, and bridge.
Both UI scripts passed syntax checks; rebuilt Worker and scoped whitespace passed.
An initial translation invocation from the outer directory failed to import tests;
it was rerun successfully from the actual application root.

Browser checks used local preview and an isolated fictional-user database, without
production credentials or outgoing Telegram messages. Verified Persian search for
Space Song, add-to-card, preview-first profile, name/bio editing and save; empty
exchange/comparison guidance; English consented comparison and return navigation;
received-pick detail, Save/removal and live saved-count updates; choose-first-song focuses its search input. Computed
width checks found no horizontal overflow for Persian at 320/390px, English at
320px, and desktop comparison/home at 1440/1536px where exercised. No automatic
questionnaire or guide modal appeared on fresh preview entry.

[Persian desktop preview](screenshots/ux-home-fa-desktop-2026-10-19.jpg).
Phone screenshots from the browser viewport tool were incorrectly scaled, so they
are not offered as visual proof; the phone geometry and interaction checks above
were observed directly. No full backend suite was run for this frontend-only pass.

## Status and limits

Implemented and checked locally, uncommitted and undeployed. Existing migration,
recording-search and other dirty work is preserved and excluded from this scope.
The review covers the Mini App; Telegram chat UX and real signed Telegram journeys
were not retested. This is an expert clarity pass, not evidence from a user study.

## Follow-up: focused discovery and personal exchanges

Implemented locally on October 19 after the user requested less scrolling, real
icons, swipe browsing, delivery feedback and more visible social identity. The
supplied redesign brief informed this incremental pass; no reference image was
attached. Existing palette, owl, fonts, vanilla JS, consent and delivery flows remain.

Home now presents one recommendation at a time, with upward/downward cover
gestures, keyboard alternatives and Previous/Next controls. Rating is optional.
Existing bounded refill/grant renewal remains in use. Artwork adapts to available
height; the 320px layout accommodates the real pending-exchange banner. Secondary
utilities live in the header menu. Profile utilities are separated into compact
Preview/Edit/Share/Saved panels rather than one long page. Lucide SVGs are bundled
locally with license and source hashes; labels remain visible.

Get Song shows opening/waiting/queued/choice/sending/confirmed/failed states.
The new read-only signed `/api/delivery-status` endpoint checks the actor's current
track grant or accessible sent swap and returns a bounded receipt. Completion
requires an owned AudioRequest with a Telegram message ID. Old completed requests
cannot count as a new send; an active older request stays bound through completion.
No job is queued by this endpoint. Local receipts omit grants and URLs. Preview
mode explicitly says no request was sent. Worker forwarding/assets were updated.

Existing exchange inbox/detail now show the approved name, initials avatar, real
song artwork where available, note and reliable sent time. Unreacted received
picks appear first. Projection adds safe `song.artwork` and nullable `sent_at`
after the existing participant/consent checks; no state-machine or sharing-rule
change. Telegram profile photos are not collected or exposed: actual opted-in
photo support still needs a separate consent/data implementation. Missing artwork
uses an honest music fallback. No fabricated social counts, faces or scores.

### Follow-up evidence and limits

31 scoped Python tests passed: SocialLoopTests (including safe-artwork/time and
revocation), DeliveryStatusTests, MiniAppDeliveryTests, and TranslationTests.
Five Node checks passed (social, UI delivery, taste card, Worker, bridge); final
social/UI-delivery checks repeated after final asset regeneration. Both JS syntax
checks, Worker build and scoped whitespace checks passed. Existing aiohttp key
warnings and Windows asyncio timing warnings remain; no full backend suite run.

Browser checks used disposable fictional users, with no outgoing Telegram sends.
Keyboard next-song navigation, preview feedback, simulated pending-to-confirmed
receipt, profile panels and exchange detail were exercised. English/Persian
phone geometry at actual 320x740 and 390x843 showed no horizontal overflow;
final 320px recommendation card bottom was 553px, controls began at 566px and
navigation at 664px with the pending banner present. Desktop exchange preview
was visually inspected at 2304x1010. Phone screenshot capture has scaling issues;
phone geometry is evidence, not a claim of physical-device testing.

[Full-context exchange screenshot, fictional users](screenshots/ux-exchanges-en-2026-10-19.png).
The fixture deliberately has missing artwork, demonstrating the fallback.
Real signed Telegram delivery, physical swipe gestures, mobile keyboard/safe-area
behavior and retention improvements remain unverified. Portrait card image and
new social features were not redesigned. No commit, push or deployment performed.

## Approved release verification

User authorized commit, push and deploy. UI commit `cdcc4d2` is pushed on
`codex/safe-publish` and installed at the existing direct VPS HTTPS origin.
19 scoped code/test/evidence files were committed; concurrent chat/recommendation
changes and the already-deployed hosting registration were excluded from staging.
Production miniapp.py retains that hosting registration plus the receipt endpoint.

The first deployment attempt rolled back its UI files after verification failed
while another release changed protected bot files/PID. The second isolated staging
run reconciled against that new runtime: all 31 affected Python tests passed again.
Successful application retained rollback copies and restarted only the Mini App
API. Target hashes matched; other Python files/private configuration and bot,
Nginx and inactive connector states/PIDs matched the refreshed baseline. No database
or environment changes were made. The old Cloudflare Worker was not republished;
generated Worker assets remain committed for compatibility.

External HTTPS checks returned 200 with byte-for-byte source hashes for index,
app.js, social.js, style.css and locales.json. Unsigned delivery-status returned
401. Real signed Telegram opening, audio receipt and physical touch gestures
remain unverified; these operational checks do not establish those journeys.

## Dual chat/Mini App access restoration

User requested both a Mini App button and chat-only use. A separate chat startup
change forced MenuButtonCommands and displaced the existing launcher. Restored
the live default Open LilCusin web_app button; default/English/Persian private-chat
command read-back still includes search, recommend and help. Existing chat reply
keyboards and direct song submission remain available. `/help` exposes those chat
buttons; `/` offers registered commands without requiring the Mini App.

Startup now registers commands without forcing the launcher to commands. When
an embedded Mini App URL is configured it may set that launcher; when unset it
preserves the separately managed launcher. Only this narrow startup patch was
applied to the existing VPS file; unrelated edits preserved, backup retained and
polling PID unchanged. No restart, messages to users, commit or push in this fix.

Two TranslationTests passed; local AsyncMock command-registration checks confirmed
localized commands do not modify the launcher, and English/Persian chat keyboards
remain chat controls. Startup syntax and scoped whitespace checked. An initial
outer-directory unittest discovery failed to import the app; corrected repo-root
invocation passed. Telegram acknowledged JSON menu writes without reflected changes;
query-parameter transport produced the verified web_app read-back. No explanation
for that transport discrepancy is established. User-device rendering and actual
chat/song-delivery journeys remain unverified after this operational fix.

## Whole-card and tab gestures - 2026-10-20

User reported cover-only gestures and artwork drifting after a swipe/tab change.
This local follow-up moves the entire recommendation card during vertical drags;
up/down advances/returns a song without rating. Horizontal drags navigate the four
primary tabs in their visual LTR/RTL order, including blank content space. Inputs,
editors and dialogs keep their gestures; other pages retain native vertical scroll.
Threshold/axis checks, pointer cancellation, multitouch cancellation, stale-view
checks and release-click suppression prevent accidental navigation/actions. New
intentional taps and keyboard controls remain usable. Swiping into Search does not
automatically focus its input or open the mobile keyboard.

Cover images are absolutely anchored inside a bounded frame instead of affecting
centered grid sizing. Discovery sizing no longer animates height or translates
the card during measurement; font/viewport changes refit the frame. Whole-card
drag transforms are cleared on release, cancellation and navigation. Palette,
artwork identity, recommendation APIs and rating/delivery behavior remain intact.

On supported Telegram clients the discovery deck disables host vertical minimize
swipes and other pages restore them, following Telegram's documented
[gesture methods](https://core.telegram.org/bots/webapps). This integration remains
unverified inside a real Telegram client.

Six Node checks passed (new gesture regression plus five existing UI/Worker checks),
two TranslationTests passed, JS syntax/Worker regeneration/scoped whitespace passed.
Browser pointer drags started on song text advanced/returned songs; horizontal
drags navigated Home/Search and returned, including Persian's mirrored direction.
At actual 390x843 and 320x740 phone viewports no horizontal overflow was observed.
A labeled disposable artwork fixture used the existing owl asset as a known loaded
image, not fabricated song artwork: measured image/frame top and bottom differences
were zero after swiping and returning to Home, natural width 320. Desktop at
2304px was also checked. Browser mouse/pointer drag is not physical-touch evidence.
Screenshot capture timed out despite alternate documented capture attempts; no
new screenshot is claimed. The normal local preview is on port 8780; the labeled
artwork test fixture is on 8784. No backend suite, production change, commit, push
or deployment was performed for this follow-up. Unrelated dirty work preserved.

### Gesture deployment - 2026-10-20

User subsequently authorized deployment. Release `28bb9f95e81cc9ab` installed only
app.js, style.css and locales.json, with prior deployed hashes checked before
writing and rollback copies retained. The two gesture/delivery Node checks and
scoped whitespace check passed again before release. Loopback served hashes matched;
external HTTPS returned 200 and exact source hashes for all five interface assets
(including unchanged index/social.js). Unsigned delivery-status returned 401.
Bot, Mini App API, Nginx and inactive connector states/PIDs remained unchanged;
all Python sources and private configuration hashes remained unchanged. No restart,
database operation, Cloudflare publication, Git commit or push was performed.
Physical Telegram swipes and client rendering still require real-device validation.


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


## A1 deployed - 2026-10-20

UI commit `02259c0` deployed as asset release `a00194180b159c2a` after explicit
user authorization. Four frontend assets updated after prior-hash checks; rollback
copies retained. All five public HTTPS UI assets returned 200 with matching hashes;
unsigned delivery-status returned 401. Service states/PIDs, Python sources and
private configuration unchanged; no restart. Initial upload disconnected before
application; retry succeeded. Supersedes the pending status below. Physical
Telegram gestures and real delivery remain unverified. No further development.

## Home card and inline owl evidence - 2026-10-20


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

The old CSS colored the first Love button without a stored rating. That rule was
removed; new tests cover unrated, four stored values, invalid and preview states,
radio-group/action ordering, fixed-color and selected-state contrast, owl reaction
reset timing and tip cycling. Existing gesture/motion/delivery regression scripts
passed. No invented reason or total catalogue size: the pill counts loaded picks.
The extra Home heading was removed so the card's actions clear the bottom bar.
All API operations, signatures, consent checks and backend state remain unchanged.
No portrait, avatar, social, audio or recommendation-algorithm work in this slice.
The previous brand JPEG block and decorative owl emoji were replaced on Home;
the user's identity is separate. No animated-image asset or dependency was added.

Screenshots are local preview data, not real user records or Telegram evidence:

| Language / width | Before | After |
| --- | --- | --- |
| en / 360px | [Before](screenshots/home-owl-before-en-360.jpg) | [After](screenshots/home-owl-after-en-360.jpg) |
| en / 390px | [Before](screenshots/home-owl-before-en-390.jpg) | [After](screenshots/home-owl-after-en-390.jpg) |
| fa / 360px | [Before](screenshots/home-owl-before-fa-360.jpg) | [After](screenshots/home-owl-after-fa-360.jpg) |
| fa / 390px | [Before](screenshots/home-owl-before-fa-390.jpg) | [After](screenshots/home-owl-after-fa-390.jpg) |

### Persian copy for owner review

Native conversational Persian; owner review is still requested.

| Key | Copy |
| --- | --- |
| `home_count` | {n} از {total} |
| `home_swipe` | کارت را بالا و پایین بکش یا فلش را بزن |
| `owl_label` | جغد راهنما؛ بزن تا یک نکته بگم |
| `owl_idle` | بزن تا یه نکته بگم |
| `owl_love` | یادم می‌مونه؛ بیشتر از اینا پیشنهاد می‌دم. |
| `owl_like` | انتخاب خوبیه. |
| `owl_neutral` | باشه، گرفتم. |
| `owl_dislike` | گرفتم؛ کمتر از اینا پیشنهاد می‌دم. |
| `owl_tip_0` | خود کارت رو بالا یا پایین بکش تا آهنگ عوض بشه |
| `owl_tip_1` | به چندتا آهنگ امتیاز بده تا پیشنهادها به سلیقه‌ات نزدیک‌تر بشن |
| `owl_tip_2` | تا پنج آهنگ محبوبت رو به کارتت اضافه کن؛ بعد پیش‌نمایش بگیر و بفرست |


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


## Viewport fix deployed - 2026-10-21

Explicitly authorized asset release `a90f126e622dc9f5` deployed commit `5c50070`'s
app.js/style.css after prior-hash checks; rollback copies retained. Viewport
regression passed again. All five public UI assets returned 200 with matching
hashes; unsigned delivery-status returned 401. Service states/PIDs, Python sources
and private configuration unchanged; no restart. This supersedes the pending
status below. Browser rendering and physical iPhone verification remain pending.
