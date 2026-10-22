"""Presentation/tag metadata; never rewrites recording identity or source selection."""
import asyncio
from dataclasses import dataclass
import re
from .matching import match_text
from .youtube_fetch import version_words

# Metadata cleanup never changes source IDs or establishes original-recording provenance.
PACKAGING = r'(?:offic(?:i)?al(?:\s+(?:music\s+)?(?:video|audio))?(?:\s*(?:&|and)\s*lyrics?)?|music video|video|audio|lyrics?|lyric video|visuali[sz]er|hd|hq|[48]k|persian karaoke|کارائوکه(?:\s+فارسی)?)'

@dataclass(frozen=True)
class RecordingMetadata:
    title: str
    artist: str
    album: str | None = None
    artwork_url: str | None = None
    versions: tuple[str, ...] = ()


def normalized(value):
    import unicodedata
    value = unicodedata.normalize('NFKC', value or '')
    value = value.translate(str.maketrans({'ـ':'|', '–':'-', '—':'-', '｜':'|'}))
    return ' '.join(value.split())


def artist_key(value):
    key = match_text(normalized(value))
    # Common spelling variants for the same artist, not title transliteration.
    return {'vigen':'viguen', 'ویگن':'viguen'}.get(key, key)


def artist_matches(left, right):
    from difflib import SequenceMatcher
    a, b = artist_key(left), artist_key(right)
    return bool(a and b and (a == b or (len(a) >= 4 and len(b) >= 4
        and SequenceMatcher(None, a, b).ratio() >= .88)))


def label_credit(value):
    return bool(re.search(r'\b(?:unverified|unknown artist|records?|enterprise|compilation|covers?|channel|lyrics)\b', value or '', re.I)
        or re.search(r'(?:taranehenterprise|caltex)', value or '', re.I))


def clean_recording(artist, title, source='', *, searched_artist=None, known_artists=(), channel=None):
    """One cleaner for discovery and delivery; raw channels are never artist credits."""
    artist, title = normalized(artist), normalized(title)
    original_title = title
    upload = source == 'youtube_recording'
    youtube = source in {'youtube_music', 'youtube_recording'}
    topic = re.sub(r'\s*-\s*Topic$', '', normalized(channel or artist), flags=re.I)
    topic = topic if re.search(r'\s*-\s*Topic$', normalized(channel or artist), re.I) else ''
    trusted = (topic or artist) if not upload and not label_credit(topic or artist) else ''
    credit = trusted or (topic if not label_credit(topic) else '')
    known = [a for a in [trusted, topic, searched_artist, *known_artists] if a and not label_credit(a)]
    if youtube:
        # Later pipe segments are upload credits, duplicated bilingual text or hashtags.
        title = title.split('|', 1)[0].strip()
        title = re.sub(r'#\S+', '', title).strip()
        title = re.sub(r'\s*[(\[]\s*' + PACKAGING + r'\s*[)\]]', '', title, flags=re.I)
        title = re.sub(r'\s+(?:[-|]\s*)?' + PACKAGING + r'\s*$', '', title, flags=re.I).strip(' -|')
        if not (trusted or topic):
            title = re.sub(r'\s+(?:ft\.?|feat\.?|featuring)\s+.*$', '', title, flags=re.I)
        title = re.sub(r'\s*(?:[-|]\s*)?cover by\s+.*$', '', title, flags=re.I).strip()
        # A bilingual upload repeats credits without a pipe before the Persian copy.
        if re.search(r'[A-Za-z]', title) and re.search(r'[\u0600-\u06ff]', title) and ('-' in title or '|' in original_title):
            title = re.sub(r'\s+[\u0600-\u06ff].*$', '', title).strip()
    # Spaced credits are explicit. Tight hyphens require a corroborating known artist.
    parts = re.split(r'\s+-\s+', title, maxsplit=1)
    if len(parts) == 1:
        for match in re.finditer('-', title):
            left, right = title[:match.start()].strip(), title[match.end():].strip()
            if any(artist_matches(left, a) or artist_matches(right, a) for a in known):
                parts = [left, right]
                break
    if len(parts) == 2 and not re.fullmatch(PACKAGING, parts[1], re.I):
        left, right = parts
        reverse = next((a for a in known if artist_matches(right, a)), None)
        prefix = next((a for a in known if artist_matches(left, a)), left)
        if reverse:
            title, parsed = left, reverse
        elif not label_credit(prefix) and (upload or any(artist_matches(left, a) for a in known)):
            title, parsed = right, prefix
        else:
            parsed = ''
        credit = credit or parsed
    if not credit and searched_artist and not label_credit(searched_artist):
        tokens = title.split()
        width = len(normalized(searched_artist).split())
        if any(artist_matches(' '.join(tokens[i:i+width]).strip(' -:(),'), searched_artist)
               for i in range(len(tokens)-width+1)):
            credit = normalized(searched_artist)
            prefix = re.match(re.escape(credit) + r'(?:\s+|[-:])', title, re.I)
            if prefix:
                title = title[prefix.end():]
    while credit:
        updated = re.sub(r'^' + re.escape(credit) + r'\s*[-:]\s*', '', title, count=1, flags=re.I)
        if updated == title:
            break
        title = updated
    title = ' '.join(title.split()).strip(' -|')
    return RecordingMetadata(title or original_title or 'Untitled', credit)



