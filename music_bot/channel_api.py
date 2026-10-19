"""Owner-scoped channel browsing and identification within the Mini App."""
from aiohttp import web
from sqlalchemy import select, exists, func
from .models import ChannelPost, PlaylistChannel, SongSubmission, Track, Rating, User, ChatControl, IdentificationFlow, utc_now
from .workflow import FlowError, active, owned_submission
from .submissions import parse_song, InvalidSubmission


def register_channel_api(app, chat, workflow, body, bundle, track_json, capacity):
    async def access(session, user_id, channel_id, token=None, post_id=None):
        channel = await session.scalar(select(PlaylistChannel).join(User).where(
            PlaylistChannel.id == channel_id, User.telegram_user_id == user_id))
        if channel is None:
            raise web.HTTPForbidden(text='Channel unavailable.')
        if token is not None:
            grant = await session.scalar(select(ChatControl).where(ChatControl.token == token,
                ChatControl.user_id == channel.user_id, ChatControl.expires_at > utc_now()))
            if (grant is None or grant.payload.get('kind') not in {'miniapp','channel-review'}
                    or not grant.payload.get('links') or grant.payload['links'][0] != channel_id
                    or (post_id is not None and post_id not in grant.payload['links'][1:])):
                raise web.HTTPForbidden(text='Refresh this channel first.')
        return channel

    async def songs(request):
        data = await body(request)
        channel_id, cursor = data.get('channel_id'), data.get('cursor', 0)
        mode, replace = data.get('filter', 'all'), data.get('replace', False)
        exclude, current = data.get('exclude', []), data.get('current', [])
        if (type(channel_id) is not int or type(cursor) is not int or cursor < 0
                or mode not in ('all','unrated','review') or type(replace) is not bool
                or not isinstance(exclude,list) or len(exclude)>20 or any(type(i) is not int or i<=0 for i in exclude)
                or not isinstance(current,list) or len(current)>20 or (current and not replace)
                or any(not isinstance(i,dict) or type(i.get('id')) is not int or not isinstance(i.get('token'),str) for i in current)):
            raise web.HTTPBadRequest(text='Invalid channel page.')
        user_id = request['user']['id']
        # A pre-read control prevents a concurrent forget/recreate from reviving access.
        anchor = await chat.create_control(user_id, kind='channel-page')
        visible = []
        async with chat.database.sessions() as session:
            channel = await access(session,user_id,channel_id)
            for item in current:
                grant = await session.scalar(select(ChatControl).where(ChatControl.token == item['token'],
                    ChatControl.user_id == channel.user_id,ChatControl.expires_at > utc_now()))
                if (grant is None or grant.payload.get('kind')!='miniapp' or item['id'] not in grant.payload.get('tracks',[])
                        or item['id'] not in exclude or not await session.scalar(select(ChannelPost.id).where(
                            ChannelPost.channel_id==channel_id,ChannelPost.track_id==item['id']).limit(1))):
                    raise web.HTTPForbidden(text='Refresh this channel first.')
                visible.append(item['id'])
            query = select(ChannelPost,SongSubmission).join(SongSubmission).where(ChannelPost.channel_id==channel_id)
            if cursor:
                query = query.where(ChannelPost.id < cursor)
            if mode=='review':
                query = query.where(ChannelPost.status.in_(['review','processing']))
            else:
                query = query.where(ChannelPost.status=='identified',ChannelPost.track_id.is_not(None))
                latest=select(func.max(ChannelPost.id)).where(ChannelPost.channel_id==channel_id,
                    ChannelPost.status=='identified').group_by(ChannelPost.track_id)
                query=query.where(ChannelPost.id.in_(latest))
                if exclude:query=query.where(ChannelPost.track_id.not_in(exclude))
                if mode=='unrated' or replace:
                    query=query.where(~exists(select(Rating.id).where(Rating.user_id==channel.user_id,Rating.track_id==ChannelPost.track_id)))
            limit=1 if replace else 10
            rows=(await session.execute(query.order_by(ChannelPost.id.desc()).limit(limit+1))).all()
            page=rows[:limit];tracks=[];items=[];seen=set()
            for post,submission in page:
                if mode=='review':
                    items.append(dict(id=post.id,title=submission.parsed_title or submission.original_filename or '',artist=submission.parsed_artist or ''))
                elif post.track_id not in seen:
                    seen.add(post.track_id)
                    track=await session.get(Track,post.track_id)
                    rating=await session.scalar(select(Rating.value).where(Rating.user_id==channel.user_id,Rating.track_id==track.id))
                    tracks.append({**track_json(track),'rating':rating})
            result=dict(channel=dict(id=channel.id,title=channel.title),filter=mode,items=items,
                next_cursor=page[-1][0].id if len(rows)>limit and page else None)
        return await bundle(user_id,tracks,visible=visible,expected_token=anchor,
            links=[channel_id,*[item['id'] for item in items]],extra=result)

    async def review(request):
        data=await body(request)
        channel_id,post_id,token,action=data.get('channel_id'),data.get('post_id'),data.get('token'),data.get('action','open')
        revision=data.get('revision')
        if (type(channel_id) is not int or type(post_id) is not int or not isinstance(token,str)
                or action not in ('open','search','select') or (action!='open' and type(revision) is not int)):
            raise web.HTTPBadRequest(text='Invalid review.')
        user_id=request['user']['id']
        async with chat.database.sessions() as session:
            channel=await access(session,user_id,channel_id,token,post_id)
            post=await session.scalar(select(ChannelPost).where(ChannelPost.id==post_id,ChannelPost.channel_id==channel_id))
            if post is None:raise web.HTTPForbidden(text='Post unavailable.')
            submission_id=post.submission_id
            if post.status=='identified':raise FlowError('stale')
        async with capacity:
            if action=='open':
                result=await workflow.review_channel(submission_id,user_id)
            elif action=='select':
                index=data.get('index')
                if type(index) is not int or not 0<=index<5:raise web.HTTPBadRequest(text='Choose a match.')
                result=await workflow.select(submission_id,user_id,revision,index)
            else:
                if not isinstance(data.get('query'),str) or not 3<=len(data['query'])<=240:
                    raise web.HTTPBadRequest(text='Use Artist - Song title.')
                try:artist,title=parse_song(data.get('query',''))
                except (InvalidSubmission,TypeError,AttributeError):raise web.HTTPBadRequest(text='Use Artist - Song title.') from None
                async with chat.database.write() as session:
                    await access(session,user_id,channel_id,token,post_id)
                    await owned_submission(session,submission_id,user_id)
                    flow=await session.get(IdentificationFlow,submission_id)
                    active(flow,revision)
                    if flow.state not in ('candidates','correction'):raise FlowError('stale')
                    flow.corrected_artist,flow.corrected_title=artist,title
                    flow.state='searching';flow.prompt_message_id=None
                result=await workflow.identify(submission_id,user_id)
        details=dict(kind=result.kind,revision=result.revision,post_id=post_id,channel_id=channel_id,
            candidates=[dict(index=i,title=c.title,artist=c.artist) for i,c in enumerate(result.candidates)])
        if result.kind=='confirmed':
            async with chat.database.sessions() as session:
                track=await session.get(Track,result.track_id)
                tracks=[track_json(track)]
            return await bundle(user_id,tracks,expected_token=token,links=[channel_id,post_id],extra=details)
        control=await chat.create_control(user_id,kind='channel-review',links=[channel_id,post_id],expected_token=token)
        return web.json_response({**details,'token':control})

    app.router.add_post('/api/channels/songs',songs)
    app.router.add_post('/api/channels/review',review)
