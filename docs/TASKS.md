# Prioritized work

This is the execution index, not a second product roadmap. Stable T00–T21 IDs and
full acceptance criteria live in [the vision, section 9](social-product-vision.md#9-ordered-implementation-tasks).
Unchecked means outstanding, not authorized for automatic implementation.

| Priority | Action | Acceptance / evidence |
| --- | --- | --- |
| Local tested | Direct Mini App audio, rated-swap removal, unseen refresh and skeleton/owl loading, 2026-10-21 | `61150aa`; 13 API cases and 10 Node scripts passed. Coordinated backend-first deployment/API restart required; browser and live Telegram validation pending. |
| Deployed | Saved feedback, received swaps in Home and artwork overlay, 2026-10-21 | Five focused checks passed; release `96b50529b5e1cdcd` public hashes/auth verified. Browser/phone visual review pending. Uses existing consented inbox and separates swap cards from recommendation grants. |
| Deployed | Correct Home overflow in Telegram, 2026-10-21 | Responsive square-cover sizing reserves real controls/navigation; viewport/safe-area changes refit. Five scoped checks passed. Release `a90f126e622dc9f5` deployed: public hashes/auth verified, no restart. Browser/iPhone visual check pending. |
| Deployed | Home card and inline owl, 2026-10-20 | `f46500d`: whole-card swipes retained, up/down arrows, square covers, honest ratings and lightweight mascot. Four scoped checks and EN/FA 360/390px layouts passed; eight screenshots in `docs/screenshots/`. Release `eda1f132f83ce635`: public hashes, auth and live Persian browser verified; no restart. Dominant-color server work deferred; real Telegram phone verification pending. Supersedes earlier Home/header polish. |
| Deployed | Search More correction, 2026-10-20 | `8b779c1`: deeper same-query discovery after cached results, five unseen songs per extension, duplicate exclusion, bounded 60-song pool and explicit exhaustion. Seven tests local/Linux; live public probe found 37 distinct songs versus initial 12. Hashes/polling verified; physical Telegram taps unverified. Supersedes cached-pool-only limitation below. |
| Deployed | Terminal 3 Telegram search and music UX, 2026-10-20 | Search More/Previous shipped first (`1108497`), then direct card ratings/Get audio (`edf6e51`). Four search tests local/Linux; 17 local UX/chat cases covered including corrected layout expectations; three focused Linux checks. Hashes/polling verified; native 320/390px visual/tap checks remain. Existing reasons retained; fetched-pool paging only, not unlimited artist browsing. |
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

Home card step 1: local/tested, undeployed. Steps 2/3 pending. See STATE for scoped commit limitations, verification and Persian copy.


Exchanges cleanup (2026-10-22): steps 1-3 implemented locally (layout/icon controls, friend menus/report/thread wording, secret/happy owl). Evidence in STATE; not deployed. Step 4 durable skipped-card persistence/cooldowns/resume remains pending; stopped at usage-limit boundary.


Home persistence step 4 (2026-10-22): implemented locally with private views/skips/hides, cooldowns, action exclusions, queue-backed resume/refill and exhausted state. Scoped evidence/migration requirements in STATE. Deployment and real-phone/offline/EN-FA phone-layout checks remain; optional artist skip ranking deferred.
