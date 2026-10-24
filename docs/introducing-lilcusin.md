# Introducing LilCusin

LilCusin is a Telegram-first music discovery product for identifying songs,
learning a listener's taste, and finding what to hear next. The bot and Telegram
Mini App share the same music profile and recommendation services. This overview
describes the repository's documented capabilities; deployment and verification
status are called out separately where relevant.

## Find and identify music

- Search by a title, an `Artist - Song title` query, or supported audio metadata.
  Search combines music catalogues and can offer bounded, metadata-only YouTube
  discovery where enabled. People choose a result before it is confirmed.
- Optional audio recognition can identify music in supported audio, video, voice
  messages and supported YouTube links. Recognition is configurable. Ordinary
  tagged music uploads use their metadata unless the user explicitly requests
  recognition.
- Correct a wrong match by choosing another result or refining the title and
  artist. Search controls are owner-bound and expire; `/cancel` closes an
  unfinished search.
- Search acknowledges private text promptly, shows progress for slower source
  checks, and reports failures and cancellation. An incomplete provider search
  is not presented as a definite no-match.

## Get music and manage taste

- **Get song** can retrieve a selected recording and deliver it as a playable
  private Telegram music message when enabled and permitted. It uses explicit
  candidate choices for uncertain matches, bounded background work, cancellation
  and delivery status. Catalogue attribution helps distinguish requested
  recordings from unrelated uploads; metadata is not acoustic proof. The
  stricter catalogue-only original-source policy is documented as local and not
  deployed in this checkout's handoff.
- Rate confirmed songs with Love, Like, Neutral or Dislike. Ratings can be
  changed. Love and Like inform personalized recommendations; choosing a match
  alone does not create a rating.
- **For You** recommends music from a listener's taste, and **More Like This**
  starts from a selected song. Search and recommendation lists support bounded
  paging, stable choices, and recovery when more candidates are needed.
- `/taste` and `/profile` show taste summaries. Optional `/setup` questions can
  suggest starter music without adding ratings.
- A private saved library and taste cards provide ways to keep and present
  selected music. Taste sharing is deliberate and revocable.

## Discover with other listeners

- Accepted friends can optionally share taste for friend-based discovery. The
  feature is consent- and access-checked; personal ratings are not automatically
  exposed. A separate purple lock control keeps a song out of friend discovery
  while preserving its private rating.
- Taste cards can be previewed and shared through revocable, owner-controlled
  links. Comparison and reciprocal song exchange are explicit interactions;
  LilCusin does not claim an unsupported compatibility score.
- An optional connected playlist channel can provide new song posts as weak
  taste signals after identification. Historical posts are not imported.

## Use the Telegram Mini App

The Mini App brings **For You**, **Search**, **Channels**, and **My Taste** into
a mobile-friendly interface inside Telegram. It shares the bot's profile and
recommendation data, supports song ratings and connected-channel browsing, and
shows available cover art. It is a discovery interface, not an audio player.
Telegram-signed session data and ownership checks protect account actions.

## Privacy and control

- `/privacy` explains stored information; `/forgetme` removes the requesting
  listener's profile and related personal records.
- Likes, saved songs, Get song requests and friend sharing have separate
  controls. Private ratings and locked songs stay out of friend discovery.
- LilCusin stores music profile and interaction data in its local database.
  Shared song metadata can remain for other listeners, and deletion cannot remove
  messages already held by Telegram or records held by external providers.

## Recent project updates

The October 2026 reliability work made slow searches more understandable,
classified source timeouts separately from clean no-match results, bounded
cover-image waiting, and reduced public Mini App artwork and startup transfer
costs by reusing available image variants and HTTP compression/cache validators.
These runtime changes are documented as deployed in the project handoff. The
stricter catalogue-attributed original-recording policy is still local-only.
See [the update and evidence record](evidence.md#2026-10-24---project-overview-and-recent-updates)
for exact status and verification limits.

## Try LilCusin

Start a private chat with the LilCusin Telegram bot and send a song title such
as `Radiohead - Creep`. Confirm the match, then use **Get song**, rate it, or ask
for recommendations. Optional features depend on how the bot is configured.

For setup and configuration, see the [repository README](../README.md),
[recognition notes](../RECOGNITION.md), [Get song guide](../GET_SONG.md), and
[Mini App deployment guide](../MINIAPP_DEPLOYMENT.md).
