# 2026-10-18 — Deployed search, recognition and chat UX repairs

Status: deployed and independently verified; code changes remain uncommitted.
Release evidence identity: `40536cae008786406bcf`.

Artist lookup now resolves verified MusicBrainz aliases before browsing an artist's
recordings and popular catalogue tracks. Live provider probes returned Faramarz
Aslani's songs for فرامرز اصلانی and familiar Pink Floyd songs for pink floyd.
The sampled requests completed in 2.32 and 4.42 seconds; these are samples, not an SLA.

Two inspected reversed Pink Floyd/Wish You Were Here records were corrected,
including the 2021 remaster. Incorrect source, delivery, selection and identity
mappings were invalidated without deleting ratings or delivered Telegram audio.
Structured-catalogue/corrected reverse identities now block low-trust recreations.

The supplied TikTok exposed a separate soundtrack which produced wrong fingerprint
credits. Preferring the video's embedded audio made the full recognition pipeline
identify Mac DeMarco — Another One. The test used a fake chat sink and sent no
Telegram messages. Audio-only fallback rejects conflicting fingerprints; uploaded
video retains its existing first-match behavior. Links inside share text and
additional YouTube page shapes are accepted; link sampling uses local duration.

Search results survive selection and permit choosing another result. New searches
remove owner-scoped tracked previous search/card/status messages. Successful audio
has no inline keyboard and its delivery status is removed. New delivery requests
retire terminal statuses. Search controls remain available on similar-song pages.

Validation: 195 isolated Python 3.13 server regressions passed; navigation and
recovery Node checks passed; scoped whitespace checks passed. Fourteen deployed
source hashes matched the tested release; the bot reached polling readiness and
remained active. The two corrected public identities, cleared source cache and
foreign-key integrity were independently checked. Configuration was unchanged.

A six-second startup gate caused one rollback. Original code and data restoration
were verified; a longer check bound to the new process then passed. Private code
and database backups remain on the server. Existing production artwork logging
was preserved. Concurrent local taste-card work was excluded from the scoped
release and left untouched in the local checkout.

Limitations: Telegram deletion limits apply; unknown/untracked old chat messages
cannot be swept. The standalone Mini App is not configured on this server, so its
updated source was not verified as a live web deployment. No visual Telegram UI
inspection, real delivery to a user, Git commit or push was performed in this pass.
