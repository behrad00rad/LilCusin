import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
class Element {
 constructor(tag='div',text,cls=''){this.tag=tag;this.textContent=text||'';this.className=cls;this.children=[];this.dataset={};this.style={};this.attributes={};this.isConnected=true;this.disabled=false;this.classList={add:(v)=>{this.className+=' '+v;},remove:()=>{},contains:v=>this.className.split(' ').includes(v)};}
 append(...els){this.children.push(...els);}
 replaceChildren(...els){this.children=els;}
 setAttribute(k,v){this.attributes[k]=v;if(k==='class')this.className=v;}
 getAttribute(k){return this.attributes[k];}
 querySelector(selector){for(const el of this.children){if((selector.startsWith('.')?el.className?.split(' ').includes(selector.slice(1)):el.tag===selector))return el;const nested=el.querySelector?.(selector);if(nested)return nested;}return null;}
 remove(){this.isConnected=false;}focus(){}showModal(){}close(){}
}
const locales=JSON.parse(readFileSync(new URL('../music_bot/web/locales.json',import.meta.url),'utf8'));
for(const [key,value] of Object.entries(locales.fa).filter(([key])=>key.startsWith('guess_'))){assert.match(value,/\p{Script=Arabic}/u,key+' must contain Persian');assert.ok(!value.includes('?'),key+' must survive UTF-8 serialization');}
let language='en',reduced=false,shared='',requests=[],timers=[],response;
const round={idx:0,options:[1,2,3,4].map(recording_id=>({recording_id,title:'Title '+recording_id,artist:'Artist',cover_url:'https://covers.test/'+recording_id}))};
const result={score:4,total:5,rounds:[true,true,false,true,true],missed:['PRIVATE MISSED TITLE'],head_to_head:{you:4,them:3},can_play_again:false};
const context=vm.createContext({console,Date,Map,Set,URLSearchParams,AbortController,Image:class{set src(v){this.url=v;}},
 setTimeout:(fn,ms)=>{timers.push({fn,ms});return timers.length;},clearTimeout(){},matchMedia:()=>({matches:reduced}),
 node:(tag,text,cls)=>new Element(tag,text,cls),icon:name=>new Element('svg',name,'ui-icon'),
 action:(label,fn,cls)=>{const b=new Element('button',label,cls);b.onclick=fn;return b;},
 t:(key,values={})=>(locales[language][key]||locales.en[key]||key).replace(/\{(\w+)\}/g,(_,k)=>values[k]??''),
 artworkURL:url=>url,telegramCall:fn=>fn(),tg:{initData:'fixture',BackButton:{show(){},hide(){}},openTelegramLink:url=>{shared=url;}},
 document:{activeElement:new Element(),body:new Element(),createElement:tag=>new Element(tag)},
 owlIllustration:()=>new Element('svg','','owl empty-owl'),window:{open(){}},
 fetch:async(url,options)=>{requests.push({url,data:JSON.parse(options.body||'null')});if(response instanceof Error)throw response;return {ok:true,json:async()=>response};},
 notice(){},preview:false,location:{search:''},api:async()=>({guess_game:false}),generation:1});
const source=readFileSync(new URL('../music_bot/web/app.js',import.meta.url),'utf8');
vm.runInContext(source.slice(source.indexOf('// Guess game:')).replace(/\nboot\(\);\s*$/,''),context);
vm.runInContext(`const friend={token:'f'.repeat(32),other:{nickname:'Mina'}},info={your_name:'Sam',share_url:'https://t.me/FixtureBot',challenge_url:'https://t.me/FixtureBot?startapp=guess_'+friend.token};`,context);
context.round=round;context.result=result;
vm.runInContext('var state=makeGuessDialog(friend,info);state.gameId="g".repeat(32);renderGuessRound(state,round);',context);
response=new Error('offline');await vm.runInContext('pickGuess(state,1)',context);
assert.equal(vm.runInContext('state.picked',context),1);
assert.equal(vm.runInContext('state.grid.children.every(b=>b.disabled)',context),true);
const count=requests.length;await vm.runInContext('pickGuess(state,2)',context);assert.equal(requests.length,count,'Failed requests keep the original pick immutable');
response={correct:false,correct_recording_id:2,next_round:{...round,idx:1},result:null};
await vm.runInContext('state.dialog.querySelector(".guess-retry").children[1].onclick()',context);
assert.equal(requests.at(-1).data.recording_id,1);
assert.equal(vm.runInContext('guessPreloads.size',context),4);
const reveal=timers.findLast(t=>t.ms<=300);assert.ok(reveal);reveal.fn();
assert.equal(vm.runInContext('state.grid.children[0].className.includes("is-wrong")',context),true);
assert.equal(vm.runInContext('state.grid.children[1].className.includes("is-correct")',context),true);
vm.runInContext('renderGuessResult(state,result);state.dialog.querySelector(".guess-result").children.find(b=>b.textContent===t("guess_send")).onclick()',context);
assert.ok(decodeURIComponent(shared).includes('4/5'));
assert.ok(!shared.includes('PRIVATE')&&!shared.includes('covers.test')&&!shared.includes('guess_'),'Result share omits songs and private relationship tokens');
reduced=true;language='fa';response={correct:true,correct_recording_id:1,next_round:null,result};
vm.runInContext('state=makeGuessDialog(friend,info);state.gameId="g".repeat(32);renderGuessRound(state,round)',context);
await vm.runInContext('pickGuess(state,1)',context);
assert.equal(vm.runInContext('state.grid.children[0].className.includes("is-correct")',context),true,'Reduced motion reveals immediately');
vm.runInContext('closeGuessGame()',context);assert.equal(vm.runInContext('guessState',context),null);
console.log('Guess UI immutable picks/retry, wrong/correct reveal, preload, score-only share, Persian and reduced-motion states passed.');
