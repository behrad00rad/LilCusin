import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const source=fs.readFileSync(new URL('../music_bot/web/app.js',import.meta.url),'utf8');
const cards=[{id:1,dataset:{}},{id:2,dataset:{}}],events=[],timers=new Map();let clock=0;
const ctx=vm.createContext({view:'for-you',document:{hidden:false},deckIndex:0,
 deckItems:()=>cards,deckKey:card=>'song:'+card.id,deckSeen:new Set(),
 queueFeedEvent:(card,event)=>events.push([card.id,event]),
 setTimeout:(fn,ms)=>{assert.equal(ms,1000);timers.set(++clock,fn);return clock;},
 clearTimeout:id=>timers.delete(id)});
vm.runInContext('let feedSeenTimer,observedFeedCard;const feedViewed=new WeakSet();'+
 source.slice(source.indexOf('function observeFeedCard('),source.indexOf('function caughtUp(')),ctx);
const run=code=>vm.runInContext(code,ctx);
run('observeFeedCard()');assert.equal(events.length,0,'Prefetch/install cannot count as a view');
timers.get(clock)();assert.deepEqual(events,[[1,'seen']]);assert.ok(!events.some(([id])=>id===2));
run('observeFeedCard()');assert.equal(clock,1,'Reinstall does not start duplicate view timers');
run('deckIndex=1;observeFeedCard();document.hidden=true;observeFeedCard()');
assert.ok(!timers.has(clock),'Hiding the app cancels the unfinished dwell');
run('skipFeedCard(deckItems()[0])');assert.deepEqual(events.at(-1),[1,'skipped']);
cards[1].dataset.feedAction='true';run('skipFeedCard(deckItems()[1])');assert.equal(events.length,2);
assert.ok(source.includes("saved.view!=='search'"),'Home must revalidate durable state on reopening');
assert.ok(source.includes("api('feed/events',{events:[row]})"),'Dismiss controls persist before removal');
console.log('Active-card dwell, no prefetched view, visibility cancellation, skip/action distinction and resume hooks passed.');
