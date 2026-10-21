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
 querySelector(selector){return this.children.find(el=>selector.startsWith('.')&&el.className?.split(' ').includes(selector.slice(1)))||null;}
}
const toast=new Element(),timers=new Map();let timerId=0;
const context=vm.createContext({window:{addEventListener(){},opened:null},navigator:{language:'en'},
 document:{hidden:false,addEventListener(){},createElement:()=>new Element(),createElementNS:()=>new Element(),getElementById:()=>toast,querySelector:selector=>selector.includes('data-track-id')?context.window.host||null:null},
 sessionStorage:{setItem(){},getItem(){return null;}},setTimeout:(fn,ms)=>{timers.set(++timerId,{fn,ms});return timerId;},clearTimeout:id=>timers.delete(id),URL,console,Date});
vm.runInContext(readFileSync(new URL('../music_bot/web/app.js',import.meta.url),'utf8').replace(/\nboot\(\);\s*$/,'\n'),context);
vm.runInContext(`
 catalogue={en:{get_song:'Get song',get_song_hint:'Audio in this bot',preview_only:'Preview only',flow_delivery_waiting:'Continue in Telegram',flow_delivery_pending:'Queued',flow_delivery_done:'Sent to Telegram',flow_delivery_unavailable:'Could not check delivery',flow_delivery_button:'Open Telegram again',home_requesting:'Requesting?',home_delivery_retry:'Try again',home_delivery_sent:'Sent to Telegram'}};
 fitDeck=()=>{throw Error('delivery must not resize the card');};preview=false;tg={openTelegramLink:url=>window.opened=url};scheduleArtwork=()=>{};
 let responses=[{after:new Date().toISOString(),state:'pending',request_id:'owned'},{state:'done',request_id:'owned'}],calls=[];
 api=async(path,data)=>{calls.push({path,data});return responses.shift();};
 const card=makeCard({id:42,title:'Song',artist:'Artist',get_song_url:'https://t.me/FixtureBot?start=get_old_42'},'initial');
 window.host=card;card.songData.token='renewed';const button=card.querySelector('.song-actions').children[0];
`,context);
await vm.runInContext('button.onclick()',context);
assert.equal(vm.runInContext('window.opened',context),null);assert.equal(vm.runInContext('calls[0].path',context),'delivery-request');
assert.equal(vm.runInContext('calls[0].data.token',context),'renewed');
assert.equal(vm.runInContext('card.querySelector(".delivery-feedback").textContent',context),'Queued');
assert.equal(vm.runInContext('button.children.at(-1).textContent',context),'Requesting?');assert.equal(vm.runInContext('button.disabled',context),true);assert.ok(vm.runInContext('card.querySelector(".delivery-feedback").className.includes("sr-only")',context));
const pending=timers.get(vm.runInContext('deliveryTimer',context));assert.equal(pending.ms,1200);
await pending.fn();
assert.equal(vm.runInContext('card.querySelector(".delivery-feedback").dataset.state',context),'done');
assert.equal(vm.runInContext('card.querySelector(".delivery-feedback").textContent',context),'Sent to Telegram');assert.equal(vm.runInContext('button.children.at(-1).textContent',context),'Sent to Telegram');assert.equal(vm.runInContext('button.disabled',context),false);
vm.runInContext("api=async()=>{throw Error('offline');};window.opened=null;",context);
await vm.runInContext('button.onclick()',context);
assert.equal(vm.runInContext('window.opened',context),null,'offline never falls back to /start');
assert.equal(vm.runInContext('card.querySelector(".delivery-feedback").textContent',context),'Could not check delivery');assert.equal(vm.runInContext('button.children.at(-1).textContent',context),'Try again');
vm.runInContext("preview=true;window.opened=null;",context);
await vm.runInContext('button.onclick()',context);
assert.equal(vm.runInContext('window.opened',context),null);assert.equal(toast.textContent,'Preview only');
console.log('Renewed grants, waiting/verified delivery feedback, offline safety and preview safety passed.');

const source=readFileSync(new URL('../music_bot/web/app.js',import.meta.url),'utf8'),css=readFileSync(new URL('../music_bot/web/style.css',import.meta.url),'utf8');
for(const width of [330,360,390])for(const available of [80,240,500]){assert.ok(vm.runInContext(`deckCoverSize(${width},${available})`,context)>=width*.75);}
assert.ok(source.includes('pill.append(previous,count,next)'));assert.ok(!source.includes('navigation.append(count,previous,next)'));assert.ok(!source.includes("hint.textContent=t('home_swipe')"));assert.ok(css.includes('grid-template-columns:44px minmax(48px,auto) 44px'));assert.ok(css.includes('-webkit-line-clamp:2'));
const locales=JSON.parse(readFileSync(new URL('../music_bot/web/locales.json',import.meta.url),'utf8'));for(const language of ['en','fa'])for(const [key,value]of Object.entries(locales[language]))if(key.startsWith('owl_')&&key!=='owl_label')assert.ok(Array.from(value).length<=28,`${language} ${key} too long`);
console.log('Button-only delivery states, no delivery resize call, 4:3 minimum artwork, counter controls and compact bilingual owl copy passed.');
