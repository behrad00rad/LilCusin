import assert from 'node:assert/strict';
import worker from './worker.mjs';
const root = 'https://lilcusin-ui.example.workers.dev';
const page = await worker.fetch(new Request(root),{});
assert.equal(page.status,200);
assert.equal(page.headers.get('X-Robots-Tag'),'noindex, nofollow');
assert.match(await page.text(),/guide-dialog/);
assert.equal((await worker.fetch(new Request(root+'/api/profile'),{})).status,401);
assert.equal((await worker.fetch(new Request(root+'/api/unknown'),{})).status,404);
assert.equal((await worker.fetch(new Request(root+'/api/rate'),{})).status,405);
assert.equal((await worker.fetch(new Request(root+'/api/profile',{headers:{'X-Telegram-Init-Data':'test'}}),{})).status,503);
let forwarded;
const response=await worker.fetch(new Request(root+'/api/profile?target=https://other.example',{
  headers:{'X-Telegram-Init-Data':'test','Cookie':'private=value','Authorization':'private'},
}),{LILCUSIN_API:{fetch:async request=>{forwarded=request;return Response.json({name:'Test'});}}});
assert.equal(response.status,200);
assert.equal(forwarded.url,'http://127.0.0.1:8091/api/profile');
assert.equal(forwarded.headers.get('Cookie'),null);
assert.equal(forwarded.headers.get('Authorization'),null);
console.log('Worker routes, noindex, authentication gate and fixed destination passed.');

const logo=await worker.fetch(new Request(root+'/bot-logo.jpg'),{});
assert.equal(logo.headers.get('Content-Type'),'image/jpeg');
assert.ok((await logo.arrayBuffer()).byteLength>1000);
const locales=await (await worker.fetch(new Request(root+'/locales.json'),{})).json();
assert.equal(Object.keys(locales).length,8);
assert.equal((await worker.fetch(new Request(root+'/api/preferences'),{})).status,401);

const font=await worker.fetch(new Request(root+'/vazirmatn.woff2'),{});
assert.equal(font.headers.get('Content-Type'),'font/woff2');
assert.equal(new TextDecoder().decode((await font.arrayBuffer()).slice(0,4)),'wOF2');
