import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const source=readFileSync(new URL('../music_bot/web/app.js',import.meta.url),'utf8');
const section=source.slice(source.indexOf('// Small native animations'),source.indexOf('const deckItems='));
const calls=[],loads=[];let reduced=false,pending=false;
function surface(name){return {name,style:{removeProperty(k){delete this[k];}},classList:{add(){},remove(){}},animate(frames,options){let reject;const finished=pending?new Promise((r,j)=>{reject=j;}):Promise.resolve();const animation={finished,cancel(){reject?.(new Error('cancelled'));}};calls.push({name,frames,options,animation});return animation;}};}
const main=surface('main'),cards=[surface('first'),surface('second')];
const context=vm.createContext({console,Promise,Set,matchMedia:()=>({matches:reduced}),view:'for-you',generation:1,deckLoading:false,deckIndex:0,deckItems:()=>cards,fitDeck(){},clearSwipe(){},primaryViews:['for-you','search','swaps','card'],
 document:{documentElement:{dir:'ltr'},querySelector:()=>main},loadDeck:async direction=>{context.deckIndex+=direction;},loadView:async(next)=>{loads.push(next);context.view=next;context.generation++;}});
vm.runInContext(section,context);
await vm.runInContext('moveDeck(1,-80)',context);
assert.equal(context.deckIndex,1);assert.equal(calls[0].frames[0].transform,'translateY(-80px)','continues from finger position');assert.equal(calls[1].frames[0].transform,'translateY(42px)');assert.equal(cards[0].style.opacity,undefined,'no persistent hidden card');
calls.length=0;await vm.runInContext('moveDeck(-1,70)',context);assert.equal(context.deckIndex,0);assert.equal(calls[1].frames[0].transform,'translateY(-42px)','previous arrives from above');
calls.length=0;await vm.runInContext("switchView('search')",context);assert.equal(loads.pop(),'search');assert.equal(calls[0].frames[1].transform,'translateX(-36px)');assert.equal(calls[1].frames[0].transform,'translateX(28px)');
context.document.documentElement.dir='rtl';context.view='for-you';calls.length=0;await vm.runInContext("switchView('search',undefined,{motionFromX:85})",context);assert.equal(calls[0].frames[0].transform,'translateX(85px)');assert.equal(calls[0].frames[1].transform,'translateX(109px)','RTL exit follows drag');
reduced=true;context.view='for-you';calls.length=0;await vm.runInContext('moveDeck(1)',context);assert.equal(calls.length,0,'reduced motion skips animation');assert.equal(context.deckIndex,1,'reduced motion keeps browsing');
reduced=false;pending=true;context.view='for-you';context.deckIndex=0;calls.length=0;const cancelled=vm.runInContext('moveDeck(1)',context);vm.runInContext('cancelUIMotion()',context);await cancelled;assert.equal(context.deckIndex,0,'cancelled exit cannot advance a stale card');assert.equal(cards[0].style.opacity,undefined);
pending=false;calls.length=0;loads.length=0;const older=vm.runInContext("switchView('search')",context),newer=vm.runInContext("switchView('card')",context);await Promise.all([older,newer]);assert.deepEqual(loads,['card'],'latest tab wins rapid navigation');
console.log('Directional card/tab motion, finger continuity, RTL, reduced motion, cancellation and rapid navigation passed.');
