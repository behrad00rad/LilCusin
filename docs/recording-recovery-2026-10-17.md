# Reported source-search and recognition failures — 2026-10-17

The user reported recording-delivery failure and a Shazam no-match after the local flow update. This follow-up preserves existing changes and leaves the Mini App and production untouched.

## Findings and change

- Runtime logs put delivery failure in source search, before downloading or audio sending. Read-only local inspection found failed jobs with no retained candidates.
- The user explicitly approved two song-name search diagnostics after automatic review rejected external disclosure of local-history metadata. YouTube listings contained eight entries, but the old matcher retained none. In the saved failing response, exact song words and artist context were present; extra upload-title text reduced title similarity, and catalogue duration disagreed with available recordings.
- The matcher now retains these as explicit choices with title/duration warnings. It does not auto-select a weak title match, discard version checks, accept a conflicting explicit artist, or accept a title substring without an adequate boundary and artist context. Offline re-ranking of the saved original response changed zero retained rows to two duration-warning choices. This verifies candidate recovery, not successful audio delivery.
- One later diagnostic selected a newly arrived request because it used recent rows instead of pinned failed-job IDs. This was disclosed to the user, further live replays were stopped, and the ignored raw provider-response file was removed. Do not replay historical identities without the relevant permission.
- Tagged Telegram audio previously always went through Shazam. It now uses the existing catalogue confirmation flow when artist/title tags exist; untagged audio still uses fingerprint recognition. Tags alone do not cause an automatic audio download.
- Recognition sample positions now use known clip duration, avoiding seeks past short clips and trying middle/later sections of long audio. Missing duration retains the old bounded offsets. A genuine no-match offers text search/another section rather than asserting the input was unclear. Fixed no-match sample counts and source failure categories improve privacy-safe diagnosis.

## Validation

- `tests.test_youtube_search`, `tests.test_recognition`, and `tests.test_bot_flow_upgrade`: **50 tests passed** in 67.953 seconds. An initial fixture incompatibility for missing optional audio tags was corrected, then the entire focused set passed.
- Compilation and scoped whitespace checks passed. Existing source/artist/version rejection tests still pass; weak upload-title matches require explicit selection.
- Verified no in-flight deliveries before restarting only the isolated local launcher. Build **chat-05300925e107** reached polling with no startup error. Mini App, production and existing unrelated edits were left unchanged; changes are uncommitted.
- Live Shazam recognition or audio delivery of the user's media has not been repeated or claimed. Candidate recovery is verified; a fingerprint service can still return a genuine no-match.
