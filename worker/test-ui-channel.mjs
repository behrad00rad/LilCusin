import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
class Element {
  children=[];dataset={};attributes={};className='';isConnected=true;style={};value='';
  constructor(tag){this.tag=tag;this.classList={contains:key=>this.className.split(' ').includes(key)};}
  append(...children){this.children.push(...children);for(const child of children)if(typeof child==='object')child.parent=this;}
  replaceChildren(...children){this.children=[];this.append(...children);}
  setAttribute(k,v){this.attributes[k]=v;} removeAttribute(k){delete this.attributes[k];}
  getBoundingClientRect(){return {top:0,height:180};}
  replaceWith(next){const i=this.parent.children.indexOf(this);this.parent.children[i]=next;next.parent=this.parent;this.isConnected=false;}
  remove(){this.parent.children=this.parent.children.filter(c=>c!==this);this.isConnected=false;}
  querySelectorAll(selector){if(selector.includes('data-track-id'))return this.children.filter(c=>c.songData&&!c.classList.contains('is-rated'));if(selector==='.end-card')return this.children.filter(c=>c.classList.contains('end-card'));return [];}
}
const elements=Object.fromEntries(['content','query','channel-pagination','status'].map(id=>[id,new Element('div')]));
const context=vm.createContext({window:{scrollY:0,addEventListener(){}},document:{documentElement:{style:{setProperty(){}}},addEventListener(){},getElementById:id=>elements[id],createElement:tag=>new Element(tag),querySelectorAll:()=>[]},navigator:{language:'en'},matchMedia:()=>({matches:true}),setTimeout,clearTimeout,URL,console});
vm.runInContext(readFileSync(new URL('../music_bot/web/app.js',import.meta.url),'utf8').replace(/\nboot\(\);\s*$/,'\n'),context);
context.card=(id)=>{const c=new Element('article');c.songData={id,token:'old'};c.dataset.trackId=String(id);return c;};
vm.runInContext(`preview=false;view='channel';similarSeed={id:1,cursor:0,cursors:[0]};lastResult={filter:'all',next_cursor:50,tracks:[]};catalogue={en:{}};makeCard=(song,token)=>{const c=card(song.id);c.songData={...song,token};return c;};remember=()=>{};`,context);
const read=expression=>JSON.parse(vm.runInContext('JSON.stringify('+expression+')',context));
const survivor=context.card(99),slot=new Element('article');elements.content.append(survivor,slot);context.slot=slot;
let calls=[];context.api=async(path,data)=>{calls.push({path,data});return {tracks:[{id:41,title:'next',artist:'artist'}],next_cursor:40,token:'renewed'};};
await vm.runInContext('fillReplacement(slot,generation,false)',context);
assert.equal(calls[0].data.cursor,50);assert.equal(read('lastResult.next_cursor'),40);
assert.equal(survivor.songData.token,'renewed');assert.deepEqual(read('lastResult.tracks.map(t=>t.id)'),[99,41]);
// Next must start after the replacement, not at the old page boundary.
assert.equal(elements['channel-pagination'].children.length,1);
context.api=async(path,data)=>{calls.push({path,data});return {tracks:[],filter:'all',next_cursor:null,token:'page'};};
vm.runInContext("switchView=async(next,result,options)=>{generation++;view=next;lastResult=result;similarSeed=options.seed;};",context);
await elements['channel-pagination'].children[0].onclick();
assert.equal(calls.at(-1).data.cursor,40);
// Two overlapping page requests must keep the latest request, even if the old response arrives last.
let pending=[];context.api=(path,data)=>new Promise(resolve=>pending.push({data,resolve}));
const first=vm.runInContext("openChannel({id:1},'all',100,[0,100],true)",context);
const second=vm.runInContext("openChannel({id:1},'all',50,[0,50],true)",context);
pending[1].resolve({tracks:[{id:2}],next_cursor:30});await second;
pending[0].resolve({tracks:[{id:1}],next_cursor:90});await first;
assert.equal(read('lastResult.tracks[0].id'),2);assert.equal(read('similarSeed.cursor'),50);
console.log('Channel replacement cursor, Next boundary, survivor grants, and overlapping page-request checks passed.');
