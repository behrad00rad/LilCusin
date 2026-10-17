"""Chat-only copy; keep the deferred Mini App unchanged."""
from .i18n import language

COPY = {
    'rate_song': ('Rate a song', 'امتیاز دادن به آهنگ'),
    'rate_prompt': ('Send or forward the song you want to rate. No fingerprint recognition or audio download is needed. If its tags are missing, I’ll ask for the artist and title.\n\nTo identify unknown audio, reply to it with /recognize.', 'آهنگی که می‌خوای امتیاز بدی رو بفرست یا فوروارد کن. برای امتیاز دادن نیازی به تشخیص صوتی یا دانلود دوباره نیست. اگه مشخصاتش ناقص باشه، اسم آهنگ و خواننده رو می‌پرسم.\n\nبرای تشخیص صدای ناشناس، روی فایل /recognize رو ریپلای کن.'),
    'close': ('✕ Close', '✕ بستن'),
    'welcome': ('Forward a song to rate it, or type a song name to search. To identify unknown audio, reply to it with /recognize.\n\nTry: Radiohead - Creep\n\n/rate · /recommend · /setup · /help', 'آهنگ رو برای امتیاز دادن فوروارد کن، یا اسمش رو برای جست‌وجو بنویس. برای تشخیص صدای ناشناس، روی فایل /recognize رو ریپلای کن.\n\nمثلاً: Radiohead - Creep\n\n/rate · /recommend · /setup · /help'),
    'get': ('Get song', 'دریافت آهنگ'),
    'details': ('Details', 'جزئیات'),
    'similar': ('More like this', 'آهنگ‌های مشابه'),
    'versions': ('Other versions', 'نسخه‌های دیگر'),
    'rate': ('Rate this song (optional)', 'امتیاز به آهنگ (اختیاری)'),
    'cancel': ('Cancel', 'لغو'),
    'cancelled': ('Cancelled. You can search for another song.', 'لغو شد. می‌تونی آهنگ دیگه‌ای جست‌وجو کنی.'),
    'queued': ('Your song is queued. I’ll send the audio here.', 'آهنگ در صفه. فایلش رو همین‌جا می‌فرستم.'),
    'searching': ('Finding the recording…', 'دارم نسخهٔ آهنگ رو پیدا می‌کنم…'),
    'fetching': ('Getting the audio…', 'دارم فایل آهنگ رو می‌گیرم…'),
    'sending': ('Sending the audio…', 'دارم فایل آهنگ رو می‌فرستم…'),
    'delivered': ('Audio sent. Rate it if you’d like, or find something similar.', 'فایل آهنگ ارسال شد. اگه خواستی امتیاز بده یا آهنگ مشابه پیدا کن.'),
    'choice': ('Which recording do you want?', 'کدوم نسخه رو می‌خوای؟'),
    'failed': ('Couldn’t get this recording. Retry or choose another version.', 'دریافت این نسخه انجام نشد. دوباره تلاش کن یا نسخهٔ دیگه‌ای انتخاب کن.'),
    'uncertain': ('Delivery could not be confirmed. Check the chat before retrying.', 'ارسال فایل تأیید نشد. قبل از تلاش دوباره، پیام‌های چت رو بررسی کن.'),
    'retry': ('Retry', 'تلاش دوباره'),
    'wrong': ('Wrong recording', 'نسخهٔ اشتباه'),
    'song': ('{artist} — {title}', '{artist} — {title}'),
    'stale': ('That control expired. Choose an action below to continue.', 'این دکمه منقضی شده. برای ادامه یکی از گزینه‌های زیر رو بزن.'),
    'search': ('Search a song', 'جست‌وجوی آهنگ'),
    'recommend': ('For You', 'پیشنهاد برای تو'),
    'lookup': ('Finding your song…', 'دارم آهنگت رو پیدا می‌کنم…'),
    'search_refine': ('Missing your song? Reply to these results with Artist - Song title. Include the artist for common titles or unreleased tracks.', 'آهنگت توی نتایج نیست؟ اسم خواننده و آهنگ رو با قالب «خواننده - آهنگ» به همین پیام ریپلای کن. برای اسم‌های تکراری یا آهنگ‌های منتشرنشده، اسم خواننده رو هم بنویس.'),
    'search_views': ('Discovery suggestions use observed YouTube upload views, not total song plays.', 'نتایج تکمیلی بر اساس بازدید نسخه‌های یوتیوب مرتب شده‌اند؛ این عدد مجموع پخش آهنگ نیست.'),
    'busy': ('Another action is running. You can cancel it below.', 'یک کار دیگه در حال انجامه. می‌تونی از دکمهٔ زیر لغوش کنی.'),
    'guide': ('Forward an audio song to rate it immediately. Missing tags? Type its artist and title when asked.\n\nType a song name to search and get audio. For unknown audio, reply with /recognize. Voice/video clips and public post links can also be identified.\n\n/cancel stops a request; /setup personalizes recommendations.', 'فایل آهنگ رو برای امتیاز دادن بفرست. اگه مشخصاتش ناقص باشه، اسم آهنگ و خواننده رو می‌پرسم.\n\nبرای جست‌وجو و دریافت فایل، اسم آهنگ رو بنویس. برای تشخیص صدای ناشناس، /recognize رو ریپلای کن. ویس، ویدیو و لینک عمومی پست هم قابل تشخیصه.\n\n/cancel برای لغو و /setup برای تنظیم سلیقه است.'),
}


def text(key, **values):
    return COPY[key][1 if language.get() == 'fa' else 0].format(**values)
