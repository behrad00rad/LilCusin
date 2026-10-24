"""Five-round friend game. Persisted answers never cross the round projection."""
import re
import secrets
from datetime import timedelta, timezone

from sqlalchemy import select, func

from .guess_game import GuessGame, GuessRound, allow_guess, enabled
from .models import Rating, Track, User, SongSubmission, UserTrackSignal, utc_now
from .comparison_invitations import ComparisonInvitation, is_friendship, invitation_state
from .taste_cards import SignatureSong
from .taste_sharing import FriendTasteSharing, GuiltyPleasure
from .social import SavedSong, SongSwap, blocked, token_valid
from .taste_learning import TasteRequest, TrackPreference
from .feed_history import FeedHistory
from .matching import comparison_text
from .recommendations.repository import load_items
from .recommendations.types import Profile, Seed
from .recommendations.candidates import guess_pool

NEED = 5
DAY_LIMIT = 3
TEHRAN = timezone(timedelta(hours=3, minutes=30))
RNG = secrets.SystemRandom()


class GuessError(ValueError):
    def __init__(self, code, status=404, **details):
        super().__init__(code)
        self.status, self.details = status, details


def base_title(title):
    # A game groups by title across performers, conservatively excluding covers.
    title = re.sub(r'\([^)]*\)|\[[^]]*\]', ' ', title)
    title = re.split(r'\s[-–—]\s', title, maxsplit=1)[0]
    title = re.sub(r'\b(?:live|acoustic|instrumental|remix|remastered|remaster|radio edit|cover|version)\b.*$', '', title, flags=re.I)
    return comparison_text(title)


def language_tags(item):
    names = {'en': {'en', 'english', 'english language'},
             'fa': {'fa', 'persian', 'farsi', 'persian language'},
             'ar': {'ar', 'arabic'}, 'tr': {'tr', 'turkish'},
             'es': {'es', 'spanish'}, 'fr': {'fr', 'french'},
             'de': {'de', 'german'}, 'ru': {'ru', 'russian'}}
    return {code for code, tags in names.items() if set(item.tags) & tags}


def group(item):
    return base_title(item.metadata.title)


def identities(items):
    return set().union(*(item.identities for item in items))


async def interactions(session, target):
    """Lifetime exclusions, including expired cooldowns and private engagement."""
    from .fetch_models import AudioRequest, FetchJob, AudioSelection
    queries = [select(model.track_id).where(model.user_id == target) for model in
               (Rating, SavedSong, TasteRequest, TrackPreference, FeedHistory,
                UserTrackSignal, SongSubmission, SignatureSong, GuiltyPleasure, AudioSelection)]
    queries.extend([
        select(FetchJob.track_id).join(AudioRequest, AudioRequest.job_id == FetchJob.id)
            .where(AudioRequest.user_id == target),
        select(SongSwap.track_id).where((SongSwap.sender_id == target) | (SongSwap.recipient_id == target)),
    ])
    ids = set(await session.scalars(queries[0].union(*queries[1:]))) - {None}
    return await load_items(session, list(await session.scalars(select(Track).where(Track.id.in_(ids)))))


async def answers(session, target):
    sharing = await session.get(FriendTasteSharing, target)
    love_rows = list(await session.scalars(select(Rating).where(Rating.user_id == target, Rating.value == 'love'))) if sharing and sharing.enabled else []
    selected = set(await session.scalars(select(SignatureSong.track_id).where(SignatureSong.user_id == target)))
    ids = selected | {row.track_id for row in love_rows}
    items = await load_items(session, list(await session.scalars(select(Track).where(Track.id.in_(ids)))))
    locked = await load_items(session, list(await session.scalars(select(Track).join(GuiltyPleasure).where(GuiltyPleasure.user_id == target))))
    hidden_aliases, hidden_groups = identities(locked.values()), {group(item) for item in locked.values()}
    safe = {key: item for key, item in items.items()
            if key not in locked and not item.identities & hidden_aliases and group(item) not in hidden_groups and group(item)}
    # Preserve all safe IDs for revalidation, while counting distinct base songs.
    changed = {row.track_id: row.updated_at for row in love_rows if row.track_id in safe}
    return safe, changed


