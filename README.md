# LilRecommenderBro
lil bros recommendin

Minimal Python Telegram bot foundation using aiogram 3 and long polling.
Requires Python 3.12. `/start` and `/help` introduce the bot. Users can submit
Telegram audio (including forwarded audio) or text as `Artist - Song title`.
Spaced Unicode dashes work too: `گوگوش — من آمده‌ام`. The bot identifies songs,
asks for confirmation when needed, and collects Love/Like/Neutral/Dislike ratings.
Confirmed Telegram audio can also be analysed locally for estimated BPM and
compact numerical features. Private-chat menus now offer For You recommendations,
More Like This, recommendation ratings, a profile summary and personal-data removal.
The recommendation engine is also available through its application service and CLI.

In the Codespaces terminal, from the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Local audio analysis also needs FFmpeg/ffprobe. If they are missing:

```bash
sudo apt-get update
sudo apt-get install -y --no-install-recommends ffmpeg
```

FFmpeg absence disables analysis gracefully; identification and rating still work.

Create `.env` in the repository root using `.env.example` as a template if you
do not already have one. Set both required variables:

- `TELEGRAM_BOT_TOKEN`: your BotFather token.
- `LASTFM_API_KEY`: your Last.fm API key for identification and enrichment.
  No shared secret or Last.fm user authentication is needed.

Optional nonsecret limits (defaults shown; invalid/out-of-range values stop startup):

```env
MAX_AUDIO_FILE_MB=20
MAX_AUDIO_DURATION_SECONDS=900
AUDIO_ANALYSIS_CONCURRENCY=2
```

Allowed ranges: 1–20 decimal MB, 1–900 seconds, and 1–2 concurrent analyses.
Text submissions require no audio and are skipped normally by local analysis.

Keep secret values out of Git and logs. `.env` is ignored. Existing environment
variables take precedence over `.env`. Startup stops if either value is missing
or the Telegram token format is invalid.

Run:

```bash
.venv/bin/python -m music_bot
```

Keep the terminal running; press Ctrl+C to stop cleanly. Run only one polling
instance for this token, and ensure no Telegram webhook is configured.
**Stopping the Codespace also stops the bot.** No public port is needed.

Code lives in `music_bot/`: configuration in `config.py`, Telegram routing in
`handlers.py`, keyboards in `interactions.py`, parsing in `submissions.py`,
identification/correction/ratings in `workflow.py`, comparisons in `matching.py`,
and canonical track persistence in `catalog.py`. Metadata clients are in
`providers/`, with caching in `cache.py` and enrichment in `enrichment.py`.
All bot reply text is in `messages.py` for future translations.
Logs cover startup, shutdown, and errors; dependency error details and
tracebacks are deliberately omitted to keep secrets and user messages private.

The bot initializes `data/music_bot.sqlite3` automatically on startup, using
SQLAlchemy 2 and aiosqlite. Initialization creates missing tables and preserves
existing data. `migrations.py` now contains a small, repeatable additive migration:
nullable display-artist/title columns on `tracks` and a display-name column on
`track_tags`. Three new tables hold identification state, provider cache entries,
and similar-track candidates. No tables or data are deleted or rebuilt. There is
no external migration framework; future changes need explicit additive migrations.
SQLite foreign keys are enabled for every connection. Timestamps use UTC and
round-trip as timezone-aware values; durations are seconds.

Models: `User`, `Track`, `TrackExternalID`, `TrackTag`, `SongSubmission`, `Rating`,
and `RecommendationHistory`, plus `IdentificationFlow`, `ProviderCache` and
`SimilarTrack`. Task 8 adds `AudioAnalysis` through the same repeatable
table-creation approach, without changing or recreating existing tables.
New canonical track keys also normalize punctuation, Arabic/Persian
yeh/kaf, diacritics and spacing; separate display columns preserve source spelling.
Existing track keys are preserved. Stable external IDs are checked first when
reusing tracks. Unique constraints and reserved SQLite write transactions prevent
duplicate confirmations and ratings. Recommendation display batches now use the
existing history table with nullable score, batch ID and position fields.
Only Telegram metadata/file identifiers and compact extracted features are stored.
Audio for analysis is downloaded temporarily and never stored in SQLite or the
repository. The database contains user data and is ignored by Git.

