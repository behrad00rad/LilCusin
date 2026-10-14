import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

// Run the actual navigation handlers with a small DOM fixture. No network or
// Telegram identity is involved; each card keeps its displayed-song grant.
class Element {
  children=[]; attributes={}; hidden=false; value='';
  append(...children){this.children.push(...children);}
  replaceChildren(...children){this.children=children;}
  setAttribute(key,value){this.attributes[key]=value;}
  querySelectorAll(){return [];}
}
const elements=Object.fromEntries(['content','query','breadcrumbs'].map(id=>[id,new Element()]));
const cards=[{songData:{id:7,title:'Creep',artist:'Radiohead',token:'owned-grant'}}];
elements.content.querySelectorAll=()=>cards;
const context=vm.createContext({
  window:{scrollY:280},navigator:{language:'en'},
  document:{getElementById:id=>elements[id],createElement:()=>new Element(),createTextNode:text=>text,documentElement:{style:{setProperty(){}}}},
  fetch:()=>new Promise(()=>{}),setTimeout,clearTimeout,URL,console,
});
vm.runInContext(readFileSync(new URL('../music_bot/web/app.js',import.meta.url),'utf8'),context);
vm.runInContext(`
catalogue={en:{for_you:'For you',search:'Search',more_title:'More like “{song}”',more_short:'Similar songs',breadcrumb_label:'Page path'}};
view='search';lastResult={tracks:[]};$('query').value='Radiohead';
status=()=>{};
switchView=async(next,result,options)=>{view=next;lastResult=result;similarSeed=options.seed||null;window.lastNavigation={next,result,options};};
`,context);
const read=expression=>JSON.parse(vm.runInContext(`JSON.stringify(${expression})`,context));
const page=read('snapshot()');
assert.equal(page.query,'Radiohead');
assert.equal(page.scroll,280);
assert.equal(page.result.tracks[0].token,'owned-grant');
await vm.runInContext("openSimilar({songData:{id:7,title:'Creep',token:'owned-grant'},isConnected:true},{disabled:false})",context);
assert.equal(read('view'),'similar');
assert.equal(read("pageTitle(view,similarSeed)"),'More like “Creep”');
assert.equal(read('pageTrail[0].view'),'search');
assert.equal(read('pageTrail[0].result.tracks[0].token'),'owned-grant');
await vm.runInContext("openSimilar({songData:{id:8,title:'Intro',token:'next-grant'},isConnected:true},{disabled:false})",context);
assert.equal(read('pageTrail.length'),2);
await vm.runInContext('restorePage()',context);
assert.equal(read('view'),'similar');
assert.equal(read('similarSeed.title'),'Creep');
assert.equal(read('pageTrail.length'),1);
await vm.runInContext('restorePage(0)',context);
assert.equal(read('view'),'search');
assert.equal(read('window.lastNavigation.options.scroll'),280);
assert.equal(elements.query.value,'Radiohead');
assert.equal(read('lastResult.tracks[0].token'),'owned-grant');
assert.equal(read('pageTrail.length'),0);
vm.runInContext("writePageTitle($('breadcrumbs'),'similar',{title:'English song inside Persian'})",context);
assert.equal(elements.breadcrumbs.children[1].dir,'auto');
assert.equal(elements.breadcrumbs.children[1].textContent,'“English song inside Persian”');
// A result belonging to a page the user has left must not create a new page.
await vm.runInContext("openSimilar({songData:{id:8,title:'Intro'},isConnected:false},{disabled:false})",context);
assert.equal(read('pageTrail.length'),0);
console.log('Similar-song titles, nested back navigation, search/scroll/grant restoration and stale results passed.');
