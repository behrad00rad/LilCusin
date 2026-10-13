const tg = window.Telegram?.WebApp;
const preview = !tg?.initData;
const $ = id => document.getElementById(id);
let view = 'for-you', generation = 0;
const demo = [{id:1,title:'Everything In Its Right Place',artist:'Radiohead',reason:'A familiar feeling, a new direction.'},{id:2,title:'Space Song',artist:'Beach House',reason:'For the softer side of your sound.'},{id:3,title:'Intro',artist:'The xx',reason:'A little space to get lost in.'}].map(t=>({...t,listen_url:`https://t.me/musicbehbot?text=${encodeURIComponent(t.artist+' '+t.title)}`}));
const demoChannels = {channels:[{id:1,title:'Late night favorites',status:'connected',learned:18,review:2},{id:2,title:'Sunday mixtape',status:'disconnected',learned:6,review:0}]};
const lists = new Map();
const storageKey = 'lilcusin-list-' + (tg?.initDataUnsafe?.user?.id || 'preview');
function node(tag, text, className) {const el=document.createElement(tag);if(text!==undefined)el.textContent=text;if(className)el.className=className;return el;}
function action(label, run, className='secondary'){const b=node('button',label,className);b.type='button';b.onclick=run;return b;}
function telegramLink(url,label,className='primary'){const a=node('a',label,className);a.href=url;a.onclick=e=>{if(tg?.openTelegramLink){e.preventDefault();tg.openTelegramLink(url);}};return a;}
function theme() {const p=tg?.themeParams;if(!p?.bg_color)return;const s=document.documentElement.style;for(const [key,val] of Object.entries({'--bg':p.bg_color,'--panel':p.secondary_bg_color,'--ink':p.text_color,'--muted':p.hint_color,'--accent':p.button_color,'--accent-ink':p.button_text_color}))if(val)s.setProperty(key,val);}
function safeArea(){const s=document.documentElement.style;s.setProperty('--safe-top',`${Math.max(tg?.safeAreaInset?.top||0,tg?.contentSafeAreaInset?.top||0)}px`);s.setProperty('--safe-bottom',`${Math.max(tg?.safeAreaInset?.bottom||0,tg?.contentSafeAreaInset?.bottom||0)}px`);}
tg?.ready();tg?.expand();theme();safeArea();tg?.onEvent('themeChanged',theme);tg?.onEvent('safeAreaChanged',safeArea);tg?.onEvent('contentSafeAreaChanged',safeArea);
async function api(path, data) {const response=await fetch(`/api/${path}`,{method:data===undefined?'GET':'POST',headers:{'Content-Type':'application/json','X-Telegram-Init-Data':tg.initData},body:data===undefined?undefined:JSON.stringify(data)});const result=await response.json();if(!response.ok)throw new Error(result.error||'Please try again.');return result;}
function empty(title, detail, search=false){const box=node('div',undefined,'empty');box.append(node('span','♪'),node('h3',title),node('p',detail));if(search)box.append(action('Find a song ↗',()=>switchView('search'),'primary'));$('content').replaceChildren(box);}
function remember(result){lists.set(view,result);if(!preview)try{sessionStorage.setItem(storageKey,JSON.stringify({view,result,time:Date.now()}));}catch{}}
function tracks(result){
  $('content').replaceChildren();
  if(!result.tracks.length){empty(result.status==='insufficient_preferences'?'Let’s get to know your sound':'Nothing here just yet',view==='search'?'Try another artist or title.':'Find and rate a few songs you already know, then come back for recommendations.',view!=='search');return;}
  for(const t of result.tracks){
    const card=node('article',undefined,'card'), row=node('div',undefined,'track'), cover=node('div','♪','cover'), info=node('div');
    if(t.artwork){const img=node('img');img.src=t.artwork;img.alt=`${t.title} artwork`;img.loading='lazy';img.onerror=()=>img.remove();cover.replaceChildren(img);}
    info.append(node('h3',t.title),node('p',t.artist));row.append(cover,info);card.append(row);
    if(t.reason)card.append(node('p',t.reason,'reason'));
    const actions=node('div',undefined,'song-actions');
    if(t.listen_url)actions.append(telegramLink(t.listen_url,'Listen in Lil Bro ↗'));
    actions.append(action('More like this',async e=>{const b=e.currentTarget, version=++generation;b.disabled=true;$('status').textContent='Finding songs with a similar feel…';try{const next=preview?{tracks:demo.filter(d=>d.id!==t.id)}:await api('similar',{token:result.token,track_id:t.id});if(version===generation){remember(next);tracks(next);$('status').textContent=`More like ${t.title}.`;}}catch(error){if(version===generation)$('status').textContent=error.message;}finally{b.disabled=false;}}));
    card.append(actions,node('p','Opens Lil Bro with this song filled in. Press Send there, listen, then come back.','hint'));
    const heard=node('details',undefined,'heard');heard.append(node('summary','I’ve heard this · Rate song'));
    const ratings=node('div',undefined,'ratings');ratings.setAttribute('aria-label',`Rate ${t.title}`);
    for(const [value,label] of [['love','♥ Love'],['like','↑ Like'],['neutral','– Neutral'],['dislike','↓ Dislike']]){
      const b=action(label,async()=>{const buttons=[...ratings.children];buttons.forEach(x=>x.disabled=true);try{if(!preview)await api('rate',{token:result.token,track_id:t.id,value});buttons.forEach(x=>{x.classList.toggle('selected',x===b);x.setAttribute('aria-pressed',String(x===b));});$('status').textContent=preview?'Preview rating selected. Your real taste is unchanged.':'Saved. Getting closer to your sound.';tg?.HapticFeedback?.notificationOccurred('success');}catch(e){$('status').textContent=e.message;}finally{buttons.forEach(x=>x.disabled=false);}},'');b.setAttribute('aria-pressed','false');ratings.append(b);
    }
    heard.append(ratings);card.append(heard);$('content').append(card);
  }
}
function profile(p){$('content').replaceChildren();const box=node('div',undefined,'stats');for(const [value,label] of [[p.songs,'Songs rated'],[p.counts.love||0,'Loved songs'],[p.channels,'Channels']]){const stat=node('div',undefined,'stat');stat.append(node('strong',String(value)),node('span',label));box.append(stat);}$('content').append(node('p',`A sound that’s all yours, ${p.name}.`),box);for(const [title,items] of [['Your artists',p.artists],['Your flavors',p.tags]]){$('content').append(node('h3',title,'taste-title'));const chips=node('div',undefined,'chips');for(const item of items)chips.append(node('span',item,'chip'));if(!items.length)chips.append(node('p','Rate songs to start building your taste.','hint'));$('content').append(chips);}$('content').append(action('Manage playlist channels',()=>switchView('channels')),node('p','Manage your data with /privacy and /forgetme in the bot.','hint'));}
function channels(p){
  $('content').replaceChildren(node('p','Your playlists help me discover your taste. Channel songs are gentle hints; your own ratings matter more. Only new audio posts are learned after connection.','hint'));
  $('content').append(action('Connect a playlist channel +',async e=>{
    const b=e.currentTarget,version=generation;b.disabled=true;
    try{if(preview){$('status').textContent='Open from Telegram to connect your own channel.';return;}const result=await api('channels/connect',{});if(version!==generation)return;const box=node('section',undefined,'card connect-guide');box.append(node('h3','Connect your playlist'),node('p','1. Add @LIL_CUSINbot to your channel as an administrator. You must also be its creator or an administrator.','hint'),node('p','2. Leave optional posting, editing, deleting and invite permissions disabled. Lil Cusin never posts in your channel.','hint'),node('p','3. Post this code as a new text post within 10 minutes:','hint'));
      const code=node('textarea',result.code,'connection-code');code.value=result.code;code.readOnly=true;code.setAttribute('aria-label','Single-use channel connection code');box.append(code,action('Copy code',async()=>{try{await navigator.clipboard.writeText(result.code);$('status').textContent='Code copied. Paste it as a new post in your channel.';}catch{code.focus();code.select();$('status').textContent='Select and copy the code above.';}}),node('p','A new code replaces the previous one. Use /cancel in the bot to cancel. Older songs can be forwarded privately to the bot.','hint'),action('I posted it · Refresh',()=>switchView('channels')));$('content').prepend(box);$('status').textContent='';
    }catch(error){if(version===generation)$('status').textContent=error.message;}finally{b.disabled=false;}
  },'primary'));
  if(!p.channels.length)$('content').append(node('p','No playlist channels connected yet.','hint'));
  for(const c of p.channels){const card=node('article',undefined,'card channel-card');card.append(node('h3',c.title),node('span',({connected:'Connected',disconnected:'Disconnected',unavailable:'Bot access unavailable'})[c.status]||'Unavailable','chip'),node('p',`${c.learned} songs learned · ${c.review} need review`,'hint'));
    if(c.review)card.append(telegramLink('https://t.me/LIL_CUSINbot?text=%2Fchannels','Review songs in bot ↗','secondary'));
    if(c.status!=='disconnected')card.append(action('Disconnect',()=>{const confirm=node('div',undefined,'disconnect-choice');confirm.append(node('p','Disconnect this channel? Choose what happens to its learned taste. Your song ratings stay.','hint'));
      for(const [remove,label] of [[false,'Disconnect · Keep learned taste'],[true,'Disconnect · Remove learned taste']])confirm.append(action(label,async()=>{const buttons=[...confirm.querySelectorAll('button')],version=generation;buttons.forEach(b=>b.disabled=true);try{if(preview){c.status='disconnected';if(remove)c.learned=0;channels(p);$('status').textContent='Preview only. Your channels are unchanged.';}else{await api('channels/disconnect',{channel_id:c.id,remove_signals:remove});if(version===generation)await switchView('channels');}}catch(error){if(version===generation)$('status').textContent=error.message;}finally{buttons.forEach(b=>b.disabled=false);}}));
      confirm.append(action('Cancel',()=>confirm.remove()));card.append(confirm);
    }));
    else card.append(node('p','Use Connect above to link this channel again.','hint'));
    $('content').append(card);
  }
  $('content').append(action('Refresh channels',()=>switchView('channels')));
}
async function switchView(next, restored){view=next;const version=++generation;document.querySelectorAll('nav button').forEach(b=>{b.classList.toggle('active',b.dataset.view===view);if(b.dataset.view===view)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current');});$('search-form').hidden=view!=='search';$('view-title').textContent={'for-you':'Made for you',search:'Find your favorites',channels:'Your playlist channels',taste:'Your taste, taking shape'}[view];$('view-note').textContent=view==='taste'?'UNIQUELY YOU':view==='channels'?'FROM YOUR PLAYLISTS':'FOLLOW YOUR EARS';$('content').replaceChildren();$('status').textContent='';if(restored){lists.set(view,restored);tracks(restored);return;}if(view==='search'){if(lists.has(view))tracks(lists.get(view));$('query').focus();return;}$('status').textContent=preview?'A peek at your music space.':'Loading your music…';try{const result=preview?(view==='taste'?{name:'friend',songs:24,counts:{love:12},channels:2,artists:['Radiohead','Beach House','The xx'],tags:['Alternative','Dream pop','Indie']}:view==='channels'?demoChannels:{tracks:demo}):await api(view==='taste'?'profile':view==='channels'?'channels':'recommendations',view==='for-you'?{}:undefined);if(version!==generation)return;$('status').textContent='';if(view==='taste')profile(result);else if(view==='channels')channels(result);else{remember(result);tracks(result);}}catch(e){if(version===generation){$('status').textContent=e.message;empty('Couldn’t load your music','Tap a section to try again.');}}}
document.querySelectorAll('nav button').forEach(b=>b.onclick=()=>switchView(b.dataset.view));$('discover').onclick=()=>switchView('for-you');
$('search-form').onsubmit=async e=>{e.preventDefault();const version=++generation;const b=e.currentTarget.querySelector('button');b.disabled=true;$('status').textContent='Looking for your song…';try{const result=preview?{tracks:demo.filter(t=>`${t.artist} - ${t.title}`.toLowerCase().includes($('query').value.trim().toLowerCase()))}:await api('search',{query:$('query').value});if(version===generation){$('status').textContent=result.tracks.length?'Found these matches. Listen, then rate the right song.':'';remember(result);tracks(result);}}catch(error){if(version===generation)$('status').textContent=error.message;}finally{b.disabled=false;}};
$('preview').hidden=!preview;
let restored;try{const saved=JSON.parse(sessionStorage.getItem(storageKey));if(!preview&&saved&&Date.now()-saved.time<25*60*1000&&['for-you','search'].includes(saved.view)&&Array.isArray(saved.result?.tracks))restored=saved;}catch{}
switchView(restored?.view||'for-you',restored?.result);
