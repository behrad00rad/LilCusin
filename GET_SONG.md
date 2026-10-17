# Get song (private Telegram chats)

## Correcting a recording

New audio deliveries and cached resends include **Wrong song**. It validates the
request owner, private chat, delivered message and immutable delivered video ID,
then queues a fresh choice of other recordings in the background. Repeated taps
reuse the same pending correction. The rejected recording is excluded only for
that user; another user's cache and the canonical song identity are unchanged.
After choosing a replacement, future Get song requests reuse that user's selected
recording and its cached Telegram reference. If no alternative passes matching,
the bot says so instead of resending the rejected audio. Use /cancel to stop.

Corrections use the normal request and queue limits. An additive nullable
`audio_requests.delivered_video_id` column keeps old message buttons independent
of reusable fetch jobs. The additive `audio_selections` table stores a preferred
video and up to 64 recent rejected video IDs per user/song. These records expire
under `GET_SONG_RETENTION_DAYS` and are deleted by /forgetme. Legacy audio messages
without the new button are unchanged. No source cookies or new credentials are needed.

Matching tests cover English/Persian spellings, Arabic/Persian letter variants,
collaboration-credit separators, requested versions and similarly named artists.
Real title words such as “Audio” are preserved. Version labels are checked before
normalization, including common Persian cover/live/remix labels. Latin transliteration
of a Persian title is not automatically treated as the same recording.

Verification: the full isolated Linux suite passed 221 mocked tests; three focused
correction tests also passed on Windows. Live metadata-only searches returned choices
for two additional songs; a Persian sample lacked duration metadata. Those searches
are not proof of audio delivery or universal automatic recognition. The new correction
button's live interaction is verified separately from the earlier DNA/cover test.

Live correction verification: the owner tapped Wrong song in the actual local test
bot, chose another recording and confirmed the replacement arrived. Its preferred
video and rejected original were persisted. A subsequent normal request reused the
same corrected Telegram reference without refetching: 1.1 seconds for the cached
send versus 56.9 seconds measured for the first replacement's Telegram upload.
Playback of that particular replacement was not separately confirmed. The test
configuration allows 20 requests/hour while testing; the default remains five.

Get song uses the recommendation's persisted canonical track ID. It never accepts
user URLs. A user-bound callback queues a persistent request and acknowledges it
before any network lookup or audio work. A bounded pool (two jobs by default,
`GET_SONG_WORKERS=1..4`) searches YouTube,
checks identity/version/duration, asks for a recording choice when uncertain, then
sends Telegram `sendAudio` with the canonical artist/title. This does not add audio
to channels, the Mini App, a public library, or Telopotify.

## Permissions and activation

This feature is OFF by default. Operators must establish permission for the source
and intended download/delivery. A public YouTube upload, an official-looking title,
a user choosing a result, and ownership of a bot do not establish permission.
YouTube terms restrict downloading and reuse except where expressly authorized by
the service or with the relevant prior written permissions. Copyright permission
alone may not satisfy YouTube's contractual terms. Do not enable this feature for
unrestricted public redistribution. No cookie imports, login/session extraction,
DRM circumvention, geo/access-control bypass, or private-content support is included.

References: https://www.youtube.com/static?template=terms and
https://github.com/yt-dlp/yt-dlp#readme . Review current terms before activation.
There is no automated rights verification; the operator is responsible for limiting
use to authorized sources and users. Leave disabled if this cannot be established.

## Install and deploy

1. Back up the SQLite database. Stop the existing bot (one process per token/database).
2. Install Python 3.12+ and `pip install -r requirements.txt`.
3. Install yt-dlp: `pip install -r requirements-audio.txt`. Install FFmpeg and ffprobe
   on PATH (e.g. Debian/Ubuntu `apt install ffmpeg`; Windows use an official FFmpeg
   distribution and add its bin directory to PATH). Verify `python -m yt_dlp --version`,
   `ffmpeg -version`, and `ffprobe -version`. Use a maintained yt-dlp version; YouTube
   extraction changes frequently. `requirements-audio.txt` installs the default EJS
   support; install Node.js on PATH for the runtime explicitly selected by this
   adapter. Unavailable extraction fails safely, without bypass attempts.
4. Set the values below in the existing private `.env`, then run `python -m music_bot`.
   The existing additive migration mechanism creates four new tables without changing
   existing records. Startup registers the worker independently of polling. No new
   port, server, scheduler, bot token or client credential is required.
