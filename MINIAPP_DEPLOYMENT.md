# Lil Cusin Mini App deployment

Live interface: https://lilcusin-ui.ghazanfaribehrad.workers.dev/

Telegram bot: https://t.me/LIL_CUSINbot

The private connection uses outgoing HTTPS/WebSocket traffic on port 443.
Cloudflare's standard tunnel port 7844 timed out on this VPS, so the unsuccessful
`lilcusin-miniapp-tunnel` service was stopped and disabled. Its unused Cloudflare
tunnel and VPC service remain inactive for reference; the live Worker uses the
`BOT_BRIDGE` Durable Object binding instead.

## VPS layout

- Existing bot: `/home/baharnaj/lilcusin-music-bot`
- Existing service: `lilcusin-music-bot` (not restarted by deployment)
- New local API: `lilcusin-miniapp`, bound to `127.0.0.1:8091`
- New outgoing connector: `lilcusin-miniapp-connector`
- Bot-only backup: `/home/baharnaj/lilcusin-miniapp-backups/20261013T133959Z`
- Original Telegram menu: `/home/baharnaj/lilcusin-miniapp-stage/original-menu.json`
- Private connector token: `.cloudflared/token` under the bot directory, mode 0600

The existing bot startup file, relay configuration, `.env`, Nginx configuration,
and website services were preserved. New Python modules use the already-installed
packages; no global application dependencies were upgraded.

## Verification

- Five Mini App API tests passed in VPS staging.
- Two connector tests passed in VPS staging.
- Worker route, authentication gate, destination, socket ownership, response,
  and disconnect checks passed locally; the Worker deployment dry run passed.
- The live Worker returned HTTP 200 for an authenticated profile request against
  the existing bot database and HTTP 401 for an altered Telegram session.
- A fresh connector session passed the same checks after a restart. Socket
  ownership uses persistent connection identifiers that survive hibernation.
- A profile request after 30 seconds idle also returned HTTP 200; the subsequent
  altered-session check returned HTTP 401. Socket attachments are saved after
  accepting the connection so they persist correctly during hibernation.
- The connector assembles chunked JSON responses before returning them to the UI.
- The new API rejects unsigned requests and uses noindex response headers.
- Local mobile interaction checks passed at 320, 390, and 650 pixel widths.
- The broader local bot suite encountered two Windows temporary SQLite file
  cleanup errors. Configuration and Mini App tests passed after the compatibility fix.

## Operations

Inspect only the two Mini App services with:

```sh
systemctl status lilcusin-miniapp lilcusin-miniapp-connector
```

Restart them independently of the original polling bot if needed:

```sh
sudo systemctl restart lilcusin-miniapp lilcusin-miniapp-connector
```

To roll back the Mini App, restore the saved Telegram menu (type `commands`)
using `setChatMenuButton`, then stop and disable the two new services:

```sh
sudo systemctl disable --now lilcusin-miniapp-connector lilcusin-miniapp
```

Leave `lilcusin-music-bot`, Nginx, and website services running. No database restore
is needed to disable the UI; restoring an old database would discard later user
activity. Retain the bot backup for recovery and avoid printing credentials in logs.
