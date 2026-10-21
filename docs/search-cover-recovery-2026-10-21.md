# Search and artwork recovery - 2026-10-21 (Asia/Tehran)

User reported failing Get song requests, covers remaining in loading states and
poor performance, then authorized repairs and reassuring progress updates.
Current runtime was inspected afresh: it has a newer recording resolver/frontend
than this checkout. Existing local delivery fixes are preserved, not overwritten.

## Evidence and fixes

Five recent logged deliveries failed at search with no_matching_candidate. The
running resolver had a three-second fallback budget and swallowed provider/detail
timeouts. An offline reproduction proved that a timed-out fallback became an empty
candidate list. Candidate gives the bounded fallback 10 seconds and detail lookup
6 seconds within a 40-second overall limit, and classifies incomplete lookups as
source unavailable, preserving genuine clean-empty results and identity safeguards.

Get song now has cancellable status updates at approximately 6 and 16 seconds:
taking longer than usual / still checking sources. English and Persian messages
replace the existing status message and retain Cancel. Notifications stop when
search completes, fails or is cancelled; notification failure cannot fail delivery.
The existing bounded retry still applies to temporary source failures.

Covers previously could wait eight seconds at the proxy then retry the original
provider directly without an application deadline. The runtime now uses 400px
prominent variants; one sample took 4.88 seconds versus 0.20 seconds for 300px.
This is a sample, not proof every 400px cover is slow. Static probes took 0.14s
and server load was low, so CPU/static transfer did not explain the reported waits.

Candidate keeps fallbacks on the allowlisted proxy (five-second upstream limit),
adds a 10-second browser deadline starting at visibility, and retains a lightweight
placeholder until image load succeeds. Hidden lazy images do not expire before
selection. Failed or stale images cannot overwrite newer artwork. Existing 400px
variants join immutable caching; host/size/redirect guards remain unchanged.

## Verification and release

83 scoped Python resolver/progress/delivery/artwork tests passed in isolated VPS
staging. All Python sources in final artifact `ab739eac183fff74` match that
tested snapshot. The final Node cover lifecycle regression passed locally,
including visibility-after-load and stale-timeout races.
[Six-file runtime-based patch](patches/search-cover-recovery-2026-10-21.patch)
is reviewable/replayable without replacing pre-existing dirty delivery files.
The helper and its test are maintained directly in this checkout.

No user records or credentials appear in evidence. No dependency, schema, consent
or recommendation changes. A second poller is never started. Real signed Telegram
receipt and physical mobile network behavior remain separate verification gates.

## Deployment evidence

Six-file artifact `ab739eac183fff74` is deployed. Exclusive locking and source
hashes preserved newer runtime features and unrelated work. No pending/sending
deliveries were interrupted. Both writers were stopped for a consistent private
SQLite backup; source rollback copies were retained. No schema/config changes.
The first application rolled back because the check did not recognize the runtime's
actual "starting long polling" marker. Restored hashes and service health were
verified before the identical patch was retried with the corrected health check.
Bot polling and API health now pass; all six target hashes match, unrelated source
hashes and Nginx/connector states remain unchanged. No second poller was launched.

Public HTTPS app hash, gzip (27,475 bytes), conditional 304 and 400px WebP immutable
caching passed. Deployed offline timeout classification and EN/FA progress-copy
checks passed. Node is present on the service PATH; it is absent only from the
noninteractive SSH shell PATH. The shell limitation was not treated as a bot defect.
Physical mobile and signed Telegram receipt/progress/cancellation remain unverified.
[Resolver test delta](patches/search-cover-recovery-tests-2026-10-21.patch) preserves
the regression expectations against the newer runtime's test baseline.

A real metadata-only lookup for Radiohead / Everything In Its Right Place returned
one accepted recording in 1.32 seconds after deployment. No audio was downloaded
or sent by the probe; this verifies source discovery, not Telegram playback.
