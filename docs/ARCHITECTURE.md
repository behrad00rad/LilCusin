# Architecture and navigation

Scoped map from existing documentation, dependency manifests and entry points;
not a full code audit. Setup remains in [README](../README.md).

| Area | Maintained entry points | Responsibility |
| --- | --- | --- |
| Telegram bot | `music_bot/__main__.py`, `handlers.py`, `chat_handlers.py`, `channel_handlers.py` | aiogram polling, commands/callbacks, chat and channel interactions |
| Identity/search | `workflow.py`, `catalog.py`, `matching.py`, `providers/` | Shared catalogue selection and provider fallback; explicit match choice |
| Recommendations | `recommendations/`, `taste_learning.py`, `preferences.py`, `taste_setup.py` | Separate request/explicit feedback evidence, durable leased For You queue, candidate ranking and optional onboarding |
| Persistence | `database.py`, `models.py`, `migrations.py` | Async SQLAlchemy/aiosqlite SQLite records; preserve user data |
| Recognition/delivery | `recognition.py`, `get_song.py`, `youtube_fetch.py`, `audio_artwork.py` | Bounded recognition, recording choice, delivery jobs, Telegram cache and artwork |
| Taste cards | `taste_cards.py`, `taste_card_chat.py`, `taste_card_api.py` | Separate selected public identity, owner edits and revocable sharing |
| Mini App API | `miniapp.py`, `miniapp_server.py`, `miniapp_delivery.py` | Signed Telegram requests, shared services and bot delivery links |
| Social loop | `social.py`, `social_api.py`, `social_chat.py`, `web/social.js` | Consented selections, swap state, private saves, blocks/reports, bounded outbox and chat/Mini App UI |
| HTTPS edge | `miniapp_connector.py`, `worker/proxy.mjs`, `bridge.mjs`, `artwork.mjs` | Allowlisted API bridge, outgoing connector and cover proxy |
| Mini App UI | `music_bot/web/` | HTML/CSS/JavaScript, locales and static assets |
| Worker bundle | `worker/build.py` → `worker/worker.mjs` | Generated embedded UI plus maintained Worker modules; no separate frontend package build |
| Checks | `tests/test_*.py`, `worker/test-*.mjs` | Scoped unittest and Node regression scripts |

Normal path: Telegram input → handlers → shared workflow/services → catalogue or
SQLite → user selection/rating/delivery. Mini App UI → Worker → outgoing connector
→ loopback API → the same services/database. A direct web-server mode also exists;
do not assume it is the deployed serving path. See [Mini App deployment](../MINIAPP_DEPLOYMENT.md).

## Major dependencies and boundaries

- Python 3.12/3.13; exact constraints in `requirements.txt`, optional audio and
  Lil Bro requirements in their existing manifests. Core: aiogram, aiohttp,
  python-dotenv, SQLAlchemy/aiosqlite, Pydantic, ShazamIO and imageio-ffmpeg.
- External catalogues include Last.fm, MusicBrainz, iTunes and optional Deezer;
  availability/configuration varies. Recognition uses unofficial ShazamIO.
- Optional media acquisition uses yt-dlp and FFmpeg/ffprobe. See
  [recognition](../RECOGNITION.md) and [Get Song](../GET_SONG.md) for constraints.
- SQLite is shared state, not a disposable test fixture. Deployment and consistent
  backups belong to [DEPLOYMENT](../DEPLOYMENT.md); security to [SECURITY](../SECURITY.md).
- Telegram initData, displayed grants and owner checks guard mutations. Card
  sharing exposes only deliberately selected fields; private ratings stay separate.
- Telopotify is a separate future integration, not a current required dependency.

Current release state belongs in [STATE](STATE.md); architecture rationale and
tradeoffs remain in [decisions](decisions.md).

## Private recommendation loop

Chat For You reserves a persisted batch, sends it, then records actual display
and removes those leased rows. Failed sends release the lease; abandoned leases
expire. Refills are metadata-only tasks owned by the recommendation service and
drained during shutdown; they never send messages. Current ratings, saves,
feedback and recent alias history are checked again at serving.

`SavedSong` remains the one private saved library for chat and exchanges.
`taste_learning.py` adds request evidence, per-track feedback and a learning
revision/generation guard; `recommendations/queue.py` adds the bounded queue.
The additive tables are registered by `Database.initialize()`. No Mini App UI,
Worker generation, friendship discovery or playlist builder belongs to this slice.
