# LilCusin

LilCusin is a Python Telegram bot for identifying songs from their metadata and
building personal recommendations from ratings. The bot accepts Telegram audio
or a text message such as `Artist - Song title`. It uses Last.fm and MusicBrainz
metadata; it does **not** identify songs by listening to their audio.

## What it does

- Asks you to confirm uncertain song matches and lets you correct them.
- Saves Love, Like, Neutral, or Dislike ratings and recommends songs from them.
- Supports private-chat recommendations and optional playlist-channel signals.
- Stores data in a local SQLite database. Audio is not downloaded.
- Provides `/privacy` and `/forgetme` controls in the bot.

## Requirements

- Python 3.12 or newer
- A Telegram bot token from [@BotFather](https://t.me/BotFather)
- A [Last.fm API key](https://www.last.fm/api/account/create)
- Network access to the Telegram Bot API, Last.fm, and MusicBrainz—or an
  appropriately configured relay for services your host cannot reach

## Set up

From the repository root, create and activate a virtual environment, then install
the dependencies:

```bash
python -m venv .venv
source .venv/bin/activate       # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in the values:

```bash
cp .env.example .env            # Windows PowerShell: Copy-Item .env.example .env
```

Required settings:

| Variable | What to enter |
| --- | --- |
| `TELEGRAM_BOT_TOKEN` | Your bot token from BotFather |
| `LASTFM_API_KEY` | Your Last.fm API key |
| `TELEGRAM_API_BASE_URL` | An HTTPS origin for Telegram's Bot API. Use the official API origin when reachable, or your own trusted relay origin. Do not include a path, query, or credentials. |

`LIL_BRO_BOT_USERNAME` is optional and defaults to `musicbehbot`.

Keep `.env` private. Never put real tokens, API keys, relay secrets, database
files, or user data in GitHub issues, commits, logs, or screenshots. `.env` and
the bot's SQLite database are ignored by Git. If a credential was ever committed,
revoke or rotate it; deleting the file in a later commit does not remove it from
Git history.

## Run

```bash
python -m music_bot
```

Keep the process running to receive updates. Use only **one polling instance per
bot token**, and do not configure a Telegram webhook for the same bot. Running a
second copy can cause Telegram polling conflicts. Stopping the host or Codespace
stops the bot; no public inbound port is required.

Users can start with `/start` or `/help`. Send or forward audio in a private chat,
or send a title as `Artist - Song title`. For playlist-channel signals, use
`/connectchannel` and follow the bot's instructions. The bot needs administrator
status in that channel to verify membership; leave posting and other unnecessary
permissions disabled.

## Tests and checks

The automated tests use mocked provider and Telegram requests:

```bash
python -m unittest discover -v
python -m compileall -q music_bot tests
```

To make live metadata requests, run:

```bash
python -m music_bot.validate_sources
```

This uses your Last.fm key and makes requests to external providers. Do not run
multiple live validators at the same time. The validator does not send Telegram
messages.

## Data and limitations

The bot stores Telegram user IDs, submitted song metadata, ratings, recommendation
history, and provider metadata in `data/music_bot.sqlite3`. For channel features,
it also stores channel identifiers and metadata for eligible new audio posts. It
does not download audio or import old channel history. `/forgetme` removes the
requesting user's profile and related personal records; shared catalog and cache
metadata may remain. See `/privacy` in the bot for details.

Identification is a metadata match, not acoustic recognition. Results depend on
provider catalog coverage and spelling; a missing match does not mean a song does
not exist. Recommendations are explainable heuristics, not a guarantee of taste.

## Project status

This is a small, self-hosted project. There is no hosted service or uptime promise.
No license is currently included; reuse permissions have not been specified.
