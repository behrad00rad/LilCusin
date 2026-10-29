const imageHosts = new Set(['lastfm.freetls.fastly.net','lastfm-img.freetls.fastly.net','lastfm-img2.akamaized.net']);
export async function cover(request) {
  if (!['GET','HEAD'].includes(request.method)) return new Response(null,{status:405});
  let url;
  try {
    const raw=new URL(request.url).searchParams.get('url');
    if (!raw || raw.length>1500) throw new Error();
    url=new URL(raw);
    if (url.protocol!=='https:' || !imageHosts.has(url.hostname) || url.username || url.password || url.port || url.hash || url.search || url.pathname.includes('2a96cbd8b46e442fc41c2b86b821562f')) throw new Error();
  } catch { return new Response(null,{status:400}); }
  const controller=new AbortController();
  const timeout=setTimeout(()=>controller.abort(),8000);
  try {
    const response=await fetch(url.href,{redirect:'manual',signal:controller.signal,headers:{Accept:'image/jpeg,image/png,image/webp,image/avif'},cf:{cacheTtl:86400,cacheEverything:true}});
    const type=response.headers.get('Content-Type')?.split(';')[0];
    if (!response.ok || !['image/jpeg','image/png','image/webp','image/avif'].includes(type) || Number(response.headers.get('Content-Length'))>2097152) return new Response(null,{status:404});
    const bytes=await response.arrayBuffer();
    if (bytes.byteLength>2097152) return new Response(null,{status:413});
    const immutable=/^\/i\/u\/(174s|300x300|600x600)\/[a-f0-9]{32}\.(png|jpe?g|webp)$/.test(url.pathname);
    return new Response(request.method==='HEAD'?null:bytes,{headers:{'Content-Type':type,'Cache-Control':immutable?'public, max-age=31536000, immutable':'public, max-age=86400','X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer'}});
  } catch { return new Response(null,{status:502}); }
  finally { clearTimeout(timeout); }
}
