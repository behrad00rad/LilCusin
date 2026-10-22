# Canonical selected metadata: step 3 - 2026-10-22

Implemented locally, not deployed. Selection saves cleaned artist/title, duration,
source/video ID, optional album and artwork beside the owner's AudioSelection.
A new AudioRequest snapshots that choice; later preference/enrichment changes do
not re-parse or overwrite the queued metadata. Source-ID validation prevents a
snapshot being reused for another recording. Alternative recording choices capture
a fresh snapshot. Original Track identities/ratings and fetch source choices stay
unchanged. Unknown/label artists are omitted from Telegram performer fields.
Successful AudioDelivery records save the exact title/performer dictionary used.
Three additive JSON columns default old rows to {}; migration is idempotent.

Four focused isolated tests passed (26.180s): legacy migration preservation/repeat,
unknown/label omission and source binding, selected metadata across a new service
instance/later track/preference changes with exact send args persisted, and existing
wrong-owner/expired selection guard. All Telegram/provider/fetch calls mocked;
no real sends/downloads or production/schema changes. No new UI strings.

Commit scope includes the already present recording-selection integration needed
by the snapshots. Other pre-existing get_song changes are deliberately left dirty;
checks describe this active working checkout, not a clean release artifact. File
metadata and clean album/artwork enrichment are step 4; cache repair is step 5.