def search_label(artist, title, source='', *, locale='en', limit=64, duration=None, metadata=None, flags=()):
    metadata = metadata or clean_recording(artist, title, source)
    title = metadata.title
    qualifiers = re.findall(r'\([^()]*\)|\[[^\[\]]*\]', title)
    versions = (set().union(*(version_words(part) for part in qualifiers)) if qualifiers else set()) | set(flags)
    suffix = re.search(r'\b(live|acoustic|remix|instrumental|cover|karaoke|remaster(?:ed)?|slowed|sped up)(?:\s+(?:at|in)\b.*)?$', title, re.I)
    if suffix and suffix.start() > 0:
        versions |= version_words(suffix[0])
    if versions:
        title = re.sub(r'\([^()]*\)|\[[^\[\]]*\]', lambda m: '' if version_words(m[0]) else m[0], title).strip()
        if suffix:
            title = re.sub(re.escape(suffix[0]) + r'$', '', title, flags=re.I).strip(' -–—|')
    labels = {'live':'اجرای زنده','acoustic':'آکوستیک','remix':'ریمیکس','instrumental':'بی‌کلام','cover':'کاور','karaoke':'کارائوکه','remaster':'ریمستر','slowed':'آهسته','sped':'تند'}
    order = {'live':0,'instrumental':1,'cover':2,'remix':3}
    edition = ', '.join(labels.get(value,value) if locale == 'fa' else value.title() for value in sorted(versions,key=lambda v:order.get(v,10)))
    context = next((part[1:-1].strip() for part in qualifiers if version_words(part)), None)
    if context and locale != 'fa':
        edition = context
    if len(edition) > 24:
        edition = edition[:23].rstrip() + '…'
    prefix = edition + ' · ' if edition else ''
    import math
    duration_text = ''
    if isinstance(duration, (float, int)) and not isinstance(duration, bool) and math.isfinite(duration) and duration > 0:
        seconds = int(duration)
        duration_text = f'{seconds // 60}:{seconds % 60:02d} • '
    artist = metadata.artist
    artist = artist if len(artist) <= 22 else artist[:21].rstrip() + '…'
    suffix = ' — ' + artist if artist else ''
    available = max(8, limit-len(prefix)-len(duration_text)-len(suffix))
    title = ' '.join(title.split())
    title = title if len(title) <= available else title[:available-1].rstrip() + '…'
    return duration_text + prefix + title + suffix


def result_metadata(row):
    saved = row.recording_metadata
    if saved.get('version') == 1:
        return RecordingMetadata(saved['title'], saved['artist'], saved.get('album'))
    return clean_recording(row.artist, row.title, row.source)


