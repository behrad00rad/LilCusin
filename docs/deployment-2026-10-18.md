# Mini App deployment — 2026-10-18 (Asia/Tehran)

Status: deployed and infrastructure/asset verified. Local changes remain
uncommitted; deployment does not imply a Git push or a live audio receipt.

## Released

The user requested publication of the current taste-card and Get Song work.
The scoped VPS release preserves existing search/recognition/audio-source fixes,
including production-only Get Song changes. It adds the card model/APIs, bot card
and delivery-link handlers, matching Mini App assets and connector allowlists.
The separate API entry point now resolves the actual bot username for links.
Connector token storage is unchanged; the service points to its existing file.

The bot was active before this release; the separate Mini App/connector units were
inactive and referenced an older checkout. The two units now use the current
checkout, with a loopback-only API on 8091. No second polling process was started.
All database writers were stopped before a consistent SQLite backup and the
file switch. Additive card tables were created through the normal initialization.
A protected backup of previous files/database and prior unit overrides is retained
on the VPS. No database restore was performed. Credentials, non-release source
files and unrelated service PIDs were verified unchanged.

## Public Worker

URL: https://lilcusin-ui.ghazanfaribehrad.workers.dev

Previous active version: 12c88fac-04fd-49c3-9d50-dc20a89b328f.
Released version: 2ff6bdc7-7cda-4a91-8bac-07dd901a3cef.

The browser editor failed to finish loading. Official Wrangler authorization
was restored with the user's assistance; generic Worker scope was insufficient,
and the script-specific scope succeeded. One callback expired and was retried
through the normal authorization flow. The final deploy used --keep-vars and
retained BOT_BRIDGE and its existing connector secret.

## Evidence

- 32 isolated staging tests passed on VPS Python 3.13.5 in 12.989 seconds:
  Mini App delivery, taste cards, existing Mini App, connector and bot handlers.
  Staged compilation passed; existing dependency environment was reused, with
  no new package installation or clean-install claim.
- Worker dry run and three final focused Worker/UI scripts passed before release.
- Published HTML, app.js and locales.json each returned 200 and matched the
  normalized local release content by SHA-256.
- Public /api/profile and /api/taste-card returned 401 for intentionally invalid
  Telegram authentication, demonstrating the public bridge reaches the API.
- Bot/API/connector services were active/running, each with NRestarts=0 in the
  final check. Deployed-file hashes and protected-file hashes matched. A read-only
  schema check confirmed both additive card tables; no user rows were inspected.
- The deployed browser preview showed Persian Get song controls and no horizontal
  overflow at 390px. This is preview data, not a genuine signed Telegram session.
  [Live-site preview screenshot](screenshots/miniapp-deployed-2026-10-18.png).

## Limits and UI direction

Actual Telegram audio receipt, source availability and playback were not retested.
The existing download enablement/quotas and source configuration were preserved.
No people, comparisons, swaps, rooms, badges, reputation or payments are claimed
implemented by this release.

The user's subsequent bot/Mini App outline was reviewed and saved in
[social-ui-brief-2026-10-18.md](social-ui-brief-2026-10-18.md). It preserves bot-first
participation and selected-data consent, while deferring unavailable metrics,
visibility modes and community screens. Next work is portrait share cards,
recipient-bound comparison consent and reciprocal exchanges with controls.
