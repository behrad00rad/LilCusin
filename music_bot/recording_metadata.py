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



def search_label(artist, title, source='', *, locale='en', limit=52):
    metadata = clean_recording(artist, title, source)
    title = metadata.title
    qualifiers = re.findall(r'\([^()]*\)|\[[^\[\]]*\]', title)
    versions = set().union(*(version_words(part) for part in qualifiers)) if qualifiers else set()
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
    available = max(8, limit-len(prefix))
    title = ' '.join(title.split())
    return prefix + (title if len(title) <= available else title[:available-1].rstrip() + '…')


async def resolve_metadata(track, providers=None):
    artist = getattr(track,'display_artist',None) or track.artist
    title = getattr(track,'display_title',None) or track.title
    source = getattr(track,'metadata_source','')
    result = clean_recording(artist,title,source)
    if source != 'youtube_recording':
        return RecordingMetadata(result.title,result.artist,getattr(track,'album',None))
    fallback = RecordingMetadata(result.title, result.artist if artist.endswith(' - Topic') else '')
    if providers is None:
        return fallback
    # Query public catalogue metadata only for the selected recording, not every list row.
    try:
        async with asyncio.timeout(2):
            rows = await providers.call('itunes','search_titles',result.title)
        matches = {}
        wanted = match_text(result.title)
        for row in rows if isinstance(rows,list) else []:
            if not row.artist or not row.title or version_words(row.title) != version_words(title):
                continue
            if result.artist:
                valid = ((match_text(row.artist) == match_text(result.artist) and match_text(row.title) == wanted)
                         or (match_text(row.title) == match_text(result.artist) and match_text(row.artist) == wanted))
            else:
                valid = wanted in {match_text(row.artist+' '+row.title),match_text(row.title+' '+row.artist)}
            duration = getattr(track,'duration',None)
            if duration and row.duration and duration >= 1 and abs(duration-row.duration) > max(12,duration*.08):
                continue
            if valid:
                matches[(match_text(row.artist),match_text(row.title))] = row
        if len(matches) == 1:
            row = next(iter(matches.values()))
            return RecordingMetadata(row.title,row.artist,getattr(track,'album',None))
    except Exception:
        pass  # Failed lookup never turns a channel name into a song artist.
    return fallback
