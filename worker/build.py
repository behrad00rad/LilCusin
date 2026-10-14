"""Generate a single dashboard-uploadable Worker from the maintained UI assets."""
from pathlib import Path
import json
import base64

root = Path(__file__).resolve().parent
assets = {}
for name, mime in [('index.html','text/html'),('app.js','text/javascript'),('style.css','text/css'),('locales.json','application/json'),('Vazirmatn-OFL.txt','text/plain')]:
    assets['/' if name == 'index.html' else '/' + name] = [
        (root.parent/'music_bot/web'/name).read_text(encoding='utf-8-sig'), mime + '; charset=utf-8']
assets['/bot-logo.jpg'] = [base64.b64encode((root.parent/'music_bot/web/bot-logo.jpg').read_bytes()).decode(), 'image/jpeg']
assets['/vazirmatn.woff2'] = [base64.b64encode((root.parent/'music_bot/web/vazirmatn.woff2').read_bytes()).decode(), 'font/woff2']
source = (root/'proxy.mjs').read_text()
source += '\n' + (root/'bridge.mjs').read_text()
source += '\nconst assets = ' + json.dumps(assets,ensure_ascii=False) + ';\n'
source += '''export default {
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
    const body=['image/jpeg','font/woff2'].includes(asset[1])?Uint8Array.from(atob(asset[0]),c=>c.charCodeAt(0)):asset[0];
    return new Response(request.method==='HEAD'?null:body, {headers:{...headers,'Content-Type':asset[1]}});
  }
};
'''
(root/'worker.mjs').write_text(source,encoding='utf-8')
print('Worker built with embedded UI assets; no secrets included.')
