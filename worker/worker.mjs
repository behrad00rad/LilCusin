// The binding is pinned to the bot's loopback HTTP service, never a caller URL.
export const routes = new Map([
  ['/api/profile', 'GET'], ['/api/recommendations', 'POST'],
  ['/api/search', 'POST'], ['/api/rate', 'POST'],
]);
export const headers = {
  'Cache-Control': 'no-store', 'X-Robots-Tag': 'noindex, nofollow',
  'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer',
  'Content-Security-Policy': "default-src 'self'; script-src 'self' https://telegram.org; style-src 'self'; img-src 'self' https://lastfm.freetls.fastly.net https://lastfm-img2.akamaized.net; connect-src 'self'; object-src 'none'; base-uri 'none'",
};
export function error(message, status) {
  return Response.json({error:message},{status,headers});
}
export async function proxy(request, env) {
  const url = new URL(request.url);
  if (!routes.has(url.pathname)) return error('Not found.',404);
  if (request.method !== routes.get(url.pathname)) return error('Method not allowed.',405);
  const auth = request.headers.get('X-Telegram-Init-Data');
  if (!auth || auth.length > 12000) return error('Open Lil Cusin from Telegram.',401);
  const backend = env.BOT_BRIDGE ? env.BOT_BRIDGE.get(env.BOT_BRIDGE.idFromName('lilcusin')) : env.LILCUSIN_API;
  if (!backend) return error('The music service is being connected. Please try again shortly.',503);
  if (Number(request.headers.get('Content-Length')) > 16384) return error('Request too large.',413);
  // Queries, cookies, destination headers and redirects are never forwarded.
  try {
    const response = await backend.fetch(new Request(`http://127.0.0.1:8091${url.pathname}`, {
      method: request.method, headers:{'Content-Type':'application/json','X-Telegram-Init-Data':auth},
      body: request.method==='POST' ? request.body : undefined, redirect:'manual',
    }));
    if (response.status >= 300 && response.status < 400) return error('Music service unavailable.',503);
    return new Response(response.body,{status:response.status,headers:{...headers,'Content-Type':'application/json'}});
  } catch { return error('Music service unavailable. Please try again.',503); }
}

