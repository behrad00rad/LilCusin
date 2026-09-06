"""All user-facing bot text; future translations belong here."""

START = (
    "Hi! This bot will learn your music taste from songs you submit. "
    "Send a Telegram audio message or text as Artist - Song title. "
    "I’ll look for a match, ask you to confirm when needed, then ask how you feel about it. "
    "Recommendations are still under development."
)
HELP = (
    "Recommendation functionality is still under development. "
    "Send an audio message (forwarded audio works too) or Artist - Song title. "
    "Choose a match or None of these, then rate it. Submitting does not rate a song. "
    "Reply directly to a correction prompt with Artist - Song title. "
    "Use /cancel to end open identification flows. Please use a private chat."
)

INVALID_TEXT = "Use this format: Artist - Song title"
UNSUPPORTED = "Send a Telegram audio message or text as Artist - Song title."
NO_USER = "Please submit songs from your personal Telegram account."
SAVE_FAILED = "Could not save your submission. Please try again."
PENDING = "Received. Looking for a matching song…"
UNKNOWN = "Not provided"
TEXT_RECEIVED = "Artist: {artist}\nTitle: {title}\n\n" + PENDING
AUDIO_RECEIVED = (
    "Telegram audio metadata:\nArtist: {artist}\nTitle: {title}\n"
    "Duration (seconds): {duration}\nFilename: {filename}\n"
    "MIME type: {mime_type}\nFile size (bytes): {file_size}\n\n" + PENDING
)


def audio_received(audio) -> str:
    def display(value):
        # Keep replies below Telegram's message limit even with long metadata.
        return str(value)[:400] if value is not None else UNKNOWN

    return AUDIO_RECEIVED.format(
        artist=display(audio.performer), title=display(audio.title),
        duration=display(audio.duration), filename=display(audio.filename),
        mime_type=display(audio.mime_type), file_size=display(audio.file_size),
    )


def text_received(artist: str, title: str) -> str:
    return TEXT_RECEIVED.format(artist=artist[:1000], title=title[:1000])


PRIVATE_ONLY = "Please send songs and use these buttons in a private chat with me."
CHOOSE = "Which song did you mean? These are possible matches."
NONE = "None of these"
CORRECTION = "Reply directly to this message with Artist - Song title, or use /cancel. Identification expires 30 minutes after it starts."
MISSING = "The audio needs an artist and title. " + CORRECTION
NOT_FOUND = "No suitable match found. " + CORRECTION
PROVIDER_FAILED = "Music metadata is temporarily unavailable. You can retry with a correction. " + CORRECTION
LIMIT = "The three search attempts are used up. Your submission is saved. Send a new submission to try again."
STALE = "This action is expired, cancelled, or unavailable for your account. Send a new submission to try again."
CANCELLED = "Open identification flows cancelled. Your saved submissions and ratings are kept."
WORKING = "Done."
RATING_QUESTION = "How do you feel about this song?"
RATING_SAVED = "Rating saved."
RATING_LABELS = {"love": "❤️ Love", "like": "👍 Like", "neutral": "😐 Neutral", "dislike": "👎 Dislike"}
FLOW_FAILED = "Could not complete that action. Your saved submission is kept. Please try again."


def candidate_label(artist, title):
    return f"{artist[:40]} — {title[:55]}"


def rating_prompt(artist, title):
    return f"Matched: {artist[:500]} — {title[:500]}\n\n{RATING_QUESTION}"


def rating_label(value, selected):
    return ("✓ " if value == selected else "") + RATING_LABELS[value]


AUDIO_ANALYSIS_FAILED = "Local audio analysis could not finish for this file. Your confirmed song and rating are kept."
AUDIO_BPM_UNKNOWN = "Audio analysis complete. A BPM estimate could not be obtained."


def audio_analysis_complete(bpm):
    if bpm is None:
        return AUDIO_BPM_UNKNOWN
    return (f"Audio analysis complete.\nEstimated BPM: {bpm:.0f}\n\n"
            "BPM is an estimate and may occasionally be detected at half or double tempo.")


REC_SIMILAR_LOVE = "Similar to a song you loved"
REC_SIMILAR_LIKE = "Similar to a song you liked"
REC_TAGS = "Matches several tags from a song you liked"
REC_SHARED_TAG = "Shares a tag with a song you liked"
REC_TEMPO_TAGS = "Close in tempo and shared tags to two songs you rated positively"
REC_TEMPO = "Close in tempo to a song you liked"
REC_AUDIO = "Shares measured audio characteristics with a song you liked"
REC_ARTIST = "Same artist as a song you liked"
REC_RELATED_ARTIST = "An artist connected to your liked songs through similar-track metadata"
REC_INSUFFICIENT = "insufficient_preferences: rate at least one song Love or Like first."
REC_EMPTY = "no_candidates: no fresh, unrated matches are available from the current metadata."
