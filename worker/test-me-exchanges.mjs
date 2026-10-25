import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';
class El{
 constructor(tag,text='',cls=''){Object.assign(this,{tagName:tag.toUpperCase(),textContent:text,children:[],className:cls,dataset:{},attributes:{},isConnected:true});this.classList={add:(...keys)=>{this.className+=' '+keys.join(' ');}};}
 append(...items){for(const el of items){if(el.parent)el.parent.children=el.parent.children.filter(x=>x!==el);el.parent=this;this.children.push(el);}}
 replaceChildren(...items){for(const el of this.children){el.parent=null;el.isConnected=false;}this.children=[];this.append(...items);}
 setAttribute(k,v){this.attributes[k]=v;}removeAttribute(k){delete this.attributes[k];}
 cloneNode(){return new El(this.tagName,this.textContent,this.className);}
 get firstChild(){return this.children[0];}scrollIntoView(){}focus(){}
}
const node=(...args)=>new El(...args),content=node('main'),language=node('select'),walk=el=>[el,...el.children.flatMap(walk)],buttons=el=>walk(el).filter(x=>x.tagName==='BUTTON');
const action=(label,run,cls='secondary')=>Object.assign(node('button',label,cls),{onclick:run});
const disclosure=(title,...children)=>{const el=node('details');el.append(node('summary',title),...children);return el;};
let data={swaps:[],saves:[],saved_count:0},calls=[],confirmations=[],sheetContent,sheet,failed=false;
const ctx=vm.createContext({document:{addEventListener(){},body:{classList:{add(){},remove(){}}},documentElement:{lang:'en'}},console,Intl,Date,node,action,disclosure,t:key=>key,icon:()=>node('svg'),view:'card',generation:1,preview:false,profilePanel:'preview',locale:'en',
 $:id=>id==='content'?content:id==='language'?language:walk(content).find(el=>el.id===id),
 owlRest(){},owlReact(){},owlIllustration:pose=>node('svg',pose),motionAllowed:()=>false,notice(){},status(){},window:{scrollTo(){},confirm:()=>true},
 switchView:async page=>ctx.view=page,setArtwork(){},confirmCard:(_card,operation)=>confirmations.push(operation),
 openSettingsSheet:()=>{sheetContent=node('div');sheet={isConnected:true,close(){this.isConnected=false;}};return {sheet,content:sheetContent};},
 api:async(path,payload)=>{calls.push({path,payload});if(failed)throw Error('offline');if(path==='social/settings')return {notifications:false,blocks:[]};if(path==='social/unsave'){data={...data,saves:[],saved_count:0};return {removed:true};}return data;}});
const app=readFileSync(new URL('../music_bot/web/app.js',import.meta.url),'utf8');
// Exercise the real single-page composition, with no tabs or hidden sections.
vm.runInContext(app.slice(app.indexOf('function installProfilePanels('),app.indexOf('let sheetCount=')),ctx);
ctx.parts=Object.fromEntries(['identity','previewBox','edit','songs','sharing'].map(key=>[key,node('section',key)]));ctx.parts.card={revision:2,shared:true};
vm.runInContext('installProfilePanels(parts)',ctx);
assert.equal(content.children.length,7);assert.ok(!walk(content).some(el=>el.className==='profile-tabs'));assert.ok(walk(content).find(el=>el.id==='profile-saved'));
vm.runInContext(readFileSync(new URL('../music_bot/web/social.js',import.meta.url),'utf8'),ctx);
await vm.runInContext('socialProfileStats()',ctx);let saved=ctx.$('profile-saved');assert.ok(walk(saved).some(el=>el.tagName==='SVG'&&el.textContent==='sleepy'));assert.ok(buttons(saved).some(el=>el.textContent==='me_find_picks'));
data={swaps:[],saves:[{id:7,artist:'Artist',title:'Real saved song'}],saved_count:1};await vm.runInContext('socialProfileStats()',ctx);assert.ok(walk(saved).some(el=>el.textContent.includes('Real saved song')));
await buttons(saved).find(el=>el.textContent==='social_unsave').onclick({currentTarget:node('button')});assert.equal(calls.find(el=>el.path==='social/unsave').payload.track_id,7);assert.ok(buttons(saved).some(el=>el.textContent==='me_find_picks'));
await vm.runInContext('socialSettings({revision:2,shared:true})',ctx);assert.ok(walk(sheetContent).some(el=>el.tagName==='SELECT'));assert.ok(walk(sheetContent).some(el=>el.textContent==='me_no_blocks'));
for(const [label,operation] of [['card_hide','hide'],['card_rotate','rotate'],['card_delete','delete']]){await vm.runInContext('socialSettings({revision:2,shared:true})',ctx);buttons(sheetContent).find(el=>el.textContent===label).onclick();assert.equal(confirmations.at(-1),operation);}
assert.ok(!calls.some(el=>el.path==='taste-card/share'),'destructive settings actions require the existing confirmation flow');
assert.ok(app.includes("if(cardDirty(card))"));assert.ok(!app.includes("expires_at.slice(0,10)"),'no raw expiry date in Me');
console.log('Single-page Me, real Saved/unsave and sleepy empty state, settings language/blocks and destructive confirmation routing passed.');

