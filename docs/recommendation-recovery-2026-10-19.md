# Recommendation recovery - 2026-10-19

## Findings and changes

- For You already consumes explicit Love/Like ratings and weak playlist-channel
  signals. Searching/downloading alone is not an explicit positive preference.
- Pool-size checks counted recently displayed songs before the seven-day
  exclusion removed them. Such songs now cannot suppress online refill.
- Artist-top-track recovery was restricted to selected-song recommendations.
  It now also recovers an empty For You pool from existing positive artists,
  strongest seed weight first, deduplicating artists. No fabricated similarity.
- Retain rated/neutral/disliked-song and recent-history alias exclusions,
  canonical conflict handling, per-call timeout and three-call overall budget.
  Reserve one call for recovery rather than exhausting all calls on similarity.

## Verification

`python -m unittest tests.test_recommendations -v`: **26 passed** on Windows,
including two added regressions for empty For You recovery and recent-history
refill. Existing scoring, provider-failure/timeout, selected-song, identity,
history and no-rating-mutation checks pass. Syntax compilation without bytecode
and scoped whitespace checks pass.

Initial sandbox execution hit temporary-file permission errors; the first
unrestricted iteration exposed three compatibility failures from over-eager
fallback. Corrected the budget and preserved nonempty local results; the final
full affected module passed. Bytecode-writing compileall was permission-blocked;
in-memory syntax compilation succeeded instead.

## Limits

Initial implementation was local only; the user subsequently approved deployment,
commit and push. Existing unrelated changes are preserved.
This fixes reproducible code paths, not a verified diagnosis of a particular
production account. Provider outages can still leave no usable candidates;
artist recovery is narrower than cross-artist discovery. Requests remain
user-triggered; no unsolicited recommendation messages were added.

## Approved deployment

Release `27ccddcae8221606` deployed on 2026-10-19 after user approval. 26 affected
tests passed again in an isolated copy of current production code, preserving
existing recommendation settings. Only `music_bot/recommendations/candidates.py`
was installed. Tested/deployed SHA-256:
`27ccddcae822160600116533d2b3e4ee9a268d3f1cc3263491c5d5599df2ae29`.

Backup and private release receipt retained on the server. First attempt rolled
back safely because offline preflight failed. Diagnosis confirmed a pre-existing
missing `packaging` module in the dependency checker; the unchanged old/new
preflight output was verified, while runtime import smoke checks independently
passed. No dependencies were installed/upgraded. Full preflight is **not** claimed
as passing; its Node PATH warning is also retained.

Controlled bot restart succeeded, polling readiness and stable PID were verified,
and no polling conflict was observed during readiness. Other runtime sources and
private configuration hashes stayed unchanged; Mini App API PID stayed unchanged.
No personal database inspection, live provider lookup or real-user Telegram
recommendation journey was performed. Commit contains only this fix, its tests
and its documentation; concurrent edits are excluded using scoped index patches.
