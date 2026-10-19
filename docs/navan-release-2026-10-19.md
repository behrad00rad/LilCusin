# Navan matching and retrieval release — 2026-10-19

Scope: this chat's Navan delivery investigation, initial live-medley matcher,
stored-identity correction, regression tests and approved one-file deployment.
Other dirty application/Mini App/social changes belong to separate work and are
excluded from this commit and deployment.

## Result

The search path uses display metadata consistently, preserving live/location
context lost from canonical keys. Live-medley matching tolerates reversed song
order and accents while retaining artist, component, location and version guards.
Incorrect stored duration recovers to explicit recording selection. Other-version
choices can offer verified live medleys. These matches never auto-confirm.

The first patch passed an idealized fixture but did not resolve real stored-track
input. User feedback prompted the stored-identity and duration regression tests.
See the [investigation and deployment record](navan-medley-fix-2026-10-19.md).

## Verified release evidence

- 20 distinct isolated search/matching tests passed against deployed source,
  latest rerun 0.141 s. Earlier runs are repetitions, not additional tests.
- Actual VPS metadata search found the Navan upload; the identical candidate
  retrieved and validated 4,398,625 bytes of audio in disposable storage.
- Approved corrected source was deployed and bot restarted with private backup.
  Final SHA-256:
  `eef6b30fd495d0c671fa93bcdd6f12434ce497454bdc87eb4a6fe319ece4af56`.
- Fresh release check: deployed hash matches, service active/running, result
  success, zero automatic restarts. No additional deployment/restart was needed.
- Scoped whitespace checks passed. Native Windows async test invocation stalled
  and is not counted as passing; isolated VPS tests provide the regression result.

No Telegram receipt or playback was observed. Provider availability can change.
No Mini App, Worker, UI/assets, database or configuration changes were deployed.
The local checkout and production contain independent unrelated edits; the release
is identified by this scoped patch and source hash, not whole-checkout parity.
