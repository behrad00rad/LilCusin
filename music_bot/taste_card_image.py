"""Bounded portrait rendering from the card's deliberately selected projection."""
import asyncio
from io import BytesIO
from pathlib import Path
import unicodedata

from PIL import Image, ImageDraw, ImageFont, ImageOps, features

from .audio_artwork import image_bytes
from .chat_ui import safe_url

ASSETS = Path(__file__).with_name('web')
FONT = ASSETS / 'vazirmatn.ttf'
RAQM = features.check_feature('raqm')
RENDER_SLOTS = asyncio.Semaphore(2)


def display(text):
    text = ''.join(c for c in str(text) if not unicodedata.category(c).startswith('C') or c == '\u200c')
    if RAQM:
        return text
    import arabic_reshaper
    from bidi.algorithm import get_display
    return get_display(arabic_reshaper.reshape(text))


def font(size):
    return ImageFont.truetype(str(FONT), size, layout_engine=ImageFont.Layout.RAQM if RAQM else ImageFont.Layout.BASIC)


def render(card, locale='en', covers=None):
    """1080×1920 Stories image; no arbitrary filesystem paths, HTML or user IDs."""
    covers = covers or {}
    rtl = locale in {'fa', 'ar'}
    image = Image.new('RGB', (1080, 1920), '#101115')
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((42, 42, 1038, 1878), 56, fill='#1b2130', outline='#41404c', width=2)
    draw.rounded_rectangle((82, 84, 998, 1838), 36, outline='#343948', width=1)
    draw.line((110, 560, 970, 560), fill='#a47587', width=4)

    def line(text, x, y, size, width, color='#f0efeb', align='left'):
        raw = str(text or '')[:500]
        chosen = font(size)
        shown = display(raw)
        while draw.textlength(shown, font=chosen) > width and raw:
            raw = raw[:-1]
            shown = display(raw.rstrip() + '…')
        anchor = 'rt' if align == 'right' else 'mt' if align == 'center' else 'lt'
        draw.text((x, y), shown, font=chosen, fill=color, anchor=anchor)

    with Image.open(ASSETS / 'bot-logo.jpg') as logo:
        logo = ImageOps.fit(logo.convert('RGB'), (100, 100))
        mask = Image.new('L', (100, 100));ImageDraw.Draw(mask).ellipse((0, 0, 100, 100), fill=255)
        image.paste(logo, (490, 130), mask)
    line('LIL CUSIN', 540, 260, 29, 700, '#b7becd', 'center')
    line(card['taste_id'], 540, 322, 32, 850, '#c9b5bf', 'center')
    line(card['nickname'] or ('نام نمایشی تو' if rtl else 'Your nickname'), 540, 414, 69, 830, align='center')
    line('آهنگ‌هایی که مرا معرفی می‌کنند' if rtl else 'A FEW SONGS THAT FEEL LIKE ME',
         540, 615, 30, 850, '#b6bdcb', 'center')

    songs = card['songs'][:5]
    for index in range(5):
        left = 98 + index * 180
        draw.rounded_rectangle((left, 710, left + 164, 874), 19, fill='#303b50')
        if index < len(songs):
            song = songs[index]
            try:
                with Image.open(BytesIO(covers[index])) as source:
                    if source.width * source.height > 12_000_000 or source.format not in {'JPEG', 'PNG', 'WEBP', 'AVIF'}:
                        raise ValueError('Unsupported cover')
                    thumb = ImageOps.fit(source.convert('RGB'), (164, 164))
                mask = Image.new('L', (164, 164));ImageDraw.Draw(mask).rounded_rectangle((0, 0, 164, 164), 19, fill=255)
                image.paste(thumb, (left, 710), mask)
            except (KeyError, OSError, ValueError, Image.DecompressionBombError):
                line(f'{index + 1:02}', left + 82, 764, 33, 140, '#b6bdcb', 'center')
            line(song['title'], left + 82, 903, 22, 166, align='center')
            line(song['artist'], left + 82, 948, 20, 166, '#b6bdcb', 'center')
        else:
            line(f'{index + 1:02}', left + 82, 764, 33, 140, '#778298', 'center')

    x, align = (964, 'right') if rtl else (116, 'left')
    line('این روزها روی تکرار' if rtl else 'CURRENT OBSESSION', x, 1120, 30, 848, '#c9b5bf', align)
    current = card.get('current')
    line(current['title'] if current else ('هنوز انتخاب نکرده‌ام' if rtl else 'Still finding my next obsession'),
         x, 1190, 47, 848, align=align)
    if current:
        line(current['artist'], x, 1267, 31, 848, '#b6bdcb', align)
    draw.line((116, 1376, 964, 1376), fill='#414553', width=2)
    line(card.get('bio') or ('موسیقی من، به انتخاب خودم.' if rtl else 'My music, chosen by me.'),
         x, 1450, 37, 848, align=align)
    line('آدم‌های هم‌سلیقه‌ات را پیدا کن' if rtl else 'Find your people through music.',
         540, 1715, 31, 820, '#c9b5bf', 'center')
    # Badges and counts are intentionally absent until real earned data exists.
    output = BytesIO();image.save(output, 'JPEG', quality=88, optimize=True)
    return output.getvalue()


async def portrait(card, locale='en'):
    async with RENDER_SLOTS:
        covers = {}
        async def load(index, song):
            url = safe_url(song.get('artwork'), artwork=True)
            if url:
                try:
                    covers[index] = await image_bytes(url)
                except (OSError, ValueError, TimeoutError):
                    pass
                except Exception:
                    pass  # Unavailable artwork is represented by the deliberate fallback.
        try:
            async with asyncio.timeout(6):
                await asyncio.gather(*(load(i, song) for i, song in enumerate(card['songs'][:5])))
        except TimeoutError:
            pass
        return await asyncio.to_thread(render, card, locale, covers)


def small_preview(data):
    """Keep the JSON bridge response below its existing 64 KiB limit."""
    with Image.open(BytesIO(data)) as source:
        image = source.resize((540, 960), Image.Resampling.LANCZOS)
    for quality in [78, 65, 50, 35]:
        output = BytesIO();image.save(output, 'JPEG', quality=quality, optimize=True)
        if len(output.getvalue()) <= 45000:
            return output.getvalue()
    image.thumbnail((270, 480))
    output = BytesIO();image.save(output, 'JPEG', quality=60, optimize=True)
    return output.getvalue()
