# LilCusin: music identity and connection inside Telegram

Written: 2026-10-17 (Asia/Tehran).
Status: documented product vision and proposed execution plan. Documentation requested by the user; implementation, dates, prices and rollout have not been approved or completed by this document.

## Implementation update — 2026-10-18

The user authorized beginning the baseline and first taste-card slice. See
[taste-card implementation and evidence](taste-card-release-2026-10-18.md).
Selected public identity and revocable sharing are implemented and locally tested,
uncommitted and undeployed. The task list below retains its original acceptance
criteria: comparison, exchange, moderation and pilot completion are not implied.

## 1. The product

LilCusin is for people who care about their music taste and want to express it, discover music, and connect with people who understand it.

Promise: **Find your people through music. Keep discovering together.**

Recommendations bring someone in. A recognizable taste identity and meaningful interactions give them reasons to return. The core social object is a song, playlist or exchange, rather than a generic status post.

The user explicitly wants to explore comments, friends' shared likes, taste IDs, shared tastes, playlists, importing music from other apps, badges, competition and meeting people with similar taste. These are the full vision, not a commitment to launch every feature together. The user also prefers staying in Telegram instead of asking people to adopt another standalone player.

## 2. Product shape: bot + optional Mini App

| Surface | Purpose |
| --- | --- |
| Telegram bot | Submit/recognize songs, get recommendations, rate, exchange songs, receive chosen notifications, share invitations and pay for a plan when available |
| Mini App | Browse profiles, choose public signature songs, inspect shared taste, manage playlists, read song notes and manage preferences |
| Existing Telegram chats | Continue conversations after a mutual introduction; LilCusin does not need to recreate private messaging |
| Telopotify | Optional later source of library/recording/playback capabilities, not a required second app or a prerequisite for the social release |

The first useful result must work in chat. Opening the Mini App should make a visual task easier, not unlock basic participation. Preserve natural English/Persian copy and RTL/mobile behavior. Reuse established LilCusin visual identity rather than starting a separate generic social brand.

## 3. Experience we want

1. A person sends songs or picks a few favorites and receives useful recommendations.
2. They choose a short public music identity: signature songs, current obsession and a bio.
3. They share their taste card with a friend through a deliberate Telegram share action.
4. Both consent to compare selected tastes. The result explains actual shared music and interesting differences.
5. Each sends one song the other might enjoy, optionally with a personal note.
6. The recipient reacts, saves it or sends a song back.
7. Over time, they follow chosen people, build shared playlists, join challenges and optionally discover new music friends.

Example invitation: «فکر می‌کنی سلیقهٔ موسیقی‌مون چقدر به هم می‌خوره؟»
Example exchange: “You share these three artists. Each of you has favorites the other has not rated. Exchange a song?”

Imported or suggested tracks are not automatically explicit likes. Listening history is not automatically public. Similar taste does not establish personality or romantic compatibility.

## 4. Full feature vision

### Music identity

- Stable shareable Taste ID, distinct from internal database IDs and Telegram contact details.
- A deliberately selected public profile: up to five signature songs, current favorite, short bio and optional featured playlist.
- A private taste model using explicit Love/Like/Neutral/Dislike feedback and any separately authorized signals.
- Understandable comparisons: shared artists/tracks, contrasting favorites and suggestions to exchange.
- If a score is introduced, document its calculation, sample size and uncertainty. Sparse profiles should say there is not enough information rather than invent precision.

### Social interaction around songs

- Short notes and comments on canonical recordings, with prompts such as “Which part gets you?” or “What memory does this bring back?”
- Reactions, replies and deliberate private dedications.
- Followed users' explicitly shared picks, never an undisclosed live listening feed.
- Attribution such as “Discovered through this person's recommendation,” with consent and reversible visibility.
- Shared playlists with clear ownership, contributor permissions and edit/removal behavior.
- Song exchanges that provide a reason to talk, rather than an empty match notification.

### Meeting people

- Begin with invitations between existing friends; add stranger discovery only after reciprocal exchanges work.
- Opt-in discovery, useful match explanations and mutual acceptance before contact sharing.
- Proposed initial stranger-discovery policy: adults only, no exact location, no exposure of private listening, and easy blocking/reporting.
- Friendship is the default positioning. Dating is a separate deferred adult-only mode requiring its own decision, moderation and age-assurance design.
- No claim that “meet this girl” access is a purchasable reward. No selling private contact details or unsolicited messaging privileges.

### Recognition and community challenges

