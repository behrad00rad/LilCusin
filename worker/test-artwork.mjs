import assert from 'node:assert/strict';
import {cover} from './artwork.mjs';
const original=globalThis.fetch;
let calls=[];
globalThis.fetch=async(url,options)=>{calls.push({url,options});return new Response(new Uint8Array([1,2,3]),{headers:{'Content-Type':'image/png'}});};
try {
  const url='https://lastfm-img.freetls.fastly.net/i/u/300x300/cover.png';
  const request=new Request('https://app.example/cover?url='+encodeURIComponent(url),{headers:{Authorization:'private','X-Telegram-Init-Data':'private'}});
  const response=await cover(request);
  assert.equal(response.status,200);assert.equal(response.headers.get('Content-Type'),'image/png');
  assert.equal(calls[0].options.redirect,'error');assert.deepEqual(Object.keys(calls[0].options.headers),['Accept']);
  for (const bad of ['https://evil.example/image.png','http://lastfm-img.freetls.fastly.net/image.png','https://lastfm-img.freetls.fastly.net:444/image.png','https://lastfm-img.freetls.fastly.net/2a96cbd8b46e442fc41c2b86b821562f.png'])
    assert.equal((await cover(new Request('https://app.example/cover?url='+encodeURIComponent(bad)))).status,400);
  assert.equal(calls.length,1);
  globalThis.fetch=async()=>new Response('<svg/>',{headers:{'Content-Type':'image/svg+xml'}});
  assert.equal((await cover(request)).status,404);
  console.log('Artwork proxy: image delivery, private-header isolation, host/port/scheme checks, placeholder and active content rejection passed.');
} finally {globalThis.fetch=original;}
