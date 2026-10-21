import assert from 'node:assert/strict';
import worker,{routes} from './worker.mjs';
const root='https://fixture.example';
const expected=[['/api/delivery-status','POST'],['/api/delivery-request','POST'],['/api/social','GET'],['/api/social/compare','POST'],['/api/social/choices','POST'],['/api/social/draft','POST'],['/api/social/action','POST'],['/api/social/settings','GET'],['/api/social/settings/update','POST'],['/api/social/relationship','POST'],['/api/social/get-song','POST'],['/api/social/unsave','POST']];
for(const [path,method] of expected){assert.equal(routes.get(path),method);assert.equal((await worker.fetch(new Request(root+path,{method}),{})).status,401);}
let received;
const response=await worker.fetch(new Request(root+'/api/social/action?user_id=foreign',{method:'POST',headers:{'X-Telegram-Init-Data':'fictional-signed','Content-Type':'application/json'},body:JSON.stringify({token:'fictional',action:'save'})}),{LILCUSIN_API:{fetch:async request=>{received=request;return Response.json({saved:true});}}});
assert.equal(response.status,200);assert.equal(received.url,'http://127.0.0.1:8091/api/social/action');
assert.equal((await received.json()).action,'save');
const html=await(await worker.fetch(new Request(root),{})).text();
for(const view of ['for-you','search','card','connections','swaps'])assert.ok(html.includes(`data-view="${view}"`));
assert.ok(html.includes('id="social-search"')&&html.includes('id="social-channels"'));
assert.equal((await worker.fetch(new Request(root+'/social.js'),{})).status,200);
const locales=await(await worker.fetch(new Request(root+'/locales.json'),{})).json();
for(const locale of ['en','fa'])for(const key of ['social_sparse','social_compare_scope','social_settings_scope','social_report_reason','social_confirm_send'])assert.ok(locales[locale][key]);
console.log('Social routes, signed gate, fixed actor-independent proxy, embedded social UI and bilingual controls passed.');
