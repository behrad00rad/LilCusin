# Recommendation loop - resumable implementation

## Scope approved by user

Implement items 1-3: separate explicit/implicit taste, a replenishing private
recommendation queue, and Get/Save/More/Not for me/Already know/Next chat controls.
No playlist builder or unsolicited messages were authorized by the implementation
request. The user later explicitly requested commit, push and deployment; see the
release checkpoint below. Notion publication remains separately approval-gated.
Preserve concurrent dirty work.

## Acceptance

- Get Song requests are weak, deduplicated evidence, never playback or ratings;
  repeated distinct requests increase influence only up to a small cap. Saves
  are deliberate stronger signals, still separate from explicit Love/Like.
- Explicit ratings override implicit evidence. Search alone is not a signal.
  Learning can be paused; reset/forget remove the new private records.
- For You uses a bounded persisted queue, filters current exclusions at serving,
  reserves distinct batches under concurrent taps, records only successful sends,
  and refills without sending unsolicited messages. Restart/expiry/cancellation
  and preference changes cannot resurrect stale recommendations or deleted users.
- Feedback is owner/message-bound and idempotent; known is not dislike; skip/Next
  is navigation. Reasons distinguish saved/requested/playlist provenance.
- Existing and new isolated tests cover the contract. No live account claims.

## Checkpoint

- Core implementation exists locally: request/save evidence, durable leased queue,
  revision guards, For You wiring, feedback and pause/reset controls.
- Baseline: recommendation recovery commit `6ec3da3` is committed/pushed/deployed.
  Existing dirty chat/Get Song/workflow/main/UI/operations edits are unrelated;
  preserve them. New loop work is uncommitted and undeployed.
- First verification: 51 affected tests completed, 50 passed; one old chat assertion
  expected three buttons rather than the new four-button row. Updated that assertion
  to verify the new Save action. Final regressions have not yet rerun.
- Usage cutoff interrupted a hardening patch; resumed and applied generation-based
  stale-refill protection, correct saved state, compact feedback acknowledgements,
  request-retention access cleanup and source-change invalidation. Tests were
  pending at that point; the subsequent results below supersede that checkpoint.
- Resumed verification: a 55-test affected run passed. A subsequent 130-case
  integration run had 129 passes and one fixture error (duplicate raw identity
  for a Persian alias); corrected the synthetic alias. These precede final edits.
- Added cold-start exclusions, artist-round-robin provider seeds, private saved
  library retrieval, account-generation guard and English/Persian callback tests.
- Unified Save with existing private `SavedSong`, including exchange-save/unsave
  and explicit Love invalidation. Known does not remove saves. Reset keeps the
  library but stops learning from pre-reset saves until deliberately saved again.
- Core implementation and integration checks are complete locally. No production
  changes, commit or push were performed for this slice.
- Subsequent integration run completed 181 cases with two Windows SQLite fixture
  cleanup errors; behavior assertions passed, but the run was not green. A focused
  44-case run reproduced one cleanup error. Short refills now get a bounded
  two-second shutdown drain before cancellation, avoiding cancellation during
  quick database work. The two affected scenarios repeated three times each plus
  the new drain regression all passed (7 executions, 3 distinct cases).
- Final sequential nine-module regression **passed all 185 cases** in 260.772 s.
  Hashes of all 24 monitored source/test inputs stayed unchanged during the run.
  Command: `python -m unittest tests.test_recommendation_loop
  tests.test_recommendations tests.test_chat_flow tests.test_get_song
  tests.test_channels tests.test_channel_library tests.test_workflow
  tests.test_taste_setup tests.test_social_loop -q`.
- A final copy-only adjustment makes rating explicitly optional in the cold-start
  message and avoids blaming the user for an exhausted pool. All 16 chat tests
  passed again in 30.856 s; the rerun is not counted as new distinct cases.
- Implementation and affected verification are complete. Next action is a
  separately authorized release review: preserve concurrent edits, reconcile
  current runtime differences, test the exact deployment candidate, then deploy
  only if approved. Friends' discovery and playlist building remain later work.

## Verification and release boundary

185 distinct scoped cases cover request evidence/retention, legacy private saves,
explicit-rating precedence, known versus dislike, reset/forget, stale account
generations, queue expiry/leases/concurrency, cross-instance capacity, failed
send/control recovery, provider rotation, chat ownership, English/Persian labels,
privacy message limits, delivery/channel/workflow and social-save compatibility.
Short-refill shutdown also passed seven repeated executions of three scenarios.
In-memory syntax checks covered 26 distinct relevant Python files; scoped whitespace checks
passed. New files are checked separately because Git diff omits untracked files.

Earlier non-green runs are retained above rather than described as passes.
Existing aiohttp AppKey warnings and asyncio slow-task diagnostics were observed;
the final nine-module run had no failures. This is not a full-repository suite,
production deployment, live provider probe or real Telegram/phone verification.

