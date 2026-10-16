# From unknown recordings to playable songs

LilCusin previously identified songs from title/artist metadata. The user requested
recognition from recordings and shared links, then asked for playable audio rather
than only a song title and Shazam link.

The implementation uses ShazamIO for bounded fingerprint recognition and connects
matches to the existing Get song worker. It preserves source-selection controls,
request limits, cancellation and Telegram file caching. Shazam covers now feed the
normal embedded artwork/thumbnail pipeline, including for ordinary Get song
requests when Last.fm artwork is missing or unavailable.

A live recognition of a live edition exposed the need to choose a different
recording. Find other versions now browses alternate editions while keeping the
original recognition and storing each selected edition separately. Covers/karaoke
are excluded and source labels remain best-effort.

Search feedback exposed two gaps: artist matches were discarded by title filtering,
and two-word lyric hints never reached discovery. Both paths were corrected and
independent catalogue fallback added. The user's Deftones and short Kanye hint
examples returned useful results live, without hard-coded song mappings.

Public social-post adapters share the recognition pipeline. The supplied TikTok
post was verified after adding its missing supported downloader transport. Other
platform adapters have local bounds/security checks but still need actual-post
verification. Earlier audio messages are unchanged and external sources can fail.

The isolated local test bot has been updated and live transport/artwork checks
passed. Production deployment is outside this session. See decisions.md and
evidence.md for the architecture, evidence and remaining limits.

Release preparation on 2026-10-17 verified 28 recognition/social-search tests,
compilation and dependency compatibility. Broader test runs did not complete;
production and remaining live-platform limitations above still apply.
