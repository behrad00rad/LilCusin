# Local rating lookup recovery — 2026-10-17 (Asia/Tehran)

Historical verification record; subsequent source publication and journal status
are tracked in the [release record](chat-release-2026-10-17.md).

The user reported a music-search outage message after uploading a file for rating.
Read-only local inspection confirmed that the last submission was audio with a
long performer tag and no accepted catalogue match. No private metadata was
replayed externally. Public sample probes confirmed the configured Last.fm key
is rejected, while MusicBrainz and iTunes return catalogue results.

The artist/title search previously retained a failure flag after another provider
successfully returned an empty response. This incorrectly presented an outage
instead of asking for usable identity information. The workflow now distinguishes
total provider failure from healthy no-match responses. An unmatched audio upload
asks for corrected artist/title tags; text searches retain the no-match response.
MusicBrainz and enabled independent fallback catalogues now run concurrently after
the primary attempt, within the existing provider and overall chat time budgets.
Strong primary matches still avoid fallback calls. No fingerprinting is added.

Verification: 75 workflow, handler, recognition and flow-upgrade regressions
passed in 162.447 seconds. An independent focused run passed 27 tests, including
four new regressions for partial failure, total outage, concurrent fallbacks and
corrected audio tags. Compilation and scoped whitespace checks passed. A public
Adele/Hello sample returned five matches in 1.51 seconds with the primary source
deliberately rejected, using the actual bounded workflow and temporary database.
This is a single sample, not a general latency benchmark. No active test downloads
were present before restarting only the exact isolated local launcher.
The rejected Last.fm credential remains unresolved; no credentials were copied
from another environment. Independent catalogue coverage is not universal.
Existing user edits, production, and Mini App files are outside this change.

## Expanded performer credits

The user supplied the expected identity: Starting Over by LSD and the Search for
God. Local inspection confirmed an exact title tag, but the performer tag appended
two musician credits. Strict artist-qualified lookups used that entire string;
the previous outage-message correction did not fix this identity recovery problem.

Uploaded audio with no qualified match now gets one bounded title-only recovery
round through MusicBrainz and enabled independent catalogues. Candidates require
an exact normalized title and an artist equal to or at the start of the original
performer tag. Recovery requires explicit selection, preserves original tags, and
adds no fingerprinting or file download. Unrelated artists are excluded.

Live metadata-only checks for the user-supplied song found the exact iTunes match;
the first 100 MusicBrainz title results omitted it. The actual recovery path found
one matching candidate in 0.80 seconds within the existing chat budgets. This
single sample does not establish general provider coverage or typical latency.

Expanded-tag regression verification: all 50 flow-upgrade and workflow tests
passed in 164.577 seconds, including the exact expanded-credits fixture, exclusion
of unrelated artists, explicit confirmation, no background warming, cancellation,
ownership and correction recovery. Compilation and scoped whitespace checks
passed. Only the isolated local bot was restarted after confirming no active
downloads. The shared Work Journal lock was held, so journal appending was deferred;
no Notion publication was attempted. All changes remain uncommitted.