5. Keep exactly ONE bot process per database. Multiple workers are unsupported in v1.
   Use a service manager that fully stops the old process and its children before
   restarting; use a private temp directory (`TMPDIR` on Linux / `TEMP` on Windows).
   Give that directory an OS quota for a strict disk ceiling. Filesystem monitoring
   is sampled, so a process can briefly overshoot the configured budget between checks.

| Environment variable | Default | Meaning |
| --- | --- | --- |
| GET_SONG_ENABLED | false | Explicitly enable after permission review |
| GET_SONG_PER_HOUR | 5 | New requests per user in rolling hour, including failures/cache hits |
| GET_SONG_QUEUE_LIMIT | 20 | Total pending requests/choices/sends |
| GET_SONG_PER_USER_QUEUE | 2 | Outstanding requests per user |
| GET_SONG_MAX_DURATION | 900 | Maximum source/actual media duration, seconds |
| GET_SONG_MAX_BYTES | 45000000 | Max uploaded audio; must be <=49000000 |
| GET_SONG_TIMEOUT | 180 | Timeout per subprocess and Telegram upload, seconds |
| GET_SONG_DISK_BYTES | 150000000 | Temp budget; >=2x max audio bytes |
| GET_SONG_RETENTION_DAYS | 7 | Delivery references, requests and unused fetch metadata retention |

The main application integrates these features; leave production disabled until
deployment is explicitly authorized. Local private tests currently use
`@testlilcuhbot` with a separate database. No VPS deployment was made.

Matching prioritizes official audio searches and checks artist, normalized song
title, requested version and duration. Exact artist/Topic uploads or enriched song
metadata can select automatically. Equivalent uploads of the same recording do
not create artificial ambiguity; materially different durations, alternate versions
and weak metadata still require a user choice. Only the two strongest uncertain
results receive additional metadata lookups. Listing lookup uses up to eight results.

Audio uploads reuse the canonical Last.fm artwork already shown on recommendation
cards. Missing artwork is enriched through the existing identity-checked loader.
Images use the same strict CDN allowlist, no redirects, an eight-second timeout and
a 2 MB input ceiling. FFmpeg creates a JPEG thumbnail within Telegram's 320-pixel /
200 KB limits. Mutagen embeds this cover and canonical title/artist/album tags in
M4A or MP3 without converting audio. Tagging replaces the original file atomically;
artwork failure leaves playable audio available. Generated artwork is cleaned up
with the job. `requirements-audio.txt` includes Mutagen.

An additive nullable `audio_deliveries.artwork_key` column identifies the cover in
each uploaded file. Existing coverless cache entries are upgraded on the next
request when canonical art is available; subsequent requests reuse the decorated
Telegram file reference, including its cover. No media or private credentials are
added to a public channel or browser client.

### Matching and cover verification — 2026-10-16

The live local worker searched for DNA. without an injected video choice, selected
the official 186-second recording using canonical metadata, embedded its saved album
cover and attached a Telegram thumbnail. A second request reused the same Telegram
file reference: one download, one upload and one cached send. Temporary media was
removed. The user confirmed the cover appeared and both messages played. The full
isolated Linux suite passed 206 tests, including matching, artwork failures, cache
upgrade, ownership, cancellation, restart recovery and additive migration checks.
Two focused database/cache tests also passed locally on Windows; its earlier broad
run timed out. No Google account or browser cookies were used. Other songs and
hosting environments are not guaranteed by this test.

yt-dlp runs without shell/config/cookies/playlists, with bounded provider retries,
timeout, rate, output and size limits. Only generated temp paths and validated
11-character video IDs enter fetching. Source M4A/AAC is preserved. WebM audio is
converted to MP3 using FFmpeg's quality mode, with no inflated fixed bitrate target.
ffprobe validates duration/audio-only content before upload. No alternative source
or version is silently substituted after an explicit recording choice.

## Persistence, privacy and recovery

`tracks` remains canonical identity (including version qualifiers). `audio_sources`
stores video ID and sanitized fetch metadata; `audio_fetch_jobs` stores source choice
and durable work state; `audio_requests` binds each subscriber to a user; and
`audio_deliveries` stores private Telegram file/message references. The file cache
is per user, not a shared redistribution library. Concurrent requests for a track
share search/fetch work; chosen videos use a separate track+video job key. Different
canonical tracks/versions never share jobs. A definite stale Telegram file reference
is removed and fetched again; network/ambiguous upload failures are not blindly retried.

