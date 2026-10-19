# Local chat flow and performance — 2026-10-17

Historical implementation checkpoint. The subsequent source publication is
tracked in the [release record](chat-release-2026-10-17.md); statements below about
uncommitted scope describe the original verification point.

## Scope and approved decision

The user approved phases 1 and 2, then phase 3: runtime identity, chat navigation and delivery UX, then latency improvements. Mini App work is deferred. Existing Worker changes, deployment notes, and recommendation-test edits predate this implementation and are preserved. No commit, push, or production deployment is part of this change.

## Implementation

- Identified the isolated local test launcher in this source checkout; it uses its own database and a restricted test account. Added a content-based `/version` identifier and startup build log. `/search` is an explicit command. The local launcher explicitly disables Mini App configuration even when a general environment file contains it.
- `/start` accepts immediate song input. `/setup` remains an optional personalization tool; language selection no longer triggers a questionnaire. Chat help explains the current direct-delivery path.
- Song cards put Get song first. Recommendation lists offer a named delivery action plus Details per song, instead of four or five controls and an external-bot handoff. Ratings are optional and can be changed; delivery status offers them after audio arrives.
- Identification status becomes the candidate picker or identified-song card in the same message. Delivery keeps a durable status message through queueing, source search, downloading, sending, completion, and failure. Recognition, version selection, and wrong-recording recovery use the same path.
- Request-specific cancellation checks both owner and bound status message. `/cancel` stops the user's active work. Navigation and a newer text query can interrupt foreground searches; cleanup drains before the next action. Destructive operations remain serialized. Rapid queued searches retain the latest intent.
- Recently expired cards/lists and candidate choices can recover within one day using retained ownership/context. Destructive grants, Mini App grants, cancelled controls and deleted-account state are not revived. Missing older context offers Search/For You recovery actions.
- Chat identification returns suitable local catalogue matches first and warms remote search caches in bounded background tasks. Cold chat provider calls have a two-second budget, with a seven-second whole-search budget and a separate bounded lyric fallback. Ambiguous matches still require a choice. Mini App search retains its existing path.
- Cached Telegram audio bypasses artwork and can be sent without waiting for an occupied download pool. Artwork for new files has a three-second total budget; missing artwork does not force an audio refetch.
- Delivery runs two jobs by default, configurable with `GET_SONG_WORKERS` (maximum four). The existing relay adapter retains its own single-request correlation lock. Queue/size/source/ownership limits remain in place. Shutdown cancels and drains worker tasks.
- Status updates serialize with cancellation, delivery, and account removal. Late failure/status updates cannot replace a cancelled terminal state. Ambiguous sends remain uncertain and are not automatically repeated.
- Sanitized search and audio-delivery timing logs contain durations and fixed categories, not user IDs, queries, file IDs, or credentials.

## Controlled before/after measurement

`python -m tests.benchmark_bot_flow` compares revision `80a6fc5` (the pre-change implementation) with this implementation using disposable fixture data, mocked Telegram/source transports, and injected 200 ms metadata/artwork delays. Five samples per case; medians:

| Scenario | Before | After |
| --- | ---: | ---: |
| Known local song identification | 252.50 ms | 34.64 ms |
| Cached audio delivery | 264.14 ms | 47.39 ms |

These are offline control-flow measurements, not live Telegram latency or service-level guarantees. They isolate the removed waits. Cold-network performance remains dependent on providers and source availability.

## Verification

- Final flow/recognition/migration run: **53 tests passed** in 169.863 seconds (`tests.test_bot_flow_upgrade`, `tests.test_flow_handlers`, `tests.test_recognition`, `tests.test_chat_flow`, `tests.test_migrations`). This includes request-specific cancellation, rapid superseding searches, protected deletion, expiry recovery, provider timeout cancellation, cached delivery with both worker slots occupied, and optional rating behavior.
- Delivery/safety run: **57 tests passed** in 159.358 seconds (`tests.test_bot_flow_upgrade`, `tests.test_get_song`; overlapping coverage, not 110 distinct tests). This covers invalid file references, ambiguous sends, source retry, version choices, owner isolation, forgetting, retention and shutdown.
- A broader 154-test regression run covered lifecycle, guidance, chat flow, delivery, legacy handlers, migrations, title search, workflow, recognition, relay fetching and configuration. It found one obsolete recognition assertion expecting the removed extra queue notice; that assertion was updated to verify status binding and recognition passed in the final run above. Earlier fixture/legacy-handler failures were resolved and rerun; no initial failing run is represented as a full pass.
- Python compilation and `pip check` passed. Scoped Git whitespace checks passed. No Mini App web asset changes; the pre-existing Worker edits were preserved.
- Restarted only the exact isolated local launcher after checking there were no active test deliveries. Startup confirmed **chat-560cb89f3eb2** and long polling without a startup error. Read-only Telegram checks confirmed the expected test identity, private-chat `/version` and `/search` command registration, polling mode, and disabled Mini App configuration. The existing local test database migrated successfully.
- No new live song download, audio send, or phone UI inspection was performed in this session. Telegram identity/command checks are not end-to-end delivery proof. Changes remain uncommitted and production was not deployed.

## Limitations

New chat-only copy supports English and Persian; other selected languages currently fall back to English for these new strings. Existing translated menus remain available. No phone screenshot or visual Telegram-client QA is claimed. No new live end-to-end audio delivery is claimed unless explicitly recorded below. Existing cached files keep their artwork rather than being downloaded again solely to upgrade it. The relay source remains serial by design even when direct-source worker concurrency is higher. MINIAPP assets and Worker changes are outside this implementation.
