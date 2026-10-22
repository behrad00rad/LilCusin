// The social loop uses the same signed actor and selected-song contract as chat.
const socialDemo={swaps:[],saves:[],saved_count:0};
async function socialData(){return preview?socialDemo:api('social');}
// Connections remain bound to the existing, explicitly accepted card snapshots.
let musicFriendContext=null,musicFriendGeneration=-1,musicFriendPromise,musicSendTarget=null;
function clearMusicSendTarget(){musicSendTarget=null;}
const musicKey=value=>(value||'').normalize('NFKC').toLocaleLowerCase().replace(/\s+/gu,' ').trim();
function musicFriends(invitations){const seen=new Set();return invitations.filter(item=>{if(item.state!=='consented'||!item.friendship)return false;const other=item[item.role==='sender'?'recipient':'sender'];if(!other?.taste_id||seen.has(other.taste_id))return false;seen.add(other.taste_id);return true;}).map(item=>({token:item.token,other:item[item.role==='sender'?'recipient':'sender'],you:item[item.role==='sender'?'sender':'recipient']}));}
function musicSwapSuggestion(friend,own){const allowed=new Set(friend.you.songs.map(song=>musicKey(song.artist)+'|'+musicKey(song.title))),theirs=new Set(friend.other.songs.map(song=>musicKey(song.artist)+'|'+musicKey(song.title))),artists=new Set(friend.other.songs.map(song=>musicKey(song.artist)));return (own.songs||[]).find(song=>allowed.has(musicKey(song.artist)+'|'+musicKey(song.title))&&artists.has(musicKey(song.artist))&&!theirs.has(musicKey(song.artist)+'|'+musicKey(song.title)));}
async function musicFriendData(){
 if(musicFriendGeneration===generation&&musicFriendPromise)return musicFriendPromise;const version=generation;musicFriendGeneration=version;musicFriendContext=null;
 musicFriendPromise=(async()=>{const listing=preview?{invitations:[]}:await api('comparison-invitations');const friends=musicFriends(listing.invitations||[]);const own=friends.length?await api('taste-card'):{songs:[]};const result={friends,own,requests:(listing.invitations||[]).filter(item=>item.state==='pending')};if(version===generation)musicFriendContext=result;return result;})();
 try{return await musicFriendPromise;}catch(error){if(version===generation)musicFriendPromise=null;throw error;}
}
async function inviteMusicFriend(){
 if(preview){notice(t('card_preview_only'));return;}const version=generation,{sheet,content}=openSettingsSheet(t('friend_add_title'));let created;
 const share=action(t('friend_share_invite'),async event=>{const button=event.currentTarget;button.disabled=true;
 try{const result=await api('friend-invites',{});if(version!==generation||!sheet.isConnected)return;created=result;
 const url='https://t.me/share/url?url='+encodeURIComponent(result.url)+'&text='+encodeURIComponent(t('friend_link_share',{name:result.nickname}));if(tg?.openTelegramLink)tg.openTelegramLink(url);else window.open(url,'_blank','noopener');notice(t('friend_link_ready'));cancel.hidden=false;
 }catch(error){if(sheet.isConnected)notice(error.message);}finally{button.disabled=false;}},'primary','share-2');
 const cancel=action(t('friend_link_cancel'),async event=>{if(!created||!window.confirm(t('friend_cancel_confirm')))return;event.currentTarget.disabled=true;try{await api('friend-invites/revoke',{token:created.token});notice(t('friend_request_cancelled'));sheet.close();}catch(error){notice(error.message);event.currentTarget.disabled=false;}},'text-button');cancel.hidden=true;
 content.append(node('p',t('friend_invite_intro'),'hint'),node('p',t('friend_link_how'),'hint'),share,cancel,disclosure(t('friend_whats_shared'),node('p',t('friend_link_scope'),'hint')));
}
function friendRequestCard(invitation){
 const other=invitation[invitation.role==='sender'?'recipient':'sender'],box=node('article',undefined,'friend-request');if(!other)return box;
 box.append(socialIdentity(other.nickname,t(invitation.role==='recipient'?'friend_wants_connect':'friend_request_waiting')));
 const decide=async(operation,button)=>{const version=generation;button.disabled=true;try{await api('comparison-invitations/decide',{token:invitation.token,action:operation});if(version!==generation)return;musicFriendPromise=null;musicFriendContext=null;notice(t(operation==='accept'?'friend_connected_notice':'friend_request_cancelled',{name:other.nickname}));await switchView('swaps');}catch(error){if(version===generation)socialError(error);}finally{button.disabled=false;}};
 if(invitation.role==='recipient')box.append(node('p',t('friend_privacy_short'),'hint'),action(t('friend_add_name',{name:other.nickname}),event=>decide('accept',event.currentTarget),'primary','plus'),action(t('invite_decline'),event=>decide('decline',event.currentTarget),'text-button'));
 else box.append(action(t('friend_cancel_request'),event=>{if(window.confirm(t('friend_cancel_confirm')))decide('revoke',event.currentTarget);},'text-button'));
 box.append(disclosure(t('friend_whats_shared'),node('p',t('invite_scope'),'hint')));return box;
}
function renderFriendRequests(host,requests){if(!host)return;host.hidden=!requests.length;host.replaceChildren();if(!requests.length)return;host.append(node('h3',t('friend_requests_title')));for(const invitation of requests)host.append(friendRequestCard(invitation));}
async function draftMusicSuggestion(friend,song,button){
 if(preview){notice(t('card_preview_only'));return;}const version=generation;button.disabled=true;
 try{const draft=await api('social/draft',{invitation:friend.token,track_id:song.id,...(song.token?{source_token:song.token}:{})});if(version!==generation)return;
 if(view!=='swaps'){await switchView('swaps');if(view!=='swaps')return;}renderSocialSwap(draft);
 }catch(error){if(version===generation)socialError(error);}finally{button.disabled=false;}
}
function coverFriendPrompt(card,friend){const send=action(t(friend?'friends_send_to':'friends_choose_recipient',friend?{name:friend.other.nickname}:{}),event=>friend?draftMusicSuggestion(friend,card.songData,event.currentTarget):chooseMusicFriend(card.songData),'icon-button friend-prompt cover-send','send');send.setAttribute('aria-label',t(friend?'friends_send_to':'friends_choose_recipient',friend?{name:friend.other.nickname}:{}));send.title=send.getAttribute?.('aria-label')||t('social_send');return send;}
function installFriendPrompt(card){
 if(!['for-you','search','similar'].includes(view)||musicFriendGeneration!==generation||!musicFriendContext||card.querySelector('.friend-prompt'))return;
 const {friends}=musicFriendContext;if(!friends.length)return;
 const friend=friends.find(item=>item.token===musicSendTarget)||friends.find(item=>item.other.songs.some(song=>musicKey(song.artist)===musicKey(card.songData.artist)));
 if(view==='for-you'){card.append(coverFriendPrompt(card,friend));return;}
 const box=node('aside',undefined,'friend-prompt');
 if(friend&&friend.other.songs.some(song=>musicKey(song.artist)===musicKey(card.songData.artist)))box.append(node('p',t('friends_artist_reason',{name:friend.other.nickname,artist:card.songData.artist}),'hint'));
 box.append(action(t(friend?'friends_send_to':'friends_choose_recipient',friend?{name:friend.other.nickname}:{}),event=>friend?draftMusicSuggestion(friend,card.songData,event.currentTarget):chooseMusicFriend(card.songData),'secondary','send'));card.append(box);
}
function chooseMusicFriend(song){const {sheet,content}=openSettingsSheet(t('friends_choose_recipient'));
 for(const friend of musicFriendContext?.friends||[]){const row=node('div',undefined,'music-friend');row.append(socialIdentity(friend.other.nickname,t('friends_connected')),action(t('social_send'),event=>{sheet.close();draftMusicSuggestion(friend,song,event.currentTarget);},'secondary','send'));content.append(row);}}
