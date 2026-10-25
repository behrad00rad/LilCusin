# Song result presentation: step 2 - 2026-10-22

Implemented locally; not deployed. Search rows now show duration (when known), a
clean title and artist. The existing edition/venue prefix stays visible. Raw source
fields and source IDs are retained, with a separate recording_metadata display
snapshot serialized by the existing candidate encoder. This is not yet delivery
canonical persistence: workflow selection and send_audio still use their old paths.

Deduplication uses normalized artist/title plus edition distinctions, preferring
Music songs over videos and Topic over label channels. Upload-only supplement
metadata is retained for the same video so an abbreviated Music-video title can
recover explicit credits. Covers, karaoke, instrumental arrangements, long/mixed
compilations and mismatched artists move behind the main choices. Non-song artist
name/singer clips are hidden. Artist context requires a catalogue/Topic credit in
the query, and a complete catalogue title suppresses artist inference. Explicit
version queries retain alternatives. No additional provider call was introduced.

Paging uses virtual display slots so a sparse first page never fills with demoted
rows. Stored choice indices and source IDs remain unchanged; More songs can reach
alternatives even when there are fewer than five primary choices. Existing owner,
message, revision, cancellation and 60-candidate bounds are preserved.

Checks: 40 distinct related unittest methods passed across scoped runs. Initial
38-case run had two obsolete whole-candidate equality expectations, since candidates
now carry an extra display snapshot; fixed those expectations to compare source
identity. Only those two, one new sparse-page DB case, and seven lightweight result
cases were rerun. No live provider, Telegram, audio fetch/download, Linux/VPS or
client checks. Audio fetching modules and download behavior were not edited.

New strings for review: row layout `4:15 • Sogand — Viguen` (same separators in
Persian; duration omitted when unknown, artist omitted when unknown). No new
translated phrases. Existing More songs/بیشتر, Previous/قبلی and version labels
(Karaoke/کارائوکه, Cover/کاور, Instrumental/بی‌کلام) reused. Removed the obsolete
view-count explanatory heading because rows no longer show view counts.

Before/after labels for the twelve trace fixtures (durations omitted here because
these are text fixtures, not live duration measurements):

1. Sogand -> Sogand — Viguen [primary; maximum five on first page]
2. Viguen-Sogand -> Sogand — Viguen [merged with #1 (Music wins)]
3. Eshegh-e Moghaddas -> Eshegh-e Moghaddas — Viguen [primary; maximum five on first page]
4. ویگن -> Cover · سوگند — Viguen [More songs: alternative]
5. Avazeh Khan -> Avazeh Khan — Viguen [primary; maximum five on first page]
6. SOGAND (Oath) Vigen Arranged for Classical Guitar B… -> Instrumental · SOGAND (Oath) Vigen Arranged for Classi… — Viguen [More songs: alternative]
7. Mara Beboos (feat. Sogand) -> Mara Beboos (feat. Sogand) — Ali N. Askin [More songs: alternative]
8. VIGEN -> (hidden) [hidden: non-song]
9. Beevafa -> Beevafa — Viguen [primary; maximum five on first page]
10. Chera Nemiraghsi -> Chera Nemiraghsi — Viguen [primary; maximum five on first page]
11. Yaadegaary -> Yaadegaary — Viguen [primary; maximum five on first page]
12. Avazeh Khan -> Avazeh Khan — Viguen [merged with #5 (Music wins)]

The separate karaoke and singer fixtures are respectively demoted and hidden.
Remaining: steps 3-6 canonical selection-to-delivery persistence, exact cached send
arguments, unknown-performer omission/tagging/enrichment, dry-run local-file cache
repair and end-to-end delivery/M4A tests. No deployment or send is authorized.
