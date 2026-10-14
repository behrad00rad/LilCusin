let tg = window.Telegram?.WebApp;
let preview = !tg?.initData;
const $ = id => document.getElementById(id);
const languages={en:'English',fa:'فارسی',ar:'العربية',tr:'Türkçe',ru:'Русский',es:'Español',fr:'Français',de:'Deutsch'};
let locale='en',catalogue={},view='for-you',generation=0,guideStep=0,lastResult=null,guideDone=false,similarSeed=null;
const pageTrail=[];
const normalize=value=>{const code=String(value||'').toLowerCase().split(/[-_]/)[0];return languages[code]?code:'en';};
const t=(key,values={})=>String(catalogue[locale]?.[key]??catalogue.en?.[key]??key).replace(/\{(\w+)\}/g,(_,k)=>String(values[k]??`{${k}}`));
const lists=new Map();let storageKey='lilcusin-list-preview';
const storageRead=key=>{try{return localStorage.getItem(key);}catch{return null;}};
const storageWrite=(key,value)=>{try{localStorage.setItem(key,value);}catch{}};
const demo=[{id:1,title:'Everything In Its Right Place',artist:'Radiohead',album:'Kid A',artwork:'https://lastfm-img.freetls.fastly.net/i/u/300x300/2ed343318c844d19cd897ec67fad11c4.png'},{id:2,title:'Space Song',artist:'Beach House',album:'Depression Cherry',artwork:'https://lastfm-img.freetls.fastly.net/i/u/300x300/92ee7e4f3afdbe6a9a8c13a4a790baf1.png'},{id:3,title:'Intro',artist:'The xx'},{id:4,title:'Teardrop',artist:'Massive Attack'},{id:5,title:'Roads',artist:'Portishead'},{id:6,title:'Says',artist:'Nils Frahm'}].map(song=>({...song,listen_url:`https://t.me/musicbehbot?text=${encodeURIComponent(song.artist+' '+song.title)}`}));
const demoChannels={channels:[{id:1,title:'Late night favorites',status:'connected',learned:18,review:1},{id:2,title:'Sunday mixtape',status:'disconnected',learned:6,review:0}]};
function node(tag,text,className){const el=document.createElement(tag);if(text!==undefined)el.textContent=text;if(className)el.className=className;return el;}
function action(label,run,className='secondary'){const b=node('button',label,className);b.type='button';b.onclick=run;return b;}
function externalIcon(){const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 24 24');svg.setAttribute('class','external-icon');svg.setAttribute('aria-hidden','true');const path=document.createElementNS(svg.namespaceURI,'path');path.setAttribute('d','M7 17 17 7M7 7h10v10');svg.append(path);return svg;}
function link(url,label,className='primary'){const a=node('a',label,className);a.append(externalIcon());a.href=url;a.onclick=e=>{if(tg?.openTelegramLink){e.preventDefault();tg.openTelegramLink(url);}};if(className==='primary')a.title=t('listen_hint');return a;}
function status(text=''){$('status').textContent=text;}
let toastTimer;function notice(text){const el=$('toast');el.textContent=text;el.hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>el.hidden=true,3500);}
function safeArea(){const s=document.documentElement.style;for(const side of ['top','bottom'])s.setProperty(`--safe-${side}`,`${Math.max(tg?.safeAreaInset?.[side]||0,tg?.contentSafeAreaInset?.[side]||0)}px`);}
function telegramCall(run){try{run();}catch{}}
async function initializeTelegram(){
 const expected=/tgWebAppData=/.test(location.hash)||/tgWebAppData=/.test(location.search);
 for(let i=0;i<50&&!window.Telegram?.WebApp;i++)await delay(100);
 tg=window.Telegram?.WebApp;preview=!tg?.initData;
 if(expected&&preview)throw new Error(t('open_telegram'));
 storageKey='lilcusin-list-'+(tg?.initDataUnsafe?.user?.id||'preview');
 telegramCall(()=>tg?.ready());telegramCall(()=>tg?.expand());safeArea();
 telegramCall(()=>tg?.onEvent('safeAreaChanged',safeArea));telegramCall(()=>tg?.onEvent('contentSafeAreaChanged',safeArea));
 telegramCall(()=>tg?.BackButton?.onClick(()=>restorePage()));
}
async function api(path,data,timeout=35000){const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),timeout);try{const response=await fetch(`/api/${path}`,{method:data===undefined?'GET':'POST',headers:{'Content-Type':'application/json','X-Telegram-Init-Data':tg.initData},body:data===undefined?undefined:JSON.stringify(data),signal:controller.signal});let result;try{result=await response.json();}catch{throw new Error(t('error'));}if(!response.ok)throw new Error(t(response.status===401?'open_telegram':response.status===400?'invalid':response.status===403?'stale':'error'));return result;}catch(error){if(error.name==='AbortError')throw new Error(t('error'));throw error;}finally{clearTimeout(timer);}}
function labels(){document.documentElement.lang=locale;document.documentElement.dir=['fa','ar'].includes(locale)?'rtl':'ltr';$('language').value=locale;$('guide-language').value=locale;$('guide-language').setAttribute('aria-label',t('language'));for(const [id,key] of Object.entries({'hero-title':'hero_title','hero-note':'hero_note',discover:'find_song',preview:'preview','query-label':'search_label','search-button':'search','search-hint':'search_hint','language-label':'language','guide-link':'guide'}))$(id).textContent=t(key);$('help').setAttribute('aria-label',t('guide'));document.querySelectorAll('[data-key]').forEach(el=>el.textContent=t(el.dataset.key));writePageTitle($('view-title'),view,similarSeed);renderBreadcrumbs();}
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
let languageChanging=false,languageWatchdog,languageSaveQueue=Promise.resolve();
function resetLanguageTransition(){
 clearTimeout(languageWatchdog);const curtain=$('language-curtain');
 if(curtain){try{curtain.hidePopover?.();}catch{}curtain.hidden=true;}
 document.documentElement.classList.remove('switching-language','curtain-fallback');
 for(const id of ['language','guide-language']){const select=$(id);if(select){select.disabled=false;select.value=locale;}}
 languageChanging=false;
}
function saveLanguage(next){
 if(preview){storageWrite('lilcusin-preview-language',next);return;}
 languageSaveQueue=languageSaveQueue.catch(()=>{}).then(()=>api('preferences/update',{language:next},8000)).catch(()=>{if(locale===next)notice(t('language_save_error'));});
}
async function chooseLanguage(event){
 const next=event.currentTarget.value;if(next===locale||languageChanging||!languages[next])return;
 languageChanging=true;const curtain=$('language-curtain'),position=window.scrollY,focused=document.activeElement;
 const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
 languageWatchdog=setTimeout(resetLanguageTransition,1800);
 try{
  for(const id of ['language','guide-language'])$(id).disabled=true;
  document.documentElement.classList.add('switching-language');
  if(!reduced){const label=curtain.querySelector('span');label.textContent=languages[next];label.lang=next;label.dir=['fa','ar'].includes(next)?'rtl':'ltr';curtain.className='language-curtain language-curtain-cover';curtain.hidden=false;
   try{if(typeof curtain.showPopover!=='function')throw new Error();curtain.showPopover();}catch{document.documentElement.classList.add('curtain-fallback');}
   await delay(160);
  }
  locale=next;labels();
  if(lastResult){if(['for-you','search','similar','channel'].includes(view)&&$('content').querySelector('.replacement-slot,.is-rated')){for(const old of $('content').querySelectorAll('[data-track-id]:not(.is-rated)'))old.replaceWith(makeCard(old.songData,old.songData.token));for(const hint of $('content').querySelectorAll('.replacement-slot .hint'))hint.textContent=t('loading');}else render(lastResult);}
  if($('guide-dialog').open)renderGuide();
  try{window.scrollTo(0,position);focused?.isConnected&&focused.focus({preventScroll:true});}catch{}
  saveLanguage(next);
  if(!reduced){curtain.className='language-curtain language-curtain-reveal';await delay(180);}
 }catch{notice(t('error'));}
 finally{resetLanguageTransition();}
}
function guideVisual(){
 const box=$('guide-visual');box.replaceChildren();box.dataset.step=guideStep;
 const song=node('div',undefined,'guide-song');song.append(node('span','♪','guide-art'),node('div',undefined,'guide-song-name'));song.lastChild.append(node('strong','Creep'),node('span','Radiohead'));
 if(guideStep===0){const search=node('div',undefined,'guide-search');search.append(node('span','Radiohead - Creep'),node('span',t('search'),'guide-mini-button'));box.append(search,node('span','↓','guide-flow'),song);}
 if(guideStep===1){const route=node('div',undefined,'guide-route');for(const [i,key] of ['listen','guide_send','guide_return'].entries()){const item=node('div',undefined,'guide-route-step');item.append(node('span',String(i+1),'guide-number'),node('span',t(key)));route.append(item);}box.append(song,route);}
 if(guideStep===2){box.append(song);const rating=node('div',undefined,'guide-rating');rating.append(node('span','♥ '+t('love'),'guide-loved'),node('span','↑ '+t('like')),node('span','↓ '+t('dislike')));box.append(rating,node('p',t('guide_new_song'),'guide-caption'));}
}
function renderGuide(){const n=guideStep+1;$('guide-title').textContent=t(`g${n}_title`);$('guide-text').textContent=t(`g${n}_text`);$('guide-step').textContent=t('step',{n});$('guide-skip').textContent=t('skip');$('guide-back').textContent=t('back');$('guide-back').hidden=guideStep===0;$('guide-next').textContent=t(guideStep===2?'done':'next');guideVisual();const dots=$('guide-dialog').querySelector('.guide-dots');dots.replaceChildren(...[0,1,2].map(i=>node('span',undefined,i===guideStep?'current':'')));$('guide-status').textContent='';if(!languageChanging&&!matchMedia('(prefers-reduced-motion: reduce)').matches){for(const id of ['guide-title','guide-text'])$(id).animate([{opacity:.35,transform:'translateY(4px)'},{opacity:1,transform:'none'}],{duration:180,easing:'ease-out'});}}
function showGuide(){guideStep=0;renderGuide();if(!$('guide-dialog').open)$('guide-dialog').showModal();}
async function closeGuide(start=false){const b=$('guide-next');b.disabled=true;try{if(!preview)await api('preferences/update',{ui_guide_done:true});else storageWrite('lilcusin-preview-guide','done');guideDone=true;$('guide-dialog').close();if(start)await switchView('search');}catch(error){$('guide-status').textContent=error.message;}finally{b.disabled=false;}}
function remember(result){lists.set(view,result);if(!preview&&['for-you','search'].includes(view))try{sessionStorage.setItem(storageKey,JSON.stringify({view,result,time:Date.now()}));}catch{}}
function empty(title,detail,search=false){const box=node('div',undefined,'empty');box.append(node('span','🦉'),node('h3',title),node('p',detail));if(search)box.append(action(t('find_song'),()=>switchView('search'),'primary'));$('content').replaceChildren(box);}
function tracks(result){$('content').replaceChildren();if(!result.tracks.length){empty(t('empty_title'),t(view==='search'?'no_matches':result.status==='insufficient_preferences'?'empty_hint':'no_recs'),view!=='search');return;}
 for(const song of result.tracks)$('content').append(makeCard(song,song.token||result.token));
}
function makeCard(song,token){const card=node('article',undefined,'card'),row=node('div',undefined,'track'),cover=node('div','♪','cover'),info=node('div');if(song.artwork){setArtwork(cover,song.artwork);}info.append(node('h3',song.title),node('p',song.artist));row.append(cover,info);card.append(row);
 if(song.reason){const key=Object.keys(catalogue.en).find(key=>key.startsWith('reason_')&&catalogue.en[key]===song.reason);card.append(node('p',key?t(key):song.reason,'reason'));}
 const buttons=node('div',undefined,'song-actions');if(song.listen_url)buttons.append(link(song.listen_url,t('listen')));buttons.append(action(t('more'),event=>openSimilar(card,event.currentTarget)));card.append(buttons);
 const heard=node('details',undefined,'heard');heard.append(node('summary',t('heard')));const ratings=node('div',undefined,'ratings');ratings.setAttribute('aria-label',t('heard'));
 for(const [value,mark] of [['love','♥'],['like','↑'],['neutral','–'],['dislike','↓']]){const b=action(`${mark} ${t(value)}`,async event=>{const all=[...ratings.children],version=generation;all.forEach(x=>x.disabled=true);try{if(!preview)await api('rate',{token:card.songData.token,track_id:song.id,value});else{previewRated.add(song.id);previewRatings.set(song.id,value);}if(version===generation){all.forEach(x=>x.setAttribute('aria-pressed',String(x===b)));all.forEach(x=>x.classList.toggle('selected',x===b));notice(t(preview?'preview_only':'saved'));telegramCall(()=>tg?.HapticFeedback?.notificationOccurred('success'));if(view==='channel-review'){await backToChannel();}else swapRatedCard(card,event.detail===0);}}catch(error){if(version===generation)status(error.message);}finally{if(!card.classList.contains('is-rated'))all.forEach(x=>x.disabled=false);}},'');b.dataset.rating=value;b.setAttribute('aria-pressed','false');ratings.append(b);}heard.append(ratings);card.append(heard);card.songData={...song,token};card.dataset.trackId=String(song.id);if(song.rating){heard.open=true;for(const b of ratings.children){const selected=b.dataset.rating===song.rating;b.classList.toggle('selected',selected);b.setAttribute('aria-pressed',String(selected));}}scheduleArtwork();return card;
}

