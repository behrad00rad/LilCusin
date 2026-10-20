import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const source=readFileSync(new URL('../music_bot/web/app.js',import.meta.url),'utf8');
class Element{
 constructor(tag,text,classes=''){Object.assign(this,{tag,textContent:text,children:[],attributes:{},dataset:{},className:classes});this.classList={toggle:(key,on)=>{this[key]=on;},contains:key=>!!this[key]};}
 append(...items){this.children.push(...items);}
 insertBefore(item,before){this.children.splice(this.children.indexOf(before),0,item);}
 setAttribute(key,value){this.attributes[key]=value;}
}
const node=(...args)=>new Element(...args),all=(el,tag)=>[...(el.tag===tag?[el]:[]),...el.children.filter(x=>x instanceof Element).flatMap(x=>all(x,tag))];
const context=vm.createContext({node,icon:()=>node('svg'),catalogue:{en:{}},t:key=>key,preview:false,scheduleArtwork(){},action:(label,run,classes)=>Object.assign(node('button',label,classes),{onclick:run}),setArtwork(){}});
vm.runInContext(source.slice(source.indexOf('function setRatingSelected('),source.indexOf('let owlTimer')),context);
vm.runInContext(source.slice(source.indexOf('function makeCard('),source.indexOf('let replacementQueue')),context);
for(const rating of [undefined,'love','like','neutral','dislike','invalid']){
 context.song={id:1,title:'Title',artist:'Artist',rating};const card=vm.runInContext("makeCard(song,'owner-token')",context),buttons=all(card,'button').filter(b=>b.dataset.rating);
 assert.equal(buttons.length,4);assert.ok(buttons.every(b=>b.attributes.role==='radio'));
 assert.equal(buttons.filter(b=>b.attributes['aria-checked']==='true').length,['love','like','neutral','dislike'].includes(rating)?1:0);
 for(const b of buttons)assert.equal(b.selected,b.dataset.rating===rating);
 assert.equal(all(card,'div').find(el=>el.attributes.role==='radiogroup')?.children.length,4);
 assert.ok(card.children.findIndex(el=>el.children.some(x=>x.attributes?.role==='radiogroup'))<card.children.findIndex(el=>el.className==='song-actions'));
}
context.preview=true;context.song.rating='love';assert.equal(all(vm.runInContext("makeCard(song,'preview')",context),'button').filter(b=>b.attributes['aria-checked']==='true').length,0);
const html=readFileSync(new URL('../music_bot/web/index.html',import.meta.url),'utf8'),css=readFileSync(new URL('../music_bot/web/style.css',import.meta.url),'utf8');
assert.ok(html.includes('id="owl-speech" aria-live="polite"'));assert.ok(html.includes('class="owl"'));assert.ok(!html.includes('class="small-owl"'));
assert.ok(css.includes('prefers-reduced-motion:reduce'));assert.ok(css.includes('aspect-ratio:1'));assert.ok(!css.includes('.ratings button:first-child'),'no cosmetic preselection');
const luminance=hex=>{const rgb=hex.match(/../g).map(v=>parseInt(v,16)/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4);return rgb[0]*.2126+rgb[1]*.7152+rgb[2]*.0722;};
assert.ok((luminance('b9bbc3')+.05)/(luminance('1f2024')+.05)>=4.5,'muted text on fixed fallback passes AA');
for(const fill of ['7a2e42','2f5b8a','4a4d55','6b3a2a'])assert.ok((luminance('f0f0ed')+.05)/(luminance(fill)+.05)>=4.5);
const mascot={setAttribute(key,value){this[key]=value;}},speech={},handler={},timers=[];
const owlContext=vm.createContext({$:id=>id==='owl-button'?{querySelector:()=>mascot}:speech,t:key=>key,clearTimeout(){},setTimeout:(fn,ms)=>timers.push({fn,ms}),document:{addEventListener:(name,fn)=>handler[name]=fn}});
vm.runInContext(source.slice(source.indexOf('let owlTimer'),source.indexOf('function makeCard(')),owlContext);
for(const value of ['love','like','neutral','dislike']){vm.runInContext(`owlReact('${value}')`,owlContext);assert.equal(speech.textContent,'owl_'+value);assert.ok(mascot.class.includes(value));assert.equal(timers.at(-1).ms,1800);timers.at(-1).fn();assert.equal(mascot.class,'owl');}
for(const i of [0,1,2,0]){vm.runInContext("owlReact('tip')",owlContext);assert.equal(speech.textContent,'owl_tip_'+i);}
console.log('Unrated/stored/invalid/preview rating states, radio group, action order, inline owl and fixed-color contrast passed.');