def query_artist(query, rows):
    """Infer context only from catalogue/Topic credits actually present in the query."""
    if any(row.source == 'youtube_music' and match_text(row.title or '') == match_text(query) for row in rows):
        return None  # A complete catalogue title is not evidence for an artist-qualified query.
    tokens = normalized(query).split()
    choices = []
    for row in rows:
        if row.source == 'youtube_music' or re.search(r'-\s*Topic$', row.artist or '', re.I):
            artist = clean_recording(row.artist, row.title, row.source).artist
            width = len(artist.split())
            if width and len(tokens) > width and any(artist_matches(' '.join(tokens[i:i+width]).strip(' -:'), artist)
                    for i in range(len(tokens)-width+1)):
                if not any(artist_matches(artist, other) for other in choices):
                    choices.append(artist)
    return choices[0] if len(choices) == 1 else None


def prepare_results(query, rows, *, searched_artist=None):
    """Clean/dedupe discovery once, keeping raw source fields and alternative recordings."""
    from dataclasses import replace
    searched_artist = searched_artist or query_artist(query, rows)
    known = [clean_recording(r.artist, r.title, r.source).artist for r in rows if r.source == 'youtube_music']
    primary, alternatives, positions = [], [], {}
    explicit_versions = bool(re.search(r'\b(?:live|concert|cover|karaoke|instrumental|mix|compilation)\b|کاور|کارائوکه|بی.کلام|گلچین|اجرای زنده', query, re.I))
    for row in rows:
        raw = row.recording_metadata
        raw_title = raw.get('raw_title', row.title) or ''
        channel = raw.get('channel', row.artist) or ''
        clean = clean_recording(row.artist, row.title if row.source == 'youtube_music' else raw_title,
            row.source, searched_artist=searched_artist, known_artists=known, channel=channel)
        text = raw_title + ' ' + channel
        flags = set()
        if re.search(r'\bkaraoke\b|کارائوکه', text, re.I): flags.add('karaoke')
        if re.search(r'\bcovers?\b|کاور', text, re.I): flags.add('cover')
        if re.search(r'\binstrumental\b|classical guitar|بی.کلام', text, re.I): flags.add('instrumental')
        compilation = bool((row.duration and row.duration > 480) or re.search(r'\b(?:mix|best of|non[- ]?stop|compilation)\b|گلچین', text, re.I))
        non_song = bool(searched_artist and (artist_matches(clean.title, searched_artist)
            or re.fullmatch(r'.*\b(?:iranian|persian)\s+singer\b.*', raw_title, re.I)))
        if non_song:
            continue
        mismatch = bool(searched_artist and not artist_matches(clean.artist, searched_artist))
        demoted = bool(not explicit_versions and (flags or compilation or mismatch))
        saved = {**raw, 'version':1, 'artist':clean.artist, 'title':clean.title, 'album':row.album,
            'duration':row.duration, 'source_id':row.external_ids.get('youtube'),
            'flags':sorted(flags), 'demoted':demoted, 'searched_artist':searched_artist}
        row = replace(row, recording_metadata=saved)
        # Editions cannot disappear into an original-song duplicate.
        key = (artist_key(clean.artist), match_text(clean.title), tuple(sorted(flags)), tuple(sorted(version_words(raw_title))))
        bucket = alternatives if demoted else primary
        quality = (row.source == 'youtube_music', bool(re.search(r'-\s*Topic$', channel, re.I)), not label_credit(channel))
        if key in positions:
            previous_bucket, index, old_quality = positions[key]
            if quality > old_quality:
                previous_bucket[index] = row
                positions[key] = (previous_bucket, index, quality)
        else:
            positions[key] = (bucket, len(bucket), quality)
            bucket.append(row)
    return primary + alternatives


