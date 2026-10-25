# LilCusin

LilCusin is a Telegram-first music discovery product. It helps people identify songs, build a taste profile, and find music through personal recommendations and friend discovery. The Telegram bot and Mini App share the same profile and recommendation services.

- [Introducing LilCusin](docs/introducing-lilcusin.md) — product overview and important features
- [Current status and handoff](docs/STATE.md) — what is deployed, local-only, and still unverified
- [Recent evidence and updates](docs/evidence.md) — commits, checks, deployments, and limitations
- [Architecture](docs/ARCHITECTURE.md) · [Get song](GET_SONG.md) · [Mini App deployment](MINIAPP_DEPLOYMENT.md)

## Features

- Identify songs from metadata, search by title or artist, and optionally recognize supported audio, video, and voice messages.
- Rate confirmed matches with Love, Like, Neutral, or Dislike; build a personal profile and get recommendations in chat or the Mini App.
- Search songs and artists, explore connected Telegram channels, and browse a personalized For You feed.
- Find and deliver a selected recording privately when Get song is enabled and the source is permitted. Delivery reports progress and its final state.
- Share unlocked Loves with accepted friends by default. Per-song privacy locks and a saved opt-out keep private choices protected; other ratings stay private.
- Exchange songs with friends, manage invitations and alerts, and use friend discovery. Telegram social alerts are enabled by default for new or missing settings; existing saved choices are retained.
- Select English or Persian. Bot responses and Mini App controls include localized copy and Persian right-to-left layout.
- A five-round “Guess their taste” game and its notification groundwork are implemented locally but remain disabled by default; they are not part of the deployed feature set. See [game status](docs/guess-game.md).

These features have different deployment and verification states. Read [the current handoff](docs/STATE.md) before treating local-only features as live. A passing test does not establish real Telegram or phone acceptance.

## Try it

Open [@LilCusinBot](https://t.me/LilCusinBot) in Telegram and send a song title or tagged audio. For an identified song, confirm the match, rate it, and ask for recommendations. The Mini App is available from the bot menu where configured. For the full introduction, see [Introducing LilCusin](docs/introducing-lilcusin.md).

## Run your own bot

Use Python 3.12 or 3.13. Create a Telegram bot with [@BotFather](https://t.me/BotFather), obtain a Last.fm API key, copy `.env.example` to `.env`, and fill in the required values. Then install dependencies and run the bot:

```bash
python -m venv .venv
python -m pip install -r requirements.txt -r requirements-audio.txt
python -m music_bot
```

See [deployment instructions](DEPLOYMENT.md), and `.env.example` for optional settings. Keep `.env`, bot tokens, API credentials, and connector secrets private.

### Mini App

The Mini App can be served by the VPS app with its HTTPS reverse proxy or by the separate Cloudflare Worker deployment. These are distinct supported routes; the Worker is not required for a VPS-hosted Mini App. Follow [Mini App deployment](MINIAPP_DEPLOYMENT.md) for the selected topology. Telegram API requests require valid, current Telegram `initData`; sample data shown outside Telegram does not write ratings.

## Development checks

Use the repository environment and focused tests for the code being changed. Examples:

```bash
python -m unittest tests.test_taste_sharing -v
node worker/test-private-love.mjs
node --check music_bot/web/app.js
```

See [contributor workflow](AGENTS.md) and [architecture](docs/ARCHITECTURE.md). Update status and evidence docs when a material capability or deployment changes.