function unfriendMusicFriend(friend){
 const {sheet,content}=openSettingsSheet(t('friends_unfriend'));content.append(socialIdentity(friend.other.nickname,friendLastSwap(lastResult?.swaps?.find(swap=>swap.invitation===friend.token&&swap.state==='sent')),true),node('p',t('friends_remove_explained'),'hint'));
 content.append(action(t('friends_unfriend'),async event=>{const version=generation,button=event.currentTarget;button.disabled=true;try{await api('comparison-invitations/decide',{token:friend.token,action:'unfriend'});sheet.close();if(version!==generation)return;musicFriendPromise=null;musicFriendContext=null;notice(t('friends_removed'));await switchView('swaps');}catch(error){socialError(error);button.disabled=false;}},'secondary danger-action','user-round'),action(t('card_cancel'),()=>sheet.close(),'secondary'));
}
function musicFriendMenu(friend){const {sheet,content}=openSettingsSheet(friend.other.nickname);const latest=lastResult?.swaps?.find(swap=>swap.invitation===friend.token&&swap.state==='sent');content.append(node('p',friendLastSwap(latest),'hint'),action(t('social_swap'),()=>{sheet.close();socialChoices(friend.token);},'secondary','send'),action(t('social_compare'),()=>{sheet.close();socialCompare(friend.token);},'secondary','arrow-left-right'),action(t('friends_unfriend'),()=>{sheet.close();unfriendMusicFriend(friend);},'secondary danger-action','user-round'),node('p',t('friends_block_explained'),'hint'),socialControls(friend.token));}
function renderSocialActivity(content,result){
 if(result.notifications===false){const box=node('aside',undefined,'social-alert-optin');box.append(node('p',t('activity_enable_hint'),'hint'),action(t('social_notices_on'),async event=>{const button=event.currentTarget;button.disabled=true;try{await api('social/settings/update',{notifications:true});box.remove();notice(t('activity_enabled'));}catch(error){socialError(error);button.disabled=false;}},'secondary','send'));content.append(box);}
 if(!result.activity?.length)return;const recent=disclosure(t('activity_title'));recent.classList.add('social-activity');
 for(const item of result.activity.slice(0,8)){const row=node('div',undefined,'activity-row');row.append(node('p',t('activity_'+item.event,{name:item.name,song:item.song||''})),action(t('social_open'),async()=>{if(item.swap){try{const version=generation,data=await socialData();if(version!==generation)return;const swap=data.swaps.find(value=>value.token===item.swap);if(swap)renderSocialSwap(swap);else notice(t('social_unavailable'));}catch(error){socialError(error);}}else await openFriendThread({token:item.invitation,other:{nickname:item.name}});},'text-button',item.event==='accepted'?'user-round':'arrow-left-right'));recent.append(row);}content.append(recent);
}
async function loadMusicFriendPrompts(){const version=generation;try{await musicFriendData();if(version!==generation||!['for-you','search','similar'].includes(view))return;for(const card of $('content').querySelectorAll('[data-track-id]'))installFriendPrompt(card);fitDeck();}catch{/* Discovery still works without connections. */}}
function friendLastSwap(swap){if(!swap?.sent_at)return t('thread_open_hint');const date=new Date(swap.sent_at);if(!Number.isFinite(date.getTime()))return t('thread_open_hint');return t(date.toDateString()===new Date().toDateString()?'thread_today':'thread_last',{date:new Intl.DateTimeFormat(document.documentElement.lang,{month:'short',day:'numeric'}).format(date)});}
function friendThreadRow(friend,latest){const row=node('article',undefined,'music-friend thread-friend-row'),open=action('',()=>openFriendThread(friend),'friend-open');open.setAttribute('aria-label',t('thread_open_name',{name:friend.other.nickname}));open.append(socialIdentity(friend.other.nickname,friendLastSwap(latest),true));const controls=node('div',undefined,'friend-row-controls');controls.append(action(t('social_swap'),()=>socialChoices(friend.token),'secondary','send'));const more=action(t('flow_more'),()=>musicFriendMenu(friend),'icon-button friend-menu-trigger','ellipsis');more.setAttribute('aria-label',t('friend_menu_for',{name:friend.other.nickname}));controls.append(more);row.append(open,controls);return row;}
function attachMusicFriends(content){
 const host=node('section',undefined,'card music-friends');host.append(node('h3',t('friends_title')),node('p',t('loading'),'hint'));host.setAttribute('aria-busy','true');content.append(host);const version=generation;
 const load=async()=>{try{const {friends,requests}=await musicFriendData();if(version!==generation||!host.isConnected)return;renderFriendRequests($('friend-requests'),requests||[]);host.setAttribute('aria-busy','false');host.replaceChildren(node('h3',t('friends_title')));
 for(const friend of friends){const latest=lastResult?.swaps?.find(swap=>swap.invitation===friend.token&&swap.state==='sent');host.append(friendThreadRow(friend,latest));}
 if(!friends.length)host.append(node('p',t('friends_empty'),'hint'));
 const others=new Map();for(const swap of lastResult?.swaps||[])if(!friends.some(friend=>friend.token===swap.invitation))others.set(swap.invitation,swap);
 if(others.size){host.append(node('h3',t('thread_other')));for(const [token,swap]of others)host.append(action(t('thread_open_name',{name:swap.partner}),()=>openFriendThread({token,other:{nickname:swap.partner}}),'secondary','eye'));}
 }catch(error){if(version!==generation||!host.isConnected)return;host.setAttribute('aria-busy','false');host.replaceChildren(node('h3',t('friends_title')),node('p',error.message,'hint'),action(t('retry'),()=>{musicFriendPromise=null;load();}));}};load();
}
let activeFriendThread=null;
function clearFriendThread(){activeFriendThread=null;document.body.classList.remove('thread-open');}
async function openFriendThread(friend){
 const version=generation,state={friend,rows:[],before:null},content=$('content');activeFriendThread=state;document.body.classList.add('thread-open');$('view-intro').hidden=true;window.scrollTo({top:0,behavior:'instant'});$('view-title').textContent=friend.other.nickname;content.replaceChildren(action(t('ux_back_exchanges'),()=>switchView('swaps'),'icon-button thread-back','arrow-left'));
 const timeline=node('section',undefined,'friend-thread'),loading=node('p',t('loading'),'hint'),send=action(t('social_swap'),()=>socialChoices(friend.token),'primary friend-thread-send','send');timeline.setAttribute('aria-label',t('thread_title'));content.append(timeline,send);timeline.append(loading);
 const draw=()=>{timeline.replaceChildren();if(!state.rows.length)timeline.append(node('p',t('thread_empty'),'hint'));if(state.before)timeline.append(action(t('thread_older'),async event=>{event.currentTarget.disabled=true;await load(state.before);},'secondary'));for(const swap of state.rows){const entry=exchangeCard(swap,true);entry.classList.add('thread-entry',swap.role==='sender'?'is-outgoing':'is-incoming');timeline.append(entry);}};
 const load=async before=>{try{const page=preview?{swaps:[],before:null}:await api('social/thread',{invitation:friend.token,...(before?{before}:{})});if(version!==generation||activeFriendThread!==state)return;const seen=new Set(state.rows.map(row=>row.token));state.rows=[...(page.swaps||[]).filter(row=>!seen.has(row.token)),...state.rows];state.before=page.before;draw();}catch(error){if(version!==generation||activeFriendThread!==state)return;timeline.replaceChildren(node('p',error.message,'hint'),action(t('retry'),()=>load(before),'secondary'));}};
 await load();
}
function backToFriendThread(){return activeFriendThread?openFriendThread(activeFriendThread.friend):switchView('swaps');}

