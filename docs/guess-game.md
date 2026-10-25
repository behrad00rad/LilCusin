# Guess their taste — data and settings, 2026-10-23

Steps 1-4 are implemented locally behind default-off `GUESS_GAME`. No deployment
or push. Phone visuals and real-user/Telegram acceptance remain unverified.
No audio fetching changes.

## Data and privacy decisions

- Additive `guess_games`, `guess_rounds`, `guess_settings`; canonical recording
  IDs refer to existing `tracks.id`. Rounds use zero-based indices 0–4.
- A partial unique SQLite index enforces one open game per ordered pair;
  finished history is retained. Status, score, index, option count and nullable
  answer pairing have constraints. ORM validation rejects duplicate/noninteger
  options. Correct-answer membership and answer projection belong to step 2.
- `allow_guess` defaults ON, including users with no setting row. It remains
  separate from Love sharing. Existing authenticated `/api/taste-sharing` GET
  returns the feature flag and, only when enabled, this setting. POST accepts
  exactly one boolean `allow_guess`, only while enabled. Existing `enabled`
  behavior is retained. The toggle uses a labelled switch and logical CSS.
- User foreign keys cascade games and settings; game deletion cascades rounds.
  Existing unfriend/block/suspension transactions call the game purge hook,
  removing completed and open games in both directions for that pair. Opt-out
  deletes games about the target, preserving their own guesses about others.
  This deliberately gives consent withdrawal stronger deletion semantics.

## Migration and rollback

`Database.initialize()` creates the three new tables and indexes in the existing
transaction. No existing table/column is changed, no legacy row is rewritten,
and repeat initialization preserves data. Before a future real-data release,
take the existing consistent SQLite backup with writers stopped. No real-data
startup was performed in this session.

Rollback: disable `GUESS_GAME` and restore the preceding code. Additive tables
can safely remain unused. For permanent removal after all writers are stopped,
drop `guess_rounds` before `guess_games`, then `guess_settings`; this permanently
discards game history and consent settings. Never restore an old database over
new user activity merely to roll back code.

## Verification and remaining work

Scoped isolated SQLite tests cover default-off flag, default-on persisted
consent/validation, one open game per direction, completed history, option and
round bounds, account deletion in both roles, pair/global interaction cleanup,
opt-out cleanup, repeat initialization, settings flag and existing `/forgetme`.
No live bot/network/provider calls. Initial sandbox fixture setup failed with
temporary-directory permissions; tests were rerun outside that sandbox.

At the end of step 1, remaining work was: answer eligibility/current visibility and alias revalidation,
candidate-service decoys and exclusions, five-round creation, start/status/
answer/nudge APIs and limits, idempotency/repeat avoidance, gameplay/result/
challenge/share UI, notification queue/batching/quiet-hours/mute, their scoped
tests, and the requested EN390 locked/reveal/result and Persian-round visuals.
The setting itself has not been visually checked at 360/390. No gameplay or
notification privacy guarantees are claimed for code that is not implemented.

## Persian additions for review

- `guess_allow`: دوستام سلیقه‌ام رو حدس بزنن
- `guess_allow_help`: فقط از آهنگ‌هایی استفاده می‌شه که دوستات همین حالا می‌بینن. آهنگ‌های محبوب خصوصی‌ات، خصوصی می‌مونن. با خاموش کردنش، بازی‌های مربوط به سلیقه‌ات پاک می‌شن.
- `guess_on`: روشن
- `guess_off`: خاموش

## Step 2 — server rules and APIs, 2026-10-23

Implemented `GET /api/guess/status?friend_id=`, `POST /api/guess/start`, and
`POST /api/guess/{id}/answer`. `friend_id` is the existing opaque 32-character
friend relationship token used by the thread, not a Telegram or internal user ID.
All routes inherit signed initData auth and no-store headers. Worker, bridge and
connector forward only these exact routes and the one validated status query;
their destination stays fixed. The existing consent settings registration/table
imports were previously dirty prerequisites and are included narrowly in this
step's commit; unrelated application edits remain uncommitted.

