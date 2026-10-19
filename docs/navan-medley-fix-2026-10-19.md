# Navan live-medley delivery matching

Initial patch deployed 2026-10-19 (Asia/Tehran), with explicit user deployment approval.
User subsequently reported continued failure; the initial patch did not resolve
the full stored-track search path. Follow-up below supersedes any completion claim.

The selected Navan Montreal medley failed before download: search candidates were
rejected because the upload reverses the two song names, removes the accent in
Voilà, and includes a cover label alongside the requested live version.

The matcher now compares live-medley components independent of order and accents,
requires matching artist/channel identity and requested location context, and
allows the additional cover label only for that verified performance. These
matches always require explicit selection. Wrong location, artist, components,
karaoke/remix, active livestream and excessive duration remain rejected.

## Verification and deployment

- 18 focused search/matching tests passed locally and against the exact
  production-based candidate (same 18 tests, not 36 distinct tests).
- Only `music_bot/youtube_fetch.py` was deployed. Existing production differences
  and local unrelated edits were preserved. No commit or push was performed.
- Private backup saved; deployed SHA-256 verified:
  `d1bd30f25499a5e8c9c0e89c4cf5228ca6a8581847fbf3b619f15c7612561b51`.
- First restart attempt lacked sudo authentication and restored original source;
  authenticated retry succeeded. Final service state: active/running, result success.
- Metadata-only fixture against the deployed module accepted the Montreal upload,
  required manual selection, and rejected the NYC alternative.
- Reviewable [one-file patch](patches/navan-live-medley-2026-10-18.patch).

No Telegram message, actual media download or playback was exercised. Provider
availability and end-to-end delivery remain unverified. Readable journal output
did not establish polling; active/running is the verified service claim.
Mini App, Worker, UI/assets, configuration and database were unchanged by this fix.

## Follow-up: actual stored identity and retrieval

Latest read-only VPS inspection confirmed `no_matching_candidate` before download.
The actual stored identity removes parentheses, while its display title preserves
the live/location context. Stored duration was 220 seconds; the upload is 272.
The initial fixture used the display title directly and missed this integration gap.

A follow-up one-file candidate uses display metadata consistently for matching,
retains explicit-choice recovery for mismatched duration, and allows verified live
medleys in other-version choices while rejecting wrong artist/components/remix/
karaoke. Original-version matching remains constrained by its requested location.

- 20 isolated search/matching tests passed in 0.103 s with the VPS dependency
  environment and the exact production-based candidate, without modifying runtime.
- A real public metadata search from the VPS returned the expected Navan upload.
- Actual retrieval using the candidate downloaded and validated 4,398,625 bytes
  in a disposable directory, subsequently removed. No Telegram message was sent.
- Native Windows test invocation stalled at event-loop setup; it is not counted
  as passing. Scoped source whitespace checks passed.
- [Follow-up patch](patches/navan-stored-identity-2026-10-19.patch) deployed after
  explicit user approval. Private backup saved; service restart succeeded and
  deployed SHA-256 verified:
  `eef6b30fd495d0c671fa93bcdd6f12434ce497454bdc87eb4a6fe319ece4af56`.
- All 20 tests passed against the actual deployed module in 0.054 s. These are
  the same 20 regressions, not additional distinct tests. Local work is uncommitted.
- Actual Telegram receipt and playback remain unverified.