ctx.view='swaps';const swap={token:'fixture-swap',invitation:'fixture-invite',state:'sent',role:'recipient',partner:'Chosen nickname',song:{id:7,title:'Song',artist:'Artist'},saved:false,loved:false};ctx.lastResult={swaps:[swap]};
ctx.api=async(path,payload)=>{calls.push({path,payload});return {...swap,saved:payload.action==='save',loved:payload.action==='love'};};
vm.runInContext('renderSocialInbox(lastResult)',ctx);assert.ok(!buttons(content).some(el=>el.textContent==='me_settings'));assert.ok(!walk(content).some(el=>el.textContent==='friend_history'));const card=vm.runInContext('exchangeCard(lastResult.swaps[0])',ctx);const save=buttons(card).find(el=>el.textContent==='social_save');await save.onclick({currentTarget:save});assert.ok(ctx.lastResult.swaps[0].saved);assert.ok(ctx.lastResult.swaps[0].saved);
ctx.invitations=[{state:'revoked',token:'old',role:'sender'}];vm.runInContext('renderSocialInvitations(invitations)',ctx);assert.ok(walk(content).some(el=>el.textContent==='ux_connections_empty'));assert.ok(walk(content).some(el=>el.textContent==='friend_add_title'));
console.log('Inbox Save updates real state; inactive invitations keep the normal empty state and a recovery action.');

ctx.view='swaps';let requestWrites=0;ctx.api=async(path,payload)=>{requestWrites++;assert.equal(path,'comparison-invitations/decide');assert.equal(payload.token,'pending-fixture');assert.equal(payload.action,'accept');return {state:'consented'};};
ctx.pending=[{token:'pending-fixture',state:'pending',role:'recipient',sender:{nickname:'Approved name',songs:[{title:'Must not be listed'}]},recipient:{nickname:'Me'}}];const requestHost=node('section');ctx.requestHost=requestHost;
vm.runInContext('renderFriendRequests(requestHost,pending)',ctx);assert.equal(requestWrites,0,'rendering never accepts a request');assert.ok(!walk(requestHost).some(el=>el.textContent==='Must not be listed'));
const accept=buttons(requestHost).find(el=>el.textContent==='friend_add_name');await accept.onclick({currentTarget:accept});assert.equal(requestWrites,1);
ctx.URL=URL;ctx.cardDirty=()=>false;ctx.tg={openTelegramLink:url=>ctx.shared=url};let inviteCalls=0;ctx.api=async(path)=>{inviteCalls++;assert.equal(path,'friend-invites');return {url:'https://t.me/FixtureBot?start=friend_'+'a'.repeat(32),token:'a'.repeat(32),nickname:'Chosen name'};};ctx.shared=null;
await vm.runInContext('inviteMusicFriend()',ctx);assert.equal(inviteCalls,0,'opening the sheet does not mint or share an invite');assert.equal(ctx.shared,null);
const shareInvite=buttons(sheetContent).find(el=>el.textContent==='friend_share_invite');await shareInvite.onclick({currentTarget:shareInvite});assert.equal(inviteCalls,1);
assert.ok(new URL(new URL(ctx.shared).searchParams.get('url')).searchParams.get('start').startsWith('friend_'),'friend link is separate from card/comparison links');
console.log('Compact request privacy, explicit acceptance and intentional direct invitation sharing passed.');