Correct songs use current unlocked, opted-in shared Loves plus current explicit
signature selections. Locks filter both aliases and base titles. No existing
version grouping was found in the relevant matching/candidate modules: the game
uses normalized titles, strips bracketed edition text and trailing version labels,
and groups across performers conservatively. Alias identities also prevent reuse.

Decoys come from the existing recommendation candidate module's new read-only
cache/local pool (shared tags, artist/related-track cache), then a bounded
popularity-ordered local catalogue fallback. Tags rank genre/era overlap. Language
requires matching explicit catalogue language tags; script is not treated as proof
of language. Unknown languages or fewer than 15 safe distinct decoys yield a 503
`guess_unavailable`, never an unsafe padded game. No provider or bot calls occur.
The local fallback inspects at most 600 tracks; live catalogue coverage is unverified.

Server exclusions cover all target ratings, locks, signatures, saves, requests,
submission/signal records, audio-request/selection records, swaps, preferences,
and feed history regardless of cooldown age. Seen-only history and draft/cancelled
interactions are excluded conservatively too. Both canonical IDs, aliases and base
titles are filtered. All 20 option recordings/base songs are distinct in a game.
Private interactions are never included in responses or errors.

Start resumes a safe open game and expires/replaces stale games after 24 hours.
There are at most three newly created games per ordered pair per Asia/Tehran
calendar day (currently UTC+03:30); resuming is free. Completed and unfinished
correct picks within 14 days are deprioritized when alternatives exist. A single
SQLite writer transaction serializes simultaneous starts and answers. Answers
must be sequential and in the persisted option set; the first pick is immutable.
Repeating the same pick returns the same reveal without incrementing the score;
a changed pick returns 409. Privacy revocation overrides replay availability.

Start/next-round projections contain only idx and shuffled option display fields.
The correct option necessarily appears among the four option IDs; no field marks
which one is correct before a pick. Only the answered round reveals its correct ID.
All five answers and all decoy exclusions are revalidated before resume/reveal;
new private locks or target interactions fail closed. Head-to-head uses each
direction's latest completed score. New-Love badges count current distinct shared
Loves updated since the previous completed game; the first game has no badge.
The result offers replay only when five songs remain outside recent correct groups.

Verification: 12 service/API cases passed (11-case run, then the additional
concurrent-start/wrong-score/unfinished-history case plus the affected daily-limit
case). Includes real signed-auth middleware, wrong actor, blocks in both directions,
opt-out, private/locked versions, lifetime exclusions, under-five grouping, resume,
concurrent duplicate picks, hidden answer fields, scores, signatures, new Loves,
limits, expiry, language abstention, and unfriend replay denial. Three connector
cases and Worker/proxy/bridge route checks passed. Tests use temporary SQLite,
mock providers/bot, and the existing dirty checkout; this is local verification,
not deployment or a real-user acceptance claim. No new Persian strings in step 2.

Remaining: game/locked/result/challenge/share screens, nudges and their limit,
notification persistence/batching/quiet hours/mute and tests, browser RTL/360/390
checks, live catalogue coverage and real two-person Telegram acceptance.

The exact staged database/API registration passed the signed-auth API case again (29.312s); the exact staged Worker passed the guess routing fixture. This checks the selectively staged prerequisites without claiming a wholly clean checkout run.


## Step 3 ? game screens, 2026-10-24

Implemented friend-thread entry with new-Love badge and locked count, full-screen
five-round choice/reveal/result flow, immutable choice/retry, reduced motion,
server-projected next-round cover preload, cached sampled dominant-color placeholders,
reused owl bob/squint states, challenge link and score-only Telegram share sheet.
Sharing requires the configured bot username; missing configuration disables buttons.
The status projection adds permission and display-name context so private opt-outs
are hidden and reverse links open the same authorized friend relationship. Existing
sharing names only appear in share text; results never include titles/covers in links.

