import assert from 'node:assert/strict';
import {LilCusinBridge} from './worker.mjs';
const state={getWebSockets:()=>[]};
const bridge=new LilCusinBridge(state,{CONNECTOR_TOKEN:'private-test'});
assert.equal((await bridge.fetch(new Request('https://internal/connect'))).status,401);
assert.equal((await bridge.fetch(new Request('https://internal/connect',{headers:{Authorization:'Bearer wrong'}}))).status,401);
assert.equal((await bridge.fetch(new Request('https://internal/connect',{headers:{Authorization:'Bearer private-test'}}))).status,400);
assert.equal((await bridge.fetch(new Request('https://internal/api/profile'))).status,401);
assert.equal((await bridge.fetch(new Request('https://internal/api/profile',{headers:{'X-Telegram-Init-Data':'test'}}))).status,503);
let sent;
const socket={readyState:1,deserializeAttachment:()=>({connectionId:'connector-1'}),send:message=>{sent=JSON.parse(message)}};
state.getWebSockets=()=>[socket];
const response=bridge.fetch(new Request('https://internal/api/profile',{headers:{'X-Telegram-Init-Data':'signed-data'}}));
await new Promise(resolve=>setTimeout(resolve,0));
bridge.webSocketMessage({},JSON.stringify({id:sent.id,status:200,body:'{}'}));
assert.equal(bridge.pending.size,1,'Other sockets cannot forge a response');
const resumedSocket={deserializeAttachment:()=>({connectionId:'connector-1'})};
bridge.webSocketMessage(resumedSocket,JSON.stringify({id:sent.id,status:200,body:'{"ok":true}'}));
assert.equal((await response).status,200);
assert.equal(bridge.pending.size,0);
const dropped=bridge.fetch(new Request('https://internal/api/profile',{headers:{'X-Telegram-Init-Data':'signed-data'}}));
await new Promise(resolve=>setTimeout(resolve,0));
bridge.webSocketClose(socket);
assert.equal((await dropped).status,503);
console.log('HTTPS bridge authentication, socket ownership, responses and disconnect handling passed.');
const nativeResponse=globalThis.Response;
globalThis.Response=class {
  constructor(body,options){return options?.status===101?{status:101}:new nativeResponse(body,options);}
  static json(...args){return nativeResponse.json(...args);}
};
let accepted=false,attachment;
const server={serializeAttachment:value=>{assert.equal(accepted,true,'Accept the socket before persisting its attachment');attachment=value;}};
globalThis.WebSocketPair=class {constructor(){this[0]={};this[1]=server;}};
state.getWebSockets=()=>[];
state.acceptWebSocket=socket=>{assert.equal(socket,server);accepted=true;};
assert.equal((await bridge.fetch(new Request('https://internal/connect',{headers:{Authorization:'Bearer private-test',Upgrade:'websocket'}}))).status,101);
assert.ok(attachment.connectionId);
globalThis.Response=nativeResponse;
console.log('Connector attachment is persisted after accepting the socket.');
