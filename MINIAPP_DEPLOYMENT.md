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

## Listening and channels update

Song cards use the same Lil Bro prefilled song links as Telegram messages. Users
press Send in Lil Bro and return to rate via “I’ve heard this.” Opening a link does
not create a rating or mark listening as verified. Recent song lists are restored
within the same browser session for up to 25 minutes.

Channels lists only the signed-in user’s playlists, with learned/review counts,
single-use connection codes and disconnect options to keep or remove playlist
signals. Review remains in the bot’s existing private confirmation flow. Similar
song requests require an owned, unexpired grant for a displayed song.

The update passed 16 targeted API, connector and channel tests locally and in VPS
staging. Worker route and hibernating socket tests passed. Only the two Mini App
services were restarted; original polling bot, website processes and Nginx files
were checked unchanged. Recovery snapshot:
`/home/baharnaj/lilcusin-miniapp-backups/20261013T154453Z-ui-update`.

## Guided multilingual interface

The bot and Mini App offer a three-step first-visit guide and an always-available
help control. English, Persian, Arabic, Turkish, Russian, Spanish, French and German
use a shared catalogue. Telegram language is the initial default; a manual choice
persists in the additive `user_preferences` table, shared by both interfaces.
Preferences and guide flags are removed with the account via the user foreign key.

The UI uses the bot’s public owl profile photo, a monochrome/navy/burgundy palette,
and self-hosted Vazirmatn for Persian/Arabic. The font is from
https://github.com/rastikerdar/vazirmatn (v33.003); its SIL license is included in
`music_bot/web/Vazirmatn-OFL.txt`. The language curtain reproduces the cover/reveal
timing from the portfolio’s LanguageSwitch component. Reduced motion is respected.

After a rating saves, only that card slides out and is replaced with a recommendation
that excludes visible songs. Surviving cards receive a fresh owner-checked control;
a cancelled/forgotten control cannot renew permissions. No new candidate shows a
clear empty state, and failed replacement requests can retry without resaving ratings.

Validation: 41 staged bot/API/privacy/guide/replacement checks passed, with the final
owner-language channel notification test checked afterward. Worker route, font binary,
locale asset and private socket tests passed. Live signed preference reads were checked
only on VPS loopback; no real user profile was exported for external testing. Telegram
command menus were verified in all eight languages. Live browser preview checks covered
Persian text, guide navigation, language switching, and animated replacement. Narrow
mobile layouts were checked for horizontal overflow.

Recovery snapshot for the final deployment:
`/home/baharnaj/lilcusin-miniapp-backups/20261014T102501Z-guides-languages`.
The bot was restarted to load translated handlers and menus. Provider relay settings,
credentials, website process IDs and Nginx routes were preserved.

## Similar-song navigation and visual guide refresh

Similar songs now have a dedicated heading and breadcrumb history, with Telegram
back-button support. Restoring a page retains its song grants, search query and
scroll position. Stale requests cannot navigate away from the current page.
The guide has visual examples and revised Persian instructions in both interfaces.
Song links use SVG icons; contrast and spacing replace decorative card borders.

The language transition uses one non-modal top-layer overlay, stable scrollbar
space, preserved focus/scroll, and suppressed card entrance animations during the
switch. The curtain uses the app's navy palette with a burgundy accent.

Validation: all 42 staged bot checks passed, plus Worker/connector checks and
`node worker/test-ui-navigation.mjs`. Browser previews covered nested navigation,
restored search, rating replacement, guide steps, and English/Persian layouts at
390px and 320px. The 320px Persian layout had no horizontal overflow.

Recovery snapshot:
`/home/baharnaj/lilcusin-miniapp-backups/20261014T112154Z-guides-languages`.
Worker version: `d1ec2f87-f282-40b6-9294-cc54f819ae21`.
Only bot services and the existing `lilcusin-ui` Worker were updated; website
process IDs, Nginx files, bot credentials and provider settings were verified unchanged.
