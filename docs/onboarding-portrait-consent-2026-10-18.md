# Bot onboarding, portrait card and consent invitations

2026-10-18, Asia/Tehran. Implemented and locally checked; **not deployed**.
The user confirmed the preceding Get Song check with “1 is ok”; that is user
confirmation, not a newly observed Telegram delivery in this session.

## Completed scope

- `/start`: two explicit entry paths. Pick five favorites uses message-bound
  search replies and chosen canonical songs without manufacturing ratings.
  Send songs learns from explicit ratings and offers three short recommendations
  after three positive ratings. Every recommendation has Love/Like/Neutral/Dislike.
- `/cardimage`: a 1080×1920 JPEG with the existing owl, palette, Taste ID,
  selected covers, current obsession and one-line bio. Missing artwork has numbered
  placeholders. No fabricated badges or statistics. The Mini App provides an
  authenticated compact preview; the bot supplies the full image. Bundled
  Vazirmatn font retains its OFL license; Pillow plus Persian shaping dependencies
  are required in the next release environment.
- Shared cards can start an explicit sender consent request. A token is bound to
  the named recipient, both card revisions and the chosen-song snapshots.
  The sender deliberately shares the invitation; no unsolicited bot notification
  is sent. Only that recipient can accept or decline; either participant can revoke.
  The Mini App and `/invitations` expose participant-only review and decisions.

## Consent contract

Only selected signature songs and chosen nicknames/Taste IDs are included.
Public invitation responses omit canonical IDs, artwork, bio, private ratings,
listening history and contact details. A public card link alone is not consent.
Invitations expire after 48 hours or the target card link expiry, whichever comes
first. Card edits, hiding, deletion and share-link rotation revoke affected
invitations and clear snapshots. Declining/revoking clears snapshots immediately;
expired snapshots clear on participant access, and expired records older than
seven days are removed on access. Account deletion cascades through invitations
and onboarding. There is no unattended retention job. Duplicate active requests
reuse the same token; creation is capped at five per sender per day.

This slice saves consent only. It does not compute overlap, percentages or scores,
perform swaps, add followers, or claim moderation/cohort readiness. Forwarded
images cannot be recalled. Actual Telegram image forwarding/button retention and
two-account invitation journeys still need verification after deployment.

## Evidence

42 distinct isolated Python tests passed across `test_social_consent` (11),
`test_taste_cards` (12), `test_handlers` (5), `test_miniapp_delivery` (3), and
`test_chat_flow` (11). Runs were scoped batches, with Windows async tests outside
the restricted sandbox. Authenticated portrait previews are valid JPEGs under
the bridge response limit; foreign identities and unauthorized acceptance fail.
Existing aiohttp request-key warnings remain; no failing checks were observed.

Worker taste-card, delivery, bridge and routing checks passed; app syntax passed.
Worker assets regenerated from maintained sources. Real browser checks used
synthetic offline fixtures, not production users: English LTR/Persian RTL at
390×844 and 1440×1000, with content bounds and document width checked.
Document width stayed within the viewport. The browser's RTL full-page capture
was clipped, so the retained Persian screenshot uses a correctly framed viewport.

- [Persian invitation phone screenshot](screenshots/social-invitation-phone-fa.png)
- [English invitation phone screenshot](screenshots/social-invitation-phone-en.png)
- [Persian portrait, synthetic selected songs](screenshots/taste-card-portrait-fa.jpg)
- [English portrait, synthetic selected songs](screenshots/taste-card-portrait-en.jpg)

Changes are uncommitted in the existing dirty checkout. Earlier search/audio,
deployment, workflow and documentation changes were preserved; this record
attributes only the onboarding/portrait/consent additions and scoped checks.
