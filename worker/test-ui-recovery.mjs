import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';

const source=readFileSync(new URL('../music_bot/web/app.js',import.meta.url),'utf8').replace(/\nboot\(\);\s*$/,'\n');
class Element {
  children=[];hidden=true;disabled=false;value='';textContent='';open=false;
  classList={add(){},remove(){}};
  append(...children){this.children.push(...children);}
  replaceChildren(...children){this.children=children;}
  cloneNode(){return new Element();}
  setAttribute(){}
  querySelector(){return new Element();}
  querySelectorAll(){return [];}
  // Some embedded browsers expose these methods but reject their use.
  showPopover(){throw new Error('Not supported in this WebView');}
  hidePopover(){throw new Error('Not open');}
}
function fixture(){
  const elements=new Map(),events={};const get=id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id);};
  const context=vm.createContext({
    window:{Telegram:{WebApp:{initData:'unit-test-fixture',initDataUnsafe:{user:{language_code:'en'}}}},scrollY:15,scrollTo(){throw new Error('Unavailable');},addEventListener:(name,fn)=>events[name]=fn},
    document:{getElementById:get,createElement:()=>new Element(),createTextNode:text=>text,documentElement:{style:{setProperty(){}},classList:{add(){},remove(){}}},querySelectorAll:()=>[],addEventListener:(name,fn)=>events[name]=fn},
    navigator:{language:'en'},location:{hash:'',search:'',reload(){}},
    localStorage:{getItem(){throw new Error('Storage disabled');},setItem(){throw new Error('Storage disabled');}},
    matchMedia:()=>({matches:false}),requestAnimationFrame(){throw new Error('Frames are paused');},
    setTimeout:(fn,ms)=>setTimeout(fn,ms<=200?0:ms),clearTimeout,AbortController,fetch:async()=>{throw new Error('Offline');},console,
  });
  vm.runInContext(source,context);
  vm.runInContext(`catalogue={en:{error:'Try again',language_save_error:'Not saved',startup_error:'Could not connect',retry:'Retry',loading:'Loading'}};labels=()=>{};`,context);
  return {context,get,events};
}
// The animation must finish even if saving never responds, popover is rejected,
// frames never arrive, storage is disabled, or scrolling is unsupported.
{
  const {context,get}=fixture();
  vm.runInContext('api=()=>new Promise(()=>{});',context);
  await vm.runInContext("chooseLanguage({currentTarget:{value:'fa'}})",context);
  assert.equal(get('language-curtain').hidden,true);
  assert.equal(get('language').disabled,false);
  assert.equal(vm.runInContext('languageChanging',context),false);
  assert.equal(vm.runInContext('locale',context),'fa');
  await vm.runInContext("chooseLanguage({currentTarget:{value:'en'}})",context);
  assert.equal(get('language-curtain').hidden,true);
  assert.equal(get('guide-language').disabled,false);
  assert.equal(vm.runInContext("storageRead('test')",context),null);
  vm.runInContext("storageWrite('test','value')",context);
}
// A rendering exception also releases the curtain and both controls.
{
  const {context,get}=fixture();
  vm.runInContext("lastResult={};render=()=>{throw new Error('Rendering failed');};",context);
  await vm.runInContext("chooseLanguage({currentTarget:{value:'fa'}})",context);
  assert.equal(get('language-curtain').hidden,true);
  assert.equal(get('language').disabled,false);
}
// Page lifecycle events clear an interrupted transition without waiting for RAF.
{
  const {context,get,events}=fixture();
  get('language-curtain').hidden=false;get('language').disabled=true;
  events.pagehide();
  assert.equal(get('language-curtain').hidden,true);
  assert.equal(get('language').disabled,false);
}
// Authenticated startup failure must show a visible retry, not a blank shell.
{
  const {context,get}=fixture();
  vm.runInContext("fetch=async()=>({ok:true,json:async()=>catalogue});api=async()=>{throw new Error('Timeout');};",context);
  await vm.runInContext('boot()',context);
  assert.equal(get('status').textContent,'Could not connect');
  assert.equal(get('content').children[0].textContent,'Retry');
  assert.equal(get('language').disabled,false);
  assert.equal(get('language-curtain').hidden,true);
}
// A missing Telegram SDK inside a Telegram launch must not become a demo session.
{
  const {context}=fixture();
  vm.runInContext("window.Telegram=undefined;location.hash='#tgWebAppData=unit-test';",context);
  await assert.rejects(vm.runInContext('initializeTelegram()',context));
}
console.log('Recovery passed: paused frames, rejected popover, hung save, rendering failure, page hide, disabled storage, authenticated startup failure and missing Telegram SDK.');
