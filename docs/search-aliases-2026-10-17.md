# Censored titles and common-title refinement — 2026-10-17 (Asia/Tehran)

The user reported missing Prayer by Kendrick Lamar and the Kanye West version of
Niggas in Paris after the chat-flow release was published as `bfe14b8`.

## Diagnosed causes and changes

- iTunes returns the joint Kanye West/JAY-Z recording as Ni**as in Paris. Literal
  title filtering rejected that spelling. Search-only masked-word matching now
  accepts bounded censorship aliases with at least two visible letters per masked
  word; unrelated words and wholly masked guesses are excluded. Canonical identity
  keys and automatic confirmation thresholds are unchanged. Users still select a
  title-search result explicitly, and provider spelling/artist credits are retained.
- Accepting the alias exposed a second failure: a ranked provider could fill all
  20 slots with versions and omit every exact-title iTunes result lacking comparable
  popularity. The best exact-title result from an otherwise omitted catalogue can
  now appear in the first five slots. Equal exact aliases preserve provider order
  rather than favoring shorter censored spellings such as bass-boosted variants.
  This is bounded diversity, not a claim to know an official recording's identity.
- Public title-only Prayer searches returned no Kendrick match in the examined
  iTunes, MusicBrainz and Deezer result windows. Artist-qualified MusicBrainz search
  did return it, so unreleased material is not categorically excluded. Common-title
  results now explain how to refine with Artist - Song title. Owner-bound replies
  can refine candidate lists directly; old choices become stale. No artist is
  guessed, no audio is downloaded and no new discovery provider is added.

## Live metadata evidence and limits

With Last.fm absent, the actual bounded multi-provider workflow returned the
joint-artist Paris recording at position 5 of 20 in 2.44 seconds. Artist-qualified
Kendrick Lamar / Prayer returned five candidates including the expected identity
in 1.30 seconds. These are individual public metadata probes, not general latency
or availability guarantees. Prayer alone still cannot guarantee the user's intended
artist. The attempted metadata-only YouTube broad-title probe produced unrelated
hints; no unverified hint or new video fallback was integrated.

The earlier source-publication request is tracked in
[the release record](chat-release-2026-10-17.md). Mini App UI/assets/Worker remain
unchanged; pre-existing edits remain separate. No production deployment or playback
verification is claimed. Final regression and local-runtime results follow below.

## Verification

- The first matching/workflow/popularity/handler/matrix run passed 56 tests in
  137.011 seconds. Final title-search/popularity regressions passed 23 tests in
  47.765 seconds after the last ordering adjustment; counts overlap.
- Fixtures cover the exact censored joint-artist result, more than twenty ranked
  alternatives, shorter masked variants, independent-source visibility, stable
  identity keys, artist-qualified Prayer refinement, foreign-user rejection and
  invalidation of old choices. Compilation and scoped whitespace checks pass.
- The isolated bot was idle before restart. The source-publication release and
  this follow-up preserve the same five unrelated edits. Native phone layout,
  actual user refinement and new audio playback remain unverified.
  Read-only checks confirmed expected test identity, polling, registered commands
  and disabled Mini App on build `chat-7131c21e4a52`.