ctx.friend={token:'friend-fixture',other:{nickname:'Approved friend'}};let removals=0;
ctx.api=async(path,payload)=>{assert.equal(path,'comparison-invitations/decide');assert.equal(payload.action,'unfriend');removals++;return {};};
vm.runInContext('musicFriendMenu(friend)',ctx);assert.equal(removals,0);assert.ok(buttons(sheetContent).some(el=>el.textContent==='social_compare'));assert.ok(buttons(sheetContent).some(el=>el.textContent==='social_block'));
buttons(sheetContent).find(el=>el.textContent==='friends_unfriend').onclick();assert.equal(removals,0,'menu selection only opens confirmation');assert.ok(walk(sheetContent).some(el=>el.textContent==='friends_remove_explained'));
const removeFriend=buttons(sheetContent).find(el=>el.textContent==='friends_unfriend');await removeFriend.onclick({currentTarget:removeFriend});assert.equal(removals,1);
ctx.activityHost=node('section');ctx.updates={activity:[{event:'accepted',name:'Approved friend',invitation:'friend-fixture'}]};vm.runInContext('renderSocialActivity(activityHost,updates)',ctx);assert.ok(walk(ctx.activityHost).some(el=>el.textContent==='activity_accepted'));assert.ok(buttons(ctx.activityHost).some(el=>el.textContent==='social_open'));
console.log('Friend sheet separates Block/Unfriend; removal requires explicit confirmation; real activity renders with an action.');

ctx.$=id=>id==='content'?content:['view-intro','view-title'].includes(id)?node('p'):walk(content).find(el=>el.id===id);ctx.friend={token:'thread-fixture',other:{nickname:'Approved friend'}};
ctx.api=async(path,payload)=>{calls.push({path,payload});assert.equal(path,'social/thread');return {swaps:[swap,{...swap,token:'sent-fixture',role:'sender'}],before:null};};
await vm.runInContext('openFriendThread(friend)',ctx);assert.ok(walk(content).some(el=>el.className==='friend-thread'));assert.equal(walk(content).filter(el=>el.className.includes('thread-entry')).length,2);assert.ok(buttons(content).some(el=>el.className.includes('friend-thread-send')));
const row=vm.runInContext('friendThreadRow(friend,null)',ctx);assert.ok(!buttons(row).some(el=>el.textContent==='friends_unfriend'),'Unfriend lives in the menu');assert.ok(buttons(row).some(el=>el.className.includes('friend-open')));
console.log('Participant thread renders both directions, pinned Send, name-first rows and menu-only Unfriend.');

let reportCalls=0;ctx.api=async(path,payload)=>{reportCalls++;assert.equal(path,'social/relationship');assert.equal(payload.reason,'other');assert.equal(payload.details,'Optional context');return {state:'reported'};};
vm.runInContext('socialReport("thread-fixture")',ctx);assert.equal(reportCalls,0,'opening Report never submits');const reason=walk(sheetContent).find(el=>el.id==='report-reason'),note=walk(sheetContent).find(el=>el.id==='report-note'),submit=buttons(sheetContent).find(el=>el.textContent==='report_submit');assert.ok(submit.disabled);reason.value='other';reason.onchange();note.value='Optional context';assert.equal(submit.disabled,false);await submit.onclick({currentTarget:submit});assert.equal(reportCalls,1);assert.equal(note.maxLength,240);
console.log('Report waits for reason and explicit submission, with optional bounded context.');