function socialError(error){status(error.message);notice(error.message);}
function socialSong(song){const p=node('p');p.append(node('bdi',song.artist+(song.title?' — '+song.title:'')));return p;}
function socialIdentity(name,label,nameFirst=false){const row=node('div',undefined,'social-identity'),avatar=node('span',undefined,'social-avatar'),copy=node('div');const letters=Array.from((name||'').trim().split(/\s+/u).filter(part=>/[\p{L}\p{N}]/u.test(part)).map(part=>Array.from(part)[0]).join('')).slice(0,2).join('');avatar.textContent=letters||'♪';avatar.setAttribute('aria-hidden','true');let shade=0;for(const letter of name||'')shade=(shade+letter.codePointAt(0))%3;avatar.dataset.shade=String(shade);const title=node('bdi',name||t('card_fallback_name')),subline=node('p',label,'hint');copy.append(...(nameFirst?[title,subline]:[subline,title]));row.append(avatar,copy);return row;}
function socialArtwork(song,large=false){const row=node('div',undefined,'exchange-song'+(large?' exchange-song-large':'')),cover=node('div','♪','cover'),copy=node('div');if(song.artwork)setArtwork(cover,song.artwork,large);copy.append(node('h3',undefined),node('bdi',song.artist));copy.firstChild.append(node('bdi',song.title));row.append(cover,copy);return row;}
function socialTime(swap){if(!swap.sent_at)return null;const date=new Date(swap.sent_at);if(!Number.isFinite(date.getTime()))return null;const time=node('time',new Intl.DateTimeFormat(document.documentElement.lang,{month:'short',day:'numeric',hour:'numeric',minute:'2-digit'}).format(date),'hint');time.dateTime=date.toISOString();return time;}
function socialSwapStatus(swap){return t(swap.state==='draft'?'social_draft':swap.role==='recipient'?(swap.saved?'social_saved':swap.loved?'social_loved':'social_waiting'):swap.saved?'social_saved_feedback':swap.loved?'social_loved_feedback':'social_sent',{name:swap.partner||t('card_fallback_name')});}
function socialSection(title,songs){const section=node('section',undefined,'card social-section');section.append(node('h3',title));if(!songs.length)section.append(node('p',t('social_none'),'hint'));for(const song of songs)section.append(socialSong(song));return section;}
function makeFeedSwap(swap){
 const card=node('article',undefined,'card feed-swap'),row=node('div',undefined,'track'),cover=node('div','♪','cover'),info=node('div');
 if(swap.song.artwork)setArtwork(cover,swap.song.artwork,true);
 info.append(node('p',t('feed_swap_from',{name:swap.partner||t('card_fallback_name')}),'feed-swap-from'),node('h3',swap.song.title),node('p',swap.song.artist));row.append(cover,info);card.append(row);
 if(swap.note)card.append(node('blockquote',swap.note,'social-note feed-swap-note'));
 const actions=node('div',undefined,'song-actions');actions.append(action(t('social_open'),()=>openFeedSwap(swap.token),'primary','arrow-left-right'));card.append(actions);card.dataset.swapToken=swap.token;card.dataset.swapTrackId=String(swap.song.id);return card;
}
async function openFeedSwap(token){await switchView('swaps');if(view!=='swaps')return;const fresh=lastResult?.swaps?.find(swap=>swap.token===token);if(fresh)renderSocialSwap(fresh);}
async function socialStrip(){loadMusicFriendPrompts();const version=generation;try{
 const result=await socialData();if(version!==generation||view!=='for-you')return;
 const incoming=result.swaps.filter(s=>s.role==='recipient'&&s.state==='sent'&&!s.rated&&!s.loved&&!ratedFeedIds.has(s.song.id));if(!incoming.length)return;if(!preview){const allowed=await api('feed/swaps');if(version!==generation||view!=='for-you')return;for(let i=incoming.length-1;i>=0;i--)if(!allowed.tokens.includes(incoming[i].token))incoming.splice(i,1);if(!incoming.length)return;}incoming.splice(3);
 const active=deckItems()[deckIndex];let anchor=deckItems()[0];if(!anchor)$('content').replaceChildren();
 for(const swap of incoming){if([...$('content').children].some(el=>el.dataset.swapToken===swap.token))continue;const card=makeFeedSwap(swap);if(anchor)anchor.after(card);else $('content').append(card);anchor=card;}
 if(active)deckIndex=Math.max(0,deckItems().indexOf(active));installDeck();
 }catch{/* Recommendations remain usable while the inbox is unavailable. */}}
