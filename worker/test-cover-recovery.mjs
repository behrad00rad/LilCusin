import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const source=readFileSync(process.argv[2],'utf8');
let observer,timers=new Map(),next=0;
const context=vm.createContext({node:()=>({style:{},removeAttribute(name){delete this[name];}}),
 artworkURL:()=> 'https://image.example/variant.webp',
 document:{createTextNode:text=>text},encodeURIComponent,
 setTimeout:fn=>{timers.set(++next,fn);return next;},clearTimeout:id=>timers.delete(id),
 IntersectionObserver:class {constructor(callback){this.callback=callback;observer=this;}observe(){}disconnect(){}}});
vm.runInContext(source.slice(source.indexOf('function setArtwork('),source.indexOf('\nlet artTimer;')),context);
const cover={dataset:{},children:[],contains(img){return this.children.includes(img);},replaceChildren(...children){this.children=children;}};
context.cover=cover;
vm.runInContext("setArtwork(cover,'https://image.example/original.png')",context);
assert.equal(timers.size,0,'hidden lazy artwork has no premature deadline');
let img=cover.children[1];observer.callback([{isIntersecting:true}]);assert.equal(timers.size,1);
img.onerror();assert.equal(img.src,'/cover?url=https%3A%2F%2Fimage.example%2Foriginal.png','fallback stays on the bounded proxy');
img.onerror();assert.equal(timers.size,0);assert.equal(cover.dataset.artFailed,'true');assert.equal(cover.children.length,1);
vm.runInContext("setArtwork(cover,'https://image.example/original.png')",context);
img=cover.children[1];observer.callback([{isIntersecting:true}]);img.onload();assert.equal(timers.size,0);assert.equal(img.style.opacity,'1');observer.callback([{isIntersecting:true}]);assert.equal(timers.size,0,'queued visibility callback cannot expire loaded artwork');
vm.runInContext("setArtwork(cover,'https://image.example/original.png')",context);
img=cover.children[1];observer.callback([{isIntersecting:true}]);const expired=[...timers.values()][0];cover.replaceChildren('newer artwork');expired();assert.deepEqual(cover.children,['newer artwork'],'an old timeout cannot overwrite a newer image');
console.log('Hidden-image deadlines, same-origin fallback, terminal placeholder, load cleanup and stale-image safety passed.');
