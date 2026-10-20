/* Static Lucide SVG subset. https://github.com/lucide-icons/lucide
ISC License

Copyright (c) 2026 Lucide Icons and Contributors

Permission to use, copy, modify, and/or distribute this software for any
purpose with or without fee is hereby granted, provided that the above
copyright notice and this permission notice appear in all copies.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

---

The following Lucide icons are derived from the Feather project:

airplay, alert-circle, alert-octagon, alert-triangle, aperture, arrow-down-circle, arrow-down-left, arrow-down-right, arrow-down, arrow-left-circle, arrow-left, arrow-right-circle, arrow-right, arrow-up-circle, arrow-up-left, arrow-up-right, arrow-up, at-sign, calendar, cast, check, chevron-down, chevron-left, chevron-right, chevron-up, chevrons-down, chevrons-left, chevrons-right, chevrons-up, circle, clipboard, clock, code, columns, command, compass, corner-down-left, corner-down-right, corner-left-down, corner-left-up, corner-right-down, corner-right-up, corner-up-left, corner-up-right, crosshair, database, divide-circle, divide-square, dollar-sign, download, external-link, feather, frown, hash, headphones, help-circle, info, italic, key, layout, life-buoy, link-2, link, loader, lock, log-in, log-out, maximize, meh, minimize, minimize-2, minus-circle, minus-square, minus, monitor, moon, more-horizontal, more-vertical, move, music, navigation-2, navigation, octagon, pause-circle, percent, plus-circle, plus-square, plus, power, radio, rss, search, server, share, shopping-bag, sidebar, smartphone, smile, square, table-2, tablet, target, terminal, trash-2, trash, triangle, tv, type, upload, x-circle, x-octagon, x-square, x, zoom-in, zoom-out

The MIT License (MIT) (for the icons listed above)

Copyright (c) 2013-present Cole Bemis

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

*/
const iconShapes={"house":[["path",{"d":"M15 21v-8a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1v8"}],["path",{"d":"M3 10a2 2 0 0 1 .709-1.528l7-6a2 2 0 0 1 2.582 0l7 6A2 2 0 0 1 21 10v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"}]],"search":[["path",{"d":"m21 21-4.34-4.34"}],["circle",{"cx":"11","cy":"11","r":"8"}]],"arrow-left-right":[["path",{"d":"M8 3 4 7l4 4"}],["path",{"d":"M4 7h16"}],["path",{"d":"m16 21 4-4-4-4"}],["path",{"d":"M20 17H4"}]],"user-round":[["circle",{"cx":"12","cy":"8","r":"5"}],["path",{"d":"M20 21a8 8 0 0 0-16 0"}]],"download":[["path",{"d":"M12 15V3"}],["path",{"d":"M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"}],["path",{"d":"m7 10 5 5 5-5"}]],"heart":[["path",{"d":"M2 9.5a5.5 5.5 0 0 1 9.591-3.676.56.56 0 0 0 .818 0A5.49 5.49 0 0 1 22 9.5c0 2.29-1.5 4-3 5.5l-5.492 5.313a2 2 0 0 1-3 .019L5 15c-1.5-1.5-3-3.2-3-5.5"}]],"plus":[["path",{"d":"M5 12h14"}],["path",{"d":"M12 5v14"}]],"bookmark":[["path",{"d":"M17 3a2 2 0 0 1 2 2v15a1 1 0 0 1-1.496.868l-4.512-2.578a2 2 0 0 0-1.984 0l-4.512 2.578A1 1 0 0 1 5 20V5a2 2 0 0 1 2-2z"}]],"share-2":[["circle",{"cx":"18","cy":"5","r":"3"}],["circle",{"cx":"6","cy":"12","r":"3"}],["circle",{"cx":"18","cy":"19","r":"3"}],["line",{"x1":"8.59","x2":"15.42","y1":"13.51","y2":"17.49"}],["line",{"x1":"15.41","x2":"8.59","y1":"6.51","y2":"10.49"}]],"pencil":[["path",{"d":"M21.174 6.812a1 1 0 0 0-3.986-3.987L3.842 16.174a2 2 0 0 0-.5.83l-1.321 4.352a.5.5 0 0 0 .623.622l4.353-1.32a2 2 0 0 0 .83-.497z"}],["path",{"d":"m15 5 4 4"}]],"arrow-up":[["path",{"d":"m5 12 7-7 7 7"}],["path",{"d":"M12 19V5"}]],"arrow-down":[["path",{"d":"M12 5v14"}],["path",{"d":"m19 12-7 7-7-7"}]],"arrow-left":[["path",{"d":"m12 19-7-7 7-7"}],["path",{"d":"M19 12H5"}]],"ellipsis":[["circle",{"cx":"12","cy":"12","r":"1"}],["circle",{"cx":"19","cy":"12","r":"1"}],["circle",{"cx":"5","cy":"12","r":"1"}]],"sliders-horizontal":[["path",{"d":"M10 5H3"}],["path",{"d":"M12 19H3"}],["path",{"d":"M14 3v4"}],["path",{"d":"M16 17v4"}],["path",{"d":"M21 12h-9"}],["path",{"d":"M21 19h-5"}],["path",{"d":"M21 5h-7"}],["path",{"d":"M8 10v4"}],["path",{"d":"M8 12H3"}]],"radio":[["path",{"d":"M16.247 7.761a6 6 0 0 1 0 8.478"}],["path",{"d":"M19.075 4.933a10 10 0 0 1 0 14.134"}],["path",{"d":"M4.925 19.067a10 10 0 0 1 0-14.134"}],["path",{"d":"M7.753 16.239a6 6 0 0 1 0-8.478"}],["circle",{"cx":"12","cy":"12","r":"2"}]],"external-link":[["path",{"d":"M15 3h6v6"}],["path",{"d":"M10 14 21 3"}],["path",{"d":"M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"}]],"send":[["path",{"d":"M14.536 21.686a.5.5 0 0 0 .937-.024l6.5-19a.496.496 0 0 0-.635-.635l-19 6.5a.5.5 0 0 0-.024.937l7.93 3.18a2 2 0 0 1 1.112 1.11z"}],["path",{"d":"m21.854 2.147-10.94 10.939"}]],"shield":[["path",{"d":"M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"}]],"flag":[["path",{"d":"M4 22V4a1 1 0 0 1 .4-.8A6 6 0 0 1 8 2c3 0 5 2 7.333 2q2 0 3.067-.8A1 1 0 0 1 20 4v10a1 1 0 0 1-.4.8A6 6 0 0 1 16 16c-3 0-5-2-8-2a6 6 0 0 0-4 1.528"}]],"trash":[["path",{"d":"M10 11v6"}],["path",{"d":"M14 11v6"}],["path",{"d":"M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"}],["path",{"d":"M3 6h18"}],["path",{"d":"M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"}]],"thumbs-up":[["path",{"d":"M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2a3.13 3.13 0 0 1 3 3.88Z"}],["path",{"d":"M7 10v12"}]],"thumbs-down":[["path",{"d":"M9 18.12 10 14H4.17a2 2 0 0 1-1.92-2.56l2.33-8A2 2 0 0 1 6.5 2H20a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2.76a2 2 0 0 0-1.79 1.11L12 22a3.13 3.13 0 0 1-3-3.88Z"}],["path",{"d":"M17 14V2"}]],"minus":[["path",{"d":"M5 12h14"}]],"eye":[["path",{"d":"M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0"}],["circle",{"cx":"12","cy":"12","r":"3"}]],"check":[["path",{"d":"M20 6 9 17l-5-5"}]],"x":[["path",{"d":"M18 6 6 18"}],["path",{"d":"m6 6 12 12"}]]};
let tg = window.Telegram?.WebApp;
let preview = !tg?.initData;
const $ = id => document.getElementById(id);
const languages={en:'English',fa:'فارسی',ar:'العربية',tr:'Türkçe',ru:'Русский',es:'Español',fr:'Français',de:'Deutsch'};
let locale='en',catalogue={},view='for-you',generation=0,guideStep=0,lastResult=null,guideDone=false,similarSeed=null,setupDone=true,setupStep=0,setupDraft={};
const pageTrail=[];
const normalize=value=>{const code=String(value||'').toLowerCase().split(/[-_]/)[0];return languages[code]?code:'en';};
const t=(key,values={})=>String(catalogue[locale]?.[key]??catalogue.en?.[key]??key).replace(/\{(\w+)\}/g,(_,k)=>String(values[k]??`{${k}}`));
const lists=new Map();let storageKey='lilcusin-list-preview';
const storageRead=key=>{try{return localStorage.getItem(key);}catch{return null;}};
const storageWrite=(key,value)=>{try{localStorage.setItem(key,value);}catch{}};
const demo=[{id:1,title:'Everything In Its Right Place',artist:'Radiohead',album:'Kid A',artwork:'https://lastfm-img.freetls.fastly.net/i/u/300x300/2ed343318c844d19cd897ec67fad11c4.png'},{id:2,title:'Space Song',artist:'Beach House',album:'Depression Cherry',artwork:'https://lastfm-img.freetls.fastly.net/i/u/300x300/92ee7e4f3afdbe6a9a8c13a4a790baf1.png'},{id:3,title:'Intro',artist:'The xx'},{id:4,title:'Teardrop',artist:'Massive Attack'},{id:5,title:'Roads',artist:'Portishead'},{id:6,title:'Says',artist:'Nils Frahm'}];
const demoChannels={channels:[{id:1,title:'Late night favorites',status:'connected',learned:18,review:1},{id:2,title:'Sunday mixtape',status:'disconnected',learned:6,review:0}]};
function node(tag,text,className){const el=document.createElement(tag);if(text!==undefined)el.textContent=text;if(className)el.className=className;return el;}
function icon(name){const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');for(const [key,value] of Object.entries({viewBox:'0 0 24 24',fill:'none',stroke:'currentColor','stroke-width':'1.8','stroke-linecap':'round','stroke-linejoin':'round','aria-hidden':'true',focusable:'false',class:'ui-icon'}))svg.setAttribute(key,value);svg.setAttribute('data-icon-name',name);for(const [tag,attrs] of iconShapes[name]||[]){const shape=document.createElementNS(svg.namespaceURI||'http://www.w3.org/2000/svg',tag);for(const [key,value] of Object.entries(attrs))shape.setAttribute(key,value);svg.append(shape);}return svg;}
function actionIcon(label){const choices={get_song:'download',flow_delivery_button:'external-link',find_song:'search',search:'search',card_search:'search',more:'radio',card_add:'plus',card_added:'check',card_remove:'x',card_save:'check',ux_choose_first:'plus',ux_edit_songs:'pencil',ux_build_card:'user-round',ux_share_title:'share-2',card_publish:'share-2',card_share:'share-2',card_image:'eye',card_delete:'trash',social_swap:'send',social_reply:'send',social_save:'bookmark',social_unsave:'bookmark',social_love:'heart',social_loved:'heart',social_block:'shield',social_report:'flag',social_settings:'sliders-horizontal',social_controls:'shield',ux_back_exchanges:'arrow-left',ux_back_comparisons:'arrow-left',card_cancel:'x',retry:'radio'};for(const [key,name] of Object.entries(choices))if(t(key)===label)return name;return null;}
function setActionLabel(button,label,name){const chosen=name||button.dataset.iconName||actionIcon(label);button.replaceChildren();if(chosen){button.dataset.iconName=chosen;button.append(icon(chosen));}button.append(node('span',label));}
function action(label,run,className='secondary',iconName){const b=node('button',undefined,className);b.type='button';setActionLabel(b,label,iconName);b.onclick=run;return b;}
function externalIcon(){return icon('external-link');}
function link(url,label,className='primary',hint='listen_hint'){const a=node('a',label,className);a.append(externalIcon());a.href=url;a.onclick=e=>{if(tg?.openTelegramLink){e.preventDefault();tg.openTelegramLink(url);}};if(className==='primary')a.title=t(hint);return a;}
function status(text=''){const el=$('status');el.textContent=text;el.dataset.loading=String(!!text&&text===t('loading'));}
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
async function api(path,data,timeout=35000){const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),timeout);try{const response=await fetch(`/api/${path}`,{method:data===undefined?'GET':'POST',headers:{'Content-Type':'application/json','X-Telegram-Init-Data':tg.initData},body:data===undefined?undefined:JSON.stringify(data),signal:controller.signal});let result;try{result=await response.json();}catch{throw new Error(t('error'));}if(!response.ok&&typeof result.error==='string'&&/^(card|invite|social)_[a-z_]+$/.test(result.error))throw new Error(t(result.error));if(!response.ok)throw new Error(t(response.status===401?'open_telegram':response.status===400?'invalid':response.status===403?'stale':'error'));return result;}catch(error){if(error.name==='AbortError')throw new Error(t('error'));throw error;}finally{clearTimeout(timer);}}
function labels(){document.documentElement.lang=locale;document.documentElement.dir=['fa','ar'].includes(locale)?'rtl':'ltr';$('language').value=locale;$('guide-language').value=locale;$('guide-language').setAttribute('aria-label',t('language'));for(const [id,key] of Object.entries({'hero-title':'hero_title','hero-note':'hero_note',discover:'find_song','taste-card-open':'ux_build_card','query-label':'search_label','search-button':'search','search-hint':'search_hint','language-label':'language','guide-link':'guide'}))$(id).textContent=t(key);$('help').setAttribute('aria-label',t('guide'));document.querySelectorAll('[data-key]').forEach(el=>el.textContent=t(el.dataset.key));writePageTitle($('view-title'),view,similarSeed);renderBreadcrumbs();contextLabels();renderPreviewBanner();}
function contextLabels(){
 const key={'for-you':'ux_home_intro',search:'ux_search_intro',card:'ux_card_intro',swaps:'ux_swaps_intro',connections:'ux_connections_intro',channels:'ux_channels_intro'}[view];
 $('view-intro').textContent=key?t(key):'';$('view-intro').hidden=!key;
 $('exchange-tabs').hidden=!['swaps','connections'].includes(view);$('exchange-tabs').setAttribute('aria-label',t('ux_exchanges'));
 $('home-tools').hidden=false;$('help').textContent=t('guide');setActionLabel($('home-setup'),t('ux_personalize'),'sliders-horizontal');setActionLabel($('home-channels'),t('ux_channels'),'radio');setActionLabel($('search-button'),t('search'),'search');$('app-menu-label').replaceChildren(icon('ellipsis'));document.querySelectorAll('[data-icon]').forEach(el=>el.replaceChildren(icon(el.dataset.icon)));$('app-menu-label').setAttribute('aria-label',t('flow_more'));
 document.querySelectorAll('#exchange-tabs button').forEach(b=>{b.setAttribute('aria-current',b.dataset.view===view?'page':'false');});
}
function disclosure(title,...children){const details=node('details',undefined,'card ux-disclosure');details.append(node('summary',title),...children);return details;}
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
 if(guideStep===1){const route=node('div',undefined,'guide-route');for(const [i,key] of ['get_song','guide_send','guide_return'].entries()){const item=node('div',undefined,'guide-route-step');item.append(node('span',String(i+1),'guide-number'),node('span',t(key)));route.append(item);}box.append(song,route);}
 if(guideStep===2){box.append(song);const rating=node('div',undefined,'guide-rating');rating.append(node('span','♥ '+t('love'),'guide-loved'),node('span','↑ '+t('like')),node('span','↓ '+t('dislike')));box.append(rating,node('p',t('guide_new_song'),'guide-caption'));}
}
function renderGuide(){const n=guideStep+1;$('guide-title').textContent=t(`g${n}_title`);$('guide-text').textContent=t(`g${n}_text`);$('guide-step').textContent=t('step',{n});$('guide-skip').textContent=t('skip');$('guide-back').textContent=t('back');$('guide-back').hidden=guideStep===0;$('guide-next').textContent=t(guideStep===2?'done':'next');guideVisual();const dots=$('guide-dialog').querySelector('.guide-dots');dots.replaceChildren(...[0,1,2].map(i=>node('span',undefined,i===guideStep?'current':'')));$('guide-status').textContent='';if(!languageChanging&&!matchMedia('(prefers-reduced-motion: reduce)').matches){for(const id of ['guide-title','guide-text'])$(id).animate([{opacity:.35,transform:'translateY(4px)'},{opacity:1,transform:'none'}],{duration:180,easing:'ease-out'});}}
function showGuide(){document.querySelector('.app-menu').open=false;guideStep=0;renderGuide();if(!$('guide-dialog').open)$('guide-dialog').showModal();}
async function closeGuide(start=false){const b=$('guide-next');b.disabled=true;try{if(!preview)await api('preferences/update',{ui_guide_done:true});else storageWrite('lilcusin-preview-guide','done');guideDone=true;$('guide-dialog').close();if(start)await switchView('search');}catch(error){$('guide-status').textContent=error.message;}finally{b.disabled=false;}}
function remember(result){lists.set(view,result);if(!preview&&['for-you','search'].includes(view))try{sessionStorage.setItem(storageKey,JSON.stringify({view,result,time:Date.now()}));}catch{}}
function empty(title,detail,search=false){const box=node('div',undefined,'empty');box.append(node('span','🦉'),node('h3',title),node('p',detail));if(search)box.append(action(t('find_song'),()=>switchView('search'),'primary'));$('content').replaceChildren(box);}
function tracks(result){$('content').replaceChildren();if(!result.tracks.length){empty(t('empty_title'),t(view==='search'?'no_matches':result.status==='insufficient_preferences'?'empty_hint':'no_recs'),view!=='search');return;}
 for(const song of result.tracks)$('content').append(makeCard(song,song.token||result.token));if(view==='for-you')installDeck();for(const card of $('content').querySelectorAll('[data-track-id]'))restoreDeliveryUI(card);
}
let deckIndex=0,deckLoading=false,profilePanel='preview';

