# Bot-first social UI brief — 2026-10-18

Source: the user's supplied bot/Mini App screen outline in this session.
Status: reviewed direction and implementation boundaries; not a claim that these
screens or social features have shipped. Finish the current release first.

## Keep in the first social loop

Bot participation must work without the Mini App. Use concise welcome actions,
explicit ratings, a deliberately selected taste card, comparison invitations,
mutual consent, explainable overlaps/differences and a reciprocal one-song swap
with an optional note, Save/Love/Send one back and accurate save feedback.
Notification preferences, reminder caps, block, report and deletion belong with
the first interactive release. Keep the current dark LilCusin identity, natural
Persian/English, RTL/phone layouts and metadata/link-based lightweight delivery.
No Mini App audio streaming is added.

The visual next slice is a portrait share-card, profile editing/preview, a compare
view and a swap-inbox strip on Home. Do not fabricate social surfaces while those
workflows are absent. The current recommendation/search/channel tools should
remain reachable until real replacement screens exist.

## Corrections and explicit boundaries

- The @nima.lofi example is a proposed chosen display handle, not permission to
  expose the Telegram username. Keep the stable opaque Taste ID separate. A
  custom handle needs uniqueness, rename and abuse rules before implementation.
- A generic shared card is not consent to private-rating comparison. Both parties
  must explicitly approve the comparison's inputs. Start with selected songs.
  Do not reveal 'has not rated' or private Love/Dislike signals without separate
  permission. Sparse data gets an honest insufficient-data state, never a score.
- A forwarded image is copyable and cannot be recalled. Preview before sharing;
  revocation stops link access, not previously forwarded images or screenshots.
  A Compare with me action needs an actual invitation/consent route; the existing
  view-card link must not silently become comparison permission.
- Current link sharing means anyone holding the active link can view it in the
  bot. It is not yet recipient-bound 'Invitation only'. Followers/Public options
  require implemented access rules before offering those controls.
- 47 saves, 12 followers and a 7-week streak are examples, not product data. Show
  only measured, explainable counts, and hide unimplemented metrics.
- People/taste twins, follower feeds, comments, weekly rooms, challenges, badges,
  public reputation totals, shared playlists and sponsorship surfaces remain
  later phases. Do not replace the four-tab navigation with empty destinations.
  Move to Home/Profile/People/Playlists when those destinations are useful.
- Earned badges require actual contribution events and abuse resistance. Cosmetic
  frames must remain visually distinct. Sponsored items must be clearly labeled,
  separated from organic picks and never imply paid trust or contact access.

## Suggested sequence after this deployment

1. Bot onboarding plus the portrait taste-card artifact and exact public preview.
2. Recipient-bound invitations and mutual consent using selected songs only.
3. Explainable comparison and reciprocal swap, with required controls/moderation.
4. Test a small invited cohort for voluntary second exchanges.
5. Add community screens and measured recognition only when activity supports them.

The current deployed slice and its verification must be recorded separately from
this future UI direction. The user requested this review and continuation; that
does not mark any unbuilt screen, metric or later-phase feature complete.