- Reward useful contributions rather than claiming to rank music taste objectively.
- Proposed badges: Good Ear (recipients save recommendations), Bridge Builder (successful cross-taste exchanges), Album Explorer (album discussions), Trusted Curator (sustained useful playlists).
- Start with transparent, bounded criteria and basic abuse resistance. Do not turn every message or repeated click into points.
- Optional weekly themes and small community challenges; no global “best taste” leaderboard at launch.
- Cosmetic supporter items must look different from earned badges. Payment must not buy trust or organic recommendation placement.

### External playlist onboarding

- Goal: reduce the effort of describing taste, not require another account before trying LilCusin.
- Ask which playlist represents favorites, background listening or another purpose; let the user confirm seed songs.
- Start with direct user-selected tracks and explicitly submitted metadata. An uploaded export is not automatically exempt from its source's terms.
- Provider connections require a documented permitted use, least-privilege authorization, deletion/disconnect behavior and account eligibility review, including the operator's residency constraints.
- Spotify is blocked pending permission/use-case review: current published policy restricts user profiling and AI/ML ingestion, and development access is limited. Do not promise Spotify-powered compatibility or bypass restrictions through scraping.
- Apple Music offers authorized library-playlist access technically; commercial use, account eligibility and exact profiling permissions remain unverified. YouTube and other integrations require their own review.
- Import metadata, not audio, unless an independently authorized audio path is established. Playlist access does not establish redistribution rights.

## 5. Existing foundation versus new work

Baseline inspected in this conversation: LilCusin `codex/safe-publish` at `27c12a2`, also present on GitHub; `main` is older. Telopotify main is `40a33cc`. These are dated source snapshots, not deployment guarantees.

| Capability | Evidence/status |
| --- | --- |
| Search, recommendations, explicit ratings, taste setup, channel collection | Present in inspected LilCusin source |
| Recognition, Get song jobs/cache, alternate versions and improved title discovery | Implemented in recent commits; activation/source availability vary; not all production behavior reverified |
| Mini App profile/search/rating/channel endpoints | Present; current profile API is not a public social profile system |
| Broader similarity candidates and empty-result artist fallback | Existing uncommitted work; runtime validation incomplete |
| Playback, queues, libraries and collections | Present in Telopotify; not connected to LilCusin |
| Public Taste IDs, follows, comments, exchanges, social matches and badges | Proposed new work; not evidenced by inspected LilCusin schema/routes |
| Paid plans and complete Iran-compatible payout path | Proposed; not implemented or verified by this review |

Do not mark recommendation quality or willingness to pay as established. Earlier discussion assumed good recommendations for product planning; it was not a benchmark result.

## 6. First release and deliberate boundaries

**First social release: a private taste profile plus a shareable public card, comparison by invitation, and a reciprocal song exchange.** Include a short note on an exchange, blocking/reporting and notification preferences from the first release.

Followed-user feeds and public comment threads come next, after a small group is exchanging music. This narrows the initial feature list proposed in conversation so the first release has one complete interaction rather than several empty surfaces.

Deferred: global feed, open stranger matching, dating, global leaderboards, continuous multi-provider sync, Mini App streaming, native-app synchronization and a full Telopotify merger. Preserve their place in the vision without making them dependencies.

## 7. Proposed business model

Keep Taste IDs, sharing, basic comparison, following, comments and mutual introductions free. These create the community and distribution.

Charge for repeated personal utility: more custom/shared playlists, deeper refinement controls, recurring discoveries and optional profile cosmetics. Avoid selling social trust, privacy access or contact privileges.

Pricing hypothesis from this discussion, subject to cost and conversion testing:

| Offer | Proposed allowance/price |
| --- | --- |
| Free | Three five-song discovery batches per week, one custom playlist/month, a shared-playlist preview and free basic social identity |
| Plus | 199 Stars per 30 days; daily selections, refinement and up to 30 custom playlists/month |
| Playlist pack | 49 Stars for three extra custom playlists |

Do not advertise unlimited costly recognition/acquisition. Finalize allowances after measuring usage and success rates. Explain renewal, expiry and refunds clearly. No annual or lifetime plans at launch.

Telegram requires Stars for digital features sold inside bots/Mini Apps; a separate checkout for the same bot benefits is not assumed to avoid that rule. Stripe is not a dependency. Acceptance of Stars does not establish ability to receive rewards in Iran. Verify Fragment eligibility and a genuine complete payout path before depending on subscription income. Do not misrepresent residency or identity.

If payout is unavailable, consider a free consumer product with separately contracted, clearly labeled sponsorships and a locally supported business payment route. That is a distinct model, not a disguised Plus checkout. Commercial Last.fm permission and other provider/content permissions remain launch dependencies.

## 8. Proposed marketing

Start in one music scene the owner understands. Position around identity and connection: “Find someone who gets your music,” rather than generic AI claims.