async def relationship(session, actor, *, friend_id=None, target=None):
    if not enabled():
        raise GuessError('guess_unavailable')
    if friend_id is not None:
        row = await session.get(ComparisonInvitation, friend_id) if token_valid(friend_id) else None
        rows = [row] if row else []
    else:
        rows = list(await session.scalars(select(ComparisonInvitation).where(
            ComparisonInvitation.state == 'consented',
            ((ComparisonInvitation.sender_id == actor) & (ComparisonInvitation.recipient_id == target)) |
            ((ComparisonInvitation.sender_id == target) & (ComparisonInvitation.recipient_id == actor)))))
    for row in rows:
        if actor not in {row.sender_id, row.recipient_id} or not is_friendship(row):
            continue
        other = row.recipient_id if row.sender_id == actor else row.sender_id
        if other == actor or await invitation_state(session, row) != 'consented' or await blocked(session, actor, other):
            continue
        if not await allow_guess(session, other):
            continue
        return other
    raise GuessError('guess_unavailable')


async def head_to_head(session, actor, target):
    result = {}
    for key, first, second in [('you', actor, target), ('them', target, actor)]:
        result[key] = await session.scalar(select(GuessGame.score).where(
            GuessGame.guesser_id == first, GuessGame.target_id == second, GuessGame.status == 'done')
            .order_by(GuessGame.finished_at.desc(), GuessGame.id).limit(1))
    return result


async def recent_right(session, actor, target, now):
    ids = set(await session.scalars(select(GuessRound.correct_recording_id).join(GuessGame).where(
        GuessGame.guesser_id == actor, GuessGame.target_id == target,
        ((GuessGame.status == 'done') & (GuessGame.finished_at >= now - timedelta(days=14))) |
        ((GuessGame.status != 'done') & (GuessGame.created_at >= now - timedelta(days=14))),
        GuessRound.correct.is_(True))))
    return await load_items(session, list(await session.scalars(select(Track).where(Track.id.in_(ids)))))


async def round_payload(session, row):
    from .chat_ui import safe_url
    tracks = {track.id: track for track in await session.scalars(select(Track).where(Track.id.in_(row.option_ids)))}
    if len(tracks) != 4:
        raise GuessError('guess_unavailable')
    return {'idx': row.idx, 'options': [dict(recording_id=key,
        title=tracks[key].display_title or tracks[key].title,
        artist=tracks[key].display_artist or tracks[key].artist,
        cover_url=safe_url(tracks[key].artwork_url, artwork=True)) for key in row.option_ids]}


async def checked_rounds(session, game, safe):
    rows = list(await session.scalars(select(GuessRound).where(GuessRound.game_id == game.id).order_by(GuessRound.idx)))
    touched = await interactions(session, game.target_id)
    excluded_aliases, excluded_groups = identities(touched.values()), {group(item) for item in touched.values()}
    all_ids = {key for row in rows for key in row.option_ids}
    items = await load_items(session, list(await session.scalars(select(Track).where(Track.id.in_(all_ids)))))
    if len(rows) != NEED or len(items) != 20:
        raise GuessError('guess_unavailable')
    for row in rows:
        if row.correct_recording_id not in safe or row.correct_recording_id not in row.option_ids:
            raise GuessError('guess_unavailable')
        for key in row.option_ids:
            if key != row.correct_recording_id and (key in touched or
                    items[key].identities & excluded_aliases or group(items[key]) in excluded_groups):
                raise GuessError('guess_unavailable')
    return rows