/cancel stops that user's pending requests and choices. The subprocess is killed if
no subscribers remain. Temporary files are removed on success, exception, cancellation,
and graceful shutdown. Retention cleanup also runs while fetching is disabled. Startup removes stale generated job directories and requeues
interrupted fetches. Interrupted Telegram sends become `uncertain` and are NOT resent:
Telegram supplies no sendAudio idempotency key. The user can tap Get song again.
Choice prompts expire after 30 minutes. An interrupted/unbound choice prompt fails
closed; tap again. Terminal rows and audio cache references expire by retention setting.
The background loop stays alive after a sanitized job failure.

/forgetme removes audio requests and Telegram references along with existing personal
records, and prevents later sends to that user. Shared canonical/source metadata may
remain until retention expires. Messages already delivered to Telegram and YouTube's
own records are not deleted. A send already in progress finishes before deletion is
confirmed. Only artist/title queries and public video IDs go to YouTube. Local media
is temporary; there is no persistent audio archive or browser playback URL. Bot tokens
and Telegram file download URLs must never be sent to the Mini App/client.

## Verify

`python -m unittest tests.test_get_song -v` covers mocked cache reuse/staleness,
uncertain choice, ownership, limits, shared jobs, cleanup, forget and restart behavior.
`python -m unittest discover -s tests -t .` runs the existing regression suite too.

Live verification requires an operator-authorized bot/account and an appropriately
permitted sample. In a private chat: Get song, choose if prompted, confirm the music
message plays with artist/title, then repeat from a new or existing recommendation.
Confirm the second send uses the saved file ID without a YouTube fetch. Do not test
against other users. Mocked tests do not establish actual YouTube extraction, codec
compatibility, Telegram delivery or playback. No live delivery was performed as part
of implementation.

### Implementation verification (2026-10-16)

- Final Get song suite: 22 mocked tests passed.
- Focused Get song/chat/config/migration run: 36 tests passed before the final
  adapter-limit and disabled-startup additions; the final Get song suite covers
  those additions.
- Compilation and scoped Git whitespace checks passed.
- Full package-discovery run: 175 tests, 4 errors involving local HTTP timeouts and
  Windows SQLite file-lock cleanup. The full regression suite is not green.
  An earlier incorrectly scoped discovery command also had import errors; use `-t .`.
- yt-dlp was not installed and FFmpeg/ffprobe were not on PATH in the implementation
  environment. No live extraction, upload, playback, or live cache reuse was verified.
- Changes are uncommitted and undeployed. Existing unrelated user changes were preserved.

### Follow-up verification (2026-10-16)

The isolated Mini App tests passed. The reproducible Windows migration-test cleanup
error was fixed by explicitly closing sqlite3 connections. Get song, Mini App and
that migration test now pass together: 33 tests. yt-dlp is installed in the local
virtual environment; FFmpeg/ffprobe and live Telegram delivery remain unverified.
No bot token or private local configuration is present in either checkout.
The full suite has not been rerun after the cleanup fix.

### Latest scoped check (2026-10-16)

Local FFmpeg/ffprobe and yt-dlp are ready. The selected Kevin MacLeod Archive
recording was fetched and media-validated as a 2,104,529-byte M4A without conversion.
Telegram preflight on the VPS relay returned HTTP 403 before any send; live delivery
and Telegram cache reuse remain unverified. No production code, configuration or
packages were changed. The full 178-test run still had two Windows SQLite teardown
errors. Unsuccessful broad database-debugging experiments were removed.

At the user request, only the local checkout now defaults to direct Telegram API
access at https://api.telegram.org; six configuration tests passed. An ignored local
.env sets this origin and contains no bot credentials. VPS relay settings remain unchanged.

### Local private test (2026-10-16)

The separate test-bot configuration was copied privately from Codespaces into an
ignored local file restricted to the current Windows user. The Codespace test
poller was stopped before starting the local owner-only test launcher, which uses
its own database. No production VPS code, credentials, routing or services changed.