let replacementQueue=Promise.resolve();
const visibleIds=()=>[...$('content').querySelectorAll('[data-track-id]')].map(el=>Number(el.dataset.trackId));
function rememberVisible(){const songs=[...$('content').querySelectorAll('[data-track-id]')].map(el=>el.songData);const result={...lastResult,tracks:songs};lastResult=result;remember(result);}
async function swapRatedCard(card,focusAfter){
 const version=generation,reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;card.classList.add('is-rated');
 const height=card.getBoundingClientRect().height;
 const exit=reduced?Promise.resolve():card.animate([{opacity:1,transform:'translateX(0) scale(1)'},{opacity:0,transform:`translateX(${['fa','ar'].includes(locale)?60:-60}px) rotate(-2deg) scale(.97)`}],{duration:260,easing:'cubic-bezier(.4,0,.2,1)',fill:'forwards'}).finished.catch(()=>{});
 await exit;if(version!==generation||!card.isConnected)return;
 const slot=node('article',undefined,'card replacement-slot');slot.style.minHeight=`${Math.max(170,Math.min(height,310))}px`;slot.setAttribute('aria-busy','true');slot.append(node('div',undefined,'loading-cover'),node('p',t('loading'),'hint'));card.replaceWith(slot);rememberVisible();
 replacementQueue=replacementQueue.catch(()=>{}).then(()=>fillReplacement(slot,version,focusAfter));
}
async function fillReplacement(slot,version,focusAfter){
 if(version!==generation||!slot.isConnected)return;
 try{
  const exclude=visibleIds();let result;
  if(preview){const next=demo.find(song=>!exclude.includes(song.id)&&!previewRated.has(song.id));result={tracks:next?[next]:[]};}
  else{const current=[...$('content').querySelectorAll('[data-track-id]:not(.is-rated)')].map(el=>({id:el.songData.id,token:el.songData.token}));result=await api(view==='channel'?'channels/songs':'recommendations',{replace:true,exclude,current,...(view==='channel'?{channel_id:similarSeed.id,filter:'unrated'}:{})});}
  if(version!==generation||!slot.isConnected)return;
  if(!preview)for(const el of $('content').querySelectorAll('[data-track-id]:not(.is-rated)'))el.songData.token=result.token;
  const song=result.tracks.find(song=>!visibleIds().includes(song.id));const positions=new Map([...$('content').children].filter(el=>el!==slot).map(el=>[el,el.getBoundingClientRect().top]));
  if(song){for(const end of $('content').querySelectorAll('.end-card'))end.remove();const fresh=makeCard(song,result.token);slot.replaceWith(fresh);if(!matchMedia('(prefers-reduced-motion: reduce)').matches)fresh.animate([{opacity:0,transform:`translateX(${['fa','ar'].includes(locale)?-40:40}px) scale(.98)`},{opacity:1,transform:'none'}],{duration:320,easing:'cubic-bezier(.2,.8,.2,1)'});if(focusAfter){fresh.tabIndex=-1;fresh.focus({preventScroll:true});}}
  else{slot.className='card end-card';slot.style.minHeight='';slot.replaceChildren(node('p',t(view==='channel'?'all_rated':'no_recs'),'hint'),action(t(view==='channel'?'all_songs':'find_song'),()=>view==='channel'?openChannel(similarSeed,'all',0,[0],true):switchView('search')));slot.removeAttribute('aria-busy');}
  if(!matchMedia('(prefers-reduced-motion: reduce)').matches)for(const [el,top] of positions){const delta=top-el.getBoundingClientRect().top;if(el.isConnected&&delta&&!el.classList.contains('is-rated'))el.animate([{transform:`translateY(${delta}px)`},{transform:'none'}],{duration:300,easing:'cubic-bezier(.2,.8,.2,1)'});}
  rememberVisible();
 }catch(error){if(version!==generation||!slot.isConnected)return;slot.setAttribute('aria-busy','false');slot.replaceChildren(node('p',error.message,'hint'),action(t('retry'),()=>{slot.replaceChildren(node('p',t('loading'),'hint'));replacementQueue=replacementQueue.catch(()=>{}).then(()=>fillReplacement(slot,version,focusAfter));}));}
}
const previewRated=new Set(),previewRatings=new Map(),previewIdentifiedChannels=new Set();
function profile(p){$('content').replaceChildren();const box=node('div',undefined,'stats');for(const [value,key] of [[p.songs,'ratings_count'],[p.counts.love||0,'loved_count'],[p.channels,'channels']]){const stat=node('div',undefined,'stat');stat.append(node('strong',String(value)),node('span',t(key)));box.append(stat);}$('content').append(box);for(const [key,items] of [['artists',p.artists],['tags',p.tags]]){$('content').append(node('h3',t(key),'taste-title'));const chips=node('div',undefined,'chips');for(const item of items)chips.append(node('span',item,'chip'));if(!items.length)chips.append(node('p',t('empty_hint'),'hint'));$('content').append(chips);}$('content').append(action(t('channels'),()=>switchView('channels')),node('p',t('privacy_hint'),'hint'));}
function channels(p){$('content').replaceChildren(node('p',t('channels_hint'),'hint'));$('content').append(action(t('connect'),async e=>{const b=e.currentTarget,version=generation;b.disabled=true;try{if(preview){status(t('open_telegram'));return;}const result=await api('channels/connect',{});if(version!==generation)return;const box=node('section',undefined,'card connect-guide');box.append(node('h3',t('connect')),...['connect1','connect2','connect3'].map(key=>node('p',t(key),'hint')));const code=node('textarea',result.code,'connection-code');code.value=result.code;code.readOnly=true;code.setAttribute('aria-label',t('copy'));box.append(code,action(t('copy'),async()=>{try{await navigator.clipboard.writeText(result.code);notice(t('copied'));}catch{code.focus();code.select();}}),node('p',t('code_note'),'hint'),action(t('refresh'),()=>switchView('channels')));$('content').prepend(box);status();}catch(error){if(version===generation)status(error.message);}finally{b.disabled=false;}},'primary'));
 if(!p.channels.length)$('content').append(node('p',t('no_channels'),'hint'));
 for(const c of p.channels){const card=node('article',undefined,'card channel-card');card.append(node('h3',c.title),node('span',t(['connected','disconnected'].includes(c.status)?c.status:'unavailable'),'chip'),node('p',t('channel_counts',{learned:c.learned,review:c.review}),'hint'));card.append(action(t('browse_songs'),()=>openChannel(c),'primary'));if(c.review)card.append(action(t('identify_songs')+' · '+c.review,()=>openChannel(c,'review')));
 if(c.status!=='disconnected')card.append(action(t('disconnect'),()=>{if(card.querySelector('.disconnect-choice'))return;const box=node('div',undefined,'disconnect-choice');box.append(node('p',t('disconnect_question'),'hint'));for(const [remove,key] of [[false,'keep'],[true,'remove']])box.append(action(t(key),async()=>{const version=generation,buttons=[...box.querySelectorAll('button')];buttons.forEach(b=>b.disabled=true);try{if(preview){status(t('preview_only'));box.remove();}else{await api('channels/disconnect',{channel_id:c.id,remove_signals:remove});if(version===generation)await switchView('channels');}}catch(error){if(version===generation)status(error.message);}finally{buttons.forEach(b=>b.disabled=false);}}));box.append(action(t('cancel'),()=>box.remove()));card.append(box);}));else card.append(node('p',t('reconnect'),'hint'));$('content').append(card);}$('content').append(action(t('refresh'),()=>switchView('channels')));
}
function render(result){if(view==='channel')channelDetail(result);else if(view==='channel-review')reviewDetail(result);else if(view==='taste')profile(result);else if(view==='channels')channels(result);else tracks(result);}
function pageTitle(page,seed){return ['channel','channel-review'].includes(page)?(page==='channel'?seed?.title||t('channels'):t('identify_songs')):page==='similar'?t('more_title',{song:seed?.title||''}):t({'for-you':'for_you',search:'search',channels:'channels',taste:'taste'}[page]);}
function writePageTitle(element,page,seed){if(page!=='similar'){element.textContent=pageTitle(page,seed);return;}const [before,after='']=t('more_title',{song:'{song}'}).split('{song}'),opening=before.match(/[“«„]$/)?.[0]||'',closing=after.match(/^[”»“]/)?.[0]||'',title=node('bdi',opening+(seed?.title||'')+closing);title.dir='auto';element.replaceChildren(document.createTextNode(opening?before.slice(0,-1):before),title,document.createTextNode(closing?after.slice(1):after));}
function renderBreadcrumbs(){const nav=$('breadcrumbs');nav.hidden=!pageTrail.length;nav.replaceChildren();if(!pageTrail.length){telegramCall(()=>tg?.BackButton?.hide());return;}telegramCall(()=>tg?.BackButton?.show());
 const list=node('ol');pageTrail.forEach((page,index)=>{const item=node('li');const button=action('',()=>restorePage(index),'breadcrumb-link');writePageTitle(button,page.view,page.seed);item.append(button);list.append(item);});const here=node('li',view==='similar'?t('more_short'):pageTitle(view,similarSeed));here.setAttribute('aria-current','page');list.append(here);nav.append(list);nav.setAttribute('aria-label',t('breadcrumb_label'));
}
function snapshot(){const result=['for-you','search','similar','channel'].includes(view)?{...lastResult,tracks:[...$('content').querySelectorAll('[data-track-id]:not(.is-rated)')].map(el=>({...el.songData}))}:lastResult;return {view,seed:similarSeed,result,query:$('query').value,scroll:window.scrollY};}
async function restorePage(index=pageTrail.length-1){if(index<0)return;const page=pageTrail[index];pageTrail.splice(index);$('query').value=page.query;await switchView(page.view,page.result,{keepTrail:true,seed:page.seed,scroll:page.scroll});}

