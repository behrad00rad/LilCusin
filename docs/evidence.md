# Recognition and search evidence

## Verification during this session

- Initial inspection recorded pre-existing Worker/deployment changes and a
  recommendation-test cleanup; those are outside this release.
- The user confirmed actual test-bot recognition responds correctly. Telegram
  verified the configured local identity as @testlilcuhbot; the user confirmed it
  after initially naming a different username.
- A public ShazamIO fixture was recognized as Gloria Gaynor - I Will Survive.
  Real Telegram audio/voice/video transport tests passed using synthetic inbound
  updates and actual downloads, recognition requests and result messages.
- Live recognition-to-full-song delivery reached done after a tester selected an
  offered recording. A later source-search issue was traced to using normalized
  database titles; searches now preserve catalogue punctuation. An intermittent
  download cause remained uncertain, but final delivery succeeded. Added bounded
  retries and fixed failure categories rather than exposing provider errors.
- Live Shazam artwork delivery returned a Telegram audio thumbnail and recorded
  successful cover embedding. Plain Get song also obtained a Shazam cover with
  Last.fm excluded from the live test.
- A live other-versions search offered original/unlabelled, live and remaster
  categories. It was cancelled without another live alternate-version download.
  Separate identity, owner/message checks and selection are tested locally.
- Live deftones search returned Deftones tracks. Someday kanye returned Kanye West
  - Ghost Town through discovery and independent catalogue matching.
- The user supplied a TikTok post. Initial extraction failed; installing the
  supported curl-cffi transport enabled download and recognition as The Smiths -
  Back to the Old House. No raw post URL is published here.

## Automated checks

Recorded regression runs passed 87 tests for delivery/search/recognition/chat
controls and 86 tests for search/providers/recognition/Mini App. Focused checks
passed after final changes, including 32 workflow tests, artwork replacement,
version selection and control authorization. Counts overlap; do not sum them.
Compilation, dependency compatibility and whitespace checks passed. A final
release test result is recorded separately when available.

## Limits and release scope

Actual posts from Instagram/Pinterest/X/SoundCloud/Vimeo were not live-tested.
Private, blocked or image-only posts can fail; source labels and Shazam matching
are not guarantees of recording identity. User confirmation of the latest button
UX is pending. Earlier Telegram messages are unchanged. Only the isolated local
test bot was restarted; this session did not deploy to the production VPS.
Local QA evidence stays ignored and contains no published credentials or chat IDs.

## 2026-10-17 — Release verification

Recognition and social/search regression: 28 tests passed. Python compilation,
dependency compatibility and staged whitespace checks passed. Broader discovery
and delivery runs were stopped after extended waits; no complete-suite pass is
claimed for this release. Earlier live checks above were not repeated.

The release includes the recognition/discovery changes and these study records.
Pre-existing Worker, deployment-note and recommendation-test edits remain outside
the commit. Production was not deployed. Commit and push identity are recorded
in the local Work Journal after remote verification.
