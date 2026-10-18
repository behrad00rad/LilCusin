import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

class Element {
  children=[];dataset={};attributes={};hidden=false;
  append(...items){this.children.push(...items);}
  setAttribute(key,value){this.attributes[key]=value;}
}
const toast=new Element();
const context=vm.createContext({window:{addEventListener(){},opened:null},navigator:{language:'en'},
  document:{addEventListener(){},createElement:()=>new Element(),getElementById:()=>toast},
  setTimeout:()=>1,clearTimeout(){},URL,console});
vm.runInContext(readFileSync(new URL('../music_bot/web/app.js',import.meta.url),'utf8').replace(/\nboot\(\);\s*$/,'\n'),context);
vm.runInContext(`
catalogue={en:{get_song:'Get song',get_song_hint:'Audio in this bot',preview_only:'Preview only'}};
preview=false;tg={openTelegramLink:url=>window.opened=url};scheduleArtwork=()=>{};
const card=makeCard({id:42,title:'Song',artist:'Artist',get_song_url:'https://t.me/FixtureBot?start=get_old_42'},'initial');
card.songData.token='renewed';
const button=card.children[1].children[0];button.onclick();
`,context);
assert.equal(vm.runInContext('window.opened',context),'https://t.me/FixtureBot?start=get_renewed_42');
vm.runInContext("preview=true;window.opened=null;button.onclick();",context);
assert.equal(vm.runInContext('window.opened',context),null);
assert.equal(toast.textContent,'Preview only');
console.log('Get song uses the current renewed grant; preview never opens an external bot.');