Use a **private chat**. Text/audio metadata starts a search in Last.fm. Weak,
incomplete or absent results also trigger MusicBrainz. Artist and title each
contribute 45% of confidence using normalized string similarity; provider relevance
contributes 10% (neutral 0.5 when unavailable). Automatic selection requires exact
normalized artist and title, an external ID, confidence at least 0.94, a lead of
at least 0.08 over the next candidate, and no provider failure. Otherwise up to
five plausible candidates and **None of these** are shown. This is metadata
matching, not acoustic identification or a guarantee of the correct recording.

Missing audio artist/title and rejected/absent matches produce a correction prompt.
Reply **directly to that prompt** with `Artist - Song title`; the reply updates the
identification input while retaining the original submission. Prompts/candidate
buttons expire after 30 minutes; there are at most three searches per submission.
New, unthreaded messages create new submissions; each correction prompt belongs to
its own submission. `/cancel` ends all your open identification flows without
deleting data. Unknown, expired or cancelled replies/buttons are rejected safely.
An interrupted search during shutdown can be retried by sending a new submission.

After a strong match or confirmation, choose ❤️ Love, 👍 Like, 😐 Neutral or
👎 Dislike. The selected button gets a check mark. Repeating a rating does not
duplicate it; changing it updates the existing record and modification time.
Ratings remain editable through their buttons, even after identification expires.
Ownership always uses Telegram user ID. Silence and submissions do not create
ratings, and there is no Skip button.

Enrichment runs after the rating prompt, with three concurrent jobs maximum and a
35-second deadline including queue time. It stores available album, duration,
artwork, display artist/title, provider IDs, and normalized community tags with
source, weight and display name. Tags are not asserted to be objective genres.
Normalized release IDs/titles/dates/countries live in cached provider metadata.
Similar-track candidates and scores are cached as relationships without creating
canonical tracks or recommending anything. Missing metadata never invents values
or erases existing fields; failures do not undo confirmation or ratings.

Cache entries contain normalized data only. Track info, tags and MusicBrainz
lookups expire after **7 days**; similar tracks after **1 day**; searches after
**15 minutes**. Empty results expire after **5 minutes**. On temporary network,
rate-limit or service failures, positive cached data can be used for up to **1 day
past expiry**. Authentication failures are never cached as successes or hidden by
stale fallback. Fresh entries avoid HTTP calls; concurrent identical calls share
one request. Provider operations have an additional 8-second deadline. Handler
and enrichment tasks are cancelled and observed before resources close at shutdown.

After a confirmed **audio** submission's rating prompt appears, local analysis
is scheduled separately. It does not depend on the rating value. One successful
compatible analysis is reused per canonical track/analyzer version, including
submissions by other users. The first successful recording supplies that track's
features; different performances of a song can differ. `Track.bpm` is written only
by the latest successful local analysis, and is null when tempo could not be
estimated. Failures retain prior successful versions and do not undo ratings.

`music_bot/audio/` separates download validation, FFmpeg conversion, synchronous
feature extraction, killable worker execution, and async persistence/scheduling.
CPU processing runs in a dedicated local Python subprocess rather than an
uncancellable worker thread, so timeout/cancellation can stop it before cleanup.
No live DB session or secret environment variables enter a worker. No remote
audio-analysis service or machine-learning model is used.

Reported size/duration/MIME/extension are checked before download. Missing labels
defer to content validation; inaccurate sizes are caught by a bounded streaming
sink. Internally generated filenames live in isolated OS-managed directories
under `/tmp`, never the repository. FFprobe checks content and duration; FFmpeg
permits only expected audio containers and local file/pipe protocols, uses no
shell, and decodes one stream to mono 22,050 Hz, 16-bit PCM. Decoded duration and
output size are bounded even when container metadata is wrong. Original filenames
are never used as paths. Input, WAV and worker cache files are removed on success,
failure, timeout and orderly cancellation. An OS-level kill or machine loss cannot
run Python cleanup; OS temporary storage may need reclamation after such a crash.