- Shareable taste cards with comparison links.
- Curators share their selected tastes; followers compare and exchange songs.
- Short Persian/English demonstrations of an actual song exchange or shared playlist.
- Voluntary friend invitations; never contact scraping or automatic messaging.
- Later creator affiliates only after checkout, payout and retention work. The discussed 20% for three months is a hypothesis, not an active program.
- Referral rewards follow a completed useful interaction, not empty bot starts; cap rewards and prevent self-referrals.

No broad paid acquisition until return usage and real paid conversion are measured. Start with roughly 30–50 invited relevant listeners, expanding only as service quality and moderation capacity allow.

## 9. Ordered implementation tasks

All boxes below are intentionally unchecked. IDs are stable for future progress updates. A task is done only when its acceptance criteria are demonstrated; a source commit alone does not establish deployment.

### Phase 0 — Establish a reliable baseline

- [ ] **T00 — Record branch and runtime baseline.** Identify local-test versus production builds and feature flags; preserve existing edits; document which changes need validation/deployment. Done: source/runtime differences and reproducible scoped checks recorded without exposing private configuration.
- [ ] **T01 — Resolve discovery reliability.** Diagnose the local async-test stall, validate the current empty-result fallback, cancellation and ordinary recommendation flow. Done: meaningful scoped tests complete and a representative private-bot journey succeeds; no universal recommendation-quality claim.
- [ ] **T02 — Fix first-release product rules.** Decide exact profile fields, visibility, comparison inputs, exchange state transitions, notification frequency, moderation owner and deletion behavior. Done: a short reviewed contract covers the edge cases below and English/Persian copy.

### Phase 1 — Identity and safe sharing

- [ ] **T03 — Add social data model and migrations.** Separate public profile fields from private ratings; introduce non-enumerable sharing tokens, privacy settings and required relationship/report records. Done: existing records migrate safely, constraints/ownership tests pass and rollback/backup procedure is documented.
- [ ] **T04 — Build profile editing and taste card.** Choose signature songs, bio and visibility; preview exactly what another person sees. Done: owner-only editing, private-by-default exposure, English/Persian mobile/RTL checks, accessible controls and no horizontal overflow.
- [ ] **T05 — Add intentional share/invitation links.** Authenticate participants, handle existing/new users and support expiry/revocation. Done: forwarded links reveal only the approved public projection and cannot expose internal IDs, private ratings or Telegram authentication data.

### Phase 2 — Comparison and reciprocal exchange

- [ ] **T06 — Implement explainable comparison.** Compare consented inputs, show shared music and differences, and handle sparse data. Done: deterministic examples and privacy tests pass; imports are not silently converted into Love ratings; no unsupported personality/dating claim.
- [ ] **T07 — Implement a two-way song exchange.** Invite, accept/decline, select a song, add an optional note, deliver and react/save. Done: unauthorized or blocked users cannot interact; duplicate callbacks/restarts do not duplicate delivery; cancellation/deletion have defined effects; inaccessible recordings have a useful fallback.
- [ ] **T08 — Add notification and moderation controls.** Opt in/out, cap reminders, support block/report/delete, and provide an owner moderation workflow. Done: block and revoked consent stop pending notifications; reports can be handled; user deletion removes or anonymizes social records according to the stated policy.
- [ ] **T09 — Pilot the full loop.** Run a small invited cohort through bot + Mini App. Done: first-use completion, reciprocal exchanges, saves, seven-day return, failures and support reports are measured with minimal disclosed analytics. No paid-conversion claim without purchases.

### Phase 3 — A small community

- [ ] **T10 — Add follow/unfollow and a bounded friends feed.** Show deliberate public picks with privacy-aware pagination, not all listening activity. Done: blocking, deletion, visibility changes and access rules apply to feed items.
- [ ] **T11 — Add song notes/comments and replies.** Reuse canonical recording IDs and include edit/delete/report, rate limits and spam controls. Done: ownership, moderation, removed accounts, notifications and empty states work; playback source variants do not accidentally create duplicate discussions.
- [ ] **T12 — Add shared playlists.** Define owner/contributor permissions, deduplication, recording availability, saved revisions and removal behavior. Done: two users can create/edit a playlist without overwriting each other or granting cross-account access to restricted audio.

### Phase 4 — Commercial validation (investigation can run early)