let profileStatsRequest=0;
async function socialProfileStats(){
 const request=++profileStatsRequest,version=generation,host=$('profile-saved');if(!host)return;
 const show=async()=>{host.replaceChildren(node('h3',t('social_saves')),node('p',t('loading'),'hint'));
 try{const result=await socialData();if(request!==profileStatsRequest||version!==generation||view!=='card'||!host.isConnected)return;
 host.replaceChildren(node('h3',t('social_saves')+' · '+result.saved_count));
 if(!result.saves.length){host.append(owlIllustration('sleepy'),node('p',t('me_saved_empty'),'hint'),action(t('me_find_picks'),()=>switchView('for-you'),'secondary','house'));return;}
 for(const song of result.saves){const row=node('div',undefined,'social-save'),actions=node('div',undefined,'saved-actions');row.append(socialSong(song));
 actions.append(action(t('me_find_song'),async()=>{await switchView('search',undefined,{focusSearch:false});if(view!=='search')return;$('query').value=song.artist+' '+song.title;$('search-form').requestSubmit();},'secondary','search'),action(t('social_unsave'),async event=>{if(preview){notice(t('card_preview_only'));return;}const b=event.currentTarget;b.disabled=true;try{await api('social/unsave',{track_id:song.id});await show();notice(t('social_unsave'));}catch(error){socialError(error);}finally{b.disabled=false;}},'text-button','x'));row.append(actions);host.append(row);}
 if(result.saved_count>result.saves.length)host.append(node('p',t('me_saved_recent',{n:result.saves.length}),'hint'));
 }catch(error){if(version!==generation||!host.isConnected)return;host.replaceChildren(node('h3',t('social_saves')),node('p',error.message,'hint'),action(t('retry'),show));}};
 await show();
}
function renderSocialInvitations(invitations){
 window.scrollTo({top:0,behavior:'instant'});const content=$('content');content.replaceChildren(action(t('ux_back_exchanges'),()=>switchView('swaps'),'text-button'),action(t('friend_add_title'),inviteMusicFriend,'secondary','plus'));
 const requests=node('section');renderFriendRequests(requests,invitations.filter(item=>item.state==='pending'));content.append(requests);
 const inactive=disclosure(t('me_previous_invitations'));for(const invitation of invitations.filter(item=>!['pending','consented'].includes(item.state)))inactive.append(node('p',t('invite_state_'+invitation.state),'hint'));
 if(!invitations.some(item=>['pending','consented'].includes(item.state)))content.append(socialEmpty('ux_connections_empty','ux_connections_next','friend_add_title',inviteMusicFriend));
 if(inactive.children.length>1)content.append(inactive);attachMusicFriends(content);
}
function socialControls(invitation,swap){const controls=node('div',undefined,'social-controls');controls.append(action(t('social_block'),async()=>{if(preview){notice(t('card_preview_only'));return;}if(!window.confirm(t('me_confirm_block')))return;try{await api('social/relationship',{invitation,action:'block'});notice(t('social_block_done'));await switchView('connections');}catch(error){socialError(error);}},'secondary danger-action','shield'),action(t('social_report'),()=>socialReport(invitation,swap)));return controls;}
function socialReport(invitation,swap){
 const {sheet,content}=openSettingsSheet(t('social_report')),reasonLabel=node('label',t('report_reason_label')),reason=node('select'),noteLabel=node('label',t('report_note_label')),note=node('textarea');reason.id='report-reason';reasonLabel.htmlFor=reason.id;reason.append(Object.assign(node('option',t('report_choose_reason')),{value:''}));for(const key of ['spam','harassment','unsafe','other'])reason.append(Object.assign(node('option',t('social_reason_'+key)),{value:key}));note.id='report-note';noteLabel.htmlFor=note.id;note.maxLength=240;note.rows=3;note.dir='auto';
 const submit=action(t('report_submit'),async event=>{if(preview){notice(t('card_preview_only'));return;}if(!reason.value)return;const button=event.currentTarget;button.disabled=true;try{await api('social/relationship',{invitation,action:'report',reason:reason.value,details:note.value,...(swap?{swap_token:swap}:{})});sheet.close();notice(t('social_report_done'));}catch(error){socialError(error);button.disabled=false;}},'primary','flag');submit.disabled=true;reason.onchange=()=>{submit.disabled=!reason.value;};content.append(node('p',t('social_report_reason'),'hint'),reasonLabel,reason,noteLabel,note,node('p',t('report_note_limit'),'hint'),submit,action(t('card_cancel'),()=>sheet.close(),'secondary'));
}

