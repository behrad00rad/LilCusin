import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
class El{
 constructor(tag,text,classes=''){Object.assign(this,{tag,textContent:text,children:[],dataset:{},attributes:{},className:classes});this.classList={add:key=>{this[key]=true;},toggle:(key,on)=>{this[key]=on;},contains:key=>!!this[key]};}
 append(...items){for(const el of items){el.parent=this;this.children.push(el);}}
 insertBefore(el,before){el.parent=this;this.children.splice(this.children.indexOf(before),0,el);}
 after(el){el.parent=this.parent;this.parent.children.splice(this.parent.children.indexOf(this)+1,0,el);}
 replaceChildren(...items){this.children=[];this.append(...items);}
 setAttribute(k,v){this.attributes[k]=v;}
 get firstChild(){return this.children[0];}
}
const source=readFileSync(new URL('../music_bot/web/app.js',import.meta.url),'utf8'),social=readFileSync(new URL('../music_bot/web/social.js',import.meta.url),'utf8');
const node=(...args)=>new El(...args),content=node('div'),calls=[],notices=[];
let owner={revision:7,songs:[]},fail=false,received;
const ctx=vm.createContext({node,icon:()=>node('svg'),catalogue:{en:{}},t:(key,args={})=>key+(args.name?' '+args.name:''),preview:false,view:'for-you',generation:1,deckIndex:0,ratedFeedIds:new Set(),
 setArtwork(){},scheduleArtwork(){},setActionLabel:(b,label)=>b.textContent=label,cardDirty:()=>false,notice:x=>notices.push(x),
 action:(label,run,classes='secondary')=>Object.assign(node('button',label,classes),{onclick:run}),
 api:async(path,data)=>{calls.push({path,data});if(path==='taste-card')return owner;if(fail)throw Error('full');return {};},
 $:()=>content,deckItems:()=>content.children.filter(el=>el.className.includes('card')),installDeck(){},
 switchView:async()=>{ctx.view='swaps';ctx.lastResult=received;},lastResult:null});
vm.runInContext(source.slice(source.indexOf('function setRatingSelected('),source.indexOf('let owlTimer')),ctx);
vm.runInContext(source.slice(source.indexOf('function makeCard('),source.indexOf('let replacementQueue')),ctx);
const make=id=>{ctx.song={id,title:'Song',artist:'Artist'};return vm.runInContext("makeCard(song,'owner-grant')",ctx);};
const add=card=>card.children.find(el=>el.className==='song-actions').children.at(-1);
let button=add(make(1));await button.onclick({currentTarget:button});assert.equal(button.textContent,'card_saved_button');assert.ok(button.disabled&&button['saved-pop']);assert.equal(calls.at(-1).data.token,'owner-grant');assert.equal(add(make(1)).textContent,'card_saved_button');
vm.runInContext('syncCardSaved({songs:[]})',ctx);assert.equal(add(make(1)).textContent,'card_add','removal invalidates saved feedback');
fail=true;button=add(make(2));await button.onclick({currentTarget:button});assert.equal(button.textContent,'card_add');assert.equal(button.disabled,false,'failure must not claim Saved');
owner={revision:8,songs:[{id:3}]};calls.length=0;button=add(make(3));await button.onclick({currentTarget:button});assert.equal(button.textContent,'card_saved_button');assert.equal(calls.length,1,'already-saved songs do not write again');
vm.runInContext(social,ctx);const swaps=Array.from({length:4},(_,i)=>({token:'swap-'+i,role:'recipient',state:'sent',song:{id:i,title:'Song '+i,artist:'Artist'},partner:'Approved nickname',note:'Personal note'}));
ctx.api=async()=>({swaps:[...swaps,{...swaps[0],token:'outgoing',role:'sender'},{...swaps[0],token:'draft',state:'draft'}]});
const recommendation=node('article',undefined,'card');recommendation.songData={id:99,token:'owner-grant'};content.append(recommendation);
await vm.runInContext('socialStrip()',ctx);assert.equal(content.children.length,4);assert.equal(content.children[0],recommendation);assert.equal(content.children[1].dataset.swapToken,'swap-0');
for(const card of content.children.slice(1)){assert.equal(card.songData,undefined);assert.equal(card.dataset.trackId,undefined,'swap cards must not join recommendation feedback/grants');}
await vm.runInContext('socialStrip()',ctx);assert.equal(content.children.length,4,'refresh does not duplicate swaps');
let opened;ctx.renderSocialSwap=swap=>opened=swap;received={swaps:[]};await vm.runInContext("openFeedSwap('revoked')",ctx);assert.equal(opened,undefined,'missing/revoked swaps are not opened from cached data');
received={swaps:[swaps[0]]};await vm.runInContext("openFeedSwap('swap-0')",ctx);assert.equal(opened,swaps[0]);
ctx.view='for-you';content.replaceChildren(recommendation);ctx.ratedFeedIds.add(2);ctx.api=async()=>({swaps:[{...swaps[0],rated:true},{...swaps[1],loved:true},swaps[2],swaps[3]]});await vm.runInContext('socialStrip()',ctx);assert.equal(content.children.length,2);assert.equal(content.children[1].dataset.swapToken,'swap-3','rated, loved and just-rated songs stay off Home');
console.log('Saved success/failure/already-owned/removal states, bounded incoming swap feed, grant separation, deduplication and fresh access checks passed.');
