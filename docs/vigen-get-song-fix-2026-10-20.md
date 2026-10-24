# Vigen Get song matching - 2026-10-20 (Asia/Tehran)

User impact: Get song on the Vigen/Sogand recommendation offered a 175-second
Sam H upload instead of the 287-second catalogue recording. Read-only production
inspection confirmed that stored candidate had score 0.55, no artist match and
relaxed duration. Title similarity alone met the old threshold. A surviving weak
candidate also prevented broader discovery. Vigen/Viguen spelling differed.

Implemented locally: require artist evidence; resolve artist aliases only from
one MusicBrainz recording identity with exact requested title and artist credit;
reject ambiguous identities. Cache bounded verified alias results. Search without
the restrictive official-audio suffix before relaxing duration. Retain version,
duration, explicit-choice and cancellation checks. This preserves production's
existing broader-search fallback while changing its order. No fuzzy artist
equivalence or song-specific mapping is introduced.

Verification: 24 focused unittest cases passed (test_youtube_search and
test_song_matching_matrix), including wrong-artist rejection, alias ambiguity,
clip/full-length ordering and existing medley cases. The candidate ran in memory
on the VPS against live metadata and found Sogand by Viguen - Topic, 288 seconds,
video dkf9Fvtn7j8, exact/confident, with no duration relaxation. MusicBrainz's
Sogand recording explicitly credits Vigen and includes Viguen as an artist alias.

Initial limits: uncommitted and not deployed during candidate verification; no
audio download, Telegram send or playback verification. Existing saved
source selections remain: use Wrong recording after deployment to bypass the
previously selected upload. Alias recovery depends on external catalogue coverage;
it adds a bounded four-second request only when initial strict matching fails.
Other concurrent checkout changes are outside this fix.

## Approved deployment

User explicitly approved deployment. Only music_bot/youtube_fetch.py was replaced,
preserving the existing broader-search behavior. The original module was backed
up privately; deployed source and service working directory were checked before
switching. The bot was stopped, the candidate installed atomically, and the
existing service restarted. Final Linux SHA-256:
`119e28834797ff5144cf53c2d02a4613b312e6334b091528855a877f3e678038`.
The service and its expected Python module process were confirmed active/running;
private configuration, get_song.py and workflow.py hashes were unchanged.
No Git commit/push, direct database edits or other service changes were performed.

The initial journal check did not establish polling readiness. Subsequent SSH
connections timed out, preventing the post-restart polling-log and live metadata
recheck. The successful live metadata run above used this identical candidate
before installation. Audio receipt/playback remains unverified. Use Wrong
recording to bypass the old saved Sam H source choice; no cached user data was
silently cleared by this release.