- [ ] **T13 — Resolve payment and provider eligibility.** Check Stars/Fragment availability for the actual operator, commercial Last.fm permissions and relevant recognition/artwork/content terms. Done: documented allowed route and, before paid scale, a genuine eligible payment-to-payout cycle; otherwise select the free/sponsorship route explicitly.
- [ ] **T14 — Measure unit costs and choose allowances.** Estimate cost per active user/playlist, peak work and support burden. Done: pricing and limits have a written rationale; rewards are not confused with buyer prices or profit.
- [ ] **T15 — Implement one Plus offer if eligible.** Stars invoices, verified successful payments, idempotent fulfillment, expiry/renewal, support/refunds and reconciliation. Done: duplicate/delayed events, cancellation and failed-payment cases are tested; no access granted merely from an unverified client success screen.
- [ ] **T16 — Test positioning and acquisition.** Start with a few relevant curators, share cards and real demonstrations. Done: campaign links distinguish starts, activation, return, purchase and renewal; spending decisions use actual cohorts rather than total registrations.

### Phase 5 — Expansion after reciprocal use is demonstrated

- [ ] **T17 — Add earned badges and themed challenges.** Define useful-contribution criteria, anti-gaming, opt-out and separation from paid cosmetics. Done: badge rules are explainable and cannot be farmed by repeated self-actions.
- [ ] **T18 — Evaluate external playlist imports.** Document each provider's access/terms/eligibility, implement only permitted paths with consent/disconnect/deletion. Done: real authorized import succeeds and users confirm what becomes a taste signal. Spotify remains blocked until the profiling use case is resolved.
- [ ] **T19 — Pilot opt-in music-friend discovery.** Define adult participation, exposure controls, relevance, mutual acceptance, blocking/reporting and moderation capacity. Done: no private contact disclosure before acceptance; no gender-based paid access; no dating claim.
- [ ] **T20 — Decide on dating separately.** Evaluate user demand, age assurance, moderation and safety operations before specifying or building it. Done: an explicit go/no-go decision, not implicit expansion of music-friend matching.
- [ ] **T21 — Reassess Telopotify integration.** Use only if an observed playback/library problem justifies it. Done: source/recording mapping, per-user access, account linking and playback boundaries are specified before implementation; no repository merger by default.

Dependencies: T00–T02 → T03–T05 → T06–T09 → T10–T12. T13 investigation can begin during Phase 0; T15 requires T13–T14 and a stable core. T17–T21 require separate evidence and decisions, not automatic inclusion in the first release.

## 10. Validation questions and release gates

- Do people finish a useful first experience without opening the Mini App unnecessarily?
- Do invitations produce a completed exchange, not just a bot start?
- Does the recipient save/react and voluntarily send something back?
- Do people return for another person's contribution without repeated reminders?
- Can moderation and operating costs support the invited cohort?
- Will returning users actually purchase and renew, and can the operator receive the rewards?

Set numeric targets after a pilot establishes denominators and baseline behavior. Do not invent retention, compatibility, profitability or growth figures in advance.

Test shared links, non-owner access, blocked pairs, deleted accounts, sparse profiles, wrong recording versions, unavailable audio, repeated callbacks, restarts, rate limits and provider outages. Visually check both languages at desktop/phone sizes, computed widths and document overflow. Build/test success is not visual proof.

## 11. Open decisions

- Public launch audience and initial music community.
- Which fields are public, followers-only, invitation-only or private.
- What comparison may use beyond the public signature songs and how consent is explained.
- Whether/how a user without sufficient ratings gets a useful first exchange.
- Exact playlist limits, ownership rules and Plus entitlements.
- How adult eligibility is established before stranger discovery or dating.
- Who handles reports and the realistic moderation workload.
- Whether external providers explicitly permit the intended imports/profiling.
- Whether Stars rewards are available to the actual operator in Iran.

## 12. Evidence and references

This is a planning artifact grounded in this conversation and scoped source inspection, not an implemented social release. The prior review is [integration/revenue research](../../lilcusin-telopotify-product-review-2026-10-17.md). Current source inspection includes `music_bot/models.py` and `music_bot/miniapp.py`.

Official sources checked during this conversation on 2026-10-17; provider terms/access can change:

- [Telegram digital payment rules](https://core.telegram.org/bots/payments-stars)
- [Telegram developer rewards and availability](https://telegram.org/tos/bot-developers)
- [Telegram affiliate programs](https://telegram.org/tour/affiliate-programs)
- [Spotify developer policy](https://developer.spotify.com/policy), especially profiling and AI restrictions
- [Spotify quota modes](https://developer.spotify.com/documentation/web-api/concepts/quota-modes)
- [Apple Music library playlists](https://developer.apple.com/documentation/applemusicapi/get-all-library-playlists)
- [Last.fm commercial API terms](https://www.last.fm/api/tos)

Maintain this document as the product plan. Update task evidence and statuses as work completes; keep proposed, implemented, tested, deployed and user-confirmed states distinct.