// Small native animations, cancelled on rapid navigation; no layout measurements depend on transforms.
const runningMotion=new Set();let tabTransition=0,deckAnimating=false,previewBannerCollapsed=false;
function motionAllowed(){return !matchMedia('(prefers-reduced-motion: reduce)').matches;}
function cancelUIMotion(){for(const animation of runningMotion)animation.cancel();runningMotion.clear();}
async function uiMotion(element,frames,duration=210){
 if(!element?.animate||!motionAllowed())return true;
 const animation=element.animate(frames,{duration,easing:'cubic-bezier(.22,.75,.2,1)',fill:'both'});runningMotion.add(animation);
 try{await animation.finished;return true;}catch{return false;}finally{runningMotion.delete(animation);animation.cancel();if(!runningMotion.size)fitDeck();}
}
function renderPreviewBanner(){
 const banner=$('preview');banner.hidden=!preview;if(!preview)return;
 banner.classList.toggle('preview-compact',previewBannerCollapsed);
 const toggle=action(t(previewBannerCollapsed?'a1_preview_expand':'a1_preview_dismiss'),()=>{previewBannerCollapsed=!previewBannerCollapsed;renderPreviewBanner();fitDeck();},'preview-toggle',previewBannerCollapsed?'eye':'x');
 toggle.setAttribute('aria-expanded',String(!previewBannerCollapsed));banner.replaceChildren(node('span',t(previewBannerCollapsed?'a1_preview_short':'preview')),toggle);
}
async function moveDeck(direction,fromY=0){
 if(view!=='for-you'||deckLoading||deckAnimating)return;
 const outgoing=deckItems()[deckIndex],version=generation;if(!outgoing)return;
 if(deckIndex+direction<0){await uiMotion(outgoing,[{transform:`translateY(${fromY}px)`},{transform:'none'}],180);return;}
 deckAnimating=true;outgoing.classList.add('card-transitioning');
 try{
  const completed=await uiMotion(outgoing,[{transform:`translateY(${fromY}px)`,opacity:1},{transform:`translateY(${-direction*Math.max(64,Math.abs(fromY)+24)}px)`,opacity:0}],150);
  if(!completed)return;
  if(version!==generation)return;outgoing.style.opacity='0';
  await loadDeck(direction);if(version!==generation)return;
  const incoming=deckItems()[deckIndex];outgoing.style.removeProperty('opacity');
  await uiMotion(incoming,[{transform:`translateY(${direction*42}px)`,opacity:0},{transform:'none',opacity:1}],220);
 }finally{outgoing.style.removeProperty('opacity');outgoing.classList.remove('card-transitioning');deckAnimating=false;}
}
async function switchView(next,restored,options={}){
 const transition=++tabTransition,previous=view;cancelUIMotion();clearSwipe();
 const region=document.querySelector('#content'),oldIndex=primaryViews.indexOf(previous==='connections'?'swaps':previous),nextIndex=primaryViews.indexOf(next==='connections'?'swaps':next);
 const change=previous!==next,axis=oldIndex>=0&&nextIndex>=0&&oldIndex!==nextIndex;
 const direction=(nextIndex>oldIndex?1:-1)*(document.documentElement.dir==='rtl'?-1:1),fromX=options.motionFromX||0;
 if(change)await uiMotion(region,[{opacity:1,transform:`translateX(${fromX}px)`},{opacity:0,transform:axis?`translateX(${-direction*Math.max(36,Math.abs(fromX)+24)}px)`:'translateY(-6px)'}],120);
 if(transition!==tabTransition)return;
 await loadView(next,restored,options);if(transition!==tabTransition)return;
 if(change)await uiMotion(region,[{opacity:0,transform:axis?`translateX(${direction*28}px)`:'translateY(6px)'},{opacity:1,transform:'none'}],220);
}