// A single, hibernating connector; no preference data is written to Cloudflare storage.
export class LilCusinBridge {
  constructor(state, env) {
    this.state=state; this.env=env; this.pending=new Map();
    if (typeof WebSocketRequestResponsePair !== 'undefined')
      state.setWebSocketAutoResponse(new WebSocketRequestResponsePair('ping','pong'));
  }
  async fetch(request) {
    const path=new URL(request.url).pathname;
    if(path==='/connect') {
      const expected=this.env.CONNECTOR_TOKEN;
      const provided=request.headers.get('Authorization')?.replace(/^Bearer /,'');
      if(!expected || !provided || provided.length>512) return error('Unauthorized.',401);
      const digest=async s=>new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(s)));
      const [a,b]=await Promise.all([digest(expected),digest(provided)]);
      let mismatch=0;for(let i=0;i<a.length;i++)mismatch|=a[i]^b[i];
      if(mismatch) return error('Unauthorized.',401);
      if(request.method!=='GET' || request.headers.get('Upgrade')?.toLowerCase()!=='websocket')
        return error('WebSocket required.',400);
      for(const previous of this.state.getWebSockets('connector')) {
        this.failSocket(previous); previous.close(1012,'Connector replaced');
      }
      const [client,server]=Object.values(new WebSocketPair());
      this.state.acceptWebSocket(server,['connector']);
      server.serializeAttachment({connectionId:crypto.randomUUID()});
      return new Response(null,{status:101,webSocket:client});
    }
    if(!routes.has(path))return error('Not found.',404);
    if(request.method!==routes.get(path))return error('Method not allowed.',405);
    const auth=request.headers.get('X-Telegram-Init-Data');
    if(!auth || auth.length>12000)return error('Open Lil Cusin from Telegram.',401);
    const socket=this.state.getWebSockets('connector').find(ws=>ws.readyState===1);
    if(!socket)return error('The music service is reconnecting. Please try again.',503);
    if(this.pending.size>=32)return error('Please try again in a moment.',429);
    let body='';
    if(request.body) {
      const reader=request.body.getReader(),chunks=[];let size=0;
      for(;;) {
        const {value,done}=await reader.read();if(done)break;
        size+=value.length;
        if(size>16384){await reader.cancel();return error('Request too large.',413);}
        chunks.push(value);
      }
      const buffer=new Uint8Array(size);let offset=0;
      for(const chunk of chunks){buffer.set(chunk,offset);offset+=chunk.length;}
      body=new TextDecoder().decode(buffer);
    }
    const id=crypto.randomUUID();
    return await new Promise(resolve=>{
      const timer=setTimeout(()=>{this.pending.delete(id);resolve(error('Music service timed out. Please try again.',504));},45000);
      this.pending.set(id,{resolve,timer,socket,connectionId:this.connectionId(socket)});
      try{socket.send(JSON.stringify({kind:'request',id,path,method:request.method,auth,body}));}
      catch{clearTimeout(timer);this.pending.delete(id);resolve(error('Music service is reconnecting.',503));}
    });
  }
  webSocketMessage(socket,message) {
    if(typeof message!=='string' || message.length>131072)return;
    let result;try{result=JSON.parse(message);}catch{return;}
    const pending=this.pending.get(result.id);
    if(!pending || !pending.connectionId || pending.connectionId!==this.connectionId(socket) || !Number.isInteger(result.status)
       || result.status<200 || result.status>599 || typeof result.body!=='string' || result.body.length>65536)return;
    clearTimeout(pending.timer);this.pending.delete(result.id);
    pending.resolve(new Response(result.body,{status:result.status,headers:{...headers,'Content-Type':'application/json'}}));
  }
  failSocket(socket) {
    const connectionId=this.connectionId(socket);
    for(const [id,item] of this.pending)if(connectionId && item.connectionId===connectionId){
      clearTimeout(item.timer);this.pending.delete(id);item.resolve(error('Music service is reconnecting.',503));
    }
  }
  connectionId(socket) {
    try {return socket.deserializeAttachment?.()?.connectionId || null;}
    catch {return null;}
  }
  webSocketClose(socket){this.failSocket(socket);}
  webSocketError(socket){this.failSocket(socket);}
}