Analysis has a **180-second total deadline including queue time**: Telegram file
lookup is limited to 10 seconds, download to 30, probing to 10, FFmpeg conversion
to 30, and librosa to 120. At most twice the configured concurrency may be queued
or running. Each user may have one active job, with a 60-second cooldown after
completion. Failed jobs may retry through a subsequent confirmation or submission,
up to three attempts for the same submission. There is no forced-analysis command.
Workers use one numerical-library thread, a 2 GiB address-space ceiling and a
120-second CPU limit. Subprocess output is capped at 16 KiB; raw diagnostics and
paths are not logged. Slow/large files can hit limits and fail without blocking ratings.

`AudioAnalysis` stores status (`pending`, `processing`, `succeeded`, `failed`),
safe error category, source submission/user, analyzer name/version, timestamps,
BPM estimate and a small validated JSON feature summary. A unique constraint on
track/analyzer/version prevents duplicate successes. Startup marks interrupted
pending/processing jobs failed and retryable; it does not download old files
automatically. No existing submissions, users or ratings are modified by analysis.

Stored features and units:

| Feature | Unit/meaning |
| --- | --- |
| BPM, beat count | Estimated beats/minute; number of detected beats |
| Mean onset strength | librosa positive spectral-flux measure; not confidence |
| RMS mean/std | Linear amplitude relative to PCM full scale |
| Spectral centroid/bandwidth/85% rolloff mean/std | Hz |
| Zero-crossing rate mean/std | Fraction of crossings per frame |
| Chroma mean | 12 dimensionless normalized pitch-class values, C through B |
| Analysed duration, sample rate | Seconds; Hz |

Values retain numerical precision in storage and must be finite/nonnegative.
Unknown BPM remains null. BPM can land at half/double perceived tempo; no assumed
correction or accuracy percentage is applied. No genre, mood, danceability or other
semantic labels are inferred. A successful new analysis sends one short result
message; ordinary failure sends at most one generic message per admitted attempt.
Cached reuse and text submissions send no analysis notification.

Run the automated tests (standard-library unittest; all HTTP is mocked):

```bash
.venv/bin/python -m unittest discover -v
.venv/bin/python -m compileall -q music_bot tests
```

Validate the live data sources independently:

```bash
.venv/bin/python -m music_bot.validate_sources
.venv/bin/python -m music_bot.validate_sources --song "Radiohead" "Creep" --song "گوگوش" "من آمده‌ام"
```

The editable `DEFAULT_SONGS` in `validate_sources.py` contains international and
Persian examples. Last.fm checks search, track information, top tags and similar
tracks. MusicBrainz checks recording search and looks up the first candidate's
metadata when an ID is available. Search candidates are not confirmed matches.
Exit codes: 0 for successful requests (including missing tracks or incomplete
metadata), 1 for provider/request failures, 2 for missing configuration.
The validator needs only `LASTFM_API_KEY`; MusicBrainz is still tested when it is
missing. No secret values or raw response dumps are printed.

Provider requests use 5-second connect, 10-second read and 20-second total
timeouts. Errors are returned as safe categories; there are no automatic retries.
MusicBrainz clients share a one-request-per-second limit within the single
application event loop, including metadata lookups. Do not run multiple live
validators concurrently. The User-Agent identifies this repository.

Persian coverage depends on provider spelling, script and catalog entries;
missing tags, artwork or identifiers are allowed. A missing result does not
mean a song does not exist. Comparison normalization helps with character variants
but does not transliterate provider queries, translate titles or infer identity
from filenames. In the initial live sample, Last.fm found
`گوگوش — من آمده‌ام` with no album/duration, tags or similar tracks; MusicBrainz
returned no candidates for that spelling.

