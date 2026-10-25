import assert from 'node:assert/strict';
import worker, {LilCusinBridge, routeMethod, guessQuery} from './worker.mjs';
const friend='f'.repeat(32), game='g'.repeat(32), auth={'X-Telegram-Init-Data':'fixture'};
assert.equal(routeMethod('/api/guess/start'),'POST');
assert.equal(routeMethod('/api/guess/nudge'),'POST');
assert.equal(routeMethod('/api/guess/preferences','GET'),'GET');
assert.equal(routeMethod('/api/guess/preferences','POST'),'POST');
assert.equal(routeMethod('/api/taste-sharing','GET'),'GET');
assert.equal(routeMethod('/api/taste-sharing','POST'),'POST');
assert.equal(routeMethod(`/api/guess/${game}/answer`),'POST');
assert.equal(routeMethod('/api/guess/bad/answer'),undefined);
assert.equal(guessQuery(new URL(`https://internal/api/guess/status?friend_id=${friend}`)),`?friend_id=${friend}`);
for(const suffix of ['',`?friend_id=${friend}&friend_id=${friend}`,`?friend_id=${friend}&target=private`,`?friend_id=bad`]) {
  assert.equal((await worker.fetch(new Request('https://internal/api/guess/status'+suffix,{headers:auth}),{})).status,400);
}
let forwarded;
const response=await worker.fetch(new Request(`https://internal/api/guess/status?friend_id=${friend}`,{headers:auth}),{
 LILCUSIN_API:{fetch:async request=>{forwarded=request;return Response.json({eligible:true});}}});
assert.equal(response.status,200);
assert.equal(forwarded.url,`http://127.0.0.1:8091/api/guess/status?friend_id=${friend}`);
assert.equal((await worker.fetch(new Request(`https://internal/api/guess/${game}/answer`,{method:'GET',headers:auth}),{})).status,405);
assert.equal((await worker.fetch(new Request('https://internal/api/guess/start',{method:'POST'}),{})).status,401);
let sent;
const socket={readyState:1,deserializeAttachment:()=>({connectionId:'guess-fixture'}),send:value=>{sent=JSON.parse(value);}};
const bridge=new LilCusinBridge({getWebSockets:()=>[socket]},{});
const pending=bridge.fetch(new Request(`https://internal/api/guess/status?friend_id=${friend}`,{headers:auth}));
await Promise.resolve();
assert.equal(sent.path,`/api/guess/status?friend_id=${friend}`);
bridge.webSocketMessage(socket,JSON.stringify({id:sent.id,status:200,body:'{"eligible":true}'}));
assert.equal((await pending).status,200);
console.log('Guess API proxy/bridge fixed-destination, method, auth and query allowlists passed.');
