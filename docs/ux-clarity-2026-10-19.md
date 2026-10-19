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
