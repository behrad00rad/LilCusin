# LilCusin 🎵

A Telegram bot that learns what music you like. Send it a song, rate the match,
and ask for recommendations.

> Try sending `Radiohead - Creep` in a private chat. You can also send or forward
> Telegram audio that has an artist and title.

## What happens when you send a song

```mermaid
flowchart LR
    A[Send a song] --> B[Check the match]
    B --> C{Right song?}
    C -->|Yes| D[Rate it]
    C -->|No| E[Choose or correct it]
    E --> D
    D --> F[Get recommendations]
```

The bot looks up song **metadata** (artist and title). It does not listen to or
download the audio. Ratings are ❤️ Love, 👍 Like, 😐 Neutral, and 👎 Dislike.
Use **For You** for a list based on your taste, or **More Like This** to start
from one song.

## Run your own bot

You need Python 3.12+, a [Telegram bot token from @BotFather](https://t.me/BotFather),
and a [Last.fm API key](https://www.last.fm/api/account/create). Your computer
or server must be able to reach the APIs described in [Network access](#network-access).

1. **Install the Python packages.** From this repository's folder:

   ```bash
   python -m venv .venv
   ```

   Activate the environment, then install:

   | System | Activate with |
   | --- | --- |
   | macOS / Linux | `source .venv/bin/activate` |
   | Windows PowerShell | `.venv\Scripts\Activate.ps1` |

   ```bash
   python -m pip install -r requirements.txt
   ```

2. **Create your private configuration file.** Copy `.env.example` to `.env`,
   then open `.env` and fill in the empty values. On macOS/Linux, use
   `cp .env.example .env`; on Windows PowerShell, use
   `Copy-Item .env.example .env`.

   | Setting | Put this in `.env` |
   | --- | --- |
   | `TELEGRAM_BOT_TOKEN` | The token from BotFather |
   | `LASTFM_API_KEY` | Your Last.fm API key |
   | `TELEGRAM_API_BASE_URL` | `https://api.telegram.org` if reachable, or the HTTPS origin of your trusted Telegram relay |
   | `LIL_BRO_BOT_USERNAME` | Optional username for the related bot; leave the example value unless you use a different bot |

3. **Start the bot.**

   ```bash
   python -m music_bot
   ```

Open your bot in Telegram and send `/start`. Keep the process running to receive
messages. LilCusin uses **polling**, so it needs no public inbound port. Run only
one copy for a bot token, and do not set a webhook for the same bot. If the bot
already runs on a VPS, stop that copy before starting another one.

> **Keep secrets private:** `.env` and the local database are ignored by Git.
> Never commit, screenshot, or paste real tokens, API keys, or user data. If a
> secret was ever committed, rotate it; deleting a file does not erase Git history.

## What can I do in Telegram?

| Action | What happens |
| --- | --- |
| Send `Artist - Song title` or Telegram audio | The bot searches for the song and asks you to confirm uncertain matches. |
| Rate a confirmed song | Love and Like teach **For You** your preferences. You can change a rating later. |
| Tap **More Like This** | Find songs related to the selected song, even before rating it. |
| `/taste` or `/profile` | See your taste summary or rating counts. |
| `/connectchannel` | Optionally connect a playlist channel; new audio posts can become weak taste signals after identification. |
| `/privacy` or `/forgetme` | Read what is stored or remove your personal records. |

If a match is wrong, choose another candidate or reply to the correction prompt
with `Artist - Song title`. `/cancel` closes an unfinished search. The match is
based on metadata and can be wrong even when the names look similar.

## Technical details

### Telegram Mini App

Lil Cusin includes a mobile interface with **For You**, **Search**, **Channels**, and **My Taste**.
It shares the bot's SQLite database and recommendation services. Song cards support
Love, Like, Neutral, and Dislike; search accepts a song title alone or
`Artist - Song title`. Ratings apply only to the selected match after listening.
Connected channel songs can be browsed, rated, and identified in the app.
Posts start collecting after channel connection; older posts are not imported.
Available album covers appear on song cards. This is music discovery, not an audio player.

To enable it, set `MINIAPP_URL=https://your-app.example` in `.env`. Forward that
HTTPS origin to `127.0.0.1:8080` with your reverse proxy, including `/api/` paths,
and run the bot normally. `MINIAPP_HOST` and `MINIAPP_PORT` change the bind address.
The bot starts the web server and registers an **Open Lil Cusin** menu button.
Keep the local port private behind the HTTPS proxy. No new Python packages are needed.
An optional main app/profile launch button can also be configured in BotFather.

API calls require Telegram-signed `initData`, checked on the server with a
one-hour maximum age. Expired sessions must reopen the Mini App. Ratings require
a user-owned, unexpired displayed-list token. Authentication data stays in memory
and is never put in URLs or local storage; HTTP access logging is disabled.
Opening the page outside Telegram shows clearly labeled sample data and never
writes real ratings. For a local design preview only, run
`python -m http.server 8080 --directory music_bot/web` and open `http://localhost:8080`.

Leave `MINIAPP_URL` empty to keep running only the chat bot. If the menu button
was previously enabled, reset it through BotFather when disabling the app.

For the deployed `workers.dev` version, the interface lives in the separate
`lilcusin-ui` Worker. The VPS runs `music_bot.miniapp_server` on loopback port
8091 and `music_bot.miniapp_connector` as a separate outgoing HTTPS connection.
The original Telegram polling process can keep running unchanged. The connector
accepts only the declared Mini App API routes and forwards only Telegram authentication
and JSON bodies to that fixed local port. No website domain or Nginx route is needed.

The Worker uses a SQLite-backed Durable Object to keep the connector available;
it does not store song preferences in Cloudflare. Preference data stays in the
existing bot database. Telegram authentication and rating ownership are still
verified by the bot API. The connector credential is stored as a Worker secret
and a private file on the VPS, never embedded in the interface.

To rebuild the Worker from the UI assets, run `python worker/build.py`, then use
the configuration in `worker/wrangler.jsonc` for deployment. Connector and API
services should be supervised and started at boot. Keep the connector secret
outside source control. See `MINIAPP_DEPLOYMENT.md` for this installation's
service names and rollback instructions.

### Where requests and data go

```mermaid
flowchart LR
    U[Telegram user] <-->|Messages| T[Telegram Bot API]
    T <-->|Polling and replies| B[LilCusin]
    B -->|Song metadata| L[Last.fm]
    B -->|Extra matches when needed| M[MusicBrainz]
    B <-->|Preferences and cache| D[(Local SQLite database)]
```

`TELEGRAM_API_BASE_URL` changes only the **Telegram Bot API** origin. It must be
an HTTPS origin such as `https://api.telegram.org`, with no path, query, or
credentials. A trusted relay can be used when Telegram is blocked on the host.

### Network access

The current repository calls Last.fm and MusicBrainz at their normal URLs.
Changing `TELEGRAM_API_BASE_URL` does **not** route those two services. If your
server cannot reach them, their provider clients need a separate relay or other
network route. The bot's song lookup and enrichment depend on those services;
Telegram connectivity alone is not enough.

### Data and privacy

The bot creates `data/music_bot.sqlite3` when it starts. It stores Telegram user
IDs and basic profile fields, song submissions and file identifiers, ratings,
recommendation history, provider metadata, and short-lived button state. The
optional channel feature also stores channel and new-post identifiers. Audio
files are not downloaded, and old channel history is not imported.

`/forgetme` removes the requesting user's profile and related personal records.
Shared song metadata can remain for other users; messages already held by
Telegram and provider-side records are outside this deletion. Read `/privacy`
in the bot for the full in-app explanation. See [SECURITY.md](SECURITY.md) for
reporting and local-data guidance.

### Playlist channels

To connect a channel, send `/connectchannel` privately, make the bot a channel
administrator, and post the one-time code as a **new text post** in that channel.
You must also be its creator or an administrator. Leave optional permissions
such as posting, editing, deleting, and inviting disabled; the bot does not
post there. Only eligible **future** audio posts are processed. Uncertain songs
wait for private review in `/channels`. A channel post is a weak signal, not a
claim that you listened to or liked the song.

### Code map

| Area | Where to look |
| --- | --- |
| Startup and polling | `music_bot/__main__.py` |
| Configuration | `music_bot/config.py`, `.env.example` |
| Song matching | `music_bot/workflow.py`, `music_bot/matching.py` |
| Last.fm and MusicBrainz clients | `music_bot/providers/` |
| Recommendations | `music_bot/recommendations/` |
| Data storage | `music_bot/database.py`, `music_bot/models.py` |
| Tests | `tests/` |

### Tests and live checks

Run the automated tests after installing `requirements.txt`:

```bash
python -m unittest discover -v
python -m compileall -q music_bot tests
```

To check the **real** Last.fm and MusicBrainz APIs, run
`python -m music_bot.validate_sources`. This uses your Last.fm key and makes
external requests, but sends no Telegram messages. Do not run multiple live
validators at once.

### Limits and project status

Identification is not acoustic recognition. Provider coverage and spelling
affect results, including songs written in Persian. Recommendations are
heuristics, not a guarantee that someone will like a song. This is a self-hosted
project with no hosted-service uptime promise. No license is currently included;
reuse permissions have not been specified.

### Guide and language

New listeners get a short three-step guide in Telegram and the Mini App. Use `/help`
to reopen it, `/language` to change language, or the language picker in the app.
Eight languages are available, with Persian/Arabic RTL layout and bundled Vazirmatn.
The app replaces rated song cards with new picks while keeping the rest of the list.
“More like this” opens a song-specific page. Breadcrumbs and Telegram’s back button
restore earlier lists, including search text, scroll position and song controls.
The Mini App guide includes small visual examples of search, listening and rating.
Language, onboarding, and replacement checks live in `tests/test_guidance.py` and
`tests/test_miniapp.py`. Run `node worker/test-ui-navigation.mjs` for the page history
and song-control restoration checks.
Run `node worker/test-ui-recovery.mjs` for interrupted transitions, unavailable
WebView features, stalled preference saves, and authenticated startup failures.
