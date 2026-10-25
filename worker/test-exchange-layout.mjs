import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const source=readFileSync(new URL('../music_bot/web/app.js',import.meta.url),'utf8'),css=readFileSync(new URL('../music_bot/web/style.css',import.meta.url),'utf8');
const node=(tag,text)=>({tag,text}),ctx=vm.createContext({node,icon:name=>({tag:'svg',name}),actionIcon:()=>null});
vm.runInContext(source.slice(source.indexOf('function setActionLabel('),source.indexOf('function externalIcon(')),ctx);
for(const label of ['More options','Close']){ctx.button={dataset:{},children:[],classList:{contains:key=>key==='icon-button'},replaceChildren(){this.children=[];},append(el){this.children.push(el);},setAttribute(key,value){this[key]=value;}};ctx.label=label;vm.runInContext('setActionLabel(button,label,"x")',ctx);assert.equal(ctx.button['aria-label'],label);assert.equal(ctx.button.children.length,1);assert.equal(ctx.button.children[0].tag,'svg');}
assert.ok(css.includes('.friend-thread,.friend-thread>.thread-entry{box-sizing:border-box;width:100%;max-width:100%;min-width:0;margin-inline:0}'));
assert.ok(css.includes('#content>.friend-thread-send'));assert.ok(css.includes('inset-inline:22px;width:auto'));assert.ok(css.includes('.icon-button>span{display:none}'));
console.log('Icon-only accessible controls and thread/page-gutter constraints passed.');