async function socialCompare(token){if(preview){notice(t('card_preview_only'));return;}const version=generation;try{status(t('loading'));const result=await api('social/compare',{token});if(version!==generation)return;status();$('view-intro').hidden=true;window.scrollTo({top:0,behavior:'instant'});const content=$('content');content.replaceChildren(action(t('ux_back_comparisons'),()=>switchView('connections'),'text-button'),node('h2',t('social_compare_title',{name:result.other.nickname})),node('p',t('social_compare_scope'),'hint'));
 const pair=node('div',undefined,'social-pair');for(const card of [result.you,result.other]){const side=node('section',undefined,'card social-section comparison-person');side.append(socialIdentity(card.nickname,t('card_songs',{n:card.songs.length})));const picks=node('div',undefined,'comparison-picks');for(const song of card.songs){const pick=node('div',undefined,'comparison-pick'),cover=node('div','?','cover');if(song.artwork)setArtwork(cover,song.artwork);pick.append(cover,socialSong(song));picks.append(pick);}side.append(picks);pair.append(side);}content.append(pair);
 if(result.sparse)content.append(node('p',t('social_sparse'),'notice'),action(t('card_edit'),()=>switchView('card')));
 for(const [key,songs] of [['social_shared_songs',result.shared_songs],['social_shared_artists',result.shared_artists.map(artist=>({artist,title:''}))]])if(songs.length)content.append(socialSection(t(key),songs));const differences=disclosure(t('flow_differences'));for(const [key,songs] of [['social_only_you',result.only_first],['social_only_other',result.only_second]])if(songs.length)differences.append(socialSection(t(key),songs));if(differences.children.length>1)content.append(differences);if(!result.shared_songs.length&&!result.shared_artists.length)content.append(node('p',t('ux_no_overlap'),'hint'));const next=node('div',undefined,'comparison-next');next.append(action(t('social_swap'),()=>socialChoices(token),'primary','arrow-left-right'));content.append(next,socialControls(token));
 }catch(error){socialError(error);}}
