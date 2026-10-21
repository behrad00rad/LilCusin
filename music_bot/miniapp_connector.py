"""Outbound HTTPS connector pinned to the Mini App API, with no public VPS port."""
import asyncio
import json
import os
from pathlib import Path
import re

import aiohttp

WORKER = 'https://lilcusin-ui.ghazanfaribehrad.workers.dev'
ROUTES = {'/api/delivery-request':'POST', '/api/delivery-status':'POST', '/api/social/unsave':'POST', '/api/social':'GET', '/api/social/compare':'POST', '/api/social/choices':'POST', '/api/social/draft':'POST', '/api/social/action':'POST', '/api/social/settings':'GET', '/api/social/settings/update':'POST', '/api/social/relationship':'POST', '/api/social/get-song':'POST', '/api/artwork':'POST', '/api/channels/songs':'POST', '/api/channels/review':'POST', '/api/preferences':'GET', '/api/preferences/update':'POST', '/api/profile':'GET', '/api/recommendations':'POST', '/api/search':'POST', '/api/rate':'POST',
          '/api/taste-card/image':'POST', '/api/comparison-invitations':'GET', '/api/comparison-invitations/create':'POST', '/api/comparison-invitations/decide':'POST', '/api/taste-card':'GET', '/api/taste-card/update':'POST', '/api/taste-card/share':'POST', '/api/taste-card/view':'POST',
          '/api/similar':'POST', '/api/channels':'GET', '/api/channels/connect':'POST',
          '/api/channels/disconnect':'POST', '/api/taste-setup':'GET', '/api/taste-setup/update':'POST'}


async def answer(session, socket, message, capacity):
    request_id=message.get('id')
    if not isinstance(request_id,str) or not re.fullmatch(r'[a-f0-9-]{36}',request_id):
        return
    path=message.get('path')
    auth=message.get('auth')
    body=message.get('body','')
    valid=(isinstance(path,str) and path in ROUTES and message.get('method')==ROUTES[path]
           and isinstance(auth,str) and len(auth)<=12000 and isinstance(body,str)
           and len(body.encode())<=16384)
    status=400
    content=json.dumps({'error':'Invalid request.'})
    if valid:
        try:
            async with capacity:
                async with session.request(ROUTES[path], 'http://127.0.0.1:8091'+path,
                        headers={'X-Telegram-Init-Data':auth,'Content-Type':'application/json'},
                        data=body if ROUTES[path]=='POST' else None,
                        allow_redirects=False, timeout=aiohttp.ClientTimeout(total=40)) as response:
                    status=response.status
                    chunks=[]
                    size=0
                    while True:
                        chunk=await response.content.read(8192)
                        if not chunk:
                            break
                        chunks.append(chunk)
                        size+=len(chunk)
                        if size>65536:
                            break
                    data=b''.join(chunks)
                    if len(data)>65536:
                        status=502;content=json.dumps({'error':'Music response was too large.'})
                    else:
                        content=data.decode('utf-8')
        except (aiohttp.ClientError,TimeoutError,UnicodeError):
            status=503;content=json.dumps({'error':'Music service unavailable. Please try again.'})
    await socket.send_json({'id':request_id,'status':status,'body':content})


async def connect():
    token_file = Path(os.environ.get('LILCUSIN_CONNECTOR_TOKEN_FILE') or
                      Path(__file__).resolve().parent.parent/'.cloudflared/token')
    token=token_file.read_text().strip()
    capacity=asyncio.Semaphore(4)
    async with aiohttp.ClientSession() as session:
        delay=1
        while True:
            jobs=set()
            try:
                async with session.ws_connect(WORKER.replace('https:','wss:')+'/connector',
                        headers={'Authorization':'Bearer '+token},heartbeat=25,max_msg_size=65536,
                        timeout=aiohttp.ClientWSTimeout(ws_receive=90)) as socket:
                    print('Lil Cusin private HTTPS connector connected.',flush=True)
                    delay=1
                    async for frame in socket:
                        if frame.type!=aiohttp.WSMsgType.TEXT or frame.data=='pong':
                            continue
                        try:
                            message=json.loads(frame.data)
                        except ValueError:
                            continue
                        if not isinstance(message,dict) or message.get('kind')!='request':
                            continue
                        if len(jobs)>=32:
                            await socket.send_json({'id':message.get('id'),'status':429,
                                                   'body':json.dumps({'error':'Please try again shortly.'})})
                            continue
                        task=asyncio.create_task(answer(session,socket,message,capacity))
                        jobs.add(task)
                        task.add_done_callback(jobs.discard)
            except (aiohttp.ClientError,TimeoutError,OSError):
                print('Mini App connector reconnecting; private details omitted.',flush=True)
            finally:
                for job in jobs:
                    job.cancel()
                await asyncio.gather(*jobs,return_exceptions=True)
            await asyncio.sleep(delay)
            delay=min(delay*2,30)


if __name__=='__main__':
    try:
        asyncio.run(connect())
    except KeyboardInterrupt:
        pass
