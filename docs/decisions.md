# Recognition and discovery decisions

## 2026-10-19 - Continuous private recommendation loop

User approved implementation of taste signals, replenishing recommendations and
low-friction feedback, requesting resumable checkpoints. Keep delivery in chat
and persist a bounded queue, not unsolicited notification delivery. Reuse the
existing private SavedSong library; never create a parallel collection or convert
requests into ratings/listening claims. Saves weigh 1.5, request evidence 0.15
up to 0.30 per song, explicit Like 1 and Love 3. Explicit ratings take precedence;
known is exclusion, not a negative preference. Reset keeps the saved library but
ignores pre-reset saves until deliberately saved again.

Queue leases, transactional serving exclusions, preference revisions and account
generations guard concurrent taps, feedback, reset/forget and restarts. Rotate
provider seeds across artists/refills while retaining existing provider budgets.
Friends' taste is a later, separate opt-in/visible-source lane with serving-time
relationship/block/visibility checks; private libraries are not social evidence.
See [contract and current verification checkpoint](recommendation-loop-2026-10-19.md).

## 2026-10-19 - Recommendation starvation

Scope: chat For You and shared recommendation candidate generation only.
Count only eligible, unseen candidates before deciding whether online refill is
needed. When similarity/local discovery is exhausted, use top tracks from an
existing positive seed artist for For You as well as selected-song discovery.
Reserve one of the existing three provider calls for this recovery; keep per-call
timeouts, canonical identity checks, ratings and recent-history exclusions.
Artist fallback is narrower than cross-artist discovery, but gives an honest
artist-based result rather than inventing similarity or treating searches as Likes.
No unsolicited notifications or changes to stored user preferences. User then
approved deployment, commit and push. Deploy only the tested candidate module,
preserving existing runtime settings and unrelated work. The first deployment
rolled back on preflight failure; retry verified the failure also occurs on the
old module (missing `packaging` checker), checked runtime imports independently
and retained the unchanged baseline limitation rather than upgrading dependencies.

Navigation: [current state](STATE.md), [priorities](TASKS.md),
[architecture](ARCHITECTURE.md), [product vision](social-product-vision.md).
This existing lowercase file is the canonical decision history; do not create
a second `DECISIONS.md` on case-sensitive systems.

## 2026-10-18 — Lightweight session handoff

Use concise AGENTS instructions plus separate state, priority and architecture
documents. Keep product criteria in the existing vision and detailed verification
in dated release/evidence records. This avoids repeated broad analysis and divergent
copies. Refresh only material changes; label historical release evidence separately
from checks performed in the current session. No application refactor is part of
this setup. Commits, pushes, deployments and production changes require user approval.

## 2026-10-16 — ShazamIO recognition

The user selected ShazamIO after discussing paid recognition APIs. Use published
ShazamIO 0.8.1 with a shared, bounded HTTP transport and no paid fallback. Extract
12-second mono WAV samples, trying offsets 0, 30 and 60 only until a match. Public
media downloads, temporary storage, queue size, per-user frequency and request
lifetimes are bounded. Use the upstream-supported cdn discovery hostname after amp
returned HTTP 403 in this environment. Send fingerprints, never token-bearing
Telegram media URLs, to Shazam. The unofficial service can change or fail.

## Recognize, then deliver

The user requested playable audio after a match. Fresh and cached matches queue the
existing Get song worker. Keep source permissions, limits, cancellation, recording
choices and cached Telegram file reuse. Do not infer ratings or taste signals.
Persist structured identity rather than parsing artist/title from display text.

## Artwork independent of Last.fm

The user reported Last.fm failures through the current VPN and requested Shazam
artwork. Retain Shazam cover/album fields from recognition. For ordinary Get song,
recognize a short sample of downloaded audio if artwork is absent or its preparation
fails. Require artist, title and version agreement. Reuse existing bounded image
conversion, embedded audio tags, Telegram thumbnails and cache upgrade checks.
Allow only the specific Apple image CDN hosts used by Shazam. Failed artwork is
optional and must not block audio; old messages cannot be changed retroactively.

## Other recording versions

The user requested Find other versions after a live recording was recognized.
Add owner/message-bound controls to recognition results, song cards, recording
choices and audio. Explicit alternate searches strip edition suffixes, ignore the
seed duration and offer up to three edition categories while checking artist/title
and excluding covers/karaoke. Selected editions get separate canonical metadata.
Call unlabelled sources Original / unlabelled rather than claiming verified studio
status. Preserve the original recognition and existing rating history.

## Search intent and public social links

Retain artist matches instead of filtering every result as a song title. Allow
two-word lyric/artist hints to reach discovery, with independent catalogue checks
and explicit user choice. Protect popular exact song titles in ambiguous artist
queries. Add anonymous iTunes metadata fallback alongside existing catalogues;
do not hard-code examples or treat discovery hints as verified lyrics.

