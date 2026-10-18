# Verified release — 2026-10-19 (Asia/Tehran)

Release commit: `f7f07399a44191dfe53649864587398cc845545a`, pushed to
`codex/safe-publish`. This consolidates the preceding local brand-shift slices and
verified existing search, recognition, artwork and retrieval work; it does not
attribute every earlier change to this release session.

## Delivered

Two-entry onboarding; selected-song taste cards and portrait images; recipient-bound
consent; explainable comparisons without invented scores; song drafts, notes,
Save/Love and reciprocal replies; block/report, capped opt-in notifications and
restricted moderation; Mini App Home/card/comparison/swap views and Get Song.
The requested moderator account was privately verified and configured.

## Verification and deployment

424 distinct Linux staging tests passed cumulatively across resumed batches, with
zero skipped or failed cases in the completed set. This was not one uninterrupted
suite run. The obsolete welcome assertion was updated; missing locale keys now
explicitly use the existing English fallback outside English/Persian. Five Node
Worker/UI/bridge checks, compilation, syntax and whitespace checks passed.
Earlier fictional-user browser checks covered English/Persian phone/desktop and
reciprocal swaps; they did not send Telegram messages.

The exact frozen runtime was deployed to the existing VPS. All three services are
active with zero restarts; runtime hashes match, original private configuration
is unchanged, and the verified moderator is active. Unsigned local social and
taste-card requests return 401. A consistent private database/code backup remains.
The first attempt rolled back after its short readiness window; the retry passed
with a longer cold-start window and final-location offline preflight.

Cloudflare accepted Worker version `5f504fb8-56ad-4334-af79-237458786531` at
https://lilcusin-ui.ghazanfaribehrad.workers.dev/ from the frozen Worker snapshot.
Previous version: `2ff6bdc7-7cda-4a91-8bac-07dd901a3cef`.

## Limits

Public URL retrieval could not be verified: local TLS/browser attempts failed and
the VPS received 403 responses. Publication success does not prove public journey
availability. Actual two-account Telegram delivery/audio and moderator review were
not exercised. Offline preflight warned that Node.js was unavailable on its PATH,
so YouTube JavaScript challenge handling remains a provider/runtime limitation.
Concurrent recording-search work appearing after the freeze remains outside this
release and is preserved uncommitted. Production uses the verified runtime manifest;
its historical Git HEAD was not reset to manufacture a clean checkout.