const deckItems=()=>[...$('content').children].filter(el=>el.matches('.card:not(.social-strip)'));
function installDeck(){
 if(view!=='for-you')return;document.body.classList.add('feed-ready');telegramCall(()=>tg?.disableVerticalSwipes?.());
 const focused=document.activeElement?.closest('#deck-controls')?document.activeElement.dataset.deck:null;const items=deckItems();deckIndex=Math.max(0,Math.min(deckIndex,items.length-1));
 for(const [i,card] of items.entries()){
  card.hidden=i!==deckIndex;card.classList.add('feed-card');
  const art=card.querySelector('.cover');if(art){art.setAttribute('aria-label',t('flow_swipe'));}if(art&&!art.dataset.swipe){art.dataset.swipe='true';art.tabIndex=0;
   art.onkeydown=e=>{if(['ArrowDown','ArrowUp'].includes(e.key)){e.preventDefault();moveDeck(e.key==='ArrowDown'?1:-1);}};
  }
 }
 let controls=$('deck-controls');if(!controls){controls=node('nav',undefined,'deck-controls');controls.id='deck-controls';controls.setAttribute('aria-label',t('flow_browse'));$('content').after(controls);}
 controls.setAttribute('aria-label',t('flow_browse'));controls.replaceChildren();const previous=action(t('flow_previous'),()=>moveDeck(-1),'secondary','arrow-up');previous.disabled=deckIndex===0;previous.dataset.deck='previous';
 const next=action(t('flow_next'),()=>moveDeck(1),'primary','arrow-down');next.disabled=deckLoading;next.dataset.deck='next';
 controls.append(previous,node('span',t('flow_pick',{n:deckIndex+1}),'deck-count'),next);
 controls.append(node('p',t('flow_swipe'),'hint deck-hint'));fitDeck();if(focused){const target=controls.querySelector('[data-deck="'+focused+'"]');if(target&&!target.disabled)target.focus({preventScroll:true});}
}
function fitDeck(){
 if(runningMotion.size||swipeGesture?.moving)return;
 if(view!=='for-you'||!document.body.classList.contains('feed-ready'))return;
 const card=document.querySelector('.feed-card:not([hidden])'),controls=$('deck-controls'),art=card?.querySelector('.cover');if(!art||!controls)return;
 const heard=card.querySelector('.heard');if(heard)heard.ontoggle=fitDeck;
 document.body.classList.remove('feed-tight');
 if(window.innerWidth>=700){art.style.height='260px';return;}
 let nonArt=card.offsetHeight-art.offsetHeight,available=controls.getBoundingClientRect().top-card.getBoundingClientRect().top-nonArt-12;
 if(available<100){document.body.classList.add('feed-tight');nonArt=card.offsetHeight-art.offsetHeight;available=controls.getBoundingClientRect().top-card.getBoundingClientRect().top-nonArt-12;}
 art.style.height=Math.max(document.body.classList.contains('feed-tight')?64:80,Math.min(230,Math.floor(available)))+'px';
}
window.addEventListener('resize',fitDeck);
window.visualViewport?.addEventListener('resize',fitDeck);
document.fonts?.ready.then(fitDeck);
document.fonts?.addEventListener('loadingdone',fitDeck);