Accept only explicit HTTPS public post URL shapes for YouTube, TikTok, Instagram,
Pinterest, X, SoundCloud and Vimeo. Use restricted yt-dlp extractors, no inherited
config/cookies/login, bounded media and approved-host short-link redirects. Install
the supported curl-cffi extra required by the tested TikTok post. Generic URLs,
private/login-only posts and image-only pins are outside this implementation.
Source: https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md


## 2026-10-17 — Local UX audit

Completed a code-based review of chat navigation, Mini App parity, search and delivery critical paths. Findings and proposed priorities: [UX audit](ux-audit-2026-10-17.md). No application changes, live Telegram checks, latency measurements, or test runs in this audit; implementation and deployment remain unverified. Existing user edits were preserved. Recommendations have not been accepted as implementation decisions.

## 2026-10-17 — Approved local chat phases 1–3

The user approved runtime identity, chat-flow improvements, and performance work, while explicitly deferring the Mini App. Implemented details, rationale, measured offline comparisons, and verification status are maintained in [local bot flow results](bot-flow-results-2026-10-17.md). The current changes remain uncommitted; production and pre-existing Worker edits are outside this work.

## 2026-10-17 — Reported recording failures

Investigated the user's reported source-search and recognition failures and implemented guarded candidate recovery, metadata-aware audio routing, and duration-aware fingerprint sampling. Findings, authorization limits and validation status: [recording recovery](recording-recovery-2026-10-17.md). Candidate recovery is distinct from verified audio delivery; the Mini App and production remain outside this change.

## 2026-10-17 — Rating intent and native bot controls

The user explicitly requested rating uploads without automatic recognition, compact Details controls, colors and Close on search results. Implemented changes and verification status: [rating and UI follow-up](rating-ui-2026-10-17.md). This supersedes automatic fingerprinting of untagged song uploads; recognition is explicit for audio files. Production and Mini App are outside this change.
# 2026-10-17 — Recover rating lookups independently of Last.fm

The local key is rejected, but MusicBrainz and iTunes public sample probes work.
Artist/title fallback searches now run concurrently; healthy empty responses no
longer count as a total outage. Unmatched audio tags ask for correction without
fingerprinting. Existing fast-search budgets remain. See
[verification and limits](search-fallback-2026-10-17.md).

Follow-up: the user's Starting Over file has a correct title but appended musician
credits in its performer tag. Add a bounded title recovery round for unmatched
uploads, retaining only exact titles and a matching artist prefix. Require an
explicit choice rather than silently stripping credits or confirming an identity.
# 2026-10-17 — Censored titles and common-title refinement

Accept bounded censorship aliases for search without merging canonical identities.
Reserve an early exact-title result for otherwise omitted catalogues when another
provider fills the visible limit. Allow owner-bound replies to refine candidate
lists with an artist. Do not infer the artist of a common title or admit unverified
video hints. See [diagnosis and evidence](search-aliases-2026-10-17.md).
# 2026-10-17 — Discover beyond catalogue popularity

Run bounded public-video metadata discovery alongside short Telegram title queries.
Validate hints independently, tolerate small search-only spelling errors, rank
validated discoveries by observed upload views and label that provenance. Keep
identity/confirmation rules, no-download discovery, admission limits, caching and
cancellation. This supersedes treating artist refinement alone as sufficient for
the reported Prayer case. See [implementation and probes](discovery-popularity-2026-10-17.md).

## 2026-10-17 — More like this sparse candidate recovery

Reported: selecting DNA by Kendrick Lamar returned no new picks. Inspection
found a five-track provider window and no online artist fallback. Increased
Last.fm similarity requests and per-seed bounds to 50 with autocorrection.
When a selected-track pool is empty after exclusions, try one cached/bounded
artist top-tracks request; retain same-artist candidates with existing identity,
rating and recent-history exclusions. Do not invent similarity scores or ratings.
Tradeoff: same-artist discovery is less specific than track similarity; exhausted
history and provider outages may still return no candidates. Live cause unverified.

## 2026-10-17 — Social music vision documented (proposed execution)

The user requested a file capturing music identity, comments, shared tastes,
playlists, badges, playlist imports and meeting people inside Telegram, followed
by an actionable task list. [The vision and roadmap](social-product-vision.md)
separate that full direction from a proposed first release: profiles, invited
comparison and reciprocal song exchange. Reuse the bot/Mini App and Telegram
conversations; defer a separate player, open matching and dating. This is a
documented proposal, not approval of every scope choice, price or implementation.
Provider profiling permissions and the operator's payout eligibility remain open.


## Deployment reliability audit - 2026-10-18

Keep the optional audio dependency file, but install it alongside base requirements
for full bot deployments. Add Python 3.13 audioop compatibility and constrain
Pydantic to the user-reported working 2.13.5 line within aiogram's declared range.
Retain unrelated pins. Adopt a 12-second best-effort artwork budget, with fixed
privacy-safe diagnostics and existing atomic tagging/cancellation limits preserved.
Use an offline preflight rather than starting a second poller. Production changes
must be reconciled privately before release; no production connection was made.
Clean Debian 13/Python 3.13 installation remains an unverified release gate because
no 3.13 runtime was available and package downloads timed out locally.


