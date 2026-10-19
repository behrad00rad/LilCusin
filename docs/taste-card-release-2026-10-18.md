# Taste card: first social implementation slice

Date: 2026-10-18 (Asia/Tehran).
Status: implemented and locally tested; uncommitted and undeployed.

## Approved direction and implemented contract

The user approved proceeding after the baseline audit. This slice adds selected
music identity and safe sharing, not comparison or a completed social release.
Existing/concurrent search, recognition, audio, artwork and deployment work is
outside this milestone. Those edits have been preserved, including unrelated
hunks in handlers.py and the deployed Get Song modification.

- A separate TasteCard record has a random stable public Taste ID, nickname
  (40 characters), bio (240), up to five deliberately selected canonical songs
  and one current obsession selected from those songs. It never copies the
  Telegram name, username, private ratings, channel activity or listening signals.
- New cards are private. Sharing needs explicit confirmation, a nickname and at
  least one song. A random 192-bit token opens the approved projection in the bot.
  Tokens expire after 30 days; hiding or replacing a link revokes the old one.
  Anyone holding an active link can view it through the bot; there is no directory.
- Card changes update the shared projection. Copy states that already delivered
  messages, screenshots and forwarded copies cannot be recalled. The public
  projection contains no internal user/track IDs, contacts or authentication data.
- Owner operations use authenticated Telegram identity, per-owner displayed-song
  grants and optimistic revisions. SQLite write transactions serialize changes.
  Replayed selections do not duplicate songs. Stale edits fail rather than
  overwrite another view. Removing the current song clears current obsession.
- /carddelete removes the card and its song selections while preserving ratings.
  /forgetme cascades card removal when deleting the owner. No public audio files
  or imported provider history are added by this feature.

## Bot and Mini App

Use /tastecard, /cardname, /cardbio and /cardsearch to edit without the Mini App.
Search results carry short-lived owner/message-bound selection controls. Inline
controls choose/remove current songs. /cardshare asks for confirmation, then offers
an intentional Telegram share action. /cardhide revokes sharing; /carddelete asks
for confirmation. start=taste_<token> shows only the approved public projection.

The Mini App adds a card editor, exact field projection, song search/selection,
current-song controls, confirmation for publish/replace/delete, and hide/revoke.
The previous private taste summary is still accessible. Unsaved text survives
language changes; sharing/song changes require saving edits first. Outside
Telegram, demo edits stay in memory and publishing is disabled.

Four signed API routes are registered in the application, HTTPS connector and
Worker allowlists. Public viewing accepts the opaque token in a POST body;
query strings and cookies are not forwarded. Worker assets were regenerated
from maintained sources. Explicit half-duplex streaming makes the POST proxy
executable under the local Node test runtime as well.

English and Persian copy is included. Other existing languages use the English
fallback for new card strings. The established owl, colors and general layout
remain. Public marketing has not been changed to promise unbuilt exchanges.

## Verification

- 12 new taste-card tests passed across a 10-test run (53.597 s) and two
  additional integration cases. Coverage includes private defaults, projection
  allowlist, forged/cross-owner/wrong-message/expired selections, stale revision
  races, five-song cap, duplicate callbacks, current-song consistency, expiry,
  rotation, hiding, card deletion, /forgetme cascade, API signing and deep links.
- The two additional cases plus the existing owner-only /forgetme confirmation
  passed together (3 tests, 17.376 s). One case upgrades a database with users
  and ratings but no social tables, preserving those records.
- 17 existing Mini App/connector/handler regressions passed (31.209 s).
- Three existing workflow/lifecycle cancellation checks passed (5.161 s).
  Total: 33 distinct scoped Python tests in this session; the full suite was not
  run. Bot command/callback paths were rechecked after the final exact-card share
  confirmation change, including proof that /cardshare alone does not publish.
- Six Worker/UI scripts passed: test-taste-card, test-worker, test-bridge,
  test-ui-navigation, test-ui-channel and test-ui-recovery. The new POST test
  initially failed due to Node streaming Request requirements; the explicit
  duplex option corrected it and all six passed on the final generated build.
- Python compilation, JavaScript syntax and scoped whitespace checks passed.
- Real browser preview: edit/save, find/add a song and set current obsession
  worked; Persian mixed-direction song names were visually inspected. Computed
  widths showed no document overflow at English/Persian desktop 1280 and phone
  390 widths, plus Persian 320. Local previews are not live Telegram proof.

Demo-only browser evidence: [Persian phone preview](screenshots/taste-card-fa-phone.png).

## Migration, release and rollback

Registration adds two new tables through the existing transactional initialize
path. It does not rebuild existing tables or backfill public data. Fresh/default
cards are private. Before release, preserve/reconcile the production-only edit,
verify configuration and actual Mini App serving route, and use the stopped-
service backup/release procedure in DEPLOYMENT.md. Keep a consistent database
backup and the previous application and Worker artifacts. Deploy bot/API and
connector allowlists before the new Worker UI; test with a disposable private
account before inviting a cohort. Do not start a second poller.

Rollback restores the previous application/connector/Worker release together.
The additive tables may remain for a code rollback; do not drop tables or restore
an old database over newer user writes. A full data restore requires a stopped
service and an explicit decision about changes since the backup. No production
backup, schema upgrade, deployment or rollback was performed in this session.

## Remaining work and limits

A representative live private-bot/provider journey, deployment and real Telegram
share-sheet behavior remain unverified. The VPS service was not changed or
restarted. Existing provider credentials and provider reliability were not
revalidated. Runtime flags/serving paths remain an open part of T00, and T01 is
still open for live evidence despite passing isolated discovery/cancellation tests.

T03/T04/T05 have this implemented subset; they are not marked fully complete:
relationship/report records, full invitation flows and launch controls are still
needed. Consented comparison, reciprocal exchanges, blocking/report handling,
notification controls and cohort testing come next. No feed, payments, badges,
stranger matching, imports or Telopotify merger was added.
