# Telegram bot flow release — 2026-10-17 (Asia/Tehran)

This release packages the approved chat phases 1–3 and subsequent user-reported
rating and metadata recovery fixes. It updates the isolated local bot only;
publishing source is not production deployment. Mini App UI/assets and existing
Worker edits are excluded. Pre-existing deployment notes and recommendation-test
changes remain separate.

## Delivered behavior

- Immediate input after `/start`, optional `/setup`, `/search`, `/rate`, `/version`.
- Metadata-based music-file rating without automatic fingerprinting or downloads;
  explicit `/recognize` remains available. Missing tags request corrected names.
- Primary Get song actions, compact rating/Details controls, native button styles,
  scoped Close controls, optional ratings after delivery and recovery from expired
  owner/message-bound controls.
- Persistent delivery status, request-specific cancellation, retry/version/wrong
  recording recovery, superseded foreground searches and preserved chat context.
- Cached-first identification/audio, bounded provider/artwork waits, two concurrent
  delivery jobs by default and safe shutdown/uncertain-send behavior.
- Independent metadata fallbacks, accurate partial-failure reporting and bounded
  title recovery for expanded performer credits, requiring explicit confirmation.

## Evidence and limits

See [phase results](bot-flow-results-2026-10-17.md),
[rating controls](rating-ui-2026-10-17.md),
[recording recovery](recording-recovery-2026-10-17.md) and
[catalogue recovery](search-fallback-2026-10-17.md).

The latest workflow/upgrade run passed 50 tests in 164.577 seconds; the preceding
broader workflow/recognition run passed 75 tests in 162.447 seconds. These overlap,
so their counts must not be added as unique coverage. Public metadata probes
returned the expected expanded-credit song via iTunes in 0.80 seconds. An offline
five-sample comparison with injected waits measured local identification medians
of 252.50→34.64 ms and cached delivery of 264.14→47.39 ms. These are controlled
measurements, not real-world latency guarantees. The benchmark baseline is pinned
to `80a6fc5` so it remains reproducible after this release is committed.

The isolated local bot was last verified polling build `chat-4f2305ffe76a` with
the expected test identity and Mini App disabled. Last.fm's local key remains
rejected; a replacement is still needed for that provider. Other catalogues are
available but do not guarantee universal coverage. Telegram controls exact button
dimensions and theme rendering; phone visual verification remains pending.
No new live song download or playback confirmation is claimed for this release.

Before publication, an additional 106-test delivery/chat/guidance/migration/source/
lifecycle/handler/recognition run completed in 315.105 seconds with 103 passing
and three obsolete legacy-handler assertions failing. The assertions expected
the removed guide and immediate parsed-tag response. They now verify welcome/help,
the progress message, workflow dispatch and presentation. All five handler tests
passed on the focused rerun; no application change was needed. All 27 staged
Python files compile, staged whitespace checks pass, and a targeted credential
pattern scan found no flags. This is not a claim that the full repository suite
was run. The five unrelated pre-existing edited files remain outside publication.
