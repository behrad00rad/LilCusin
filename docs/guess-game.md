# Guess their taste — data and settings, 2026-10-23

Step 1 implemented locally; no deployment or push. The game is not playable yet.
`GUESS_GAME` defaults off; true/1/yes/on exposes only the new consent control
in Settings. No gameplay endpoint, notification sender or audio change exists.

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

Remaining: answer eligibility/current visibility and alias revalidation,
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