API references: [Last.fm](https://www.last.fm/api),
[MusicBrainz rate limiting](https://musicbrainz.org/doc/MusicBrainz_API/Rate_Limiting),
and [SQLAlchemy SQLite](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html).

## Recommendation engine (Task 9)

Evaluate an existing user's explicit ratings from the repository root. Replace
`123456789` with their **Telegram user ID**, not the internal SQLite user ID:

```bash
.venv/bin/python -m music_bot.evaluate_recommendations 123456789 --limit 5 --seed 42
```

This is **For You**, using every Love/Like rating. For **More Like This**, add
the selected canonical track ID (shown as `track_id` in evaluation output):

```bash
.venv/bin/python -m music_bot.evaluate_recommendations 123456789 --track-id 17 --limit 5 --seed 42
```

This defaults to local/cached data and prints artist, title, internal score,
reason, source categories and exploration status. It sends no Telegram messages
and records no recommendation history. Optional `--online` allows cached Last.fm
similar-track lookups when the candidate pool is sparse; only this option needs
`LASTFM_API_KEY`. `--database /tmp/evaluation.sqlite3` selects a separate database.
The command initializes missing schema additively and exits after evaluation.
No new dependencies are required.

Application interface:

```python
from music_bot.recommendations import RecommendationService

service = RecommendationService(database, providers=cached_providers)
preview = await service.recommend_for_user(telegram_user_id, limit=5, random_seed=42)
similar = await service.recommend_similar_to_track(
    telegram_user_id, track_id=17, limit=5, random_seed=42,
)
display = await service.recommend_for_user(
    telegram_user_id, limit=5, random_seed=42,
    for_display=True, batch_id="unique-display-request-id",
)
```

Pass `providers=None` for local/cache-only operation. The caller owns database and
provider sessions. Results have `status`, `recommendations` and optional `batch_id`;
each recommendation has canonical `track_id`, artist/title, optional album/artwork,
external IDs, internal `score`, user-facing `reason`, debug `sources`, and
`exploration`. Normal user interfaces should display the reason, never the score.
Task 10 connects these methods to private-chat Telegram controls, described below.

No Love/Like ratings returns `insufficient_preferences`; submissions, neutral
ratings and silence create no preferences. One positive rating is sufficient.
`no_candidates` means the available metadata has no fresh unrated matches; the
engine does not invent a fallback preference. Every rated song is excluded,
including neutral/disliked songs, with external-ID and Unicode-normalized identity
checks. Conflicting external IDs are skipped. Display spelling is preserved.

More Like This instead uses only the selected song as its positive seed, with
request weight 3. This is a temporary focus, not a Love rating: it never creates
or changes ratings, even if the selected track was unrated, neutral or disliked.
The user's disliked seeds and shared recommendation history still apply. The
selected track and its aliases are excluded from results. Reasons refer to the
song selected rather than claiming the user liked it. This mode needs no positive
ratings, but does require an existing user and canonical track; an unknown user,
missing track or no usable matches returns `no_candidates`. Both methods accept
the same `for_display`, `batch_id` and `random_seed` options.

Candidates come from positive seeds' Last.fm similar-track relationships, shared
local tags, exact artists, related artists supported by those relationships, and
compatible successful local audio analyses. Existing MusicBrainz IDs/metadata
help resolve canonical identity; this engine makes no MusicBrainz requests.
Tags are community metadata, not predicted genres. Features must have the same
analyzer name, version and sample rate; missing features remain unknown.

All weights and bounds live in `music_bot/recommendations/settings.py`:

| Factor | Weight or calculation |
| --- | --- |
| Explicit ratings | Love +3, Like +1, Neutral 0, Dislike −3 |
| More Like This focus | Selected seed 3, independently of its stored rating |
| Seed affinity | Last.fm 0.45, weighted tags 0.30, artist 0.10, audio 0.15 |
| Provider similarity | Finite scores clamped to [0, 1]; invalid scores unknown |
| Tag weights | Provider count / 100, clamped to [0, 1]; unknown weight 0.5; duplicate tags take maximum |
| Tag similarity | Weighted Jaccard: sum of minimum weights / sum of maximum weights |
| Artist | Exact normalized match 1; supported related artist 0.5 × strongest relationship; otherwise 0 |
| Audio | BPM 0.50, spectral 0.30, RMS 0.10, chroma 0.10 |
| BPM similarity | `exp(-abs(log2(bpm_a / bpm_b)) / 0.25)`; no half/double correction |
| Spectral/RMS similarity | `1 - abs(a-b) / max(a,b)`; both zero gives 1; spectral averages centroid, bandwidth, rolloff and zero-crossing means |
| Chroma | Cosine similarity of 12 pitch-class means; zero vectors are unknown |
| Positive score | Best `affinity × rating / 3`, plus 0.15 × each of the next two positive contributions; capped at 1 |
| Close negative evidence | Last.fm ≥0.70; or tag similarity ≥0.60 with ≥2 shared tags; or audio ≥0.85 and tags ≥0.25 |
| Negative penalty | Each close negative contributes `3 × affinity`; subtract 0.10 × strongest and 0.15 × each of next two as a fraction of score, capped at 90% reduction |
| History | Suppress for 7 days; multiply score by 0.35 from 7–30 days; no penalty after 30 days |
| Variety | Selection priority divided by `(1 + 0.75 × already selected from this seed)` and `(1 + 0.25 × already selected from this artist)` |
| Exploration | Nearest integer to 20% of requested limit; remaining slots use greedy variety-adjusted priority |
| Exploration eligibility | Affinity ≥0.30 and penalized score ≥0.05; weighted sampling by variety priority, with ×1.20 for a new artist |

Missing optional signals leave the weighted denominator; they are not zero-quality
evidence. Artist mismatch and measured tag non-overlap are actual zero signals.
Separate seed scores preserve taste patterns rather than averaging audio vectors
or all genres into one profile. One disliked artist or one shared broad tag is
insufficient to penalize an entire artist/genre. Multiple close dislikes can
reduce a candidate by up to 90%. Explanations name evidence actually present.
The returned score precedes variety selection, so output scores need not be
monotonically decreasing. A fixed random seed gives reproducible choices for
unchanged data. Small or weak pools can return fewer tracks or fewer exploration
slots; every exploration candidate still needs positive evidence.

Bounds: 1–20 results; all positive seeds are scored, with up to 40 negative seeds
selected round-robin across artists. Retrieval uses 10 similar relationships per
seed, capped at 400 total positive relationships and a separate 400 negative
relationship budget, plus at most 800 cached seed entries. It uses 20 tags per
seed and 100 local
candidates per source (tags/artists/audio). Tag and artist loading interleaves
patterns before its cap; similar relationships interleave seeds before their cap.
At most 700 positive raw entries (400 similar + 300 local)
are deduplicated and compared for affinity, then at most 200 candidates receive
full negative/history ranking, distributed across dominant positive seeds.
Every Love/Like seed participates in affinity scoring, even when retrieval caps
omit some of its similar relationships. Every rated identity remains excluded;
preference loading/scoring cost grows with the user's positive rating count.
Local audio discovery is capped in canonical-ID order; very large catalogs may
need a better retrieval strategy later.

Database reads use bulk joins/IN queries, including metadata, IDs, features and
cached relationships. No per-candidate SQL or provider lookup is performed.
Sparse pools may make at most three sequential cache-backed Last.fm calls, each
with an 8-second deadline (up to 24 seconds total). Fresh relationships/entries
and fresh empty cache responses prevent requests. Relationships expire after one
day and may be used for one additional day offline or during failures. Existing
cache TTLs, singleflight and safe provider errors are reused. Failures leave local
and bounded stale candidates usable; no retry loop or new infrastructure exists.

Previews can materialize the selected canonical tracks/external IDs so results
always have real track IDs, but never change ratings, submissions or history.
`for_display=True` records only returned tracks, under a reserved SQLite write
transaction that rechecks ratings/history. Reusing a batch ID returns its original
order without inserting more rows; newly rated tracks are removed on replay.
Reuse the same ID for retries; omit it to generate a fresh UUID for a new display
request. Batch IDs are unique per user across both modes; reuse for a different
mode or selected track raises `ValueError` rather than replaying unrelated songs.
The selected track ID is stored in the existing source JSON, requiring no further
schema change. A repeated batch ignores a changed limit. Concurrent different batches
may return fewer tracks after the final exclusion recheck. Empty batches have no
stored rows and can be regenerated when metadata becomes available.

Migration adds nullable `ranking_score`, `batch_id`, `position` to
`recommendation_history`; existing reason/source fields store the explanation and
compact source/exploration JSON. A unique `(user_id, batch_id, track_id)` index
prevents duplicate batch entries; legacy rows with null batches are preserved.
Indexes on `(user_id, recommended_at)` and tags `(name, track_id)` support history
and shared-tag retrieval. No tables or existing records are deleted or rebuilt.

Recommendation tests use synthetic Love/Like/Neutral/Dislike fixtures, mocked
providers and temporary SQLite databases. They cover scoring, mixed tastes,
Persian aliases, exclusions, missing metadata, stale cache, timeouts, history,
concurrency, migration, candidate caps and a query-count regression guard.
Focused mode tests also verify selected-track focus, unchanged ratings, shared
history, safe batch replay, empty results and cached fallback during failure.

Limitations: quality depends on the user's explicit ratings and catalog coverage.
Sparse Persian tags/similar links may yield fewer or no results. Normalization
handles script variants and spacing but does not translate or transliterate.
Different recordings can share names, provider IDs can be incomplete, BPM may
be half/double perceived tempo, and numerical similarity does not establish genre,
mood or perceptual equivalence. This is an explainable heuristic, not a trained
model or a guarantee of user satisfaction.

## Private-chat recommendation experience (Task 10)

Run the bot from the repository root:

```bash
.venv/bin/python -m music_bot
```

`/start` opens **Send a song**, **For You**, **My Music Profile**, and **Help**.
The private-chat command menu registers `/start`, `/recommend`, `/profile`,
`/help`, `/privacy`, `/forgetme`, and `/cancel`.

Send or forward Telegram audio, or submit `Artist - Song title`. Identification
and confirmation work as before. The confirmed song card has Love/Like/Neutral/
Dislike, More Like This, For You, and Done. More Like This can be used before
rating; selecting or forwarding a song never creates a preference automatically.

For You and More Like This each send one numbered list of up to five tracks,
with concise reasons and optional albums. Each entry offers Rate and More Like
This. Catalogue/artwork links are shown only for validated HTTPS URLs on known
Last.fm/MusicBrainz hosts; artwork is an optional link so invalid or unavailable
artwork never blocks a text list. Provider text is bounded and sent as plain text,
with automatic previews disabled. Internal scores and database IDs are not shown.

Rate opens a compact card whose rating can be changed. It also offers More Like
This, Continue recommendations, and Main menu. Another list preserves the current
mode and seed. Navigation, opening links and silence are never rating signals.
Insufficient preferences prompt the user to rate a song; empty results offer the
main menu and For You. `/profile` shows the four rating counts and the number of
recommendation entries shown (including later redisplays).

`chat_service.py` handles authorization, UI state, history, profiles and removal;
`chat_ui.py` formats lists/cards and validates links; `chat_handlers.py` handles
navigation. Both submission and recommendation ratings share the same upsert in
`workflow.py`. Existing handlers and background enrichment/analysis are retained.

One new `chat_controls` table is created additively by the existing initialization
path. Random compact tokens bind actions to the owning user, Telegram message,
allowed track IDs and mode. Controls expire after 30 minutes; at most 20 active
controls are retained per user. Consumed navigation actions cannot create duplicate
lists/cards; rating callbacks remain editable and idempotent. Private-chat updates
are serialized per user, with a three-second recommendation navigation cooldown.
Busy clicks receive a short acknowledgement. `/cancel` invalidates open controls
and identification flows while retaining saved submissions and ratings.

The UI previews through the recommendation service, sends the list, then records
exactly those displayed tracks using the control token as an idempotent batch ID.
Failed sends do not count as recommendations shown. Telegram delivery and SQLite
cannot share a transaction: a process crash or database failure immediately after
a successful send can leave that delivered list unrecorded. Controls from deleted,
expired or inaccessible messages are rejected safely.

`/privacy` explains profile/submission/rating/history storage, shared metadata,
provider metadata requests and temporary audio processing. `/forgetme` requires
an owner-checked confirmation with a cancel option. It cancels and drains that
user's active audio jobs, then deletes their controls, identification state,
submissions, ratings, history, audio-analysis rows and profile in one transaction.
Canonical tracks, external IDs, tags, cached metadata and other users' rows remain.
Shared numerical track metadata such as BPM is retained without user linkage.
Messages already in Telegram and provider-side records are outside this deletion.
Old controls cannot recreate a deleted account; a new explicit interaction can.

No channel integration/import, acoustic recognition, new download/link-processing
feature, Mini App, admin panel, paid service or deployment infrastructure is added.
The existing temporary audio-analysis path is unchanged apart from per-user cancellation.
