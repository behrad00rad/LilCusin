// The binding is pinned to the bot's loopback HTTP service, never a caller URL.
export const routes = new Map([
  ['/api/social/unsave','POST'],
  ['/api/social','GET'], ['/api/social/compare','POST'], ['/api/social/choices','POST'], ['/api/social/draft','POST'], ['/api/social/action','POST'], ['/api/social/settings','GET'], ['/api/social/settings/update','POST'], ['/api/social/relationship','POST'], ['/api/social/get-song','POST'],
  ['/api/taste-card/image','POST'], ['/api/comparison-invitations','GET'], ['/api/comparison-invitations/create','POST'], ['/api/comparison-invitations/decide','POST'], ['/api/taste-card','GET'], ['/api/taste-card/update','POST'], ['/api/taste-card/share','POST'], ['/api/taste-card/view','POST'],
  ['/api/taste-setup','GET'], ['/api/taste-setup/update','POST'],
  ['/api/preferences', 'GET'], ['/api/preferences/update', 'POST'], ['/api/profile', 'GET'], ['/api/recommendations', 'POST'],
  ['/api/search', 'POST'], ['/api/rate', 'POST'], ['/api/similar', 'POST'],
  ['/api/artwork', 'POST'], ['/api/channels/songs', 'POST'], ['/api/channels/review', 'POST'], ['/api/channels', 'GET'], ['/api/channels/connect', 'POST'], ['/api/channels/disconnect', 'POST'],
]);
export const headers = {
  'Cache-Control': 'no-store', 'X-Robots-Tag': 'noindex, nofollow',
  'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer',
  'Content-Security-Policy': "default-src 'self'; script-src 'self' https://telegram.org; style-src 'self'; img-src 'self' data: https://lastfm.freetls.fastly.net https://lastfm-img.freetls.fastly.net https://lastfm-img2.akamaized.net; connect-src 'self'; object-src 'none'; base-uri 'none'",
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
      body: request.method==='POST' ? request.body : undefined, redirect:'manual', duplex:'half',
    }));
    if (response.status >= 300 && response.status < 400) return error('Music service unavailable.',503);
    return new Response(response.body,{status:response.status,headers:{...headers,'Content-Type':'application/json'}});
  } catch { return error('Music service unavailable. Please try again.',503); }
}
