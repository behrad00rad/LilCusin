import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock
from music_bot.miniapp_connector import answer, route_method

class ConnectorTests(unittest.IsolatedAsyncioTestCase):
    def test_guess_routes_only_forward_expected_query_and_method(self):
        friend = 'f' * 32
        self.assertEqual(route_method('/api/guess/start'), 'POST')
        self.assertEqual(route_method('/api/taste-sharing', 'POST'), 'POST')
        self.assertEqual(route_method('/api/guess/'+friend+'/answer'), 'POST')
        self.assertEqual(route_method('/api/guess/status?friend_id='+friend), 'GET')
        for path in ['/api/guess/status', '/api/guess/bad/answer',
                     '/api/guess/start?target=x', '/api/guess/status?friend_id='+friend+'&target=x',
                     '/api/guess/status?friend_id='+friend+'&friend_id='+friend,
                     'http://[', 'https://elsewhere/api/guess/status?friend_id='+friend]:
            self.assertIsNone(route_method(path))

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
