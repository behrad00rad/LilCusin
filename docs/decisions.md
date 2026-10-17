# Recognition and discovery decisions

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