async function socialChoices(invitation,reply_to){if(preview){notice(t('card_preview_only'));return;}const version=generation;try{const result=await api('social/choices',{invitation,...(reply_to?{reply_to}:{})});if(version!==generation)return;window.scrollTo({top:0,behavior:'instant'});const content=$('content');content.replaceChildren(action(t('ux_back_exchanges'),()=>switchView('swaps'),'text-button'),node('h2',t('social_choose_title')),node('p',t('social_choose'),'hint'));if(!result.songs.length)content.append(node('p',t('friend_link_find_song'),'hint'),action(t('find_song'),()=>{musicSendTarget=invitation;switchView('search');},'primary','search'));for(const song of result.songs){const button=action(song.artist+' — '+song.title,async()=>{button.disabled=true;try{const draft=await api('social/draft',{invitation,track_id:song.id,...(reply_to?{reply_to}:{})});if(version===generation)renderSocialSwap(draft);}catch(error){socialError(error);}finally{button.disabled=false;}});content.append(button);}content.append(action(t('card_cancel'),()=>switchView('swaps')));}catch(error){socialError(error);}}
function exchangeCard(swap,thread=false){
 const box=node('section',undefined,'card social-section exchange-card');if(thread)box.append(node('p',t(swap.role==='sender'?'thread_you_sent':'thread_they_sent',{name:swap.partner}),'thread-direction'));else box.append(socialIdentity(swap.partner,t(swap.role==='recipient'?'exchange_from':'exchange_to')));box.append(socialArtwork(swap.song));
 if(swap.note){const note=node('blockquote',swap.note,'social-note');note.dir='auto';box.append(note);}const meta=node('div',undefined,'exchange-meta');meta.append(node('p',socialSwapStatus(swap),'hint'));const time=socialTime(swap);if(time)meta.append(time);box.append(meta);
 const actions=node('div',undefined,'exchange-quick-actions');actions.append(action(t(swap.state==='draft'?'a1_continue_draft':'me_open_song'),()=>renderSocialSwap(swap),'secondary','eye'));
 if(swap.state==='sent'&&swap.role==='recipient')actions.append(action(t(swap.saved?'social_unsave':'social_save'),event=>inboxReaction(swap,swap.saved?'unsave':'save',event.currentTarget),'secondary','bookmark'),socialLoveButton(swap,event=>inboxReaction(swap,'love',event.currentTarget)));
 box.append(actions);return box;
}
function renderSocialInbox(result){
 clearFriendThread();window.scrollTo({top:0,behavior:'instant'});const content=$('content'),toolbar=node('div',undefined,'exchange-toolbar'),requests=node('section');requests.id='friend-requests';requests.hidden=true;
 toolbar.append(action(t('friend_add_title'),inviteMusicFriend,'primary','plus'));content.replaceChildren(toolbar,requests);renderSocialActivity(content,result);attachMusicFriends(content);
}

