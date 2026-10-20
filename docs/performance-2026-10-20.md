# A2/A3 Mini App performance - 2026-10-20 (Asia/Tehran)

Scope: artwork delivery and startup only. Terminal 1 A1 commit `02259c0` and its
verified deployment record `64a4a7e` were integrated by fast-forward to `937313b`.
The checkout initially had no changes. Later concurrent delivery-module/test and
Vigen documentation edits are excluded from this session's implementation.

## Baseline and reproducibility

Measured current VPS/public HTTPS responses, not historical documentation.
The direct VPS route is active; the old Cloudflare Worker is not the serving path.
Public GETs with `Accept-Encoding: gzip` compressed only HTML before this release.
JS, CSS and the eight-language catalogue were uncompressed and all assets plus
proxied covers had `Cache-Control: no-store`. The Worker already requested edge
artwork caching, but direct hosting had no disk/memory transformation cache.

| Public asset body bytes | Before | Candidate |
| --- | ---: | ---: |
| index.html | 1,671 (Nginx gzip) | 1,504 (gzip level 6) |
| app.js | 79,833 | 23,669 |
| social.js | 15,400 | 4,004 |
| style.css | 36,869 | 8,921 |
| locales.json | 300,464 | 77,944 |
| bot-logo.jpg | 30,957 | 30,957 |
| English initial font | 111,152 | 0 (load when needed) |
| English static total | 576,346 | 146,999 |
| Persian static total | 576,346 | 258,151 |

Measured body budgets exclude artwork, SDK, API bodies, favicon, headers and TLS.
English reduction: 74.5%; Persian: 55.2%. Uncompressed JS grows by 786 bytes to
80,619; the saving comes from transfer encoding, not removing functionality.
Run `python tools/measure_web.py` for source/gzip budgets; add `--origin` with the
current public origin to measure real wire bodies and conditional responses.

For a fixed public Radiohead cover (hash
`2ed343318c844d19cd897ec67fad11c4`), measured from the VPS:

| Size / format | Body bytes |
| --- | ---: |
| 300px PNG (baseline main and list) | 184,467 |
| 300px WebP | 25,442 |
| 174px PNG | 66,885 |
| 174px WebP list thumbnail | 10,056 |
| 600px PNG | 668,580 |
| 600px WebP large high-density card | 83,752 |

For that representative first cover plus static assets, body totals are 760,813
bytes before, 172,441 after for English at 1x, and 283,593 for Persian at 1x.
Higher-density English using the 600px variant totals 230,751 bytes. These are
sums of the measured fixture bodies, excluding SDK/API/header/TLS overhead.

These are one public cover, not catalogue-wide averages. Reproduce with HTTPS GET
`https://lastfm.freetls.fastly.net/i/u/<size>/<hash>.<format>` using the sizes above.
The upstream served the expected MIME types and long cache lifetimes.

## Implemented release

- Existing Last.fm variants provide 174px list/signature/inbox artwork and 300px
  prominent artwork at 1x or Save-Data, 600px at higher density (frames reach
  roughly 230px high). Both exchange detail and discovery use the larger context.
  Only known hash paths are rewritten to WebP; errors retain the original-image
  fallback and then the music placeholder. No paid service, resizing, storage,
  database change or artwork disk cache.
- Native lazy loading and async decoding remain. One visible discovery image loads;
  hidden deck images remain deferred. The owl is one shared request despite three
  elements. Existing behavior already did this; no image-count improvement claimed.
  No speculative next-image preload on expensive connections.
- Missing-cover API lookup now excludes hidden deck cards and resumes on selection.
  A visible cover may still use the existing four bounded lookup attempts. Before,
  a hidden missing cover could trigger those calls on first open.
- Known hash-based artwork variants get one-year immutable browser caching; other
  allowed covers get one day. Failures remain uncached. The maintained Python proxy
  is reconciled from the runtime module, preserving its host/redirect/header guards,
  eight-second timeout and streamed 2 MB limit.
- Public static responses use gzip, representation-specific SHA-256 ETags and
  revalidation (`public, no-cache`), with `Vary: Accept-Encoding`. Only 16 static
  representations are retained in memory. Stable URLs cannot pin an old release.
  Authenticated API responses retain `no-store` even on errors.