def result_pages(rows):
    """Virtual slots leave the first page clean without changing physical choice indices."""
    main = [i for i, r in enumerate(rows) if not r.recording_metadata.get('demoted')]
    other = [i for i, r in enumerate(rows) if r.recording_metadata.get('demoted')]
    start = max(5, ((len(main)+4)//5)*5) if other else len(main)
    slots = dict(enumerate(main))
    slots.update({start+i:index for i,index in enumerate(other)})
    return slots, (start+len(other) if other else len(main))


async def resolve_metadata(track, providers=None, *, canonical=None):
    """Enrich optional fields; a selected canonical identity is never re-parsed."""
    from .chat_ui import safe_url
    from .providers.common import TrackCandidate
    artist = getattr(track,'display_artist',None) or track.artist
    title = getattr(track,'display_title',None) or track.title
    source = getattr(track,'metadata_source','')
    parsed = clean_recording(artist,title,source) if canonical is None else canonical
    fallback_artist = parsed.artist if canonical is not None or source != 'youtube_recording' or artist.endswith(' - Topic') else ''
    base = canonical or RecordingMetadata(parsed.title, fallback_artist, getattr(track,'album',None),
        safe_url(getattr(track,'artwork_url',None),artwork=True))
    if providers is None or (base.album and safe_url(base.artwork_url,artwork=True)):
        return base
    # The clean artist/title query is metadata-only, independent of audio retrieval.
    query = ' '.join(filter(None,[parsed.artist,parsed.title]))
    async def lookup(provider, method, *args):
        try:
            async with asyncio.timeout(2):
                rows = await providers.call(provider, method, *args)
            return rows if isinstance(rows,list) else []
        except Exception:
            return []
    groups = await asyncio.gather(lookup('itunes','search_titles',query),
        lookup('musicbrainz','search_recordings',parsed.artist,parsed.title))
    matches = {}
    wanted_versions = set(base.versions) | version_words(parsed.title)
    for rows in groups:
        for row in rows:
            if not isinstance(row,TrackCandidate) or not row.artist or not row.title or label_credit(row.artist) or version_words(row.title) != wanted_versions:
                continue
            if parsed.artist:
                direct = artist_matches(row.artist,parsed.artist) and match_text(row.title) == match_text(parsed.title)
                reverse = canonical is None and artist_matches(row.artist,parsed.title) and match_text(row.title) == match_text(parsed.artist)
                valid = direct or reverse
            else:
                valid = match_text(parsed.title) in {match_text(row.artist+' '+row.title),match_text(row.title+' '+row.artist)}
            duration = getattr(track,'duration',None)
            if duration and row.duration and abs(duration-row.duration) > max(12,duration*.08):
                continue
            if valid:
                matches.setdefault((artist_key(row.artist),match_text(row.title)),[]).append(row)
    if len(matches) != 1:
        return base
    rows = next(iter(matches.values()))
    row = rows[0]
    album = base.album or next((r.album for r in rows if r.album),None)
    art = safe_url(base.artwork_url,artwork=True) or next((safe_url(r.artwork_url,artwork=True) for r in rows if safe_url(r.artwork_url,artwork=True)),None)
    return RecordingMetadata(base.title if canonical is not None else row.title,
        base.artist if canonical is not None and base.artist else row.artist, album, art, base.versions)


def canonical_snapshot(candidate, *, searched_artist=None):
    """Freeze display metadata for this selected source; never mutate catalogue keys."""
    saved = candidate.recording_metadata
    metadata = result_metadata(candidate) if saved.get('version') == 1 else clean_recording(
        candidate.artist, candidate.title, candidate.source, searched_artist=searched_artist)
    return {'version':1, 'artist':metadata.artist, 'title':metadata.title,
        'duration':candidate.duration, 'source_id':candidate.external_ids.get('youtube'),
        'source':candidate.source, 'album':candidate.album, 'artwork_url':candidate.artwork_url,
        'flags':saved.get('flags',[])}


def snapshot_metadata(snapshot, video=None):
    if (not isinstance(snapshot, dict) or snapshot.get('version') != 1
            or not isinstance(snapshot.get('title'), str) or not snapshot['title'].strip()
            or (video is not None and snapshot.get('source_id') != video)):
        return None
    artist = snapshot.get('artist') or ''
    if not isinstance(artist, str) or label_credit(artist):
        artist = ''
    return RecordingMetadata(snapshot['title'], artist, snapshot.get('album'), snapshot.get('artwork_url'), tuple(snapshot.get('flags') or ()))


def telegram_fields(metadata):
    fields = {'title':metadata.title}
    if metadata.artist and not label_credit(metadata.artist):
        fields['performer'] = metadata.artist
    return fields