// Vertical browsing owns the whole discovery card; horizontal browsing owns tabs.
// Other screens retain native vertical scrolling and inputs retain editing gestures.
let swipeGesture=null,suppressSwipeClickUntil=0;
const primaryViews=['for-you','search','swaps','card'];
function swipeTabIndex(){return primaryViews.indexOf(view==='connections'?'swaps':view);}
function clearSwipe(){const gesture=swipeGesture;swipeGesture=null;if(gesture?.moving){gesture.moving.style.removeProperty('transform');gesture.moving.style.removeProperty('opacity');gesture.moving.classList.remove('is-swiping');}return gesture;}
function startSwipe(event){
 if(event.isPrimary===false){clearSwipe();return;}if(event.button>0||swipeTabIndex()<0||deckAnimating)return;
 suppressSwipeClickUntil=0;
 const target=event.target;if(!target?.closest||target.closest('input,textarea,select,[contenteditable],dialog,.app-menu,[data-no-swipe]'))return;
 if(!target.closest('main,.main-nav')&&target!==document.body&&target!==document.documentElement&&!target.matches?.('.shell'))return;
 clearSwipe();swipeGesture={id:event.pointerId,x:event.clientX,y:event.clientY,version:generation,card:view==='for-you'?target.closest('.feed-card'):null,axis:null,moving:null};
}
function swipeAxis(dx,dy){return Math.abs(dx)>Math.abs(dy)*1.3?'x':Math.abs(dy)>Math.abs(dx)*1.3?'y':null;}
function dragSwipe(event){
 const gesture=swipeGesture;if(!gesture||gesture.id!==event.pointerId)return;
 const dx=event.clientX-gesture.x,dy=event.clientY-gesture.y;
 if(!gesture.axis&&Math.max(Math.abs(dx),Math.abs(dy))>12)gesture.axis=swipeAxis(dx,dy);
 if(!gesture.axis||gesture.axis==='y'&&!gesture.card)return;
 if(event.cancelable)event.preventDefault();
 gesture.moving=gesture.axis==='y'?gesture.card:document.querySelector('#content');
 const distance=Math.max(-120,Math.min(120,gesture.axis==='y'?dy:dx));
 gesture.offset=distance;gesture.moving.classList.add('is-swiping');gesture.moving.style.transform='translate'+(gesture.axis==='y'?'Y':'X')+'('+distance+'px)';gesture.moving.style.opacity=String(1-Math.min(Math.abs(distance)/600,.2));
}
function finishSwipe(event){
 if(!swipeGesture||swipeGesture.id!==event.pointerId)return;const offset=swipeGesture.offset||0,gesture=clearSwipe();
 if(gesture.version!==generation)return;const dx=event.clientX-gesture.x,dy=event.clientY-gesture.y,axis=gesture.axis||swipeAxis(dx,dy);
 if(gesture.moving)suppressSwipeClickUntil=Date.now()+450;
 if(axis==='y'&&gesture.card&&Math.abs(dy)>=60){suppressSwipeClickUntil=Date.now()+450;moveDeck(dy<0?1:-1,offset);return;}
 if(axis==='x'&&Math.abs(dx)>=60){const direction=(dx<0?1:-1)*(document.documentElement.dir==='rtl'?-1:1),index=swipeTabIndex()+direction;if(index>=0&&index<primaryViews.length){suppressSwipeClickUntil=Date.now()+450;switchView(primaryViews[index],undefined,{focusSearch:false,motionFromX:offset});return;}}
 if(gesture.moving)uiMotion(gesture.moving,[{transform:'translate'+(axis==='y'?'Y':'X')+'('+offset+'px)',opacity:.9},{transform:'none',opacity:1}],180);
}
document.addEventListener('pointerdown',startSwipe);
document.addEventListener('pointermove',dragSwipe,{passive:false});
document.addEventListener('pointerup',finishSwipe);
document.addEventListener('pointercancel',clearSwipe);
document.addEventListener('click',event=>{if(Date.now()<suppressSwipeClickUntil&&(event.detail>0||event.pointerType)){event.preventDefault();event.stopImmediatePropagation();}},true);
document.addEventListener('dragstart',event=>{if(event.target.closest?.('.feed-card'))event.preventDefault();});
window.addEventListener('blur',clearSwipe);
document.addEventListener('visibilitychange',()=>{if(document.hidden)clearSwipe();});
async function loadDeck(direction){
 if(view!=='for-you'||deckLoading)return;const items=deckItems(),target=deckIndex+direction;
 if(target<0)return;if(target<items.length){deckIndex=target;installDeck();return;}
 const version=generation;deckLoading=true;installDeck();
 try{
  const exclude=visibleIds(),current=items.filter(el=>el.songData).map(el=>({id:el.songData.id,token:el.songData.token}));
  const result=preview?{tracks:demo.filter(song=>!exclude.includes(song.id)&&!previewRated.has(song.id)).slice(0,1)}:await api('recommendations',{replace:true,exclude,current});
  if(version!==generation)return;
  if(result.token)for(const el of items)if(el.songData)el.songData.token=result.token;
  const song=result.tracks.find(song=>!exclude.includes(song.id));
  if(!song){notice(t('flow_no_more'));return;}
  $('content').append(makeCard(song,result.token));deckIndex=items.length;
  if(deckItems().length>12){deckItems()[0].remove();deckIndex--;}
  rememberVisible();
 }catch(error){if(version===generation)notice(error.message);}
 finally{deckLoading=false;if(version===generation)installDeck();}
}
function installProfilePanels(parts){
 const content=$('content'),tabs=node('nav',undefined,'profile-tabs');tabs.setAttribute('aria-label',t('flow_card_sections'));
 for(const key of ['preview','edit','share','saved']){const b=action(t('flow_tab_'+key),()=>selectProfilePanel(key));b.dataset.panel=key;tabs.append(b);}
 content.prepend(tabs);
 for(const [key,children] of Object.entries({preview:[parts.previewBox],edit:[parts.edit,parts.songs],share:[parts.sharing,parts.previewActions,parts.imageBox],saved:[parts.advanced]})){
  const panel=node('section',undefined,'profile-panel');panel.id='profile-'+key;panel.dataset.panel=key;panel.setAttribute('aria-label',t('flow_tab_'+key));panel.append(...children);content.append(panel);
 }
 parts.edit.open=false;parts.previewBox.querySelector('.taste-title')?.remove();
 parts.previewBox.append(action(t('ux_share_title'),()=>selectProfilePanel('share'),'secondary profile-share'));
 selectProfilePanel(profilePanel,false);
}
function selectProfilePanel(key,scroll=true){
 profilePanel=key;document.querySelectorAll('.profile-panel').forEach(el=>el.hidden=el.dataset.panel!==key);
 document.querySelectorAll('.profile-tabs button').forEach(el=>el.setAttribute('aria-current',el.dataset.panel===key?'page':'false'));
 $('view-intro').hidden=true;if(scroll){$('content').querySelector('.card-confirm')?.remove();window.scrollTo({top:0,behavior:'instant'});}
}
const deliveryReceipts=new Map();let deliveryTimer,activeReceipt=null;
const receiptKey=()=>storageKey+'-delivery';
function loadDeliveryReceipts(){try{const rows=JSON.parse(sessionStorage.getItem(receiptKey())||'[]');for(const row of rows)if(Number.isInteger(row.track_id)&&row.until>Date.now()&&typeof row.after==='string')deliveryReceipts.set(row.track_id,row);}catch{}}
function storeDeliveryReceipts(){try{sessionStorage.setItem(receiptKey(),JSON.stringify([...deliveryReceipts.values()].slice(-10).map(({track_id,after,state,until,request_id})=>({track_id,after,state,until,request_id}))));}catch{}}
function deliveryFeedback(host,entry){
 if(!host?.isConnected)return;let box=host.querySelector('.delivery-feedback');if(!box){box=node('p',undefined,'delivery-feedback');box.setAttribute('role','status');box.setAttribute('aria-live','polite');host.append(box);}
 box.dataset.state=entry.state;box.textContent=t('flow_delivery_'+entry.state);if(typeof document.querySelector==='function'&&document.querySelector('.feed-ready'))fitDeck();
}
function openSongChat(url){if(tg?.openTelegramLink)tg.openTelegramLink(url);else{const opened=window.open(url,'_blank','noopener');if(!opened)notice(t('flow_delivery_waiting'));}}
async function requestDelivery(track_id,url,source,button,host){
 if(button.disabled)return;button.disabled=true;setActionLabel(button,t('flow_delivery_opening'),'download');
 const entry={track_id,url,source,state:'opening',until:Date.now()+240000};deliveryReceipts.set(track_id,entry);host.dataset.deliveryTrack=String(track_id);deliveryFeedback(host,entry);
 try{const result=await api('delivery-status',{track_id,...source},8000);entry.after=result.after;entry.request_id=result.request_id;entry.state=result.state;storeDeliveryReceipts();}
 catch{entry.state='unavailable';}
 finally{button.disabled=false;setActionLabel(button,t('flow_delivery_button'),'external-link');deliveryFeedback(host,entry);}
 try{openSongChat(url);}catch{entry.state='unavailable';deliveryFeedback(host,entry);}
 if(entry.after)watchDelivery(entry,host);
}
function watchDelivery(entry,host){
 clearTimeout(deliveryTimer);activeReceipt=entry;
 async function poll(){
  if(activeReceipt!==entry||document.hidden)return;host=deliveryHost(entry.track_id);
  if(Date.now()>entry.until){if(!['done','failed','cancelled','uncertain'].includes(entry.state)){entry.state='uncertain';deliveryFeedback(host,entry);storeDeliveryReceipts();}return;}
  try{const result=await api('delivery-status',{track_id:entry.track_id,...entry.source,after:entry.after,...(entry.request_id?{request_id:entry.request_id}:{})},8000);entry.request_id=result.request_id;entry.state=result.state;storeDeliveryReceipts();deliveryFeedback(host,entry);}
  catch{entry.state='unavailable';deliveryFeedback(host,entry);storeDeliveryReceipts();return;}
  if(!['done','failed','cancelled','uncertain'].includes(entry.state))deliveryTimer=setTimeout(poll,3000);
 }
 deliveryTimer=setTimeout(poll,1200);
}
function deliveryHost(track_id){return document.querySelector('#content [data-track-id="'+track_id+'"]')||($('content').dataset.deliveryTrack===String(track_id)?$('content'):null);}
function restoreDeliveryUI(card){const entry=deliveryReceipts.get(card.songData?.id);if(!entry)return;entry.source={token:card.songData.token};deliveryFeedback(card,entry);if((!activeReceipt||activeReceipt.track_id===entry.track_id)&&entry.after&&entry.until>Date.now()&&!['done','failed','cancelled','uncertain'].includes(entry.state))watchDelivery(entry,card);}
document.addEventListener('visibilitychange',()=>{if(document.hidden)clearTimeout(deliveryTimer);else if(activeReceipt?.after)watchDelivery(activeReceipt,deliveryHost(activeReceipt.track_id));});
function makeCard(song,token){const card=node('article',undefined,'card'),row=node('div',undefined,'track'),cover=node('div','♪','cover'),info=node('div');if(song.artwork){setArtwork(cover,song.artwork);}info.append(node('h3',song.title),node('p',song.artist));row.append(cover,info);card.append(row);
 if(song.reason){const key=Object.keys(catalogue.en).find(key=>key.startsWith('reason_')&&catalogue.en[key]===song.reason);const reason=node('aside',undefined,'reason');reason.append(node('span',t('recommendation_why'),'reason-label'),node('p',key?t(key):song.reason));card.append(reason);}
 const buttons=node('div',undefined,'song-actions');const getSong=action(t('get_song'),()=>{if(preview){notice(t('preview_only'));deliveryFeedback(card,{state:'preview'});return;}if(!song.get_song_url){notice(t('get_song_unavailable'));return;}const url=new URL(song.get_song_url);url.searchParams.set('start',`get_${card.songData.token}_${song.id}`);return requestDelivery(song.id,url.href,{token:card.songData.token},getSong,card);},'primary');getSong.title=t('get_song_hint');buttons.append(getSong);buttons.append(action(t('more'),event=>openSimilar(card,event.currentTarget)));buttons.append(action(t('card_add'),async event=>{const b=event.currentTarget;b.disabled=true;try{const owner=preview?previewTasteCard:await api('taste-card');if(cardDirty(owner))throw new Error(t('card_draft_hint'));if(preview){if(!owner.songs.some(s=>s.id===song.id)){if(owner.songs.length>=5)throw new Error(t('card_full'));owner.songs.push({...song});owner.revision++;}notice(t('card_preview_only'));}else{await api('taste-card/update',{action:'add',revision:owner.revision,track_id:song.id,token:card.songData.token});notice(t('card_added'));}}catch(error){notice(error.message);}finally{b.disabled=false;}}));card.append(buttons);
 const heard=node('div',undefined,'heard');const ratings=node('div',undefined,'ratings');ratings.setAttribute('aria-label',t('heard'));
 for(const [value,mark] of [['love','♥'],['like','↑'],['neutral','–'],['dislike','↓']]){const b=action(t(value),async event=>{const all=[...ratings.children],version=generation;all.forEach(x=>x.disabled=true);try{if(!preview)await api('rate',{token:card.songData.token,track_id:song.id,value});else{previewRated.add(song.id);previewRatings.set(song.id,value);}if(version===generation){all.forEach(x=>x.setAttribute('aria-pressed',String(x===b)));all.forEach(x=>x.classList.toggle('selected',x===b));notice(t(preview?'preview_only':'saved'));telegramCall(()=>tg?.HapticFeedback?.notificationOccurred('success'));if(view==='channel-review'){await backToChannel();}else swapRatedCard(card,event.detail===0);}}catch(error){if(version===generation)status(error.message);}finally{if(!card.classList.contains('is-rated'))all.forEach(x=>x.disabled=false);}},'',{love:'heart',like:'thumbs-up',neutral:'minus',dislike:'thumbs-down'}[value]);b.dataset.rating=value;b.setAttribute('aria-pressed','false');ratings.append(b);}heard.append(ratings);card.append(heard);card.songData={...song,token};card.dataset.trackId=String(song.id);if(song.rating){for(const b of ratings.children){const selected=b.dataset.rating===song.rating;b.classList.toggle('selected',selected);b.setAttribute('aria-pressed',String(selected));}}scheduleArtwork();return card;
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
  else if(view==='channel'&&!lastResult.next_cursor){result={tracks:[],next_cursor:null};}
  else{const current=[...$('content').querySelectorAll('[data-track-id]:not(.is-rated)')].map(el=>({id:el.songData.id,token:el.songData.token}));result=await api(view==='channel'?'channels/songs':'recommendations',{replace:true,exclude,current,...(view==='channel'?{channel_id:similarSeed.id,filter:'unrated',cursor:lastResult.next_cursor}:{})});}
  if(version!==generation||!slot.isConnected)return;
  if(!preview&&result.token)for(const el of $('content').querySelectorAll('[data-track-id]:not(.is-rated)'))el.songData.token=result.token;
  if(view==='channel'&&!preview){lastResult.next_cursor=result.next_cursor;channelPagination(lastResult);}
  const song=result.tracks.find(song=>!visibleIds().includes(song.id));const positions=new Map([...$('content').children].filter(el=>el!==slot).map(el=>[el,el.getBoundingClientRect().top]));
  if(song){for(const end of $('content').querySelectorAll('.end-card'))end.remove();const fresh=makeCard(song,result.token);slot.replaceWith(fresh);if(!matchMedia('(prefers-reduced-motion: reduce)').matches)fresh.animate([{opacity:0,transform:`translateX(${['fa','ar'].includes(locale)?-40:40}px) scale(.98)`},{opacity:1,transform:'none'}],{duration:320,easing:'cubic-bezier(.2,.8,.2,1)'});if(focusAfter){fresh.tabIndex=-1;fresh.focus({preventScroll:true});}}
  else{for(const end of $('content').querySelectorAll('.end-card'))end.remove();slot.className='card end-card';slot.style.minHeight='';slot.replaceChildren(node('p',t(view==='channel'?'channel_end':'no_recs'),'hint'),action(t(view==='channel'?'all_songs':'find_song'),()=>view==='channel'?openChannel(similarSeed,'all',0,[0],true):switchView('search')));slot.removeAttribute('aria-busy');}
  if(!matchMedia('(prefers-reduced-motion: reduce)').matches)for(const [el,top] of positions){const delta=top-el.getBoundingClientRect().top;if(el.isConnected&&delta&&!el.classList.contains('is-rated'))el.animate([{transform:`translateY(${delta}px)`},{transform:'none'}],{duration:300,easing:'cubic-bezier(.2,.8,.2,1)'});}
  rememberVisible();if(view==='for-you')installDeck();
 }catch(error){if(version!==generation||!slot.isConnected)return;slot.setAttribute('aria-busy','false');slot.replaceChildren(node('p',error.message,'hint'),action(t('retry'),()=>{slot.replaceChildren(node('p',t('loading'),'hint'));replacementQueue=replacementQueue.catch(()=>{}).then(()=>fillReplacement(slot,version,focusAfter));}));}
}
const previewRated=new Set(),previewRatings=new Map(),previewIdentifiedChannels=new Set();
function profile(p){$('content').replaceChildren();const box=node('div',undefined,'stats');for(const [value,key] of [[p.songs,'ratings_count'],[p.counts.love||0,'loved_count'],[p.channels,'channels']]){const stat=node('div',undefined,'stat');stat.append(node('strong',String(value)),node('span',t(key)));box.append(stat);}$('content').append(box);for(const [key,items] of [['artists',p.artists],['tags',p.tags]]){$('content').append(node('h3',t(key),'taste-title'));const chips=node('div',undefined,'chips');for(const item of items)chips.append(node('span',item,'chip'));if(!items.length)chips.append(node('p',t('empty_hint'),'hint'));$('content').append(chips);}$('content').append(action(t('channels'),()=>switchView('channels')),node('p',t('privacy_hint'),'hint'));}
function channels(p){$('content').replaceChildren(node('p',t('channels_hint'),'hint'));$('content').append(action(t('connect'),async e=>{const b=e.currentTarget,version=generation;b.disabled=true;try{if(preview){status(t('open_telegram'));return;}const result=await api('channels/connect',{});if(version!==generation)return;const box=node('section',undefined,'card connect-guide');box.append(node('h3',t('connect')),...['connect1','connect2','connect3'].map(key=>node('p',t(key),'hint')));const code=node('textarea',result.code,'connection-code');code.value=result.code;code.readOnly=true;code.setAttribute('aria-label',t('copy'));box.append(code,action(t('copy'),async()=>{try{await navigator.clipboard.writeText(result.code);notice(t('copied'));}catch{code.focus();code.select();}}),node('p',t('code_note'),'hint'),action(t('refresh'),()=>switchView('channels')));$('content').prepend(box);status();}catch(error){if(version===generation)status(error.message);}finally{b.disabled=false;}},'primary'));
 if(!p.channels.length)$('content').append(node('p',t('no_channels'),'hint'));
 for(const c of p.channels){const card=node('article',undefined,'card channel-card');card.append(node('h3',c.title),node('span',t(['connected','disconnected'].includes(c.status)?c.status:'unavailable'),'chip'),node('p',t('channel_counts',{learned:c.learned,review:c.review}),'hint'));card.append(action(t('browse_songs'),()=>openChannel(c),'primary'));if(c.review)card.append(action(t('identify_songs')+' · '+c.review,()=>openChannel(c,'review')));
 if(c.status!=='disconnected')card.append(action(t('disconnect'),()=>{if(card.querySelector('.disconnect-choice'))return;const box=node('div',undefined,'disconnect-choice');box.append(node('p',t('disconnect_question'),'hint'));for(const [remove,key] of [[false,'keep'],[true,'remove']])box.append(action(t(key),async()=>{const version=generation,buttons=[...box.querySelectorAll('button')];buttons.forEach(b=>b.disabled=true);try{if(preview){status(t('preview_only'));box.remove();}else{await api('channels/disconnect',{channel_id:c.id,remove_signals:remove});if(version===generation)await switchView('channels');}}catch(error){if(version===generation)status(error.message);}finally{buttons.forEach(b=>b.disabled=false);}}));box.append(action(t('cancel'),()=>box.remove()));card.append(box);}));else card.append(node('p',t('reconnect'),'hint'));$('content').append(card);}$('content').append(action(t('refresh'),()=>switchView('channels')));
}
function render(result){if(view==='swaps')renderSocialInbox(result);else if(view==='connections')renderSocialInvitations(result.invitations);else if(view==='card')renderTasteCard(result);else if(view==='setup')renderSetup();else if(view==='channel')channelDetail(result);else if(view==='channel-review')reviewDetail(result);else if(view==='taste'){profile(result);$('content').append(action(t('setup_edit'),openSetup,'secondary'));}else if(view==='channels')channels(result);else tracks(result);if(view==='for-you')socialStrip();}
function pageTitle(page,seed){return ['channel','channel-review'].includes(page)?(page==='channel'?seed?.title||t('channels'):t('identify_songs')):page==='similar'?t('more_title',{song:seed?.title||''}):t({'for-you':'for_you',search:'search',channels:'channels',taste:'taste',card:'card_title',connections:'ux_exchanges',swaps:'ux_exchanges',setup:'setup_title'}[page]);}
function writePageTitle(element,page,seed){if(page!=='similar'){element.textContent=pageTitle(page,seed);return;}const [before,after='']=t('more_title',{song:'{song}'}).split('{song}'),opening=before.match(/[“«„]$/)?.[0]||'',closing=after.match(/^[”»“]/)?.[0]||'',title=node('bdi',opening+(seed?.title||'')+closing);title.dir='auto';element.replaceChildren(document.createTextNode(opening?before.slice(0,-1):before),title,document.createTextNode(closing?after.slice(1):after));}
function renderBreadcrumbs(){const nav=$('breadcrumbs');nav.hidden=!pageTrail.length;nav.replaceChildren();if(!pageTrail.length){telegramCall(()=>tg?.BackButton?.hide());return;}telegramCall(()=>tg?.BackButton?.show());
 const list=node('ol');pageTrail.forEach((page,index)=>{const item=node('li');const button=action('',()=>restorePage(index),'breadcrumb-link');writePageTitle(button,page.view,page.seed);item.append(button);list.append(item);});const here=node('li',view==='similar'?t('more_short'):pageTitle(view,similarSeed));here.setAttribute('aria-current','page');list.append(here);nav.append(list);nav.setAttribute('aria-label',t('breadcrumb_label'));
}
function snapshot(){const result=['for-you','search','similar','channel'].includes(view)?{...lastResult,tracks:[...$('content').querySelectorAll('[data-track-id]:not(.is-rated)')].map(el=>({...el.songData}))}:lastResult;return {view,seed:similarSeed,result,query:$('query').value,scroll:window.scrollY};}
async function restorePage(index=pageTrail.length-1){if(index<0)return;const page=pageTrail[index];pageTrail.splice(index);$('query').value=page.query;await switchView(page.view,page.result,{keepTrail:true,seed:page.seed,scroll:page.scroll});}

