import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock
from music_bot.miniapp_connector import answer

class ConnectorTests(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_other_hosts_paths_methods_and_large_bodies(self):
        session=MagicMock()
        socket=AsyncMock()
        base=dict(id='00000000-0000-0000-0000-000000000000',path='/api/profile',method='GET',auth='signed',body='')
        for change in [dict(path='https://other.example/'),dict(path='/api/profile?target=website'),
                       dict(path=[]),dict(method='DELETE'),dict(body='x'*16385)]:
            with self.subTest(change=list(change)):
                await answer(session,socket,{**base,**change},asyncio.Semaphore(1))
                self.assertEqual(socket.send_json.call_args.args[0]['status'],400)
        session.request.assert_not_called()

    async def test_forwards_only_to_the_fixed_bot_endpoint(self):
        response=MagicMock(status=200)
        response.content.read=AsyncMock(side_effect=[b'{"ok":',b'true}',b''])
        context=MagicMock()
        context.__aenter__=AsyncMock(return_value=response)
        context.__aexit__=AsyncMock(return_value=False)
        session=MagicMock()
        session.request.return_value=context
        socket=AsyncMock()
        await answer(session,socket,dict(id='00000000-0000-0000-0000-000000000000',
                    path='/api/profile',method='GET',auth='signed',body=''),asyncio.Semaphore(1))
        args,kwargs=session.request.call_args
        self.assertEqual(args,('GET','http://127.0.0.1:8091/api/profile'))
        self.assertFalse(kwargs['allow_redirects'])
        self.assertEqual(socket.send_json.call_args.args[0]['status'],200)
        self.assertEqual(socket.send_json.call_args.args[0]['body'],'{"ok":true}')
