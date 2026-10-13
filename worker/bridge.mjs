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
