import asyncio
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from sqlalchemy import select, func
from aiohttp.test_utils import TestClient, TestServer
from .support import ServiceTestCase, dispatcher
from .test_miniapp import signed, TOKEN
from music_bot.models import User, Track, Rating, utc_now
from music_bot.chat_service import ChatService
from music_bot.submissions import Submitter
from music_bot.taste_cards import TasteCards, CardError
from music_bot.comparison_invitations import ComparisonInvitations, ComparisonInvitation
from music_bot.social import Social, SongSwap, SavedSong, SocialNotice, SocialReport, SocialBlock, SocialSettings
from music_bot.miniapp import create_app


class SocialLoopTests(ServiceTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.chat=ChatService(self.database,AsyncMock())
        self.social=Social(self.database);self.cards=TasteCards(self.database);self.invites=ComparisonInvitations(self.database)
        for number in [123,456,789]: await self.chat.ensure_user(Submitter(number))
        async with self.database.write() as session:
            tracks=[Track(artist='Shared Artist' if i in [0,1,3] else f'Artist {i}',title=f'Song {i}',metadata_source='fixture') for i in range(6)]
            session.add_all(tracks);await session.flush();self.ids=[row.id for row in tracks]
        owners={}
        for number,indices in [(123,[0,1,2]),(456,[0,3,4])]:
            owner=await self.cards.owner(number)
            owner=await self.cards.update(number,dict(action='edit',revision=owner['revision'],nickname=f'Chosen {number}',bio='Not compared'))
            grant=await self.chat.create_control(number,tracks=self.ids,kind='miniapp')
            for i in indices: owner=await self.cards.update(number,dict(action='add',revision=owner['revision'],track_id=self.ids[i],token=grant))
            owners[number]=owner
        owners[456]=await self.cards.sharing(456,'publish',owners[456]['revision'])
        self.owners=owners
        invite=await self.invites.create(123,owners[456]['share_token'],owners[123]['revision'],owners[456]['revision'])
        self.token=invite['token']
        await self.invites.decide(456,self.token,'accept')

    async def send(self,track=None,actor=123,reply_to=None):
        row=await self.social.draft(actor,self.token,track or self.ids[0],reply_to)
        return await self.social.act(actor,row['token'],'send')

    async def test_selected_only_explainable_comparison_and_roles(self):
        value=await self.social.compare(123,self.token)
        self.assertFalse(value['sparse']);self.assertEqual(len(value['shared_songs']),1)
        self.assertEqual(value['shared_artists'],['shared artist'])
        self.assertEqual(len(value['only_first']),2);self.assertNotIn('percentage',value)
        self.assertNotIn('id',value['you']['songs'][0]);self.assertNotIn('bio',value['you'])
        reverse=await self.social.compare(456,self.token)
        self.assertEqual(value['only_first'],reverse['only_second'])
        with self.assertRaisesRegex(CardError,'social_unavailable'): await self.social.compare(789,self.token)
        await self.invites.decide(123,self.token,'revoke')
        with self.assertRaises(CardError): await self.social.compare(123,self.token)

    async def test_sparse_is_selected_count_not_private_ratings(self):
        async with self.database.write() as session:
            invite=await session.get(ComparisonInvitation,self.token)
            invite.sender_snapshot={**invite.sender_snapshot,'songs':invite.sender_snapshot['songs'][:1]}
        value=await self.social.compare(123,self.token)
        self.assertTrue(value['sparse']);self.assertEqual(value['minimum'],3)
        self.assertNotIn('ratings',str(value))

    async def test_swap_artwork_and_time_keep_existing_consent_boundary(self):
        async with self.database.write() as session:
            track = await session.get(Track, self.ids[0])
            track.artwork_url = 'https://lastfm-img.freetls.fastly.net/i/u/300x300/test.png'
        swap = await self.send()
        received = await self.social.read(456, swap['token'])
        self.assertEqual(received['song']['artwork'], 'https://lastfm-img.freetls.fastly.net/i/u/300x300/test.png')
        self.assertIsNotNone(received['sent_at'])
        self.assertNotIn('photo', received)
        self.assertNotIn('bio', received)
        async with self.database.write() as session:
            track = await session.get(Track, self.ids[0])
            track.artwork_url = 'http://127.0.0.1/private'
        self.assertFalse((await self.social.read(456, swap['token']))['song']['artwork'])
        await self.invites.decide(123, self.token, 'revoke')
        with self.assertRaises(CardError):
            await self.social.read(456, swap['token'])

    async def test_duplicate_send_save_and_reciprocal_reply(self):
        draft=await self.social.draft(123,self.token,self.ids[1])
        self.assertEqual((await self.social.draft(123,self.token,self.ids[1]))['token'],draft['token'])
        self.assertEqual(await self.social.inbox(456),[])
        await self.social.act(123,draft['token'],'note','For your late-night walk')
        await asyncio.gather(self.social.act(123,draft['token'],'send'),self.social.act(123,draft['token'],'send'))
        self.assertEqual(len(await self.social.inbox(456)),1)
        await self.social.act(456,draft['token'],'save')
        await self.social.act(456,draft['token'],'save')
        self.assertTrue((await self.social.read(123,draft['token']))['saved'])
        async with self.database.sessions() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(SavedSong)),1)
            self.assertEqual(await session.scalar(select(func.count()).select_from(Rating)),0)
            self.assertEqual(await session.scalar(select(func.count()).select_from(SocialNotice)),2)
        reply=await self.send(self.ids[3],456,draft['token'])
        self.assertEqual(reply['reply_to'],draft['token'])
        await self.social.act(123,reply['token'],'love')
        async with self.database.sessions() as session:
            self.assertEqual(await session.scalar(select(Rating.value)),'love')

    async def test_owner_roles_and_forged_track_rejected(self):
        swap=await self.send()
        calls=[lambda:self.social.read(789,swap['token']),lambda:self.social.act(123,swap['token'],'save'),
               lambda:self.social.act(456,swap['token'],'send'),lambda:self.social.draft(123,self.token,self.ids[5]),
               lambda:self.social.draft(123,self.token,self.ids[1],swap['token'])]
        for operation in calls:
            with self.assertRaises(CardError): await operation()

    async def test_block_cancels_queued_notices_and_requires_new_consent(self):
        swap=await self.send()
        await self.social.settings(456,True)
        await self.social.relationship(456,self.token,'block')
        self.assertEqual(await self.social.inbox(123),[])
        with self.assertRaises(CardError): await self.social.act(123,swap['token'],'send')
        with self.assertRaises(CardError): await self.invites.create(123,self.owners[456]['share_token'],self.owners[123]['revision'],self.owners[456]['revision'])
        async with self.database.sessions() as session:
            self.assertEqual(await session.scalar(select(SocialNotice.state)),'cancelled')
        settings=await self.social.settings(456)
        with self.assertRaises(CardError): await self.social.relationship(123,settings['blocks'][0]['handle'],'unblock')
        await self.social.relationship(456,settings['blocks'][0]['handle'],'unblock')
        with self.assertRaises(CardError): await self.social.compare(123,self.token)

    async def test_card_revision_stops_sent_swap_and_queued_notice(self):
        swap=await self.send()
        owner=await self.cards.owner(123)
        await self.cards.update(123,dict(action='edit',revision=owner['revision'],nickname='Changed',bio=''))
        with self.assertRaises(CardError): await self.social.read(456,swap['token'])
        async with self.database.sessions() as session:
            self.assertEqual(await session.scalar(select(SocialNotice.state)),'cancelled')
            self.assertEqual(await session.scalar(select(SongSwap.state)),'cancelled')

    async def test_opt_in_and_restart_safe_notification_attempt(self):
        bot=SimpleNamespace(send_message=AsyncMock(side_effect=TimeoutError()))
        await self.social.settings(456,True)
        await self.send()
        await self.social.flush_notices(bot)
        await Social(self.database).flush_notices(bot)
        bot.send_message.assert_awaited_once()
        async with self.database.sessions() as session:
            self.assertEqual(await session.scalar(select(SocialNotice.state)),'uncertain')

    async def test_notification_hard_cap_and_off_switch(self):
        bot=SimpleNamespace(send_message=AsyncMock())
        await self.social.settings(456,True)
        for _ in range(4): await self.send()
        await self.social.flush_notices(bot)
        self.assertEqual(bot.send_message.await_count,3)
        await self.send()
        await self.social.settings(456,False)
        await self.social.flush_notices(bot)
        self.assertEqual(bot.send_message.await_count,3)

    async def test_default_off_and_manual_reminder_limits(self):
        bot=SimpleNamespace(send_message=AsyncMock())
        swap=await self.send()
        await self.social.flush_notices(bot);bot.send_message.assert_not_awaited()
        with self.assertRaisesRegex(CardError,'social_limit'): await self.social.act(123,swap['token'],'remind')
        async with self.database.write() as session:
            row=await session.get(SongSwap,swap['token']);row.sent_at=utc_now()-timedelta(hours=25)
        await self.social.act(123,swap['token'],'remind')
        with self.assertRaisesRegex(CardError,'social_limit'): await self.social.act(123,swap['token'],'remind')
        await self.social.act(456,swap['token'],'love')
        with self.assertRaisesRegex(CardError,'social_limit'): await self.social.act(123,swap['token'],'remind')

    async def test_report_dedupe_admin_auth_and_suspension(self):
        draft=await self.social.draft(123,self.token,self.ids[0])
        await self.social.act(123,draft['token'],'note','Reported note')
        await self.social.act(123,draft['token'],'send')
        for _ in range(2): await self.social.relationship(456,self.token,'report','harassment',draft['token'])
        with self.assertRaises(CardError): await self.social.moderate(789,{123})
        reports=(await self.social.moderate(789,{789}))['reports']
        self.assertEqual(len(reports),1);self.assertEqual(reports[0]['note'],'Reported note')
        await self.social.moderate(789,{789},reports[0]['token'],'suspend')
        self.assertEqual(await self.social.inbox(456),[])
        with self.assertRaises(CardError): await self.social.compare(123,self.token)

    async def test_cancel_delete_and_private_save_removal_after_expiry(self):
        swap=await self.send()
        await self.social.act(456,swap['token'],'save')
        await self.social.act(456,swap['token'],'delete')
        with self.assertRaises(CardError): await self.social.read(123,swap['token'])
        await self.social.remove_save(456,self.ids[0])
        async with self.database.sessions() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(SavedSong)),0)
        draft=await self.social.draft(123,self.token,self.ids[2])
        await self.chat.cancel_controls(123)
        with self.assertRaises(CardError): await self.social.read(123,draft['token'])

    async def test_account_deletion_removes_social_data(self):
        swap=await self.send()
        await self.social.act(456,swap['token'],'save')
        await self.social.relationship(456,self.token,'report','spam',swap['token'])
        await self.chat.forget(456)
        async with self.database.sessions() as session:
            for model in [SongSwap,SavedSong,SocialReport,SocialNotice]:
                self.assertEqual(await session.scalar(select(func.count()).select_from(model)),0)

    async def test_signed_api_actor_and_swap_audio_link(self):
        client=TestClient(TestServer(create_app(TOKEN,self.chat,self.workflow,bot_username='FixtureBot')))
        await client.start_server();headers={'X-Telegram-Init-Data':signed(123)}
        try:
            self.assertEqual((await client.get('/api/social')).status,401)
            swap=await self.send()
            foreign={'X-Telegram-Init-Data':signed(789)}
            self.assertEqual((await client.post('/api/social/get-song',json={'token':swap['token']},headers=foreign)).status,404)
            response=await client.post('/api/social/get-song',json={'token':swap['token']},headers=headers)
            self.assertTrue((await response.json())['url'].endswith('swap_'+swap['token']))
            self.assertEqual((await client.post('/api/social/draft',json={'invitation':self.token,'track_id':self.ids[0],'user_id':456},headers=headers)).status,400)
            self.assertEqual((await client.get('/social.js')).status,200)
            self.assertEqual((await client.get('/api/social',headers=headers)).status,200)
        finally: await client.close()

    async def test_chat_note_send_save_and_audio_deep_link(self):
        from aiogram import Bot
        from aiogram.types import Update
        bot=Bot(TOKEN);delivery=SimpleNamespace(begin=AsyncMock())
        async def click(actor,data):
            update=Update.model_validate(dict(update_id=1,callback_query=dict(id='fixture',chat_instance='fixture',
                data=data,**{'from':dict(id=actor,is_bot=False,first_name='Fixture')},
                message=dict(message_id=70,date=1700000000,chat=dict(id=actor,type='private'),text='fixture'))))
            await dispatcher.feed_update(bot,update,chat_service=self.chat,get_song=delivery)
        async def message(actor,text,reply=None):
            data=dict(message_id=71,date=1700000000,chat=dict(id=actor,type='private'),text=text,**{'from':dict(id=actor,is_bot=False,first_name='Fixture')})
            if reply: data['reply_to_message']=dict(message_id=reply,date=1700000000,chat=dict(id=actor,type='private'),text='prompt')
            await dispatcher.feed_update(bot,Update.model_validate(dict(update_id=2,message=data)),chat_service=self.chat,get_song=delivery,workflow=self.workflow,submissions=self.submissions,enrichment=AsyncMock())
        try:
            with patch('aiogram.types.Message.answer',new_callable=AsyncMock,return_value=SimpleNamespace(message_id=70)),patch('aiogram.types.CallbackQuery.answer',new_callable=AsyncMock):
                await click(123,'sc:pick:'+self.token+':'+str(self.ids[1]))
                swap=(await self.social.inbox(123))[0]
                await click(123,'ss:note:'+swap['token'])
                await message(123,'Chosen note',70)
                self.assertEqual((await self.social.read(123,swap['token']))['note'],'Chosen note')
                await click(123,'ss:send:'+swap['token'])
                await click(456,'ss:save:'+swap['token'])
                self.assertTrue((await self.social.read(123,swap['token']))['saved'])
                await message(456,'/start swap_'+swap['token'])
                delivery.begin.assert_awaited_once()
                await message(789,'/start swap_'+swap['token'])
                delivery.begin.assert_awaited_once()
        finally: await bot.session.close()

    async def test_additive_initialization_and_expiry(self):
        swap=await self.send()
        await self.database.initialize()
        self.assertEqual((await self.social.read(456,swap['token']))['song']['id'],self.ids[0])
        async with self.database.write() as session:
            row=await session.get(SongSwap,swap['token']);row.expires_at=utc_now()-timedelta(seconds=1);row.note='Expired note'
        self.assertEqual(await self.social.inbox(456),[])
        async with self.database.sessions() as session:
            self.assertEqual((await session.get(SongSwap,swap['token'])).note,'')
        bot=SimpleNamespace(send_message=AsyncMock())
        await self.social.flush_notices(bot);bot.send_message.assert_not_awaited()

    async def test_unsave_updates_feedback_and_block_labels_do_not_follow_private_edits(self):
        first=await self.send();second=await self.send()
        await self.social.act(456,first['token'],'save')
        await self.social.act(456,second['token'],'save')
        await self.social.act(456,first['token'],'unsave')
        self.assertFalse((await self.social.read(123,second['token']))['saved'])
        await self.social.relationship(456,self.token,'block')
        owner=await self.cards.owner(123)
        await self.cards.update(123,dict(action='edit',revision=owner['revision'],nickname='New private nickname',bio=''))
        self.assertEqual((await self.social.settings(456))['blocks'][0]['nickname'],'Chosen 123')

    async def test_settings_menu_exposes_social_controls(self):
        from aiogram.types import Message
        from music_bot import chat_handlers
        message=Message.model_validate(dict(message_id=1,date=1700000000,chat=dict(id=123,type='private'),text='/settings',
            **{'from':dict(id=123,is_bot=False,first_name='Fixture')}))
        with patch('music_bot.chat_handlers.language_picker',new_callable=AsyncMock),patch('aiogram.types.Message.answer',new_callable=AsyncMock) as answer:
            await chat_handlers.command(message,self.chat)
            self.assertEqual(answer.call_args.kwargs['reply_markup'].inline_keyboard[0][0].callback_data,'sc:settings')

    async def test_opted_in_delivery_is_a_song_card_and_save_feedback_names_partner(self):
        bot=SimpleNamespace(send_message=AsyncMock())
        await self.social.settings(456,True);await self.social.settings(123,True)
        swap=await self.send()
        await self.social.flush_notices(bot)
        call=bot.send_message.await_args_list[0]
        self.assertEqual(call.args[0],456)
        self.assertIn('song 0',call.args[1])
        buttons=call.kwargs['reply_markup'].inline_keyboard
        self.assertEqual([item.callback_data.split(':')[1] for item in buttons[0]],['save','love','reply'])
        self.assertTrue(all(len(item.callback_data.encode())<=64 for row in buttons for item in row))
        await self.social.act(456,swap['token'],'save')
        await self.social.flush_notices(bot)
        self.assertIn('Chosen 456 saved your pick',bot.send_message.await_args.args[1])