async function inboxReaction(swap,operation,button){
 if(preview){notice(t('card_preview_only'));return;}const version=generation;button.disabled=true;
 try{const next=await api('social/action',{token:swap.token,action:operation});if(version!==generation||!button.isConnected)return;
 if(lastResult?.swaps){lastResult={...lastResult,swaps:lastResult.swaps.map(item=>item.token===swap.token?next:item)};if(activeFriendThread)await openFriendThread(activeFriendThread.friend);else renderSocialInbox(lastResult);}notice(t(operation==='love'?'social_loved':operation==='save'?'social_saved':'social_unsave'));if(operation==='love')owlReact('love');
 }catch(error){if(version===generation)socialError(error);}finally{button.disabled=false;}
}
function renderSocialSwap(swap){$('view-intro').hidden=true;window.scrollTo({top:0,behavior:'instant'});const content=$('content');content.replaceChildren(action(t('ux_back_exchanges'),backToFriendThread,'text-button'),socialIdentity(swap.partner,t(swap.role==='recipient'?'exchange_from':'exchange_to')),node('p',socialSwapStatus(swap),'swap-status'),socialArtwork(swap.song,true));if(swap.note){const noteText=node('blockquote',swap.note,'social-note');noteText.dir='auto';content.append(noteText);}const sentTime=socialTime(swap);if(sentTime)content.append(sentTime);
 const version=generation;async function act(operation,extra={}){if(preview){notice(t('card_preview_only'));return;}try{const result=await api('social/action',{token:swap.token,action:operation,...extra});if(version!==generation)return;if(['deleted','cancelled'].includes(result.state)){notice(t('social_removed'));await switchView('swaps');}else if(operation==='send'&&activeFriendThread)await openFriendThread(activeFriendThread.friend);else renderSocialSwap(result);}catch(error){socialError(error);}}
 if(swap.state==='draft'){content.append(node('p',t('social_draft'),'notice'));const label=node('label',t('social_note_label')),note=node('textarea');note.id='social-note';note.maxLength=240;note.rows=3;note.value=swap.note;note.dir='auto';label.htmlFor=note.id;content.append(label,note);const send=action(t('social_send'),async()=>{if(preview){notice(t('card_preview_only'));return;}if(!window.confirm(t('social_confirm_send')))return;send.disabled=true;try{await api('social/action',{token:swap.token,action:'note',note_text:note.value});await act('send');}catch(error){socialError(error);}finally{send.disabled=false;}},'primary');content.append(send,action(t('card_cancel'),()=>act('cancel')));
 }else{if(swap.role==='recipient')content.append(node('p',t('ux_save_love'),'hint'));if(swap.role==='recipient'){const reactions=node('div',undefined,'exchange-actions');reactions.append(action(t(swap.saved?'social_unsave':'social_save'),()=>act(swap.saved?'unsave':'save')),socialLoveButton(swap,()=>act('love')),action(t('social_reply'),()=>socialChoices(swap.invitation,swap.token)));content.append(reactions);}else content.append(node('p',t(swap.saved?'social_saved_feedback':'social_sent'),'notice'),...(swap.loved?[node('p',t('social_loved_feedback'))]:[]),action(t('social_remind'),()=>act('remind')));
 const getSong=action(t('get_song'),async()=>{if(preview){notice(t('card_preview_only'));deliveryFeedback(content,{state:'preview'});return;}try{await requestDelivery(swap.song.id,'',{swap_token:swap.token},getSong,content);}catch(error){socialError(error);}},'primary');const listen=node('section',undefined,'swap-delivery');listen.append(getSong,node('p',t('social_unavailable_audio'),'hint'));const privacy=disclosure(t('social_controls'),socialControls(swap.invitation,swap.token),action(t('social_delete'),()=>{if(window.confirm(t('social_delete_confirm')))act('delete');},'text-button'));content.append(listen,privacy);}

}
async function socialSettings(card){
 const version=generation,{sheet,content}=openSettingsSheet(t('me_settings'));content.append(node('p',t('loading'),'hint'));
 const show=async()=>{try{const result=preview?{notifications:false,blocks:[]}:await api('social/settings');if(version!==generation||!sheet.isConnected)return;content.replaceChildren(node('p',t('me_privacy_hint'),'hint'),disclosure(t('ux_visibility_details'),node('p',t('social_settings_scope'),'hint')));
 const languageLabel=node('label',t('language')),select=$('language').cloneNode(true);select.removeAttribute('id');select.removeAttribute('aria-labelledby');select.setAttribute('aria-label',t('language'));select.value=locale;select.onchange=async()=>{await chooseLanguage({currentTarget:select});if(sheet.isConnected){sheet.close();socialSettings(card);}};languageLabel.append(select);content.append(languageLabel);
 if(typeof appendTasteSharingSettings==='function')await appendTasteSharingSettings(content);
 content.append(action(t(result.notifications?'social_notices_off':'social_notices_on'),async event=>{if(preview){notice(t('card_preview_only'));return;}event.currentTarget.disabled=true;try{await api('social/settings/update',{notifications:!result.notifications});await show();}catch(error){socialError(error);event.currentTarget.disabled=false;}},'secondary','sliders-horizontal'),node('h3',t('me_blocked')));
 if(!result.blocks.length)content.append(node('p',t('me_no_blocks'),'hint'));
 for(const block of result.blocks)content.append(action(t('social_unblock')+' · '+block.nickname,async event=>{if(!window.confirm(t('me_confirm_unblock')))return;event.currentTarget.disabled=true;try{await api('social/relationship',{invitation:block.handle,action:'unblock'});notice(t('social_unblock_done'));await show();}catch(error){socialError(error);event.currentTarget.disabled=false;}}));
 if(card&&Number.isInteger(card.revision)){content.append(action(t('card_private_summary'),()=>{sheet.close();switchView('taste');},'text-button'));
 for(const operation of [...(card.shared?['hide','rotate']:[]),'delete']){const key={hide:'card_hide',rotate:'card_rotate',delete:'card_delete'}[operation];content.append(action(t(key),()=>{sheet.close();confirmCard(card,operation);},'danger',operation==='delete'?'trash':'shield'));}}
 }catch(error){if(version!==generation||!sheet.isConnected)return;content.replaceChildren(node('p',error.message,'hint'),action(t('retry'),show));}};await show();
}

function socialLoveButton(swap,run){const button=action(t(swap.loved?'social_loved':'social_love'),run);button.setAttribute('aria-pressed',String(swap.loved));return button;}

function socialEmpty(title,description,label,run){const box=node('section',undefined,'empty');box.append(node('h3',t(title)),node('p',t(description)),action(t(label),run,'primary'));return box;}

if(typeof document!=='undefined')document.addEventListener('visibilitychange',()=>{if(!document.hidden&&view==='swaps'&&$('content').querySelector('.exchange-toolbar')){musicFriendPromise=null;switchView('swaps');}});
