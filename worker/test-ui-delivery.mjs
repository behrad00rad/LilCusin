import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
class Element {
 children=[];dataset={};attributes={};hidden=false;isConnected=true;disabled=false;
 classList={toggle(){},contains(){return false;}};
 append(...items){this.children.push(...items);}
 insertBefore(item,before){this.children.splice(this.children.indexOf(before),0,item);}
 replaceChildren(...items){this.children=[...items];}
 setAttribute(key,value){this.attributes[key]=value;}
 querySelector(selector){return this.children.find(el=>selector==='.'+el.className)||null;}
}
const toast=new Element(),timers=new Map();let timerId=0;
const context=vm.createContext({window:{addEventListener(){},opened:null},navigator:{language:'en'},
 document:{hidden:false,addEventListener(){},createElement:()=>new Element(),createElementNS:()=>new Element(),getElementById:()=>toast,querySelector:selector=>selector.includes('data-track-id')?context.window.host||null:null},
 sessionStorage:{setItem(){},getItem(){return null;}},setTimeout:(fn,ms)=>{timers.set(++timerId,{fn,ms});return timerId;},clearTimeout:id=>timers.delete(id),URL,console,Date});
vm.runInContext(readFileSync(new URL('../music_bot/web/app.js',import.meta.url),'utf8').replace(/\nboot\(\);\s*$/,'\n'),context);
vm.runInContext(`
 catalogue={en:{get_song:'Get song',get_song_hint:'Audio in this bot',preview_only:'Preview only',flow_delivery_waiting:'Continue in Telegram',flow_delivery_done:'Sent to Telegram',flow_delivery_unavailable:'Could not check delivery',flow_delivery_button:'Open Telegram again'}};
 preview=false;tg={openTelegramLink:url=>window.opened=url};scheduleArtwork=()=>{};
 let responses=[{after:new Date().toISOString(),state:'waiting',request_id:null},{state:'done',request_id:'owned'}],calls=[];
 api=async(path,data)=>{calls.push({path,data});return responses.shift();};
 const card=makeCard({id:42,title:'Song',artist:'Artist',get_song_url:'https://t.me/FixtureBot?start=get_old_42'},'initial');
 window.host=card;card.songData.token='renewed';const button=card.querySelector('.song-actions').children[0];
`,context);
await vm.runInContext('button.onclick()',context);
assert.equal(vm.runInContext('window.opened',context),'https://t.me/FixtureBot?start=get_renewed_42');
assert.equal(vm.runInContext('calls[0].data.token',context),'renewed');
assert.equal(vm.runInContext('card.querySelector(".delivery-feedback").textContent',context),'Continue in Telegram');
const pending=timers.get(vm.runInContext('deliveryTimer',context));assert.equal(pending.ms,1200);
await pending.fn();
assert.equal(vm.runInContext('card.querySelector(".delivery-feedback").dataset.state',context),'done');
assert.equal(vm.runInContext('card.querySelector(".delivery-feedback").textContent',context),'Sent to Telegram');
vm.runInContext("api=async()=>{throw Error('offline');};window.opened=null;",context);
await vm.runInContext('button.onclick()',context);
assert.ok(vm.runInContext('window.opened',context));
assert.equal(vm.runInContext('card.querySelector(".delivery-feedback").textContent',context),'Could not check delivery');
vm.runInContext("preview=true;window.opened=null;",context);
await vm.runInContext('button.onclick()',context);
assert.equal(vm.runInContext('window.opened',context),null);assert.equal(toast.textContent,'Preview only');
console.log('Renewed grants, waiting/verified delivery feedback, offline fallback and preview safety passed.');
