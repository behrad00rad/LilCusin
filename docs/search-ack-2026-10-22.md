# Early search acknowledgement - 2026-10-22 (Asia/Tehran)

User reported plain-text searches sometimes produced neither results nor a loading
message. Current runtime inspection found language/user database setup and waiting
for an older task's cancellation before the handler's first acknowledgement.
Reply handling also preceded that message. These are verified silent-wait paths,
not proof of which path affected every user-reported request.

The new outer middleware acknowledges owned private non-command text before
language/database setup and mutation-lock waits. EN/FA status updates at roughly
6 and 16 seconds explain that processing continues; Cancel remains available.
The normal handler claims/reuses the receipt. Notifications stop before results
are displayed. Failures visibly finish the receipt; cancellation removes an active
receipt, including cancellation during submission. Special note/onboarding replies
remove their unused receipt without changing social behavior. Telegram send failures
retain the original handler's reply attempt; an unreachable Telegram API still
cannot be guaranteed to deliver an acknowledgement.

Cancellation waits are bounded at two seconds. If an older task ignores cancellation,
a new request receives the existing localized busy/cancel response instead of
waiting silently. The mutation lock is retained: the new handler does not run
alongside the old task. Clean completed tasks are still observed.

## Checks

Eight focused receipt tests passed locally. 45 distinct runtime-staging tests passed
cumulatively: 43 passed in the main run; two chat cases passed after their missing
synthetic fixture was supplied. Coverage includes cancellation-resistant handlers,
receipt reuse, no late edits over results, text/audio flows, search, language and
preferences. Earlier staging attempts lacked test fixtures; those were packaging
errors, not product failures. A pre-existing full locale-key parity assertion fails
for other languages; catalogue bytes were unchanged and that failure is retained,
while language-selection/preferences checks pass. No catalogue rewrite was attempted.

## Deployment

Four-file artifact `a5f28398fa68d32c` is deployed with matching source hashes and
verified bot polling. Only the existing bot was restarted. API PID/health, Nginx,
connector and unrelated source/configuration stayed unchanged. Exclusive locking,
active audio-delivery checks, source guards, backups and rollback were retained.
No schema/data change or database restore. Existing consistent recovery backups remain.
No second poller was started. Real signed Telegram receipt/progress remains unverified.

[Runtime patch](patches/search-ack-2026-10-22.patch) and
[integration fixture](patches/test_ack_integration-2026-10-22.py) retain the exact
runtime-based changes while preserving unrelated dirty delivery work. Replay check:
`git apply --check --ignore-space-change <patch>` against the frozen runtime base.
Blank unified-diff context markers can trigger whitespace warnings; source/prose
checks are separate. This older checkout is not a full runtime snapshot; do not
replace the live checkout wholesale. No new frontend assets or dependencies.