## Implementation contract

- Explicit Like/Love retain weights 1/3 and override inferred signals. Existing
  private saves weigh 1.5; accepted Get Song requests weigh 0.15, capped at 0.30
  across repeated distinct requests. Searches, version correction and audio sends
  are not listening signals. Playlist-channel evidence retains its weak weight.
- Request evidence is capped at 500 rows per user, with a 90-day window and
  access-driven expiry cleanup. Private saves and feedback persist until changed
  or account deletion. Pause stops new request learning; reset removes ratings,
  channel/request evidence and feedback, invalidates the queue and ignores old
  saved-library evidence without deleting the library. Deliberate resaving opts
  a song back into learning. These semantics are disclosed in chat.
- Queue target 20, low-water refill below 10, one-day entry TTL and two-minute
  recoverable leases. At most two concurrent refills and 32 scheduled user tasks;
  each refill has a 30-second budget including lock/capacity waits. No new provider
  dependencies or audio downloads for warming. Existing three-call provider limit
  remains; provider seeds interleave artists and rotate over successive refills.
- Queued items are not shown history. Exact successful displays are recorded;
  failed sends/control creation release reservations. Account generation and
  preference revisions reject stale in-flight refills. Serving rechecks ratings,
  known/disliked/saved/requested/channel songs and recent canonical aliases.
- Chat lists retain direct Get Song and optional rating, add Save and named
  Options. Cards expose More, Save/remove save, Not for me, Already know and Next.
  /taste exposes pause/resume and the ten most recent private saves, with owner-
  bound retrieval/removal. Feedback uses compact acknowledgements, not new spam.

## Limits

Implementation is committed and pushed; deployment is blocked at source-transfer
approval and real Telegram use is unverified. Cold or exhausted catalogues require bounded online work
and can return no candidates; this is not an unlimited catalogue or Spotify-scale
model. Queue warming follows user activity; no periodic message scheduler exists.
English/Persian copy and callback contracts have fixture tests, not a real phone
rendering/playback check. Friends' discovery and playlist creation are not built.

## Friends' taste - agreed direction, not implemented

User proposed friend-influenced discovery. Keep it a separate, explainable lane
using only deliberately shared/visible songs, with overlap weighting, mute controls,
and current friendship/block/visibility checks at serving. Private saves/requests
must never leak into social candidates. Personal dislikes/exclusions take priority.
This is design context for a later slice, not a completed social recommender.

## Commit/push and deployment checkpoint

User requested commit, push and deployment on 2026-10-19. Reviewed and committed
only the recommendation slice as `cbad204401c84d04e345e2f1f64184b88fe6a712`,
tree `7d31e75c0367016fc571e3a8e7af436369512e9e`. Pushed to the existing
`codex/safe-publish` branch; `git ls-remote` matched the local commit SHA.
The commit has 31 scoped files: 22 runtime modules, two affected test files and
seven documentation files/sections. Mixed main/delivery/workflow/privacy files
were staged hunk-by-hunk; unrelated delivery-copy keys and other local work remain
outside this commit. The final exact staged snapshot passed **183 affected Windows
tests** in 129.557 s. This excludes two unrelated uncommitted delivery tests from
the earlier 185-case working-tree verification; counts are not added together.

Read-only production inspection found existing runtime-only fixes in main,
delivery, discovery and copy. Initial patch application failed in isolated staging;
three-way reconciliation preserved those changes. A runtime-hash guard then
detected a concurrent main-module update and stopped before testing/deployment.
The baseline/candidate were refreshed. No live files or services were changed by
these attempts; no live database was opened or migrated.

Automatic approval review rejected the refreshed upload of private source/test
archives to the existing VPS. It requires explicit source-transfer confirmation
for `103.75.197.217`; this was requested from the user. Do not bypass that review.
**Not deployed.** Final Linux tests and additive schema installation have not run.

Prepared local release artifacts are outside Git in the dedicated
`recommendation-loop-release` directory: reviewed Git/test archives, the reconciled
22-file candidate, old/new hash manifest and baseline. Prepared helper scripts
perform isolated Git/runtime tests and a guarded stop/backup/additive-migration/
restart with rollback; they must not be run until source-transfer approval exists.
Resume by refreshing runtime hashes, retesting both candidates on Linux, verifying
the pushed code commit/tree, then performing the guarded release if authorized.
Full preflight previously had a missing-packaging-checker limitation; refresh its
actual baseline rather than claiming it passed or upgrading unrelated dependencies.

## Resume rule

Read this checkpoint and `docs/STATE.md`, inspect scoped Git diffs, and run the
affected tests before extending work. Do not restart a poller or deploy implicitly.
Record actual completed slices and unresolved failures here after each checkpoint.