- Preload the existing catalogue so it overlaps JS/CSS; keep all eight languages
  and reliable synchronous switching. Remove unconditional font preload, retain
  both font assets and licenses. The TTF is not requested by this UI, but is kept
  because server-side portrait generation can use it. No localization split.

## Verification

13 Node checks pass: performance, artwork, Worker, bridge, A1, motion, gestures,
navigation, recovery, channels, delivery, social, taste card. Both frontend syntax
checks and Worker build pass. Four new offline HTTP regressions and ten existing
Mini App checks pass locally (14 total). The first sandboxed test run failed on
Windows temporary-file access; the same isolated run passed outside that sandbox.
Recovery's older DOM fixture lacked dataset/SVG/span support; corrected only its
fixture/assertion, retaining timeout/offline/retry checks.

An isolated local direct-host harness used the frozen baseline assets and actual
candidate compression handler, plus passive DOM performance instrumentation.
At 300 ms added delay per static response, first song heading: 1,065.5 ms before,
725.5 ms after. Zero-delay samples: 310 ms before, 147.5 ms after. Single samples,
not distributions or physical mobile measurements. The locale request moved from
705 ms to 323 ms in the delayed run and transferred once. Static/SDK startup
requests fall from 8 to 7 including the document, excluding artwork/favicon and
instrumentation. Signed first-open API preferences/recommendations are necessary
and remain sequential; no live signed timing claim.

Local EN/FA switching, 320/390px overflow, deck/search navigation and preview
song-action checks passed. List artwork loaded at natural width 174px; the third
deck song demonstrated the missing-artwork fallback. Screenshot capture timed out; DOM geometry/accessibility evidence must
not be described as visual screenshot approval. The sandboxed local proxy cannot
reach upstream artwork reliably; placeholders/error fallback remain usable. Public
artwork size probes succeeded separately from the VPS.

## Verified release

Performance commit `dafc6546f0df3689937263e1953f9190e39dbf17` is pushed to
`codex/safe-publish` and deployed as frozen artifact `dbd57299600da7b3`.
Direct local GitHub connections timed out. A temporary localhost CONNECT route,
restricted to GitHub HTTPS over the approved existing SSH connection, enabled a
non-force push; remote commit equality was verified and the tunnel closed. No
permanent Git/network configuration change.

Deployment rechecked every target and protected Python/UI/configuration hash,
used an exclusive release lock, and retained six-file rollback metadata/copies
under the protected release receipt. No database/schema/configuration changes;
no user data was copied into staging or touched for this asset/cache release.
Only the Mini App API restarted. API active, all six deployed hashes match;
bot/connector/Nginx states and PIDs and unrelated sources/configuration unchanged.
The existing inactive connector remains inactive. No full-checkout synchronization.
The old Cloudflare Worker was built/tested for compatibility and was not published.

All seven public HTTPS assets returned 200 with exact decoded source hashes and
304 for matching validators. Public text transfers match the table above exactly;
PNG/JPEG/font binaries are not needlessly recompressed. Public artwork returned
174px WebP 10,056 bytes, 300px 25,442 bytes and 600px 83,752 bytes, each with one-year
immutable caching. Unsigned public preferences returned 401 with no-store.

The deployed public browser preview loaded 300px WebP artwork while the second
hidden deck image remained unloaded. English at actual 320px and Persian at 390px
showed no horizontal overflow; Persian switching completed with controls enabled
and the curtain hidden. This supplements local EN/FA checks at both widths.
Browser screenshot capture timed out. No signed Telegram session, physical touch,
real audio delivery or measured mobile-network performance is claimed.

Remaining limits: initial data still requires authenticated preferences then
recommendations; all locale data still transfers once per changed release;
static revalidation incurs round trips; first-seen artwork still traverses the VPS
and provider; original-format fallback can cost more. Artwork sizes are bounded
variants, not a CDN-wide average. No unbounded disk cache was introduced. Stop at
A2/A3; no new social behavior or forbidden delivery modules changed in this release.
