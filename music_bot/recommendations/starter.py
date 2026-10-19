"""Small cold-start list based on the user's own setup answers."""
from sqlalchemy import select
from ..models import User,Track,Rating,ChannelPost,PlaylistChannel
from ..taste_setup import read_setup,ARTISTS
from ..matching import comparison_text,deduplicate
from ..catalog import canonical_track,IdentityConflict
from ..providers.common import ProviderError
from .repository import aliases, load_exclusions, load_items
from .types import Recommendation,RecommendationResult

STYLE_TAGS={'hiphop':{'hip hop','rap'},'persian':{'persian','iranian'},'indie':{'indie','alternative'},'electronic':{'electronic','ambient'},'classical':{'classical','piano'}}
MOOD_TAGS={'calm':{'ambient','chill','piano','acoustic','dream pop'},'energetic':{'dance','electronic','rock','hip hop'},'mixed':set()}

async def starter_recommendations(database,telegram_id,providers,limit,*,excluded_track_ids=()):
    setup=await read_setup(database,telegram_id)
    if not setup['completed'] or not (setup['style'] or setup['artist']):return RecommendationResult('insufficient_preferences')
    style,mood=setup['style'],setup['mood'] or 'mixed'
    defaults=ARTISTS.get(style,ARTISTS['pop'])
    artist=setup['artist'] or defaults[1 if mood=='energetic' else 0]
    async with database.sessions() as session:
        user=await session.scalar(select(User.id).where(User.telegram_user_id==telegram_id))
        if user is None:return RecommendationResult('insufficient_preferences')
        excluded,excluded_aliases=await load_exclusions(session,user,excluded_track_ids)
        rows=(await session.scalars(select(Track).where(Track.id.not_in(excluded)).order_by(Track.id.desc()).limit(300))).all()
        items=await load_items(session,rows)
    wanted=STYLE_TAGS.get(style,{style})
    choices=[]
    for item in items.values():
        if item.identities&excluded_aliases:continue
        exact=comparison_text(artist)==comparison_text(item.metadata.artist)
        tags=set(item.tags)
        if exact or tags&wanted:
            choices.append((4*exact+len(tags&wanted)+len(tags&MOOD_TAGS.get(mood,set())),item.metadata))
    if providers is not None and sum(score>=4 for score,_ in choices)<limit:
        try:
            online=await providers.call('musicbrainz','search_recordings',artist,'')
            choices.extend((4,c) for c in online if c.artist and c.title and comparison_text(artist)==comparison_text(c.artist))
        except ProviderError:pass
    choices.sort(key=lambda pair:pair[0],reverse=True)
    tracks=[]
    async with database.write() as session:
        current=await session.scalar(select(User.id).where(User.telegram_user_id==telegram_id))
        if current!=user:return RecommendationResult('insufficient_preferences')
        excluded,excluded_aliases=await load_exclusions(session,user,excluded_track_ids)
        for candidate in deduplicate([c for _,c in choices]):
            if aliases(candidate)&excluded_aliases:continue
            try:track=await canonical_track(session,candidate)
            except IdentityConflict:continue
            if track.id in excluded:continue
            tracks.append(Recommendation(track.id,track.display_artist or track.artist,track.display_title or track.title,
                track.album,track.artwork_url,candidate.external_ids,.5,'Based on your first picks',('taste_setup',)))
            if len(tracks)>=limit:break
    return RecommendationResult('ok' if tracks else 'no_candidates',tuple(tracks))