The local adapter now explicitly enables Node when available and disables cookie
files and browser-cookie imports. Install `requirements-audio.txt` with its
`yt-dlp[default]` dependency group and Node 22+ (or supported Deno); FFmpeg and
ffprobe must be available to the worker. These dependencies do not guarantee access:
fresh local YouTube probes now also receive the sign-in challenge. No YouTube audio
was sent in these attempts, and no login or cookie import was used.

A separate real integration check injected an official-source adapter into the
existing fetching worker. It fetched Incompetech's original 125-second Kevin MacLeod
MP3, validated its audio format/duration, uploaded one playable Telegram music
message with artist/title and source/licence attribution, then sent a second message
using the persisted Telegram file reference. Counts: one source download, one
upload, one file-ID reuse; both referenced the same Telegram audio. Temporary media
was removed. The user confirmed that both messages arrived and played.

This verifies delivery and caching with that adapter; it does not establish that
YouTube or arbitrary songs work. The regular local Get song button still uses the
YouTube adapter. The separate multi-source work in Codespaces is unfinished and
was not deployed locally. Windows regression-test results are reported separately;
previous Linux test results are not proof of this local configuration.

### Lil Bro bot-to-bot source

Set `GET_SONG_PROVIDER=lilbro` to use the existing background worker with
@musicbehbot (pinned Telegram bot ID 5098692079). The default remains `youtube`.
Both the LilCusin/test bot and Lil Bro must enable bot-to-bot communication in
BotFather. Bot transport does not use a user account, Telethon session, Chrome login
or button clicks. In the live backend test its link was accepted but no media reply
arrived; it is not a verified fallback. Use this source only where its operator permits
automation and delivery of the selected recording. No access restrictions are bypassed.

The adapter searches public YouTube metadata without downloading formats, then
requires the user to choose a recording. If the saved duration appears to describe
a clip rather than the full recording, choices explicitly flag the mismatch.
Metadata search still depends on YouTube being reachable; the source does not
provide a replacement search API. A selected video's duration is checked again
against the actual returned media before sending.

After cache lookup, the worker sends only a generated single-video YouTube link.
Incoming media is consumed before normal submission handlers. The sender and private
chat must both match the pinned provider bot. The response must reply to that exact
request or identify the same YouTube video; unrelated, old, protected, or ambiguous
media is ignored. Request state and upstream request/response references are stored
in the durable job, separately from public source metadata and user delivery records.
An interrupted upstream send is not automatically repeated; the user must request
the song again. No callback buttons are clicked and no arbitrary URLs are accepted.

The hosted Telegram Bot API only permits file downloads up to 20 MB. This adapter
uses a conservative **19,000,000-byte source-media limit**, also bounded by the temp
disk budget. This is a limit on the video before audio extraction; a short song can
still exceed it if its video is large. Large/protected files fail safely. The whole
request is timed out, and downloads, extraction, failure and cancellation clean up
generated media. Existing queue, per-user and audio-output limits still apply.

FFmpeg remuxes compatible AAC into M4A and MP3 into MP3 without re-encoding. Other
audio codecs are converted to MP3 in quality mode. The output must be audio-only,
within limits and essentially the same duration as the input; truncated output is
rejected. Fetch provenance records YouTube as the identity source and Lil Bro as
the fetching transport. Telegram file references remain private backend data.

Verification commands:

```sh
python -m unittest tests.test_lilbro_fetch tests.test_get_song -v
```

Tests mock Telegram and media processing. Live verification must additionally
confirm the exact response correlation, extraction, private delivery and second
request's cached reuse. A successful `sendMessage` to Lil Bro alone does not establish
end-to-end delivery. The browser direct-link/video response was observed separately;
the backend's real delivery test must be reported independently.

### Direct YouTube verification — 2026-10-16

The local downloader fetched the official Kendrick Lamar DNA. music video without
login or browser cookies (286 seconds, M4A, 4,622,810 bytes). A separate song-length
recording was then delivered through the real GetSong worker to the authorized
owner's private test chat. The second request reused Telegram's saved reference:
one source download, one upload, one cached send, with source metadata persisted
and generated media removed. The user confirmed both new DNA messages arrived and
played. This is local verification, not
Codespace/VPS verification or a guarantee of availability for every recording.

Search now requests listing metadata without extracting every result's media
formats. If an imported clip duration excludes all otherwise matching recordings,
it offers explicitly marked duration-mismatch choices instead of silently failing
or selecting a different version. Covers and other unrequested versions remain
excluded. Flat results still require the normal recording-choice confirmation.
