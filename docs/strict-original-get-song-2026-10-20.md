# Catalogue-attributed Get song sources - 2026-10-20 (Asia/Tehran)

## Problem and decision

The deployed artist-evidence fix was insufficient. Read-only production inspection
confirmed Dele Divaneh/Vigen (catalogue duration 264 seconds) had offered Sam
Shirazi's unlabelled 248-second upload HrPVLTdyaS8 as an uncertain choice. Vigen
in an upload title established search relevance, not actual performer/source
attribution. The user reported instrumental audio; the agent inspected metadata,
not that audio. Its lack of an instrumental label explains why word filters did
not catch it. Earlier metadata confidence must not be treated as original-audio
verification.

Normal Get song now accepts only exact artist/track catalogue attribution on a
distributor-supplied, auto-generated Topic source, or an attributed verified
artist channel. Album edition labels also participate in version rejection.
An artist/channel name or rich track metadata alone is insufficient. The existing
explicit Find other versions action remains the route to unverified alternatives;
it always requires manual choice and stamps that authorization separately.
That authorization does not make an unlabelled alternative reusable as the normal
original on a later Get song request.
This trades coverage for fewer misleading original-recording choices. Verified
Vigen/Viguen catalogue aliases and bounded broader discovery remain supported.

## Implementation and recovery

Three runtime files change: youtube_fetch.py, get_song.py and bot_copy.py.
The source rule applies to search output, stored candidates, manual callbacks,
preferred sources and cached sends. Legacy unverified preferences are cleared
on the requesting user's next Get song action; cached records remain intact
but cannot be reused without current source-policy evidence. English/Persian
failure copy explains that an original could not be verified and points to
explicit alternatives. No direct production data edits or bulk cache deletion.

The production-checked [three-file patch](patches/strict-original-get-song-2026-10-20.patch)
preserves unrelated deployed changes. git apply --check succeeded against current
production sources without applying it. Patch SHA-256:
`dc478700a1b18a33229929d1361c16c028a9397d5dd2c6a72b67c72d46c3925d`.

## Verification and limits

78 distinct affected cases passed across runs: search, Get song and song-matching
matrix. Initial sandbox fixture access failed; the unrestricted affected run
passed 77/78, with one obsolete copy assertion. That assertion was corrected;
the affected failure/cache/alternative paths then passed a three-case rerun.
The final cache-separation change passed 27 search and targeted cache/failure
checks, and the final patch passed production apply checking again.
No broad application suite was run.

The candidate source policy ran in VPS memory with metadata-only public searches:
Dele Divaneh returned Viguen Topic catalogue releases at 255 and 269 seconds;
Sogand returned its 284-second Viguen Topic release. The reported Sam Shirazi
and Sam H uploads were excluded from normal results. Dele Divaneh retains manual
choice because duration/edition ambiguity remains. No audio was downloaded or
played, and no Telegram message was sent.

Implemented locally, uncommitted and not deployed. Catalogue attribution is not
waveform fingerprinting or vocal verification: incorrectly attributed distributor
metadata remains a limitation. Catalogue coverage failures now abstain rather
than offer an unverified upload as the normal song. This stricter policy supersedes
the earlier slice's reliance on Wrong recording to avoid legacy cached choices.