English/Persian logical CSS and translations are implemented; [all new Persian
strings](guess-game-persian.md) are listed for review. The local UI fixture passed
immutable/retry picks, right/wrong reveals, preloading, score-only share, Persian
and reduced motion. The affected signed-auth API case passed (14.039s), plus JS
syntax and Worker regeneration. No browser surfaces were available and opening
the in-app browser returned unavailable: requested EN390 locked/reveal/result and
Persian round/360/390 visual acceptance remains UNVERIFIED. No visual screenshots,
real Telegram share, push or deployment. Nudge sending and finish notifications
are the next separate step; the entry's nudge control is wired for that API.


## Step 4 - nudges and notifications, 2026-10-24

Implemented signed nudge and game-alert preference APIs, a once-per-three-days
pair nudge, finish queueing only on the first final pick from an explicitly human
request, and an API-server cleanup-managed worker using the already configured
bot. The business service defaults human=False; startup/status/replay never
creates alerts. No second Telegram poller or external messages were run.

The existing social notification permission is required. Added optional game
alerts and quiet start/end controls because the existing social settings had no
quiet-hour fields. Defaults are 22:00-08:00 Tehran; users can set an overnight or
daytime interval (hours 0-23). Muting a friend or stopping game alerts is owner-
checked and removes queued alerts. Stop applies to game alerts only. Existing
notification opt-out, suspension, current friendship, allow_guess and block
checks run again before sending. Nudge text recalculates the number still needed;
if five songs are now available, it is suppressed. Nudge opens song search;
finish opens the reverse game directly.

Finish messages batch for two minutes, showing the latest score and number of
games in that window, with no songs/covers/ratings. Later games that day do not
create a second alert. A persistent pair/day attempt timestamp also caps old
quiet-hour backlog and survives deletion of game notice receipts on opt-out.
A conservative cap of three game-alert attempts per recipient per rolling 24 hours is applied.
Nudges have their separate three-day pair limit. API acknowledgement means queued,
not confirmed Telegram delivery. Mute/Stop buttons are included on both kinds.

The send claim commits before the network request. A second write transaction
rechecks privacy and holds the writer lock through a five-second bounded send,
so a block/unfriend cannot finish before a stale send. An uncertain/attempted
send is never automatically retried. Missing MINIAPP_URL leaves notices queued.
Multiple API workers serialize claims through SQLite. The worker checks every
30 seconds; flag-off prevents sending and lifecycle cleanup cancels the task.

Migration adds only guess_alert_settings, guess_pairs and guess_notices (including
a due-state index). Account/forgetme cascade, unfriend/block and opt-out cleanup
are covered. Before any real-data startup, take the normal consistent private
SQLite backup with writers stopped. Code rollback can leave these tables unused.
Permanent removal: stop writers and drop guess_notices, then guess_pairs and
guess_alert_settings; existing game tables are handled by the step-1 note. No
real database was initialized or changed in this session.

Verification: the combined related Python run completed 32 cases with one
Persian-copy encoding failure. The copy was corrected with direct UTF-8 file
writes; all new Persian keys now have Unicode/content assertions. All eight
notification cases then passed in a fresh process (37.417s), and the affected
quiet-hour race/batch case passed again (18.289s). Across scoped runs, 33 unique
related Python cases passed (10 data, 12 service/API, 8 notices, 3 connector),
plus the UI state/translation fixture and Worker/proxy/bridge checks. Providers
and every Telegram send were mocked. Tests ran in the existing dirty checkout;
unrelated edits are excluded from the commits. [Persian copy review](guess-game-persian.md).

Remaining acceptance: EN390 locked/reveal/result visuals and one Persian round,
360/390 overflow/tap checks, actual Telegram share/deep-link/notification taps,
real two-person journeys and live candidate-language coverage. Browser inventory
was empty and opening the in-app browser returned unavailable, so these visual
checks could not be performed. No deployment, push, live send or dependency change.


Exact staged database/API registration passed the batch/quiet-race and signed-auth API checks (2 cases, 3.983s). Exact staged Worker routes, JS syntax and all Persian game-string Unicode assertions passed.
