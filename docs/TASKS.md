# Prioritized work

This is the execution index, not a second product roadmap. Stable T00–T21 IDs and
full acceptance criteria live in [the vision, section 9](social-product-vision.md#9-ordered-implementation-tasks).
Unchecked means outstanding, not authorized for automatic implementation.

| Priority | Action | Acceptance / evidence |
| --- | --- | --- |
| Local complete | Recommendation loop items 1-3, explicitly requested 2026-10-19 | [Contract and 185 affected tests](recommendation-loop-2026-10-19.md): private taste signals, durable queue/refill and owner-bound feedback; final 16-case chat rerun passed. Release preparation tracked in STATE; deployment requires approval. Friends' discovery, playlists and unsolicited delivery excluded. |
| P0 | Close remaining T00/T01 release-baseline and live-journey gaps | Record current source/runtime identity and relevant flags/serving route without exposing configuration; a representative signed private-bot journey covers search, selection, cancellation, card sharing and delivery. Explicitly retain unavailable checks. Production changes require approval. |
| P1 | Release and verify the local social slices | [Steps 5–8 and 60 scoped tests](social-loop-release-2026-10-19.md), plus [earlier onboarding/portrait](onboarding-portrait-consent-2026-10-18.md), are complete locally. Configure a moderator, obtain deployment authorization, then verify the real two-account Telegram loop. |
| P1 | Confirm operational T02 ownership | The implemented contract covers sparse data, selected inputs, swaps, notification limits, access-driven retention and deletion. An accountable moderation operator and actual deployment remain release gates. |
| P2 | Finish remaining T03–T05 invitation/data/access work | Preserve deployed private-by-default card behavior; add missing recipient/relationship controls and ownership, expiry, revocation and migration checks using canonical criteria. Existing view links do not imply consent. |
| P2 | Close T06–T08 live acceptance | Comparison, reciprocal exchange and controls are implemented and locally tested. Real two-account Telegram/audio/notification checks and operator configuration remain. Do not infer production readiness from local checks. |
| P3 | T09 invited cohort | Complete end-to-end loop with minimal disclosed measurements and real evidence; no retention or payment claims from registrations. |

T10–T21 remain later work in the vision, including feeds, comments, playlists,
payments, imports and optional Telopotify integration. No separate duplicate list.
T13 eligibility investigation can run earlier if explicitly scoped.

When starting a task: select one row, state scope and measurable acceptance,
read its linked contract plus affected source/tests, and stop at that scope.
Update priority or acceptance here only when it changes materially; current
verification/blockers belong in [STATE](STATE.md), rationale in [decisions](decisions.md).
