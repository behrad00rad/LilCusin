import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const source=readFileSync(new URL('../music_bot/web/app.js',import.meta.url),'utf8');
let cover=320,width=320,height=645,top=80,details=330,drag=false,value='';
const art={get offsetHeight(){return cover;}},track={get clientWidth(){return width;}};
const card={get offsetHeight(){return details+cover;},querySelector:s=>s==='.cover'?art:track,getBoundingClientRect:()=>({top}),style:{getPropertyValue:()=>value,setProperty:(key,size)=>{assert.equal(key,'--cover-size');value=size;cover=Number.parseFloat(size);}}};
const context=vm.createContext({view:'for-you',Number,Math,Infinity,runningMotion:new Set(),get swipeGesture(){return drag?{moving:card}:null;},$:()=>({offsetHeight:20}),
 document:{body:{classList:{contains:()=>true}},querySelector:s=>s==='.main-nav'?{getBoundingClientRect:()=>({top:height-110})}:card},
 window:{visualViewport:{get height(){return height;}}},tg:{get viewportStableHeight(){return height;}}});
vm.runInContext(source.slice(source.indexOf('function deckCoverSize('),source.indexOf("window.addEventListener('resize',fitDeck)")),context);
for(const viewport of [645,700,810])for(const content of [300,360]){
 height=viewport;details=content;cover=width;vm.runInContext('fitDeck()',context);
 assert.ok(cover<=width&&cover>=44);
 assert.ok(top+details+cover+20<height-110,'actions and hint clear the navigation');
 const fitted=cover;for(let i=0;i<10;i++)vm.runInContext('fitDeck()',context);assert.equal(cover,fitted,'repeated fits do not drift');
}
const previous=cover;drag=true;height=600;vm.runInContext('fitDeck()',context);assert.equal(cover,previous,'drag transforms must not influence sizing');drag=false;
top+=24;details=300;vm.runInContext('fitDeck()',context);assert.ok(top+details+cover+20<height-110,'safe-area and host-height changes refit');
assert.ok(source.includes("tg?.onEvent('viewportChanged',fitDeck)"));
console.log('Short/tall Telegram viewports, long-card content, safe areas, repeated fits and drag guards passed.');
