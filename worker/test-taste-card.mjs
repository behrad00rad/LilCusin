import assert from 'node:assert/strict';
import worker, {routes} from './worker.mjs';

const root='https://lilcusin-ui.example.workers.dev';
for(const [path,method] of [['/api/taste-card','GET'],['/api/taste-card/update','POST'],['/api/taste-card/share','POST'],['/api/taste-card/view','POST'],['/api/taste-card/image','POST'],['/api/comparison-invitations','GET'],['/api/comparison-invitations/create','POST'],['/api/comparison-invitations/decide','POST']]) {
  assert.equal(routes.get(path),method);
  assert.equal((await worker.fetch(new Request(root+path,{method}),{})).status,401);
}
let received;
const payload={token:'synthetic-card-token'};
const result=await worker.fetch(new Request(root+'/api/taste-card/view?user_id=someone-else',{
  method:'POST',headers:{'X-Telegram-Init-Data':'signed-fixture','Content-Type':'application/json','Cookie':'private'},body:JSON.stringify(payload),
}),{LILCUSIN_API:{fetch:async request=>{received=request;return Response.json({nickname:'Chosen name',songs:[]});}}});
assert.equal(result.status,200);
assert.equal(received.url,'http://127.0.0.1:8091/api/taste-card/view');
assert.equal(received.headers.get('Cookie'),null);
assert.deepEqual(await received.json(),payload);
const html=await (await worker.fetch(new Request(root),{})).text();
const js=await (await worker.fetch(new Request(root+'/app.js'),{})).text();
const locales=await (await worker.fetch(new Request(root+'/locales.json'),{})).json();
assert.match(html,/data-view="card"/);
assert.match(js,/function renderTasteCard/);
for(const language of ['en','fa'])assert.ok(locales[language].card_visibility&&locales[language].card_confirm_publish);
console.log('Taste-card routes, fixed proxy, signed access, embedded editor and English/Persian copy passed.');
