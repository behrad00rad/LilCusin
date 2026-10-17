# Bot flow implementation checkpoint — 2026-10-17, Asia/Tehran

**Historical checkpoint, superseded:** approved phases 1–3 have now been implemented and locally verified. See [final results and limitations](bot-flow-results-2026-10-17.md). The unfinished-state description below records the earlier scheduling handoff and does not describe the final state.

User requested scheduled continuation at next 03:35 Asia/Tehran: finish approved phases 1 and 2, then phase 3. Leave Mini App unchanged. Inspect current progress before resuming, implement and test, stop schedule after verified completion. Work is NOT complete or tested. Do not restart the bot with the partial changes below until they pass relevant checks.

## Verified runtime

Sanitized elevated Win32_Process inspection identified local_test_bot.py running from this source checkout's .venv/qa. Its launcher imports this checkout, uses an isolated database at .venv/qa/local-test-bot-data/music_bot.sqlite3, restricts interaction to the configured test user, and removes MINIAPP_URL. No Mini App HTTP listener was observed on the checked standard ports. Do not print .env.test, private IDs, command lines, or credentials. D:\lilcusin\LilCusin is an older separate checkout (e15cc38); source HEAD was 80a6fc5. Runtime local process had not been restarted during this implementation session. PIDs are ephemeral; recheck before any restart. Start-Process must use -WindowStyle Hidden.

## Existing work before implementation (preserve)

MINIAPP_DEPLOYMENT.md, tests/test_recommendations.py, worker/artwork.mjs, worker/test-artwork.mjs, worker/worker.mjs were already modified. Earlier audit added docs/ux-audit-2026-10-17.md and appended audit notes to docs/decisions.md, docs/evidence.md, docs/case-study.md. Do not revert or claim those edits as implementation work. No commits/pushes in this implementation session.

## Partial code changes (untested)

- New bot_copy.py: independent chat-only English/Persian copy (other languages currently fall back to English), avoids changing deferred web/locales.json.
- New build_info.py: deterministic Python-source hash; /version handler and startup log use it.
- handlers.start: compact welcome and immediate input, optional /setup. help uses compact current chat guide.
- guidance: removed automatic questionnaire/guide injection and setup on language change. Explicit /setup remains. Legacy explicit guide pages still exist and should be reconciled to avoid outdated cross-bot instructions.
- chat_ui: recommendation lists have two buttons per track (Get via title, Details), remove Lil Bro links/handoff, Get song first on card; optional rating disclosure. Cancel/recovery keyboards added with nav:* callbacks.
- lifecycle.PrivateActions: stores active handler tasks, removes 3-second cooldown, permits menu/command/navigation to cancel and drain an active foreground task before obtaining the shared mutation lock. Needs cancellation/concurrency/forget/privacy tests; review rapid competing navigation and channel-lock behavior carefully.
- chat_handlers: uses get_song.begin, expands optional ratings in place, offers recovery navigation after stale controls. Existing consumed-control handling will need adjustments for repeat rating disclosure. nav:* routes ARE NOT IMPLEMENTED YET, so buttons currently do not work.
- fetch_models.AudioRequest: added nullable status_message_id. migrations adds corresponding INTEGER column for existing databases.
- GetSong: partial begin/bind_status/progress/show_choices and retry keyboard helpers; offer edits bound status when present; send updates status before/after audio; cancellation/failure updates status. Must review races, locking, exceptions, state transitions, duplicate-request binding, bound choice message ownership, deletion/forget races, notifications without status, and whether UI failures can wrongly fail audio jobs. This is unfinished and must not be considered reliable yet.

## Next necessary work

1. Inspect scoped diff, compile, run focused tests to discover current failures; preserve fixtures and update expectations for deliberately changed flows.
2. Implement safe private nav:cancel/search/recommend callbacks, actual contextual cancellation and retry, foreground cancellation cleanup and status behavior. Do not weaken owner/message authorization or deletion locking.
3. Consolidate initial search/candidate/identification progress into edited messages; avoid deletion of the final result. Preserve corrections and explicit ambiguous recording choice. /cancel must invalidate stale flows and remove pending controls.
4. Wire version selection, Wrong recording, and recognized-audio delivery into persistent status. Current handlers still emit old queue notices; recognition still emits extra notices. Add post-delivery optional rating and recovery without forced restart. Refresh expired controls only with retained owner/message context; never resurrect deleted account grants or destructive actions.
5. Set queued/finding/downloading/sending/delivered/error statuses consistently (download progress not wired yet). Preserve useful errors rather than collapsing operator-disabled/limits into an endless generic retry.
6. Phase 3 remains unstarted: cache-first search with bounded remote enrichment, provider budgets, superseded searches, cached audio before artwork, bounded delivery concurrency respecting source/queue limits, stable chat state, measured baseline/comparison. Existing git HEAD can supply baseline; no live latency measurement has been done. Distinguish mocked regression timings from real transport measurements.
7. Add meaningful tests for first-use bypass, primary delivery, optional ratings, ownership, migration, existing databases, interruptible work, same/different users, ambiguous choice, repeated requests, invalid cached references, uncertain sends, failure/retry, expired controls, deletion races, and worker shutdown. Existing tests assume old button positions/list handoffs and will need purposeful updates.
8. Only after verification, restart the exact isolated local bot and verify identity/build via safe checks; do not touch VPS/production. No Mini App asset/Worker edits. Tests should use source/.venv/Scripts/python.exe. Avoid dumping private QA logs or DB rows.
9. Update project decision/evidence/case-study docs, record verified milestone locally per work-journal README with stable deduped ID, offer exact-payload Notion action only after completion. This partial implementation has no accomplishment journal entry.
10. Report implemented vs tested vs live-verified limitations and disable/delete the same-chat follow-up after approved work is complete. Do not archive the chat.
