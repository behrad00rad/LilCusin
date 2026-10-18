# Search responsiveness — 2026-10-18 (Asia/Tehran)

Scope authorized by the user: acknowledge before cleanup/persistence, cache complete
validated searches, and publish useful results without waiting for slower discovery.
Artwork and download optimizations remain outside this release.

## Behavior and tradeoffs

Old-message cleanup runs in bounded background tasks (four users, eight-second
budget); it only touches older owner-scoped messages and checks references again
before clearing them. The new acknowledgement and results are protected.

A bounded five-minute cache holds up to 128 complete public metadata result sets.
Equivalent in-flight searches share work, with eight concurrent keys maximum.
Failures/empty results are not cached; forgetting data clears the search cache.
Catalogue and discovery run concurrently. The first nonempty branch can publish
up to ten choices; later results append up to twenty without moving existing
callback indices. Selection, closure, expiry and owner checks prevent stale updates.
This favors stable controls over reordering late results by a new score.

## Verification

The frozen production-based package passed 128 affected Python regression tests
in isolated Linux staging (34.830 seconds), including hung cleanup, cache expiry,
shared waiters/cancellation, capacity, owner isolation and late-result lifecycle.
Older delivery/search test expectations were aligned with the already deployed UX.

A real-provider query for فرامرز اصلانی against a temporary synthetic database
returned the intended artist: cold 3430.34 ms; repeated searches 56.54 and 90.60 ms
with zero provider calls before first results. The earlier deployed path measured
3560 ms cold and 1940 ms warm. These are small engine samples, exclude Telegram
round-trips and do not establish an end-to-end latency guarantee. Cold search
remains approximately 3.4 seconds in this sample.

No user-facing Telegram messages were sent. Real Telegram presentation, receipt
and perceived latency still require user verification. Concurrent invitation and
onboarding work was excluded from the frozen release; existing local changes
remain uncommitted. Deployment identity and readiness are recorded below after
live verification.

## Deployment

Release `e62d51a326501d2ee357` deployed six scoped bot modules. All deployed hashes match
the passing staging receipt; configuration was preserved, and the service reached
active long-polling readiness. The deployment performed no database edits. A private
code backup supports rollback. Local receipt: `performance-release-receipt.json`
in the outer workspace.