class GuessService:
    def __init__(self, database):
        self.db = database

    async def actor(self, session, telegram_id):
        actor = await session.scalar(select(User.id).where(User.telegram_user_id == telegram_id))
        if actor is None or not enabled():
            raise GuessError('guess_unavailable')
        return actor

    async def status(self, telegram_id, friend_id):
        async with self.db.sessions() as session:
            actor = await self.actor(session, telegram_id)
            try:
                target = await relationship(session, actor, friend_id=friend_id)
            except GuessError:
                return dict(eligible=False, permitted=False, have=0, need=NEED, new_loves_since_last_game=0,
                            head_to_head={'you': None, 'them': None})
            safe, changed = await answers(session, target)
            have = len({group(item) for item in safe.values()})
            last = await session.scalar(select(func.max(GuessGame.finished_at)).where(
                GuessGame.guesser_id == actor, GuessGame.target_id == target, GuessGame.status == 'done'))
            new = len({group(safe[key]) for key, when in changed.items() if last and when > last})
            from .guess_notices import nudged
            return dict(eligible=have >= NEED, permitted=True, nudged=await nudged(session,actor,target), have=have, need=NEED,
                        new_loves_since_last_game=new, head_to_head=await head_to_head(session, actor, target))

    async def start(self, telegram_id, friend_id):
        async with self.db.write() as session:
            actor = await self.actor(session, telegram_id)
            target = await relationship(session, actor, friend_id=friend_id)
            safe, _ = await answers(session, target)
            have = len({group(item) for item in safe.values()})
            if have < NEED:
                raise GuessError('not_enough', 409, not_enough={'have': have, 'need': NEED})
            now = utc_now()
            current = await session.scalar(select(GuessGame).where(GuessGame.guesser_id == actor,
                GuessGame.target_id == target, GuessGame.status == 'open'))
            if current and current.created_at > now - timedelta(hours=24):
                try:
                    rows = await checked_rounds(session, current, safe)
                except GuessError:
                    current.status, current.finished_at = 'expired', now
                else:
                    pending = next(row for row in rows if row.picked_recording_id is None)
                    return dict(game_id=current.id, round=await round_payload(session, pending))
            elif current:
                current.status, current.finished_at = 'expired', now
            midnight = now.astimezone(TEHRAN).replace(hour=0, minute=0, second=0, microsecond=0)
            count = await session.scalar(select(func.count()).select_from(GuessGame).where(
                GuessGame.guesser_id == actor, GuessGame.target_id == target, GuessGame.created_at >= midnight))
            if count >= DAY_LIMIT:
                raise GuessError('guess_limit', 429)
            touched = await interactions(session, target)
            prior = await recent_right(session, actor, target, now)
            prior_groups, prior_aliases = {group(item) for item in prior.values()}, identities(prior.values())
            choices = list(safe.values()); RNG.shuffle(choices)
            choices.sort(key=lambda item: group(item) in prior_groups or bool(item.identities & prior_aliases))
            correct, used_groups, used_aliases = [], set(), set()
            for item in choices:
                if group(item) not in used_groups and not item.identities & used_aliases:
                    correct.append(item); used_groups.add(group(item)); used_aliases.update(item.identities)
            if len(correct) < NEED:
                raise GuessError('not_enough', 409, not_enough={'have': len(correct), 'need': NEED})
            profile = Profile(target, [Seed(item, None) for item in correct], [], set(touched), identities(touched.values()), {})
            primary, fallback = await guess_pool(session, profile)
            excluded_aliases, excluded_groups = identities(touched.values()), {group(item) for item in touched.values()}
            pool = {item.track_id: item for item in primary + fallback if item.track_id and
                item.track_id not in touched and not item.identities & excluded_aliases and group(item) not in excluded_groups}
            primary_ids = {item.track_id for item in primary}
            planned = []
            used_groups, used_aliases = set(), set()
            for answer in correct:
                langs = language_tags(answer)
                # Missing language metadata may use matched/popular decoys. An
                # explicit language conflict still excludes the candidate.
                candidates = [item for item in pool.values() if
                              (not langs or not language_tags(item) or language_tags(item) == langs) and
                              group(item) not in used_groups and not item.identities & used_aliases]
                # Prefer proven language matches, then genre/era affinity and
                # recommendation candidates; stable popularity fallback last.
                candidates.sort(key=lambda item: (not (langs and language_tags(item) == langs),
                    -len((set(item.tags) & set(answer.tags)) - langs), item.track_id not in primary_ids,
                    ))
                decoys = []
                round_groups, round_aliases = set(used_groups), set(used_aliases)
                for item in candidates:
                    if group(item) in round_groups or item.identities & round_aliases:
                        continue
                    decoys.append(item.track_id); round_groups.add(group(item)); round_aliases.update(item.identities)
                    if len(decoys) == 3:
                        break
                if len(decoys) != 3:
                    continue
                used_groups, used_aliases = round_groups, round_aliases
                used_groups.add(group(answer)); used_aliases.update(answer.identities)
                options = decoys + [answer.track_id]; RNG.shuffle(options)
                planned.append((answer.track_id, options))
                if len(planned) == NEED:
                    break
            if len(planned) != NEED:
                raise GuessError('guess_unavailable', 503)
            game = GuessGame(guesser_id=actor, target_id=target, created_at=now)
            session.add(game); await session.flush()
            rows = [GuessRound(game_id=game.id, idx=idx, correct_recording_id=key, option_ids=options)
                    for idx, (key, options) in enumerate(planned)]
            session.add_all(rows); await session.flush()
            return dict(game_id=game.id, round=await round_payload(session, rows[0]))

    async def answer(self, telegram_id, game_id, idx, recording_id, *, human=False):
        if not token_valid(game_id) or type(idx) is not int or not 0 <= idx < NEED or type(recording_id) is not int or recording_id <= 0:
            raise GuessError('guess_invalid', 400)
        async with self.db.write() as session:
            actor = await self.actor(session, telegram_id)
            game = await session.get(GuessGame, game_id)
            if game is None or game.guesser_id != actor:
                raise GuessError('guess_unavailable')
            await relationship(session, actor, target=game.target_id)
            if game.status == 'expired' or (game.status == 'open' and game.created_at <= utc_now() - timedelta(hours=24)):
                raise GuessError('guess_expired', 410)
            safe, _ = await answers(session, game.target_id)
            rows = await checked_rounds(session, game, safe)
            row = rows[idx]
            if recording_id not in row.option_ids or any(previous.picked_recording_id is None for previous in rows[:idx]):
                raise GuessError('guess_invalid', 409)
            if row.picked_recording_id is not None and row.picked_recording_id != recording_id:
                raise GuessError('guess_answered', 409)
            if row.picked_recording_id is None:
                row.picked_recording_id = recording_id
                row.correct = recording_id == row.correct_recording_id
                game.score += int(row.correct)
                if idx == NEED - 1:
                    game.status, game.finished_at = 'done', utc_now()
                    if human:
                        from .guess_notices import enqueue_finish
                        await enqueue_finish(session, game)
                await session.flush()
            result = None
            if idx == NEED - 1:
                prior = await recent_right(session, actor, game.target_id, utc_now())
                old_groups = {group(item) for item in prior.values()}
                result = dict(score=game.score, total=NEED, rounds=[bool(value.correct) for value in rows],
                    missed=[safe[value.correct_recording_id].metadata.title for value in rows if not value.correct],
                    head_to_head=await head_to_head(session, actor, game.target_id),
                    can_play_again=len({group(item) for item in safe.values()} - old_groups) >= NEED)
            return dict(correct=bool(row.correct), correct_recording_id=row.correct_recording_id,
                        next_round=await round_payload(session, rows[idx+1]) if idx < NEED-1 else None, result=result)
