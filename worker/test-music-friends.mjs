import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';
const source=readFileSync(new URL('../music_bot/web/social.js',import.meta.url),'utf8'),calls=[];
const you={taste_id:'chosen-you',nickname:'You',songs:[{artist:'Artist',title:'Your pick'}]},other={taste_id:'chosen-friend',nickname:'Chosen friend',songs:[{artist:'Artist',title:'Their pick'}]};
const invitation={token:'friend-token',state:'consented',friendship:true,role:'sender',sender:you,recipient:other};
let displayed;
const ctx=vm.createContext({console,generation:1,view:'for-you',preview:false,window:{confirm:()=>true},notice(){},socialError:error=>{throw error;},renderSocialSwap:row=>displayed=row,
 switchView:async page=>{ctx.view=page;ctx.generation++;},
 api:async(path,data)=>{calls.push({path,data});if(path==='comparison-invitations')return {invitations:[invitation,invitation,{...invitation,friendship:false},{...invitation,state:'revoked'}]};if(path==='taste-card')return {songs:[{id:8,artist:'Artist',title:'Your pick'},{id:9,artist:'Unshared',title:'Private selection'}]};return {state:'draft',song:{id:data.track_id}};}});
vm.runInContext(source.slice(source.indexOf('let musicFriendContext='),source.indexOf('function socialError')),ctx);
let data=await vm.runInContext('musicFriendData()',ctx);assert.equal(data.friends.length,1,'only active, durable, deduplicated friendships');assert.equal(calls.length,2);
await vm.runInContext('musicFriendData()',ctx);assert.equal(calls.length,2,'one read per view');ctx.friend=data.friends[0];ctx.own=data.own;
assert.equal(vm.runInContext('musicSwapSuggestion(friend,own).id',ctx),8,'suggestions use approved shared artists and songs');
ctx.button={disabled:false};ctx.song={id:99,token:'owned-current-grant'};await vm.runInContext('draftMusicSuggestion(friend,song,button)',ctx);
assert.equal(calls.at(-1).path,'social/draft');assert.equal(calls.at(-1).data.source_token,'owned-current-grant');assert.equal(displayed.state,'draft');assert.ok(!calls.some(row=>row.path==='social/action'),'suggestions never send automatically');assert.equal(ctx.button.disabled,false);
console.log('Durable friend filtering/deduplication, bounded reads, explainable suggestions and owner-grant draft-only sending passed.');

assert.ok(source.includes("api('friend-invites',{})"),'friend sharing uses explicit dedicated invitation API');assert.ok(source.includes("'secondary danger-action','user-round'"),'Unfriend is a confirmed danger action in the menu');
assert.ok(source.includes("operation==='accept'"));
