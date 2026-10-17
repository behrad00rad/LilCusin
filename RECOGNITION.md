# Music recognition

Install `requirements.txt` and restart the bot. ShazamIO recognition is enabled
by default and needs no API key. FFmpeg on PATH is used when available, otherwise
the bundled imageio-ffmpeg executable is used. No database migration is needed. Set `RECOGNITION_ENABLED=false` to restore existing audio metadata identification.

Send voice, video, a video note, or a video document in private chat.
Music files default to metadata-based rating without fingerprinting or downloading.
Reply to an earlier audio/media message with `/recognize` to explicitly identify it.
Supported public HTTPS
post links include YouTube/Shorts, TikTok, Instagram reels/posts, Pinterest video
pins, X/Twitter posts, SoundCloud tracks and Vimeo videos. TikTok short links and
pin.it links are accepted. Install `requirements-audio.txt`, including the curl-cffi
transport needed by current TikTok extraction. Only specific post URL shapes are
allowed; generic URLs, profile pages, private posts, playlists and humming are
outside this version. Platforms can require login or deny extraction, and image-only
posts have no audio to recognize. Send a local media file when a post is inaccessible.

A user-supplied TikTok link was downloaded and recognized live on 2026-10-16.
Instagram and Pinterest have allowlist/extractor tests but no live-post verification
in this session. Support means an implemented bounded adapter, not guaranteed
availability of every public post.

Telegram uploads are limited to 20 MB. YouTube sources are bounded to 15 minutes,
20 MB downloaded media and 60 MB temporary storage per job. One worker handles
up to 20 pending requests; each user can have one request and start one every
30 seconds. Jobs time out after 4 minutes. `/cancel` stops that user's job.
Queued jobs are ephemeral and lost on restart; resend after a restart.

FFmpeg extracts up to three 12-second mono WAV samples from the start, middle and
end of media with a known duration (otherwise at 0, 30 and 60 seconds),
stopping at the first match. ShazamIO calculates a fingerprint locally and sends it to Shazam over HTTPS,
never via a Telegram token-bearing URL. Users see this disclosure
when submitting. The third party processes audio under its own service terms.
Temporary media is removed on completion, failure, cancellation or normal shutdown.
After a hard process/host crash, the OS temporary directory may need cleanup.
Results are cached in memory for one hour (maximum 500 entries); request limits
and the cache reset on restart. Nothing is added to taste history automatically.

Results include artist, title and available listening links. A failed match offers
typed song/artist input or another audio section; provider failures are distinguished from media failures.
When Get song is enabled, recognition automatically queues the identified artist
and title for full-song audio delivery, including recognition-cache hits. The
existing source permissions, per-user limits, recording selection, cached Telegram
file reuse and /cancel apply. Ambiguous recordings prompt a choice. Delivery failure
does not discard the recognition result. Recognition creates no rating or taste
signal; canonical music metadata and delivery request records are persisted under
the normal Get song retention and /forgetme behavior.

Provider: https://github.com/shazamio/ShazamIO . This is an unofficial remote
Shazam client, not an offline catalogue or a guaranteed service. Each sample
makes at most one HTTP request; the bot does not use the library default retries. Validate Persian
songs, remixes, noisy recordings and sped-up clips before public rollout.

Local automated checks use mocked provider and Telegram transports. Network access and representative real recordings are required to verify match quality.

Verified locally on 2026-10-16: FFmpeg extraction plus ShazamIO recognition of the
upstream public Gloria.ogg fixture returned Gloria Gaynor — I Will Survive.
The adapter uses the upstream-supported cdn discovery endpoint and an iPhone
profile; the amp endpoint returned HTTP 403 from this environment. This smoke
test does not establish Persian/noisy/remix accuracy or deployed Telegram delivery.
Run `python -m tests.recognition_live_check` for an explicit network check.

Source search preserves original catalogue title punctuation. Transient source
search and direct-download errors get at most one retry each. Repeated errors
stop and retain the recognition result. This does not guarantee source availability.

Shazam cover artwork and album metadata are retained directly. Valid Apple image
CDN artwork goes through the normal audio-tagging and Telegram thumbnail pipeline,
without depending on Last.fm for covers. Cached Telegram audio is sent before
artwork work; it is not re-fetched solely to upgrade a cover. Earlier sent messages
remain unchanged. Missing or unavailable artwork never prevents audio delivery.

Find other versions appears on new recognition messages, song cards, recording
choices and delivered audio. It shows up to three edition categories for the same
artist/song; covers and karaoke are excluded. Select a recording to send it. An
unlabelled source is not proof of a studio master. Original recognition is retained;
the selected edition gets its own track metadata and artwork when available.

All Get song paths can identify a 12-second sample of downloaded audio through
Shazam to obtain a missing or unreachable cover. Artist/title/version checks protect
against artwork from another recording. New-file artwork work has a three-second
total budget; cached audio bypasses it. Failed fallback attempts are remembered for this process.
No new API key is needed. Old Telegram messages and buttons remain unchanged.
