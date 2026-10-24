import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
class Element{
 constructor(tag,text,classes=''){this.tag=tag;this.textContent=text??'';this.className=classes;this.children=[];this.attributes={};this.dataset={};}
 get firstChild(){return this.children[0];}
 append(...children){this.children.push(...children);}
 replaceChildren(...children){this.children=children;}
 setAttribute(key,value){this.attributes[key]=value;}
}
const content=new Element('div');
const node=(...args)=>new Element(...args),all=(el,predicate)=>[...(predicate(el)?[el]:[]),...el.children.filter(x=>x instanceof Element).flatMap(x=>all(x,predicate))];
const text=el=>el.textContent+el.children.map(x=>x instanceof Element?text(x):String(x)).join(' ');
const context=vm.createContext({console,Intl,Date,node,icon:name=>node('svg',name),setArtwork:(el,url)=>el.artwork=url,t:(key,args={})=>key+JSON.stringify(args),$:()=>content,window:{scrollTo(){}},action:(label,run,classes='secondary')=>Object.assign(node('button',label,classes),{onclick:run}),switchView(){}});
const source=readFileSync(new URL('../music_bot/web/app.js',import.meta.url),'utf8');
vm.runInContext(source.slice(source.indexOf('function cardProjection('),source.indexOf('async function cardMutation(')),context);
let projection=vm.runInContext("cardProjection({taste_id:'',nickname:'',bio:'',songs:[],current:null})",context);
assert.equal(all(projection,el=>el.className.includes('signature-slot')).length,5);assert.equal(all(projection,el=>el.className==='card-taste-id').length,0,'no developer preview ID');
projection=vm.runInContext("cardProjection({taste_id:'real-selected-id',nickname:'Nima / نیما',bio:'<script>plain text</script>',songs:[{title:'A very long title / آهنگ',artist:'Artist',artwork:'https://art.example/selected.jpg'}],current:{title:'Selected song',artist:'Artist',artwork:'https://art.example/selected.jpg'}})",context);
assert.ok(text(projection).includes('real-selected-id'));assert.ok(text(projection).includes('Nima / نیما'));assert.ok(text(projection).includes('<script>plain text</script>'),'bio remains text');assert.equal(all(projection,el=>el.artwork).length,2,'signature and current art preserved');assert.equal(all(projection,el=>el.className.includes('signature-empty')).length,4);
vm.runInContext(readFileSync(new URL('../music_bot/web/social.js',import.meta.url),'utf8'),context);
const make=(token,role,state='sent',extra={})=>({token,role,state,partner:'Approved name',song:{title:'Song '+token,artist:'Artist'},note:'A personal note',saved:false,loved:false,...extra});
context.result={swaps:[make('in','recipient'),make('draft','sender','draft'),make('reacted','recipient','sent',{loved:true}),make('out','sender')]};
vm.runInContext('renderSocialInbox(result)',context);
let filters=content.children[0];assert.deepEqual(filters.children.map(x=>x.textContent),['a1_pending{} · 2','a1_received{} · 2','a1_sent{} · 2']);assert.equal(all(content,el=>el.className.includes('exchange-card')).length,2);
filters.children[1].onclick();assert.ok(text(content).includes('Song reacted'));assert.ok(!text(content).includes('Song draft'));
content.children[0].children[2].onclick();assert.ok(text(content).includes('Song draft'));assert.ok(text(content).includes('a1_continue_draft'));
context.result={swaps:[]};vm.runInContext('renderSocialInbox(result)',context);assert.ok(text(content).includes('ux_swaps_empty'));
console.log('Five-slot identity projection, real selected artwork/current song, text safety, derived exchange counts/filters and draft actions passed.');