const assets = {"/": ["<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1,viewport-fit=cover\"><meta name=\"color-scheme\" content=\"dark light\"><meta name=\"robots\" content=\"noindex,nofollow\"><title>Lil Cusin · Your next favorite</title><link rel=\"stylesheet\" href=\"/style.css\"><script src=\"https://telegram.org/js/telegram-web-app.js\"></script><script src=\"/app.js\" defer></script></head>\n<body><div class=\"shell\"><header><a class=\"brand\" href=\"/\" aria-label=\"Lil Cusin home\"><span class=\"logo\">lc<span>♪</span></span><span>lil cusin<span class=\"brand-note\">A LITTLE CLOSER TO YOUR SOUND</span></span></a><span class=\"badge\">YOUR MUSIC PAL</span></header>\n<main><p id=\"preview\" class=\"notice\" hidden>Design preview · Open from Telegram to load your music.</p><section class=\"hero\"><p class=\"eyebrow\">GOOD MUSIC. GOOD COMPANY.</p><h1>Your next<br>favorite is <em>out there.</em></h1><p>A little discovery. A lot of you.<br>Let’s find something that feels right.</p><div class=\"record\" aria-hidden=\"true\"><div>lc ♪</div></div><button id=\"discover\" class=\"primary\">Find my sound <span>↗</span></button></section>\n<div class=\"section-title\"><h2 id=\"view-title\">Made for you</h2><span id=\"view-note\">FOLLOW YOUR EARS</span></div>\n<form id=\"search-form\" hidden><label for=\"query\">Find a song you know</label><div class=\"search-box\"><input id=\"query\" maxlength=\"240\" placeholder=\"Radiohead - Creep\" required autocomplete=\"off\"><button class=\"primary\" type=\"submit\">Search ↗</button></div><p class=\"hint\">Find the right song, then rate it to teach me your taste.</p></form>\n<div id=\"status\" role=\"status\" aria-live=\"polite\"></div><div id=\"content\"></div>\n<aside class=\"tip\"><span>✦</span><p><strong>Every little like goes a long way.</strong><br>Your ratings help me get to know your sound.</p></aside>\n</main><nav aria-label=\"Main navigation\"><button data-view=\"for-you\" class=\"active\" aria-current=\"page\"><span>✦</span>For You</button><button data-view=\"search\"><span>⌕</span>Search</button><button data-view=\"taste\"><span>♡</span>My Taste</button></nav></div></body></html>\n", "text/html; charset=utf-8"], "/app.js": ["const tg = window.Telegram?.WebApp;\nconst preview = !tg?.initData;\nconst $ = id => document.getElementById(id);\nlet view = 'for-you', generation = 0;\nconst demo = [{id:1,title:'Everything In Its Right Place',artist:'Radiohead',reason:'A familiar feeling, a new direction.'},{id:2,title:'Space Song',artist:'Beach House',reason:'For the softer side of your sound.'},{id:3,title:'Intro',artist:'The xx',reason:'A little space to get lost in.'}];\nfunction node(tag, text, className) {const el=document.createElement(tag);if(text!==undefined)el.textContent=text;if(className)el.className=className;return el;}\nfunction theme() {const p=tg?.themeParams;if(!p?.bg_color)return;const s=document.documentElement.style;for(const [key,val] of Object.entries({'--bg':p.bg_color,'--panel':p.secondary_bg_color,'--ink':p.text_color,'--muted':p.hint_color,'--accent':p.button_color,'--accent-ink':p.button_text_color}))if(val)s.setProperty(key,val);}\nfunction safeArea(){const s=document.documentElement.style;s.setProperty('--safe-top',`${Math.max(tg?.safeAreaInset?.top||0,tg?.contentSafeAreaInset?.top||0)}px`);s.setProperty('--safe-bottom',`${Math.max(tg?.safeAreaInset?.bottom||0,tg?.contentSafeAreaInset?.bottom||0)}px`);}\ntg?.ready();tg?.expand();theme();safeArea();tg?.onEvent('themeChanged',theme);tg?.onEvent('safeAreaChanged',safeArea);tg?.onEvent('contentSafeAreaChanged',safeArea);\nasync function api(path, data) {const response=await fetch(`/api/${path}`,{method:data===undefined?'GET':'POST',headers:{'Content-Type':'application/json','X-Telegram-Init-Data':tg.initData},body:data===undefined?undefined:JSON.stringify(data)});const result=await response.json();if(!response.ok)throw new Error(result.error||'Please try again.');return result;}\nfunction empty(title, detail, search=false){const box=node('div',undefined,'empty');box.append(node('span','♪'),node('h3',title),node('p',detail));if(search){const b=node('button','Find a song ↗','primary');b.onclick=()=>switchView('search');box.append(b);}$('content').replaceChildren(box);}\nfunction tracks(result){$('content').replaceChildren();if(!result.tracks.length){empty(result.status==='insufficient_preferences'?'Let’s get to know your sound':'Nothing here just yet',view==='search'?'Try another artist or title.':'Rate a few songs you love, then come back for recommendations.',view!=='search');return;}for(const t of result.tracks){const card=node('article',undefined,'card'), row=node('div',undefined,'track'), cover=node('div','♪','cover'), info=node('div');if(t.artwork){const img=node('img');img.src=t.artwork;img.alt=`${t.title} artwork`;img.loading='lazy';img.onerror=()=>img.remove();cover.replaceChildren(img);}info.append(node('h3',t.title),node('p',t.artist));row.append(cover,info);card.append(row);if(t.reason)card.append(node('p',t.reason,'reason'));const ratings=node('div',undefined,'ratings');ratings.setAttribute('aria-label',`Rate ${t.title}`);for(const [value,label] of [['love','♥ Love'],['like','↑ Like'],['neutral','– Neutral'],['dislike','↓ Dislike']]){const b=node('button',label);b.setAttribute('aria-pressed','false');b.onclick=async()=>{const buttons=[...ratings.children];buttons.forEach(x=>x.disabled=true);try{if(!preview)await api('rate',{token:result.token,track_id:t.id,value});buttons.forEach(x=>{x.classList.toggle('selected',x===b);x.setAttribute('aria-pressed',String(x===b));});$('status').textContent=preview?'Preview rating selected. Your real taste is unchanged.':'Saved. Getting closer to your sound.';tg?.HapticFeedback?.notificationOccurred('success');}catch(e){$('status').textContent=e.message;}finally{buttons.forEach(x=>x.disabled=false);}};ratings.append(b);}card.append(ratings);$('content').append(card);}}\nfunction profile(p){$('content').replaceChildren();const box=node('div',undefined,'stats');for(const [value,label] of [[p.songs,'Songs rated'],[p.counts.love||0,'Loved songs'],[p.channels,'Channels']]){const stat=node('div',undefined,'stat');stat.append(node('strong',String(value)),node('span',label));box.append(stat);}$('content').append(node('p',`A sound that’s all yours, ${p.name}.`),box);for(const [title,items] of [['Your artists',p.artists],['Your flavors',p.tags]]){$('content').append(node('h3',title,'taste-title'));const chips=node('div',undefined,'chips');for(const item of items)chips.append(node('span',item,'chip'));if(!items.length)chips.append(node('p','Rate songs to start building your taste.','hint'));$('content').append(chips);}const help=node('p','Connect playlist channels with /connectchannel in the bot. Manage your data with /privacy and /forgetme.','hint');$('content').append(help);}\nasync function switchView(next){view=next;const version=++generation;document.querySelectorAll('nav button').forEach(b=>{b.classList.toggle('active',b.dataset.view===view);if(b.dataset.view===view)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current');});$('search-form').hidden=view!=='search';$('view-title').textContent={'for-you':'Made for you',search:'Find your favorites',taste:'Your taste, taking shape'}[view];$('view-note').textContent=view==='taste'?'UNIQUELY YOU':'FOLLOW YOUR EARS';$('content').replaceChildren();$('status').textContent='';if(view==='search'){$('query').focus();return;}$('status').textContent=preview?'A peek at your music space.':'Finding your sound…';try{const result=preview?(view==='taste'?{name:'friend',songs:24,counts:{love:12},channels:2,artists:['Radiohead','Beach House','The xx'],tags:['Alternative','Dream pop','Indie']}: {tracks:demo}):await api(view==='taste'?'profile':'recommendations',view==='taste'?undefined:{});if(version!==generation)return;$('status').textContent='';if(view==='taste')profile(result);else tracks(result);}catch(e){if(version===generation){$('status').textContent=e.message;empty('Couldn’t load your music','Tap For You or My Taste to try again.');}}}\ndocument.querySelectorAll('nav button').forEach(b=>b.onclick=()=>switchView(b.dataset.view));$('discover').onclick=()=>switchView('for-you');$('search-form').onsubmit=async e=>{e.preventDefault();const version=++generation;const b=e.currentTarget.querySelector('button');b.disabled=true;$('status').textContent='Looking for your song…';try{const result=preview?{tracks:demo.filter(t=>`${t.artist} - ${t.title}`.toLowerCase().includes($('query').value.trim().toLowerCase()))}:await api('search',{query:$('query').value});if(version===generation){$('status').textContent=result.tracks.length?'Found these matches. Rate the right song.':'';tracks(result);}}catch(error){if(version===generation)$('status').textContent=error.message;}finally{b.disabled=false;}};$('preview').hidden=!preview;switchView('for-you');\n", "text/javascript; charset=utf-8"], "/style.css": [":root{--bg:#101014;--panel:#1a1a21;--ink:#f4f2fa;--muted:#a7a3b5;--line:#303039;--accent:#bc9aff;--accent-ink:#221637;--safe-top:0px;--safe-bottom:0px;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,\"Segoe UI\",sans-serif;color:var(--ink);background:var(--bg)}\n*{box-sizing:border-box}body{margin:0}button,input{font:inherit}button,a{-webkit-tap-highlight-color:transparent}button{cursor:pointer}button:disabled{opacity:.55;cursor:wait}button:focus-visible,a:focus-visible,input:focus-visible{outline:2px solid var(--accent);outline-offset:4px}button{color:inherit;border:0}a{color:inherit;text-decoration:none}.shell{max-width:650px;margin:auto;padding:calc(26px + var(--safe-top)) 24px calc(116px + var(--safe-bottom))}header{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:34px}.brand{display:flex;gap:12px;align-items:center;font-size:23px;font-weight:800;letter-spacing:-1px}.logo{background:var(--accent);color:var(--accent-ink);height:43px;width:43px;border-radius:13px;display:grid;place-content:center;position:relative;transform:rotate(-5deg)}.logo span{position:absolute;font-size:16px;right:4px;top:0}.brand-note{display:block;font-size:7px;letter-spacing:1.6px;font-weight:600;margin-top:4px;color:var(--muted)}.badge{font-size:8px;letter-spacing:1.5px;color:var(--muted);border:1px solid var(--line);border-radius:30px;padding:9px}.hero{position:relative;overflow:hidden;background:linear-gradient(125deg,#272036,#1d1b27 60%,#302342);border:1px solid #3d334e;border-radius:25px;padding:29px 25px;min-height:323px;color:#f4f2fa}.eyebrow{font-size:9px;letter-spacing:2px;color:#d0b9f5;margin:0 0 19px}h1{font-size:clamp(32px,7vw,46px);font-weight:750;line-height:1.08;letter-spacing:-2px;margin:0;position:relative;z-index:1}h1 em{font-style:normal;color:#c4a2ff;display:block}.hero>p:not(.eyebrow){color:#bab3cb;font-size:13px;line-height:1.7;position:relative;z-index:1}.primary{background:var(--accent);color:var(--accent-ink);padding:13px 18px;border-radius:12px;font-size:13px;font-weight:700;min-height:44px}.hero .primary{margin-top:10px;position:relative;z-index:1;min-width:157px;display:flex;justify-content:space-between;gap:25px}.record{position:absolute;right:-66px;bottom:4px;border-radius:50%;height:235px;width:235px;background:repeating-radial-gradient(circle,#121116 0px,#121116 3px,#29232e 4px,#17141d 5px);box-shadow:0 0 0 10px #ffffff03;display:grid;place-items:center;transform:rotate(-25deg)}.record div{width:83px;height:83px;border-radius:50%;background:#ba98ea;color:#20172c;display:grid;place-items:center;font-size:23px;font-weight:800}.section-title{display:flex;justify-content:space-between;align-items:center;margin:30px 0 17px;gap:10px}h2{margin:0;font-size:21px;letter-spacing:-.6px}.section-title>span{font-size:8px;letter-spacing:1.5px;color:var(--muted)}.card{padding:16px;background:var(--panel);border:1px solid var(--line);border-radius:17px;margin-bottom:12px}.track{display:flex;align-items:center;gap:14px}.cover{height:64px;width:64px;border-radius:11px;flex-shrink:0;background:linear-gradient(145deg,#755392,#2c314d);display:grid;place-items:center;color:#e5cbff;font-size:28px;overflow:hidden}.cover img{height:100%;width:100%;object-fit:cover}.card:nth-child(3n+2) .cover{background:linear-gradient(145deg,#586d61,#232d31)}.card:nth-child(3n) .cover{background:linear-gradient(145deg,#ac785c,#482d42)}.track h3{font-size:15px;margin:0 0 5px;line-height:1.3}.track p{margin:0;font-size:12px;color:var(--muted)}.reason{font-size:11px;color:var(--muted);line-height:1.6;margin:12px 0}.ratings{display:flex;gap:6px;margin-top:13px}.ratings button{flex:1;border:1px solid var(--line);background:transparent;border-radius:9px;min-height:40px;font-size:11px;padding:5px}.ratings button.selected{border-color:var(--accent);background:var(--accent);color:var(--accent-ink)}.tip{display:flex;gap:13px;color:var(--muted);font-size:11px;line-height:1.8;margin-top:25px;padding:18px 0;border-top:1px solid var(--line)}.tip>span{color:var(--accent);font-size:22px}.tip p{margin:0}.tip strong{color:var(--ink);font-weight:500}nav{position:fixed;bottom:0;left:50%;transform:translateX(-50%);width:min(100%,650px);display:flex;justify-content:space-around;padding:12px 20px calc(13px + max(env(safe-area-inset-bottom),var(--safe-bottom)));background:var(--bg);border-top:1px solid var(--line);z-index:3}nav button{background:none;color:var(--muted);font-size:10px;min-height:48px;width:30%;border-radius:12px}nav button span{display:block;font-size:22px;margin-bottom:4px}nav button.active{color:var(--accent);background:var(--panel)}.notice{font-size:11px;padding:12px;border:1px dashed var(--line);border-radius:12px;color:var(--muted)}#status{font-size:12px;color:var(--muted);line-height:1.6;margin:12px 0}label{font-size:12px;color:var(--muted);display:block;margin-bottom:10px}.search-box{display:flex;gap:8px}input{min-width:0;flex:1;background:var(--panel);border:1px solid var(--line);color:var(--ink);padding:13px;border-radius:12px;font-size:13px}.hint{font-size:11px;color:var(--muted);line-height:1.7}.empty{padding:30px 23px;border:1px dashed var(--line);border-radius:17px;text-align:center}.empty>span{color:var(--accent);font-size:32px}.empty h3{font-size:17px}.empty p{font-size:12px;line-height:1.7;color:var(--muted)}.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:9px;margin:20px 0}.stat{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:17px 10px;text-align:center;font-size:11px;color:var(--muted)}.stat strong{display:block;font-size:25px;color:var(--accent);margin-bottom:6px}.chips{display:flex;flex-wrap:wrap;gap:8px}.chip{background:var(--panel);padding:10px 13px;border-radius:24px;font-size:12px;border:1px solid var(--line)}.taste-title{margin:25px 0 14px;font-size:15px}@media(max-width:360px){.shell{padding-left:16px;padding-right:16px}.badge{display:none}.hero{padding:23px 20px}.record{right:-105px}.ratings button{font-size:10px}}[hidden]{display:none!important}@media(prefers-reduced-motion:no-preference){.card{animation:appear .2s ease-out}@keyframes appear{from{opacity:0;transform:translateY(5px)}to{opacity:1;transform:none}}}\n", "text/css; charset=utf-8"]};
export default {
  async fetch(request, env) {
    const path = new URL(request.url).pathname;
    if (path === '/connector') {
      if (!env.BOT_BRIDGE) return error('Connector is not configured.',503);
      return env.BOT_BRIDGE.get(env.BOT_BRIDGE.idFromName('lilcusin')).fetch(new Request('https://internal/connect',request));
    }
    if (path.startsWith('/api/')) return proxy(request,env);
    const asset = assets[path];
    if (!asset) return error('Not found.',404);
    if (!['GET','HEAD'].includes(request.method)) return error('Method not allowed.',405);
    return new Response(request.method==='HEAD'?null:asset[0], {headers:{...headers,'Content-Type':asset[1]}});
  }
};
