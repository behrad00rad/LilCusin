import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const source=readFileSync(new URL('../music_bot/web/app.js',import.meta.url),'utf8');
const start=source.indexOf('// Vertical browsing owns');
const section=source.slice(start,source.indexOf('async function loadDeck',start));
const listeners={};
function surface(){return {style:{removeProperty(key){delete this[key];}},classList:{add(){},remove(){}}};}
const main=surface(),card=surface(),songs=[],tabs=[],tabOptions=[];
const context=vm.createContext({console,Date,deckAnimating:false,uiMotion:async()=>true,view:'for-you',generation:1,moveDeck:n=>songs.push(n),switchView:(v,result,options)=>{tabs.push(v);tabOptions.push(options);},
 document:{documentElement:{dir:'ltr'},querySelector:()=>main,addEventListener:(name,fn)=>listeners[name]=fn},window:{addEventListener(){}}});
vm.runInContext(section,context);
const target=(options={})=>({closest(selector){if(selector.startsWith('input'))return options.editing||false;if(selector==='main,.main-nav')return options.main!==false;if(selector==='.feed-card')return options.card===false?null:card;return null;}});
function event(x,y,options={}){return {clientX:x,clientY:y,pointerId:1,isPrimary:true,button:0,target:target(options),cancelable:true,preventDefault(){this.prevented=true;},...options};}
function swipe(dx,dy,options={}){listeners.pointerdown(event(150,200,options));const drag=event(150+dx,200+dy,options);listeners.pointermove(drag);listeners.pointerup(drag);return drag;}
swipe(0,-100);assert.equal(songs.pop(),1,'whole card swipes up');
swipe(0,100);assert.equal(songs.pop(),-1,'whole card swipes down');
listeners.pointerdown(event(150,200));listeners.pointermove(event(150,120));assert.equal(card.style.transform,'translateY(-80px)','whole card follows the finger');listeners.pointercancel();assert.equal(card.style.transform,undefined,'cancel clears transform');
swipe(-100,5);assert.equal(tabs.pop(),'search','LTR left swipe advances tab');
assert.equal(tabOptions.pop().focusSearch,false,'swiping into Search does not open the keyboard');
context.view='search';swipe(100,0,{card:false});assert.equal(tabs.pop(),'for-you','LTR right swipe goes back');
context.document.documentElement.dir='rtl';context.view='for-you';swipe(100,0);assert.equal(tabs.pop(),'search','RTL follows visual tab order');
context.view='search';swipe(-100,0,{card:false});assert.equal(tabs.pop(),'for-you');
context.document.documentElement.dir='ltr';context.view='card';swipe(-100,0,{card:false});assert.equal(tabs.length,0,'no wrapping at tab edge');
context.view='search';const scroll=swipe(0,100,{card:false});assert.equal(songs.length,0,'other pages keep vertical scrolling');assert.ok(!scroll.prevented,'native scrolling is not cancelled');
swipe(-120,0,{editing:true});assert.equal(tabs.length,0,'editing gestures ignored');
context.view='for-you';swipe(25,10);assert.equal(songs.length+tabs.length,0,'short drag is not navigation');
swipe(-100,-100);assert.equal(songs.length+tabs.length,0,'ambiguous diagonal ignored');
listeners.pointerdown(event(150,200));listeners.pointermove(event(150,100));context.generation++;listeners.pointerup(event(150,100));assert.equal(songs.length,0,'stale view gesture ignored');assert.equal(card.style.transform,undefined);
listeners.pointerdown(event(150,200));listeners.pointerdown(event(160,200,{isPrimary:false,pointerId:2}));listeners.pointerup(event(150,100));assert.equal(songs.length,0,'multitouch cancels navigation');
swipe(0,-100);const click={detail:1,preventDefault(){this.prevented=true;},stopImmediatePropagation(){this.stopped=true;}};listeners.click(click);assert.ok(click.prevented&&click.stopped,'drag cannot activate a button on release');
const keyboardClick={detail:0,preventDefault(){this.prevented=true;},stopImmediatePropagation(){}};listeners.click(keyboardClick);assert.ok(!keyboardClick.prevented,'keyboard action remains available');
listeners.pointerdown(event(150,200,{editing:true}));const freshTap={detail:1,preventDefault(){this.prevented=true;},stopImmediatePropagation(){}};listeners.click(freshTap);assert.ok(!freshTap.prevented,'a deliberate new tap is not suppressed');
console.log('Whole-card gestures, drag motion, RTL tabs, thresholds, scrolling/editing safety, cancellation and click suppression passed.');