## 2026-10-18 — Start the social-release baseline

The user authorized the baseline-first implementation sequence and supplied VPS
access. Preserve the running release and its existing Get Song edit; reconcile
source differences before deployment. Begin comparisons with deliberately selected
signature songs, keeping ratings private. The first proposed social loop remains
taste card, invitation, consented comparison and reciprocal exchange; this entry
does not mark those features implemented. See [baseline](social-release-baseline-2026-10-18.md).


## 2026-10-18 — Implement the first taste-card slice

After the user's go-ahead, implement private-by-default identity before comparison
and exchange. Keep ratings separate, share only selected fields, require explicit
confirmation, expire links after 30 days and revoke on hide/replace. Use existing
canonical songs and owner-bound grants; current obsession is selected from the
five signature songs. Support bot commands as well as the Mini App. These are
implemented local defaults; no pilot/deployment or later social feature is implied.
See [contract and limits](taste-card-release-2026-10-18.md).


## 2026-10-18 — Deployed search, recognition and chat UX repairs

Resolve artist aliases and rank artist catalogues; prefer embedded social-video audio over separately credited soundtrack audio. Preserve reusable search results and clear only owner-scoped tracked transient UI. Correct the two verified reversed identities and invalidate derived mappings. Keep the deployed patch separate from concurrent taste-card work. See [rationale, evidence and limitations](search-recognition-ux-2026-10-18.md).


## 2026-10-18 — Mini App Get song

Replace the Mini App Lil Bro link with an owner-bound link into this bot’s existing Get Song workflow. Reuse delivery, cache, version-choice and cancellation behavior; keep source enablement unchanged.


## 2026-10-18 — Taste-card/Get Song deployment and UI brief

Reviewed the user’s bot-first social UI outline. Keep selected-song comparison consent and swaps in the first interactive loop; defer rooms, badges, follower/streak/save totals and expanded visibility until supported. Restored the inactive Mini App services against the current bot checkout; preserve existing secrets/source and use the existing deployment Worker. See [UI brief](social-ui-brief-2026-10-18.md) and [release](deployment-2026-10-18.md).

## 2026-10-18 — Search responsiveness

Move bounded transient-message cleanup off the response path; cache complete public
metadata results for five minutes and share in-flight work. Publish the first useful
branch and append late choices without reordering active buttons. This removes
repeated provider waits while preserving selection identity. Cold provider latency
remains. [Decision, tradeoffs and evidence](search-performance-2026-10-18.md).

## 2026-10-18 — Bot onboarding, portrait and selected-song consent
Use bot-first entry paths and deterministic image rendering in the existing identity. Invitations bind both selected-song snapshots, card revisions and recipient identity; public links never imply agreement. No automatic friend notification, computed comparison or swap in this slice. [Contract and tradeoffs](onboarding-portrait-consent-2026-10-18.md).

## 2026-10-19 — Match explicitly selected live medleys safely

Compare medley components independent of order/accents, retain artist and location
checks, and permit the cover label only for verified live medleys. Require user
selection rather than automatic delivery. [Evidence and tradeoffs](navan-medley-fix-2026-10-19.md).


## 2026-10-19 — Explainable comparisons and reciprocal picks

Compare only mutually consented signature-song snapshots; absence means not selected. Use a sender-only draft and explicit send, independent saves and explicit Love ratings. Reuse existing audio delivery. Alerts are opt-in, capped, and claimed durably before network work; prefer avoiding duplicate sends over retrying an ambiguous result. Block/revocation invalidates pending interactions. Reports disclose their note evidence and require an explicitly configured operator. [Contract and tradeoffs](social-loop-release-2026-10-19.md).

### Navan follow-up: match display metadata consistently

Canonical keys remove punctuation needed for live/location parsing. Use display
metadata for both source query and matching, and test the actual stored identity
plus mismatched clip duration. Preserve explicit selection and artist/version guards.
[Evidence](navan-medley-fix-2026-10-19.md).

Navan follow-up deployment confirmed: user-approved one-file correction deployed,
source hash verified, restart succeeded; all 20 isolated regressions passed against
the deployed module. The identical candidate retrieved/validated actual audio.
Telegram receipt/playback remains unverified; Mini App unchanged.
[Deployment evidence](navan-medley-fix-2026-10-19.md).


## 2026-10-19 — Verified release

Deploy the frozen, tested snapshot using explicit Git blobs and runtime hashes, preserving concurrent recording-search edits. Keep private configuration and persistent data; use a consistent backup and rollback guard. Longer cold-start readiness succeeded after a safe rollback. See [release evidence](deployment-2026-10-19.md).

## 2026-10-23 — Guess game data/consent

Use additive private tables and an ordered-pair partial unique index; keep allow_guess independent of Love sharing. Opt-out removes games about the user; unfriend/block purges both directions inside the existing transaction. This prioritizes revocable visibility over retaining scores. Step 1 only, default-off, local tests; gameplay and notification policy pending. [Evidence/rollback](guess-game.md).