async function openSimilar(card,button){const song=card.songData,version=generation;button.disabled=true;status(t('loading'));try{const next=preview?{tracks:demo.filter(s=>s.id!==song.id)}:await api('similar',{token:song.token,track_id:song.id});if(version!==generation||!card.isConnected)return;pageTrail.push(snapshot());if(pageTrail.length>12)pageTrail.splice(1,1);await switchView('similar',next,{keepTrail:true,seed:{id:song.id,title:song.title,artist:song.artist}});}catch(error){if(version===generation)status(error.message);}finally{button.disabled=false;}}
async function loadView(next,restored,options={}){
 clearSwipe();telegramCall(()=>tg?.enableVerticalSwipes?.());
 document.querySelector('.app-menu').open=false;document.body.classList.remove('feed-ready','feed-tight');$('deck-controls')?.remove();if(!options.keepTrail)pageTrail.length=0;similarSeed=options.seed||null;view=next;document.body.dataset.view=view;if(next==='for-you'&&!restored)deckIndex=0;document.querySelector('.hero').hidden=view!=='for-you';const version=++generation;lastResult=null;
 window.scrollTo({top:0,behavior:'instant'});document.querySelectorAll('.main-nav button').forEach(b=>{const parent=['similar','channel','channel-review'].includes(view)?pageTrail[0]?.view:view;const active=b.dataset.view===({connections:'swaps',taste:'card',channels:'for-you',setup:'for-you'}[parent]||parent);b.classList.toggle('active',active);if(active)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current');});$('search-form').hidden=!['search','similar'].includes(view);$('channel-tools').hidden=view!=='channel';$('channel-pagination').replaceChildren();labels();$('content').replaceChildren();delete $('content').dataset.deliveryTrack;status();
 if(restored){lastResult=restored;render(restored);window.scrollTo({top:options.scroll||0,behavior:'instant'});return;}
 if(view==='setup'){lastResult={setup:true};renderSetup();return;}
 if(view==='card'){status(t('loading'));try{const result=preview?previewTasteCard:await api('taste-card');if(version===generation){lastResult=result;status();renderTasteCard(result);}}catch(error){if(version===generation){status(error.message);$('content').append(action(t('retry'),()=>switchView('card')));}}return;}
 if(['connections','swaps'].includes(view)){status(t('loading'));try{const result=preview?(view==='connections'?{invitations:[]}:socialDemo):await api(view==='connections'?'comparison-invitations':'social');if(version!==generation)return;lastResult=result;status();render(result);}catch(error){if(version===generation){status(error.message);$('content').append(action(t('retry'),()=>switchView(view)));}}return;}
 if(view==='search'){if(!lists.has(view))empty(t('ux_search_empty'),t('ux_search_example'));if(lists.has(view)){lastResult=lists.get(view);tracks(lastResult);}if(options.focusSearch!==false)$('query').focus({preventScroll:true});return;}
 status(t('loading'));try{const result=preview?(view==='taste'?{songs:24,counts:{love:12},channels:2,artists:['Radiohead','Beach House','The xx'],tags:['Alternative','Dream pop','Indie']}:view==='channels'?demoChannels:{tracks:demo.slice(0,3)}):await api(view==='taste'?'profile':view==='channels'?'channels':'recommendations',view==='for-you'?{}:undefined);if(version!==generation)return;lastResult=result;status();if(view==='for-you')remember(result);render(result);}catch(error){if(version===generation){status(error.message);empty(t('error'),'');$('content').append(action(t('retry'),()=>switchView(view)));}}
}
function setArtwork(cover,url){const img=node('img');let fallback=false;img.src='/cover?url='+encodeURIComponent(url);img.alt='';img.loading='lazy';img.decoding='async';img.onerror=()=>{if(!fallback){fallback=true;img.src=url;return;}cover.replaceChildren(document.createTextNode('♪'));cover.dataset.artFailed='true';};cover.replaceChildren(img);}
let artTimer;
function scheduleArtwork(){if(preview)return;clearTimeout(artTimer);const version=generation;artTimer=setTimeout(()=>pollArtwork(version,0),1200);}
async function pollArtwork(version,attempt){
 if(version!==generation)return;const groups=new Map();
 for(const card of $('content').querySelectorAll('[data-track-id]:not(.is-rated)')){const cover=card.querySelector('.cover');if(!cover||cover.querySelector('img')||cover.dataset.artFailed)continue;const key=card.songData.token;if(!groups.has(key))groups.set(key,[]);groups.get(key).push(card);}
 for(const [token,cards] of groups){try{const result=await api('artwork',{token,track_ids:cards.slice(0,10).map(c=>c.songData.id)},10000);if(version!==generation)return;for(const card of cards){const url=result.artwork?.[String(card.songData.id)];if(url&&card.isConnected){card.songData.artwork=url;setArtwork(card.querySelector('.cover'),url);}}}catch{}}
 if(attempt<3&&groups.size&&version===generation)artTimer=setTimeout(()=>pollArtwork(version,attempt+1),[2500,5000,9000][attempt]);
}
async function openChannel(channel,filter='all',cursor=0,cursors=[0],keepTrail=false){
 const previous=snapshot(),version=++generation,controls=[...document.querySelectorAll('#channel-tools button,#channel-pagination button')];controls.forEach(b=>b.disabled=true);status(t('loading'));
 try{const result=preview?{channel,filter,tracks:filter==='review'?[]:demo.filter(s=>filter!=='unrated'||!previewRated.has(s.id)).slice(0,3).map(s=>({...s,rating:previewRatings.get(s.id)||null})),items:filter==='review'&&!previewIdentifiedChannels.has(channel.id)?[{id:1,title:'',artist:''}]:[],next_cursor:null}:await api('channels/songs',{channel_id:channel.id,filter,cursor});
  if(version!==generation)return;if(!keepTrail)pageTrail.push(previous);await switchView('channel',result,{keepTrail:true,seed:{...channel,filter,cursor,cursors}});
 }catch(error){if(version===generation){status(error.message);scheduleArtwork();}}finally{controls.forEach(b=>b.disabled=false);}
}
function channelDetail(result){
 const channel=similarSeed;$('channel-tools').hidden=false;const filters=node('div',undefined,'channel-filters');filters.setAttribute('aria-label',t('channel_filter'));
 for(const [value,key] of [['all','all_songs'],['unrated','unrated'],['review','identify_songs']]){const button=action(t(key),()=>openChannel(channel,value,0,[0],true),'filter-button');button.dataset.key=key;button.setAttribute('aria-pressed',String(result.filter===value));filters.append(button);}
 const hint=node('p',t('channel_history'),'hint');hint.dataset.key='channel_history';$('channel-tools').replaceChildren(filters,hint);
 if(result.filter==='review'){$('content').replaceChildren();for(const item of result.items){const card=node('article',undefined,'card review-post');card.append(node('h3',item.title||t('unknown_song')),node('p',item.artist||t('missing_artist'),'hint'),action(t('identify_song'),()=>openReview(item,result.token),'primary'));$('content').append(card);}if(!result.items.length)empty(t('review_clear'),t('review_clear_hint'));}
 else{tracks(result);if(!result.tracks.length)empty(t(result.filter==='unrated'?'all_rated':'channel_empty'),t('channel_history'));}
 channelPagination(result);
}
function channelPagination(result){
 const channel=similarSeed,pagination=$('channel-pagination');pagination.replaceChildren();const cursors=channel.cursors||[0];
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

const setupArtists={pop:['Billie Eilish','Dua Lipa'],rock:['Radiohead','Muse'],indie:['Beach House','Arctic Monkeys'],hiphop:['Mac Miller','Kendrick Lamar'],electronic:['Nils Frahm','Daft Punk'],jazz:['Bill Evans','John Coltrane'],classical:['Frédéric Chopin','Ludwig van Beethoven'],persian:['Mohammad Reza Shajarian','Hayedeh']};
async function openSetup(){const version=++generation;status(t('loading'));try{setupDraft=preview?{}:await api('taste-setup');if(version!==generation)return;setupStep=0;await switchView('setup');}catch(error){if(version===generation)status(error.message);}}
function renderSetup(){
 const box=node('section',undefined,'card setup-panel');box.append(node('p',t('step',{n:setupStep+1}),'hint'),node('h3',t('setup_q'+(setupStep+1))),node('p',t('setup_note'),'hint'));
 const choices=node('div',undefined,'setup-choices');
 if(setupStep<2){const key=setupStep===0?'style':'mood',values=setupStep===0?Object.keys(setupArtists):['calm','energetic','mixed'];for(const value of values){const b=action(t(key+'_'+value),()=>{setupDraft[key]=value;renderSetup();},'secondary');b.setAttribute('aria-pressed',String(setupDraft[key]===value));choices.append(b);}box.append(choices);}
 else{const input=node('input');input.id='setup-artist';input.value=setupDraft.artist||'';input.maxLength=80;input.dir='auto';input.placeholder=t('setup_artist_hint');input.oninput=()=>setupDraft.artist=input.value;const label=node('label',t('setup_artist_label'));label.htmlFor=input.id;box.append(label,input);for(const name of setupArtists[setupDraft.style]||setupArtists.pop)choices.append(action(name,()=>{setupDraft.artist=name;input.value=name;},'secondary'));box.append(choices);}
 const actions=node('div',undefined,'guide-actions');if(setupStep)actions.append(action(t('back'),()=>{setupStep--;renderSetup();}));const next=action(t(setupStep===2?'setup_finish':'next'),()=>{if(setupStep<2){setupStep++;renderSetup();}else finishSetup();},'primary');next.disabled=setupStep===0?!setupDraft.style:setupStep===1?!setupDraft.mood:false;actions.append(next);box.append(actions,action(t('skip'),()=>finishSetup(true),'text-button'));$('content').replaceChildren(box);
}
async function finishSetup(skip=false){const version=generation,buttons=[...$('content').querySelectorAll('button')];buttons.forEach(b=>b.disabled=true);status(t('loading'));try{const data=skip?{}:{style:setupDraft.style||null,mood:setupDraft.mood||null,artist:setupDraft.artist||null};if(!preview)await api('taste-setup/update',data);else storageWrite('lilcusin-preview-setup','done');if(version!==generation)return;setupDone=true;lists.clear();try{sessionStorage.removeItem(storageKey);}catch{}await switchView('for-you');notice(t('setup_saved'));}catch(error){if(version===generation)status(error.message);}finally{buttons.forEach(b=>b.disabled=false);}}

async function boot(){
 document.querySelectorAll('.main-nav button').forEach(button=>button.disabled=true);
 resetLanguageTransition();status('Opening Lil Cusin… / در حال باز شدن…');
 try{
  const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),8000);let response;
  try{response=await fetch('/locales.json',{signal:controller.signal});if(!response.ok)throw new Error();catalogue=await response.json();}finally{clearTimeout(timer);}
  locale=normalize(navigator.language);labels();status(t('loading'));
  await initializeTelegram();loadDeliveryReceipts();locale=normalize(tg?.initDataUnsafe?.user?.language_code||navigator.language);
  if(preview){locale=normalize(new URLSearchParams(location.search).get('lang')||storageRead('lilcusin-preview-language')||locale);guideDone=storageRead('lilcusin-preview-guide')==='done';setupDone=storageRead('lilcusin-preview-setup')==='done';}
  for(const id of ['language','guide-language'])$(id).replaceChildren();
  for(const [code,label] of Object.entries(languages)){const option=node('option',label);option.value=code;$('language').append(option);$('guide-language').append(option.cloneNode(true));}
  labels();$('preview').hidden=!preview;
  $('language').onchange=chooseLanguage;$('guide-language').onchange=chooseLanguage;$('help').onclick=showGuide;$('guide-link').onclick=showGuide;
  $('guide-back').onclick=()=>{guideStep--;renderGuide();};$('guide-next').onclick=()=>{if(guideStep===2)closeGuide(true);else{guideStep++;renderGuide();}};$('guide-skip').onclick=()=>closeGuide(false);
  $('guide-dialog').oncancel=event=>{event.preventDefault();closeGuide(false);};
  document.querySelectorAll('.main-nav button').forEach(b=>b.onclick=()=>switchView(b.dataset.view));$('discover').onclick=()=>switchView('search');$('taste-card-open').onclick=()=>switchView('card');$('social-search').onclick=()=>switchView('search');$('social-channels').onclick=()=>switchView('channels');$('home-channels').onclick=()=>switchView('channels');$('home-setup').onclick=openSetup;document.querySelectorAll('#exchange-tabs button').forEach(b=>b.onclick=()=>switchView(b.dataset.view));
  $('search-form').onsubmit=async event=>{event.preventDefault();if(view!=='search')await switchView('search');const version=++generation,b=$('search-button');b.disabled=true;status(t('loading'));try{const term=$('query').value.trim().toLocaleLowerCase();const result=preview?{tracks:demo.filter(s=>`${s.artist} - ${s.title}`.toLocaleLowerCase().includes(term)||s.title.toLocaleLowerCase().includes(term))}:await api('search',{query:$('query').value});if(version===generation){lastResult=result;remember(result);tracks(result);status(result.tracks.length?t('found'):'');}}catch(error){if(version===generation)status(error.message);}finally{b.disabled=false;}};
  if(!preview){for(const id of ['language','guide-language'])$(id).disabled=true;const prefs=await api('preferences',undefined,8000);locale=normalize(prefs.language);guideDone=prefs.ui_guide_done;setupDone=prefs.taste_setup_done!==false;labels();}
  let saved;try{saved=JSON.parse(sessionStorage.getItem(storageKey));if(preview||!saved||Date.now()-saved.time>25*60*1000||!['for-you','search'].includes(saved.view)||!Array.isArray(saved.result?.tracks)||!saved.result.tracks.length)saved=null;}catch{}
  await switchView(saved?.view||'for-you',saved?.result);
 }catch{
  status(catalogue.en?t('startup_error'):'Could not connect. Try again. / وصل نشد. دوباره تلاش کن.');
  $('content').replaceChildren(action(catalogue.en?t('retry'):'Retry / تلاش دوباره',()=>location.reload(),'primary'));
 }finally{resetLanguageTransition();document.querySelectorAll('.main-nav button').forEach(button=>button.disabled=false);}
}
const previewTasteCard={taste_id:'',nickname:'',bio:'',songs:[],current:null,revision:0,shared:false,share_token:null};
let cardDraft=null,cardBusy=false;
function cardDirty(card){return cardDraft&&cardDraft.revision===card.revision&&(cardDraft.nickname!==card.nickname||cardDraft.bio!==card.bio);}
function cardProjection(card){
 const box=node('article',undefined,'card taste-card-preview');box.setAttribute('aria-label',t('card_preview'));
 const brand=node('div',undefined,'card-brand'),owl=node('img');owl.src='/bot-logo.jpg';owl.alt='';owl.width=24;owl.height=24;brand.append(owl,node('span','LilCusin'));box.append(brand);
 if(card.taste_id)box.append(node('p',card.taste_id,'card-taste-id'));box.append(node('h3',card.nickname||t('flow_unnamed')));
 if(card.bio)box.append(node('p',card.bio,'card-bio'));
 box.append(node('p',t('card_songs',{n:card.songs.length}),'hint'));
 const covers=node('div',undefined,'signature-covers');covers.setAttribute('role','list');covers.setAttribute('aria-label',t('card_songs',{n:card.songs.length}));
 for(let i=0;i<5;i++){const song=card.songs[i],slot=node('div',undefined,'signature-slot'+(song?'':' signature-empty'));slot.setAttribute('role','listitem');slot.setAttribute('aria-label',song?song.title+' — '+song.artist:t('a1_empty_slot',{n:i+1}));if(song){const cover=node('div','♪','cover');if(song.artwork)setArtwork(cover,song.artwork);slot.append(cover);}else slot.append(node('span',String(i+1).padStart(2,'0'),'signature-number'),icon('plus'));covers.append(slot);}box.append(covers);
 const songs=node('ol',undefined,'card-song-list');for(const song of card.songs){const item=node('li'),title=node('bdi',song.title),artist=node('bdi',song.artist);title.dir=artist.dir='auto';item.append(title,node('span',' · '),artist);songs.append(item);}box.append(songs);
 if(!card.songs.length)box.append(node('p',t('card_empty'),'hint'));
 if(card.current){const current=node('div',undefined,'card-current');const cover=node('div','♪','cover'),copy=node('div');if(card.current.artwork)setArtwork(cover,card.current.artwork);copy.append(node('p',t('card_current'),'hint'),node('bdi',card.current.artist+' — '+card.current.title));current.append(cover,copy);box.append(current);}
 return box;
}
async function cardMutation(path,data){
 if(cardBusy)return;const version=generation;cardBusy=true;const buttons=[...$('content').querySelectorAll('button,input,textarea')];buttons.forEach(b=>b.disabled=true);status(t('loading'));
 try{
  let next;
  if(preview){
   if(path==='taste-card/share'){if(data.action==='delete'){Object.assign(previewTasteCard,{nickname:'',bio:'',songs:[],current:null});previewTasteCard.revision++;}else{notice(t('card_preview_only'));return;}}
   else{if(data.action==='edit')Object.assign(previewTasteCard,{nickname:data.nickname.trim(),bio:data.bio.trim()});if(data.action==='remove'){previewTasteCard.songs=previewTasteCard.songs.filter(s=>s.id!==data.track_id);if(previewTasteCard.current?.id===data.track_id)previewTasteCard.current=null;}if(data.action==='current')previewTasteCard.current=previewTasteCard.songs.find(s=>s.id===data.track_id)||null;previewTasteCard.revision++;}
   next=previewTasteCard;notice(t('card_preview_only'));
  }else{next=await api(path,data);if(next.deleted)next=await api('taste-card');}
  if(version!==generation)return;cardDraft=null;lastResult=next;renderTasteCard(next);status();if(!preview)notice(t('flow_card_updated'));
 }catch(error){if(version===generation){status(error.message);notice(error.message);}}
 finally{cardBusy=false;buttons.forEach(b=>b.disabled=false);if(version===generation&&$('status').textContent===t('loading'))status();}
}
function confirmCard(card,operation){
 if(cardDirty(card)){notice(t('card_draft_hint'));return;}
 const parent=$('content');parent.querySelector('.card-confirm')?.remove();const box=node('section',undefined,'card card-confirm');box.setAttribute('aria-label',t('card_confirm_'+operation));box.append(node('p',t('card_confirm_'+operation)));const buttons=node('div',undefined,'song-actions');buttons.append(action(t('card_confirm'),()=>cardMutation('taste-card/share',{action:operation,revision:card.revision}),'primary'),action(t('card_cancel'),()=>box.remove()));box.append(buttons);parent.append(box);buttons.firstChild.focus();box.scrollIntoView({block:'nearest',behavior:'smooth'});
}
function renderTasteCard(card){
 const content=$('content');content.replaceChildren();
 if(!cardDraft||cardDraft.revision!==card.revision)cardDraft={revision:card.revision,nickname:card.nickname,bio:card.bio};

 const visibility=node('p',card.shared?t('card_shared',{date:card.expires_at.slice(0,10)}):t('card_private'),'notice');content.append(visibility);
 const form=node('form',undefined,'card taste-card-editor');
 function field(key,value,max,multi=false){const label=node('label',t(key)),input=node(multi?'textarea':'input');input.id=key;input.name=key;input.value=value;input.maxLength=max;input.dir='auto';if(multi)input.rows=3;label.htmlFor=key;form.append(label,input);return input;}
 const name=field('card_nickname',cardDraft.nickname,40),bio=field('card_bio',cardDraft.bio,240,true);
 const save=node('button',t('card_save'),'primary');save.type='submit';form.append(save,node('p',t('card_draft_hint'),'hint'));
 const previewBox=node('section',undefined,'taste-card-preview-wrap');previewBox.append(node('h3',t('card_preview'),'taste-title'),cardProjection({...card,nickname:cardDraft.nickname,bio:cardDraft.bio}));
 function syncDraft(){cardDraft.nickname=name.value;cardDraft.bio=bio.value;previewBox.querySelector('.taste-card-preview').replaceWith(cardProjection({...card,nickname:name.value,bio:bio.value}));}
 name.oninput=bio.oninput=syncDraft;
 form.onsubmit=event=>{event.preventDefault();cardMutation('taste-card/update',{action:'edit',revision:card.revision,nickname:name.value,bio:bio.value});};const edit=disclosure(t('ux_edit_identity'),form);content.append(previewBox,edit);
 const imageBox=node('div');const imageAction=action(t('card_image'),async()=>{if(cardDirty(card)){notice(t('card_draft_hint'));return;}if(preview){notice(t('card_preview_only'));return;}const version=generation;try{status(t('loading'));const result=await api('taste-card/image',{});if(version!==generation)return;const img=node('img');img.src=result.image;img.alt=t('card_image');img.style.cssText='display:block;width:100%;max-width:360px;height:auto;margin:16px auto;border-radius:18px';imageBox.replaceChildren(img,node('p',t('card_image_download'),'hint'));status();}catch(error){status(error.message);}});
 const previewActions=node('div',undefined,'song-actions');previewActions.append(imageAction);previewBox.append(previewActions,imageBox);
 const songs=node('section',undefined,'card taste-card-selections');songs.append(node('h3',t('card_songs',{n:card.songs.length})));
 for(const song of card.songs){const row=node('div',undefined,'card-selected-song');row.append(node('bdi',song.artist+' — '+song.title));const buttons=node('div',undefined,'song-actions');for(const [operation,key] of [['current','card_set_current'],['remove','card_remove']]){const button=action(t(key),()=>{if(cardDirty(card)){notice(t('card_draft_hint'));return;}cardMutation('taste-card/update',{action:operation,revision:card.revision,track_id:song.id});});if(operation==='current')button.setAttribute('aria-pressed',String(card.current?.id===song.id));buttons.append(button);}row.append(buttons);songs.append(row);}
 if(!card.songs.length)songs.append(node('p',t('ux_first_song'),'hint'));
 if(card.current)songs.append(action(t('card_clear_current'),()=>{if(cardDirty(card)){notice(t('card_draft_hint'));return;}cardMutation('taste-card/update',{action:'current',revision:card.revision,track_id:null});}));
 const search=node('form',undefined,'card-song-search'),label=node('label',t('card_find')),input=node('input');input.id='card-song-query';input.maxLength=240;input.required=true;input.dir='auto';label.htmlFor=input.id;const searchButton=node('button',t('card_search'),'secondary');searchButton.type='submit';const results=node('div');search.append(label,input,searchButton);songs.append(search,results);content.append(songs);const next=action(t(card.songs.length?'ux_edit_songs':'ux_choose_first'),()=>{selectProfilePanel('edit');input.focus();search.scrollIntoView({block:'center',behavior:'smooth'});},'primary');previewBox.append(next,node('p',t(card.shared?'ux_card_live':'ux_card_next'),'hint'));
 search.onsubmit=async event=>{event.preventDefault();if(cardDirty(card)){notice(t('card_draft_hint'));return;}const version=generation;searchButton.disabled=true;results.replaceChildren(node('p',t('loading'),'hint'));try{const term=input.value.toLocaleLowerCase().trim();const found=preview?{tracks:demo.filter(s=>(s.artist+' '+s.title).toLocaleLowerCase().includes(term))}:await api('search',{query:input.value});if(version!==generation)return;results.replaceChildren();if(!found.tracks.length)results.append(node('p',t('card_no_matches'),'hint'));for(const song of found.tracks){const row=node('div',undefined,'card-selected-song'),button=action(t('card_add'),async()=>{button.disabled=true;try{if(preview){if(!card.songs.some(s=>s.id===song.id)){if(card.songs.length>=5)throw new Error(t('card_full'));card.songs.push({...song});card.revision++;}cardDraft=null;renderTasteCard(card);notice(t('card_preview_only'));}else{await cardMutation('taste-card/update',{action:'add',revision:card.revision,track_id:song.id,token:found.token});}}catch(error){notice(error.message);}finally{button.disabled=false;}});row.append(node('bdi',song.artist+' — '+song.title),button);results.append(row);}}catch(error){if(version===generation)results.replaceChildren(node('p',error.message,'hint'));}finally{searchButton.disabled=false;}};
 const sharing=node('section',undefined,'card taste-card-sharing');sharing.append(node('h3',t('ux_share_title')),node('p',t('ux_share_intro'),'hint'));const privacy=disclosure(t('ux_visibility_details'),node('p',t('card_visibility'),'hint'));sharing.append(privacy);
 if(preview)sharing.append(node('p',t('card_preview_only'),'notice'));
 if(card.shared&&card.share_url){const share=link('https://t.me/share/url?url='+encodeURIComponent(card.share_url),t('card_share'));share.onclick=event=>{event.preventDefault();if(cardDirty(card)){notice(t('card_draft_hint'));return;}if(tg?.openTelegramLink)tg.openTelegramLink(share.href);else window.open(share.href,'_blank','noopener');};sharing.append(share);const url=node('input');url.value=card.share_url;url.readOnly=true;url.dir='ltr';url.setAttribute('aria-label',t('card_link_hint'));sharing.append(url);}
 if(card.shared){sharing.append(action(t('card_hide'),()=>{if(cardDirty(card)){notice(t('card_draft_hint'));return;}cardMutation('taste-card/share',{action:'hide',revision:card.revision});}),action(t('card_rotate'),()=>confirmCard(card,'rotate')));}else{const publish=action(t('card_publish'),()=>confirmCard(card,'publish'),'primary');publish.disabled=preview||!card.nickname?.trim()||!card.songs.length;sharing.append(publish);if(!card.nickname?.trim()||!card.songs.length)sharing.append(node('p',t('a1_publish_requirements'),'hint'));}
 const advanced=disclosure(t('ux_card_options'),action(t('card_private_summary'),()=>switchView('taste'),'text-button'),action(t('card_delete'),()=>confirmCard(card,'delete'),'text-button'));content.append(sharing,advanced);installProfilePanels({previewBox,edit,songs,sharing,advanced,previewActions,imageBox});socialProfileStats();
}

function renderInvitations(invitations){renderSocialInvitations(invitations);}
document.addEventListener('visibilitychange',()=>{if(document.hidden)resetLanguageTransition();});
window.addEventListener('pagehide',resetLanguageTransition);
boot();
