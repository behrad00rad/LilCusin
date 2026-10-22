# Shared song cleaner: step 1 - 2026-10-22

Implemented locally only. Both existing search_label and resolve_metadata call
clean_recording. New optional searched_artist/known_artists/channel inputs support
context without treating uploaders as artists. NFKC, separator and packaging cleanup,
Topic/song priority, guarded tight-hyphen parsing and Persian/English fixtures added.
The source module already existed untracked from earlier authorized work; this
commit brings that required module under version control. Unrelated dirty work is
excluded. Existing search-label format and delivery fallback remain until later steps.

Verification: 12 related unittest methods passed (0.027s), including a table of all
12 trace rows, Unicode/Persian cases, credit priority and ezafe preservation. No live
provider calls, database changes, Telegram calls, audio fetches/downloads or deployment.
No new user-facing English/Persian strings in this step. Existing strings unchanged.

Actual before/after search labels below (without new query-context wiring), followed
by cleaner output WITH known searched artist Viguen. This distinction is deliberate:
the new canonical context is not yet persisted or passed by callers.

1. Sogand -> Sogand; cleaner with query context: Viguen / Sogand
2. Viguen-Sogand ویگن ـ سوگند -> Viguen-Sogand; cleaner with query context: Viguen / Sogand
3. Eshegh-e Moghaddas -> Eshegh-e Moghaddas; cleaner with query context: Viguen / Eshegh-e Moghaddas
4. ویگن | Sogand – Vigen | Golden Persian Covers -> ویگن; cleaner with query context: Viguen / سوگند
5. Avazeh Khan -> Avazeh Khan; cleaner with query context: Viguen / Avazeh Khan
6. SOGAND (Oath) Vigen Arranged for Classical Guitar B… -> SOGAND (Oath) Vigen Arranged for Classical Guitar B…; cleaner with query context: Viguen / SOGAND (Oath) Vigen Arranged for Classical Guitar By: Boghrat
7. Mara Beboos (feat. Sogand) -> Mara Beboos (feat. Sogand); cleaner with query context: Ali N. Askin / Mara Beboos (feat. Sogand)
8. VIGEN -> VIGEN; cleaner with query context: Viguen / VIGEN
9. Beevafa -> Beevafa; cleaner with query context: Viguen / Beevafa
10. Chera Nemiraghsi (Offical Audio & Lyrics) | ویگن -… -> Chera Nemiraghsi; cleaner with query context: Viguen / Chera Nemiraghsi
11. Yaadegaary -> Yaadegaary; cleaner with query context: Viguen / Yaadegaary
12. Avazeh Khan | ویگن - آواز خوان -> Avazeh Khan; cleaner with query context: Viguen / Avazeh Khan

Remaining: step 2 duration/title/artist labels, deduplication and demotion; step 3
selection canonical snapshot and exact cached send args; step 4 canonical send/tag
and bounded album/art enrichment; step 5 dry-run local-file cache repair; step 6
end-to-end selection/tag/dry-run integration fixtures. Current delivery can still
emit Unknown artist; this step does not claim that end-to-end issue is fixed.