async function openSimilar(card,button){const song=card.songData,version=generation;button.disabled=true;status(t('loading'));try{const next=preview?{tracks:demo.filter(s=>s.id!==song.id)}:await api('similar',{token:song.token,track_id:song.id});if(version!==generation||!card.isConnected)return;pageTrail.push(snapshot());if(pageTrail.length>12)pageTrail.splice(1,1);await switchView('similar',next,{keepTrail:true,seed:{id:song.id,title:song.title,artist:song.artist}});}catch(error){if(version===generation)status(error.message);}finally{button.disabled=false;}}
async function switchView(next,restored,options={}){
 if(!options.keepTrail)pageTrail.length=0;similarSeed=options.seed||null;view=next;document.querySelector('.hero').hidden=view!=='for-you';const version=++generation;lastResult=null;
 document.querySelectorAll('.main-nav button').forEach(b=>{const active=b.dataset.view===(['similar','channel','channel-review'].includes(view)?pageTrail[0]?.view:view);b.classList.toggle('active',active);if(active)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current');});$('search-form').hidden=view!=='search';$('channel-tools').hidden=view!=='channel';$('channel-pagination').replaceChildren();labels();$('content').replaceChildren();status();
 if(restored){lastResult=restored;render(restored);window.scrollTo({top:options.scroll||0,behavior:'instant'});return;}
 if(view==='search'){if(lists.has(view)){lastResult=lists.get(view);tracks(lastResult);}$('query').focus({preventScroll:true});return;}
 status(t('loading'));try{const result=preview?(view==='taste'?{songs:24,counts:{love:12},channels:2,artists:['Radiohead','Beach House','The xx'],tags:['Alternative','Dream pop','Indie']}:view==='channels'?demoChannels:{tracks:demo.slice(0,3)}):await api(view==='taste'?'profile':view==='channels'?'channels':'recommendations',view==='for-you'?{}:undefined);if(version!==generation)return;lastResult=result;status();if(view==='for-you')remember(result);render(result);}catch(error){if(version===generation){status(error.message);empty(t('error'),'');$('content').append(action(t('retry'),()=>switchView(view)));}}
}
function setArtwork(cover,url){const img=node('img');img.src=url;img.alt='';img.loading='lazy';img.decoding='async';img.onerror=()=>{cover.replaceChildren(document.createTextNode('♪'));cover.dataset.artFailed='true';};cover.replaceChildren(img);}
let artTimer;
function scheduleArtwork(){if(preview)return;clearTimeout(artTimer);const version=generation;artTimer=setTimeout(()=>pollArtwork(version,0),1200);}
async function pollArtwork(version,attempt){
 if(version!==generation)return;const groups=new Map();
 for(const card of $('content').querySelectorAll('[data-track-id]:not(.is-rated)')){const cover=card.querySelector('.cover');if(!cover||cover.querySelector('img')||cover.dataset.artFailed)continue;const key=card.songData.token;if(!groups.has(key))groups.set(key,[]);groups.get(key).push(card);}
 for(const [token,cards] of groups){try{const result=await api('artwork',{token,track_ids:cards.slice(0,10).map(c=>c.songData.id)},10000);if(version!==generation)return;for(const card of cards){const url=result.artwork?.[String(card.songData.id)];if(url&&card.isConnected){card.songData.artwork=url;setArtwork(card.querySelector('.cover'),url);}}}catch{}}
 if(attempt<3&&groups.size&&version===generation)artTimer=setTimeout(()=>pollArtwork(version,attempt+1),[2500,5000,9000][attempt]);
}
async function openChannel(channel,filter='all',cursor=0,cursors=[0],keepTrail=false){
 const version=generation;status(t('loading'));
 try{const result=preview?{channel,filter,tracks:filter==='review'?[]:demo.filter(s=>filter!=='unrated'||!previewRated.has(s.id)).slice(0,3).map(s=>({...s,rating:previewRatings.get(s.id)||null})),items:filter==='review'&&!previewIdentifiedChannels.has(channel.id)?[{id:1,title:'',artist:''}]:[],next_cursor:null}:await api('channels/songs',{channel_id:channel.id,filter,cursor});
  if(version!==generation)return;if(!keepTrail)pageTrail.push(snapshot());await switchView('channel',result,{keepTrail:true,seed:{...channel,filter,cursor,cursors}});
 }catch(error){if(version===generation)status(error.message);}
}
function channelDetail(result){
 const channel=similarSeed;$('channel-tools').hidden=false;const filters=node('div',undefined,'channel-filters');filters.setAttribute('aria-label',t('channel_filter'));
 for(const [value,key] of [['all','all_songs'],['unrated','unrated'],['review','identify_songs']]){const button=action(t(key),()=>openChannel(channel,value,0,[0],true),'filter-button');button.dataset.key=key;button.setAttribute('aria-pressed',String(result.filter===value));filters.append(button);}
 const hint=node('p',t('channel_history'),'hint');hint.dataset.key='channel_history';$('channel-tools').replaceChildren(filters,hint);
 if(result.filter==='review'){$('content').replaceChildren();for(const item of result.items){const card=node('article',undefined,'card review-post');card.append(node('h3',item.title||t('unknown_song')),node('p',item.artist||t('missing_artist'),'hint'),action(t('identify_song'),()=>openReview(item,result.token),'primary'));$('content').append(card);}if(!result.items.length)empty(t('review_clear'),t('review_clear_hint'));}
 else{tracks(result);if(!result.tracks.length)empty(t(result.filter==='unrated'?'all_rated':'channel_empty'),t('channel_history'));}
 const pagination=$('channel-pagination');pagination.replaceChildren();const cursors=channel.cursors||[0];
 if(cursors.length>1)pagination.append(action(t('back'),()=>openChannel(channel,result.filter,cursors.at(-2),cursors.slice(0,-1),true)));
 if(result.next_cursor)pagination.append(action(t('next'),()=>openChannel(channel,result.filter,result.next_cursor,[...cursors,result.next_cursor],true)));
}
async function openReview(item,token){const channel=similarSeed,version=generation;status(t('loading'));try{const result=preview?{kind:'candidates',post_id:item.id,channel_id:channel.id,revision:1,token:'preview',candidates:demo.slice(0,2).map((s,index)=>({...s,index}))}:await api('channels/review',{channel_id:channel.id,post_id:item.id,token,action:'open'});if(version!==generation)return;pageTrail.push(snapshot());await switchView('channel-review',result,{keepTrail:true,seed:{...channel,post_id:item.id}});}catch(error){if(version===generation)status(error.message);}}
async function backToChannel(){const channel={...similarSeed};const index=pageTrail.map(p=>p.view).lastIndexOf('channel');if(index>=0)pageTrail.splice(index);await openChannel(channel,channel.filter||'all',0,[0],true);}
function reviewDetail(result){
 $('content').replaceChildren();const box=node('section',undefined,'card identify-panel');
 if(result.kind==='confirmed'){tracks(result);$('content').prepend(node('p',t('identified'),'hint'));$('content').append(action(t('back_channel'),backToChannel));return;}
 box.append(node('p',t('choose_identity'),'hint'));
 for(const candidate of result.candidates||[]){const button=action('',()=>reviewAction('select',{index:candidate.index}),'candidate-button');button.append(node('strong',candidate.title),node('span',candidate.artist));box.append(button);}
 if(result.kind==='limit')box.append(node('p',t('review_limit'),'hint'),action(t('retry'),()=>reviewAction('open')));
 else{const form=node('form',undefined,'identity-search'),label=node('label',t('review_search_label')),input=node('input');input.placeholder='Radiohead - Creep';input.dir='auto';input.required=true;input.maxLength=240;input.id='identity-query';label.htmlFor=input.id;const submit=node('button',t('search'),'primary');submit.type='submit';form.append(label,input,submit);form.onsubmit=e=>{e.preventDefault();reviewAction('search',{query:input.value});};box.append(node('p',t('identity_correction'),'hint'),form);}
 box.append(action(t('back_channel'),backToChannel));$('content').append(box);
}
async function reviewAction(action,extra={}){const version=generation,result=lastResult,buttons=[...$('content').querySelectorAll('button')];buttons.forEach(b=>b.disabled=true);status(t('loading'));try{const next=preview?{kind:'confirmed',tracks:[demo[0]],token:'preview'}:await api('channels/review',{channel_id:similarSeed.id,post_id:similarSeed.post_id,token:result.token,revision:result.revision,action,...extra});if(version!==generation)return;if(preview&&next.kind==='confirmed'){previewIdentifiedChannels.add(similarSeed.id);const channel=demoChannels.channels.find(c=>c.id===similarSeed.id);if(channel)channel.review=0;}lastResult=next;reviewDetail(next);status();}catch(error){if(version===generation)status(error.message);}finally{buttons.forEach(b=>b.disabled=false);}}

async function boot(){
 resetLanguageTransition();status('Opening Lil Cusin… / در حال باز شدن…');
 try{
  const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),8000);let response;
  try{response=await fetch('/locales.json',{signal:controller.signal});if(!response.ok)throw new Error();catalogue=await response.json();}finally{clearTimeout(timer);}
  locale=normalize(navigator.language);labels();status(t('loading'));
  await initializeTelegram();locale=normalize(tg?.initDataUnsafe?.user?.language_code||navigator.language);
  if(preview){locale=normalize(storageRead('lilcusin-preview-language')||locale);guideDone=storageRead('lilcusin-preview-guide')==='done';}
  for(const id of ['language','guide-language'])$(id).replaceChildren();
  for(const [code,label] of Object.entries(languages)){const option=node('option',label);option.value=code;$('language').append(option);$('guide-language').append(option.cloneNode(true));}
  labels();$('preview').hidden=!preview;
  $('language').onchange=chooseLanguage;$('guide-language').onchange=chooseLanguage;$('help').onclick=showGuide;$('guide-link').onclick=showGuide;
  $('guide-back').onclick=()=>{guideStep--;renderGuide();};$('guide-next').onclick=()=>{if(guideStep===2)closeGuide(true);else{guideStep++;renderGuide();}};$('guide-skip').onclick=()=>closeGuide(false);
  $('guide-dialog').oncancel=event=>{event.preventDefault();closeGuide(false);};
  document.querySelectorAll('.main-nav button').forEach(b=>b.onclick=()=>switchView(b.dataset.view));$('discover').onclick=()=>switchView('search');
  $('search-form').onsubmit=async event=>{event.preventDefault();const version=++generation,b=$('search-button');b.disabled=true;status(t('loading'));try{const term=$('query').value.trim().toLocaleLowerCase();const result=preview?{tracks:demo.filter(s=>`${s.artist} - ${s.title}`.toLocaleLowerCase().includes(term)||s.title.toLocaleLowerCase().includes(term))}:await api('search',{query:$('query').value});if(version===generation){lastResult=result;remember(result);tracks(result);status(result.tracks.length?t('found'):'');}}catch(error){if(version===generation)status(error.message);}finally{b.disabled=false;}};
  if(!preview){for(const id of ['language','guide-language'])$(id).disabled=true;const prefs=await api('preferences',undefined,8000);locale=normalize(prefs.language);guideDone=prefs.ui_guide_done;labels();}
  let saved;try{saved=JSON.parse(sessionStorage.getItem(storageKey));if(preview||!saved||Date.now()-saved.time>25*60*1000||!['for-you','search'].includes(saved.view)||!Array.isArray(saved.result?.tracks)||!saved.result.tracks.length)saved=null;}catch{}
  if(!guideDone)showGuide();await switchView(saved?.view||'for-you',saved?.result);
 }catch{
  status(catalogue.en?t('startup_error'):'Could not connect. Try again. / وصل نشد. دوباره تلاش کن.');
  $('content').replaceChildren(action(catalogue.en?t('retry'):'Retry / تلاش دوباره',()=>location.reload(),'primary'));
 }finally{resetLanguageTransition();}
}
document.addEventListener('visibilitychange',()=>{if(document.hidden)resetLanguageTransition();});
window.addEventListener('pagehide',resetLanguageTransition);
boot();
