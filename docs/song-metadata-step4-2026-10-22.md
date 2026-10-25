# Canonical delivery and file tags: step 4 - 2026-10-22

Step 3 committed as c832255: canonical owner selection/request snapshots, exact
successful send arguments and three additive JSON columns. Step 4 now implemented
locally: send fields and local-file MP3/M4A tags consume the same saved snapshot.
Unknown or label artists are omitted from Telegram performer and removed from file
artist tags; known album is written, unknown stale album removed. Existing embedded
covers are preserved. Each pending recipient's snapshot tags the existing local
artifact before sending; no audio source selection, fetch, retry or download change.
The existing cache metadata guard now compares the same request snapshot used for
tagging, so clean files can be reused rather than repeatedly failing that guard.

Clean artist/title metadata lookups run through existing provider interfaces:
iTunes search_titles('artist title') and MusicBrainz search_recordings(artist,title),
independent and bounded to two seconds each. Only unique artist/title corroboration
with duration/version agreement fills optional album/artwork. Selected identities
are frozen; malformed responses/failures leave canonical metadata intact. Explicit
karaoke/cover/instrumental flags survive selection so they cannot inherit original
recording album/artwork. Safe artwork URLs flow through the existing artwork path;
no extra audio download, cookie/provider configuration or fetch mechanism added.

Evidence: step 3's four isolated checks passed. Step 4 ran 26 related methods (7.409s),
then four focused delivery/cache/no-research methods (34.031s): all passed. A final
malformed-provider guard case passed independently (0.163s). Includes a real M4A
created offline from 50ms of silence, title/artist/album/cover round-trip and unknown
artist removal; selection-to-delivery fixture verifies file tags equal send fields
and a second request reuses the clean Telegram file ID with zero fetch/search calls.
Existing atomic tag failure, cover preservation, wrong-source/owner and cross-user
cache timestamp checks passed. Mock invalid-audio fixtures log non-fatal tag warnings.
Syntax/whitespace and exact source-prefix checks confirm the audio fetching portion
of execute is unchanged relative to this session's baseline.

No new English/Persian UI strings. Step 2 labels/before-after list remain in
[song-metadata-step2-2026-10-22.md](song-metadata-step2-2026-10-22.md).
No deployment, actual Telegram send, live provider query or song download occurred.
No native Telegram/player or Linux verification. Already cached Telegram file IDs
cannot have embedded tags rewritten in place: repair remains step 5. Full step 6
acceptance coverage remains pending, though scoped selection/tag integration passes.
Only required metadata/artwork edits are committed; pre-existing dirty audio runtime
and concurrent staged social/UI work remain outside the commits. Tests apply to the
active working checkout, not a pristine committed release artifact.
