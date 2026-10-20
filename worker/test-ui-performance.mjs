import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import worker from './worker.mjs';
const source=readFileSync(new URL('../music_bot/web/app.js',import.meta.url),'utf8');
const context=vm.createContext({URL,navigator:{connection:{}},window:{devicePixelRatio:2}});
vm.runInContext(source.slice(source.indexOf('function artworkURL('),source.indexOf('function setArtwork(')),context);
const original='https://lastfm-img.freetls.fastly.net/i/u/300x300/'+'a'.repeat(32)+'.png';
context.original=original;
assert.match(vm.runInContext('artworkURL(original)',context),/\/174s\/.+\.webp$/);
assert.match(vm.runInContext('artworkURL(original,true)',context),/\/600x600\/.+\.webp$/);
context.navigator.connection.saveData=true;
assert.match(vm.runInContext('artworkURL(original,true)',context),/\/300x300\/.+\.webp$/);
for(const url of ['https://other.example/i/u/300x300/a.png',original+'?x=1','invalid']){
 context.raw=url;assert.equal(vm.runInContext('artworkURL(raw)',context),url);
}
for(const path of ['/','/app.js','/locales.json','/vazirmatn.woff2']){
 const request=new Request('https://fixture.example'+path),response=await worker.fetch(request,{});
 assert.equal(response.headers.get('Cache-Control'),'public, no-cache');
 const etag=response.headers.get('ETag');assert.ok(etag);
 assert.equal((await worker.fetch(new Request(request,{headers:{'If-None-Match':'W/'+etag}}),{})).status,304);
 assert.equal((await worker.fetch(new Request(request,{headers:{'If-None-Match':'"old"'}}),{})).status,200);
}
assert.equal((await worker.fetch(new Request('https://fixture.example/api/profile'),{})).headers.get('Cache-Control'),'no-store');
const html=await(await worker.fetch(new Request('https://fixture.example/'),{})).text();
assert.match(html,/href="\/locales.json" as="fetch"/);assert.doesNotMatch(html,/preload[^>]+woff2/);
const cover={querySelector:()=>null,dataset:{}},cards=[{hidden:false,songData:{id:1,token:'owned'},querySelector:()=>cover},{hidden:true,songData:{id:2,token:'owned'},querySelector:()=>cover}];
const calls=[];
const polling=vm.createContext({preview:false,generation:7,view:'for-you',$:()=>({querySelectorAll:()=>cards}),api:async(path,data)=>{calls.push(data.track_ids);return {};},setTimeout:()=>{},clearTimeout:()=>{}});
vm.runInContext(source.slice(source.indexOf('let artTimer;'),source.indexOf('async function openChannel(')),polling);
await vm.runInContext('pollArtwork(7,3)',polling);assert.deepEqual(Array.from(calls[0]),[1]);
cards[0].hidden=true;cards[1].hidden=false;await vm.runInContext('pollArtwork(7,3)',polling);assert.deepEqual(Array.from(calls[1]),[2]);
await vm.runInContext('pollArtwork(6,3)',polling);assert.equal(calls.length,2,'stale page does not request artwork');
console.log('Context sizes, data-saving mode, conservative URL fallback, static validators and private API no-store passed.');
