import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';
class El{
 constructor(tag,text,classes=''){Object.assign(this,{tag,textContent:text,className:classes,children:[],dataset:{},attributes:{}});}
 append(...els){for(const el of els){el.parent=this;this.children.push(el);}}
 remove(){if(this.parent)this.parent.children=this.parent.children.filter(el=>el!==this);}
 setAttribute(k,v){this.attributes[k]=v;}
 querySelector(){return {setAttribute(){}};}
}
const node=(...a)=>new El(...a),content=node('div'),owl=node('div'),speech=node('p');
const card=(song,token)=>Object.assign(node('article',undefined,'card'),{songData:{...song,token}});
const find=id=>content.children.find(el=>el.id===id),calls=[],notices=[];
const ctx=vm.createContext({node,view:'for-you',generation:1,deckLoading:false,deckAnimating:false,deckIndex:0,deckSeen:new Set(['song:1']),preview:false,owlState:'',t:key=>key,
 $:id=>id==='content'?content:id==='owl-button'?owl:id==='owl-speech'?speech:find(id),
 deckItems:()=>content.children.filter(el=>el.className==='card'),deckKey:el=>'song:'+el.songData.id,
 visibleIds:()=>content.children.filter(el=>el.songData).map(el=>el.songData.id),
 makeCard:card,installDeck:()=>{const active=ctx.deckItems()[ctx.deckIndex];if(active)ctx.deckSeen.add(ctx.deckKey(active));},
 rememberVisible(){},uiMotion:async()=>true,owlReact:state=>ctx.owlState=state,notice:text=>notices.push(text),
 api:async(path,data)=>{assert.ok(find('deck-loader'));assert.equal(ctx.owlState,'loading');calls.push({path,data});return {token:'renewed',tracks:[{id:1},{id:4},{id:5}]};}});
const source=readFileSync(new URL('../music_bot/web/app.js',import.meta.url),'utf8');
vm.runInContext(source.slice(source.indexOf('function setDeckBusy('),source.indexOf('function installProfilePanels(')),ctx);
content.append(card({id:1},'old'),card({id:2},'old'),card({id:3},'old'));
await vm.runInContext('refreshDeck(70)',ctx);assert.deepEqual(ctx.visibleIds(),[2,3]);assert.equal(calls.length,0,'pull refresh uses buffered unseen picks');
await vm.runInContext('refreshDeck()',ctx);assert.deepEqual(ctx.visibleIds(),[3]);assert.equal(calls.length,0);
await vm.runInContext('refreshDeck()',ctx);assert.deepEqual(ctx.visibleIds(),[4,5]);assert.equal(calls.length,1,'only an exhausted buffer fetches');assert.equal(calls[0].data.batch,true);assert.ok(calls[0].data.exclude.includes(1));
assert.equal(find('deck-loader'),undefined);assert.equal(ctx.owlState,'');assert.equal(content.attributes['aria-busy'],'false');
await vm.runInContext('loadDeck(1)',ctx);assert.equal(ctx.deckIndex,1);assert.equal(calls.length,1,'the rest of a batch is reused');
ctx.deckIndex=0;ctx.api=async()=>{throw Error('offline');};await vm.runInContext('refreshDeck()',ctx);assert.equal(ctx.deckItems()[0].songData.id,4,'failed refresh retains a usable card');assert.equal(find('deck-loader'),undefined);assert.equal(ctx.deckLoading,false);
console.log('Pull refresh reuses unseen cards, batches only at exhaustion, excludes seen picks, shows skeleton/owl loading, and recovers after failure.');
