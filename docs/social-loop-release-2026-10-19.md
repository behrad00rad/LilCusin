# Comparison, reciprocal picks and interaction controls

2026-10-19, Asia/Tehran. **Implemented and checked locally; uncommitted and not deployed.**
This completes the implementation scope of the user's numbered steps 5–8. It
does not establish production readiness, a completed pilot, or real Telegram delivery.

## What is implemented

- Both participants can compare the exact signature-song snapshots covered by an
  active agreement. Results show shared canonical songs, normalized shared artists,
  and songs selected by only one participant. Absence means **not selected**, not
  unheard or unrated. Each person needs at least three selections for a sufficient
  sample; smaller cards show an explicit sparse-data notice. No compatibility
  percentage, private rating disclosure, or personality inference is produced.
- Either participant can choose a consented favorite, preview an optional note
  (240 characters), send it, and receive a reciprocal pick. Drafts are sender-only.
  Sending the same draft twice is idempotent. Save creates a separate personal save;
  Love is an explicit private Love rating. Save feedback names the actual partner.
  Removing a save updates related feedback and cancels queued save notices.
- `/swaps`, `/savedsongs`, `/socialsettings`, comparison callbacks and song actions
  work in private bot chat. Replies to note prompts are bound to the user and exact
  prompt. `/cancel` discards drafts. Get Song reuses the existing delivery service
  and rechecks ownership/consent at the bot link. Unavailable audio retains useful
  title/artist information; the Mini App does not stream audio.
- The Mini App has Home, My taste card, Comparisons and Song swaps. Home shows
  waiting swaps, Profile shows real private save data, comparisons have two cards
  (stacked on phones), and swaps expose the same actions. Search and Channels
  remain directly accessible. Existing LilCusin assets/palette are retained.

## Interaction and retention contract

- Swaps require current mutual consent and expire with that agreement, at most
  48 hours from invitation creation. Editing/hiding/deleting either card, rotating
  the target share link, withdrawal, blocking or social suspension prevents further
  interaction and cancels queued alerts. Unblocking does not restore old consent.
  Block labels retain the originally disclosed name; later private edits do not leak.
- Creation is limited to ten drafts per sender in a rolling 24 hours. Inbox and
  saved lists are bounded to the latest 40/50 items; saved counts are actual totals.
- Telegram alerts are **off by default**, with a hard cap of three attempted alerts
  per recipient per rolling 24 hours. Opted-in pick alerts contain the song, note
  and Save/Love/Send one back plus Block/Report. Feedback alerts name the partner.
- Reminders require an explicit sender action, no reaction yet, and a delay of
  24 hours after sending. At most one reminder per day and two per swap; expiry
  may permit fewer. There is no recurring reminder scheduler.
- A durable outbox claims each notification before sending. Concurrent callbacks
  or restarts cannot replay that attempt. Ambiguous failures are retained without
  automatic retry; this favors avoiding duplicate messages over guaranteed push
  delivery. The inbox remains authoritative. Flushes run on send/reaction/reminder
  actions, are bounded to eight seconds, and check opt-in, current consent, block
  and daily cap at claim time. Already dispatched/in-flight messages cannot be recalled.
- Deleting an exchange removes it for both participants and clears its note, but
  leaves personal saves and explicit ratings. Saves can be removed independently,
  even after consent expires. Account deletion cascades through all social records.
- On participant access, expired notes are cleared and swaps over seven days past
  expiry are removed. Reports retain the reported note for review and become eligible for removal at 90 days, with
  cleanup on social access/operator review; deletion of either account removes its
  reports too. There is no unattended retention job; inactive records can therefore remain longer until the next cleanup trigger.

## Moderation and release gate

Block and reason-based Report are present on invitations, comparison and received
picks. Reporting discloses that the note is included for operator review and does
not silently block someone. Duplicate open reports are reused; reporting is capped
at five per reporter per day. No arbitrary private history is exposed to moderators.

The bot's `/socialreports` command is restricted to Telegram IDs explicitly
configured in `LILCUSIN_MODERATOR_IDS` (comma-separated). Empty configuration grants
no access. The operator can list open reports, then run
`/socialreports <report-token> dismiss` or `suspend`. Suspension stops that user's
social interactions and pending alerts. Report tokens identify the subject without
displaying Telegram IDs. This is a limited first review workflow, not a full admin UI.

**Before launch:** configure an accountable moderator, approve and stage a release,
back up the shared database, and verify real two-account Telegram image, consent,
notification, audio, cancellation and deletion journeys. Do not run another poller
with the production token. Existing deployed source/audio behavior must be preserved.
No production settings or services were changed during this implementation.

## Verification

**60 distinct scoped Python tests passed**, not the full application suite:

- 57-test batch: social loop, prior consent/onboarding/card tests, handlers, chat
  flow and Mini App delivery; 409.632 seconds.
- Five final targeted checks: two new private-label/unsave/settings cases and
  three rechecks after final changes; 57.316 seconds.
- Three final notification checks: one new actual card/partner-feedback case and
  two cap/uncertain-send rechecks; 37.706 seconds.

The current test modules contain 18 social-loop tests and 42 affected regressions.
Cases cover unauthorized actors, sender/recipient roles, sparse comparisons,
duplicate sends, explicit ratings, saves/replies, block/unblock, revoked/expired
consent, rate/reminder caps, report authorization, suspension, account deletion,
additive initialization, signed routes, note prompts and audio deep-link ownership.
Initial fixture failures (canonical case and missing dispatcher dependencies) were
corrected; interrupted test attempts are not counted as passing runs. Existing
aiohttp request-key warnings remain.

Five Node checks passed: social routes, taste cards, delivery UI, bridge and Worker
routing. Python compilation, both UI script syntax checks and scoped whitespace
checks passed. Worker assets were regenerated from maintained sources.

Real browser checks used an isolated database and signed **fictional** users, no
production credentials or outgoing Telegram messages. Verified: Persian Save,
reply selection/note/Send, English receipt/Love, sender save feedback, pending Home
strip, two-card desktop comparison and stacked phone layout. Computed document
widths fit 390/320px phone and 1440px desktop in English/Persian where applicable.

- [Persian received pick](screenshots/social-swap-fa-phone.png)
- [English reciprocal reply](screenshots/social-reply-en-phone.png)
- [English desktop comparison](screenshots/social-compare-en-desktop.png)
- [Persian narrow-phone comparison](screenshots/social-compare-fa-phone.png)

The disposable preview is served on this computer at `http://127.0.0.1:8770/`;
`?lang=fa` is the fictional recipient and `?lang=en` the sender. External bot/audio
links are disabled in that fixture. It lasts only while the preview process runs.
The public Worker still serves the preceding approved deployment.

HEAD remains `27c12a2`; substantial earlier and concurrent user changes remain in
the dirty checkout. This slice adds `social.py`, `social_api.py`, `social_chat.py`,
`web/social.js`, scoped tests, and the necessary existing integration hooks. It
does not claim ownership of the prior search/audio/language-picker work.
