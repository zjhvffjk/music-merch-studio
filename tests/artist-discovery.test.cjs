const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const context = {renderArtistResultStage() {}, window:{}, document:{querySelector:()=>null}};
vm.createContext(context);
vm.runInContext(fs.readFileSync('workbench/artist-browser.js','utf8'),context);

test('artist suggestions include image and escaped name without injecting HTML', () => {
  const markup = context.window.ArtistDiscovery.rows([{name:'A"<img>',pic:'https://example.com/artist.jpg'}]);
  assert.ok(markup.includes('https://example.com/artist.jpg'));
  assert.ok(markup.includes('A&quot;&lt;img&gt;'));
  assert.ok(!markup.includes('A"<img>'));
});
test('unsafe avatar URLs use a placeholder', () => {
  const markup = context.window.ArtistDiscovery.rows([{name:'歌手',pic:'javascript:alert(1)'}]);
  assert.ok(!markup.includes('javascript:'));
  assert.ok(markup.includes('data-artist-avatar="歌手"'));
});
test('duplicate artist names are removed and result size is bounded', () => {
  const list = [{name:'同名'},{name:'同名'},...Array.from({length:12},(_,i)=>({name:`歌手${i}`}))];
  const markup = context.window.ArtistDiscovery.rows(list);
  assert.equal((markup.match(/data-search-artist=/g)||[]).length, 5);
  assert.equal((markup.match(/data-search-artist="同名"/g)||[]).length,1);
});
test('an exact artist query keeps the actual match ahead of unrelated fuzzy accounts', () => {
  const markup = context.window.ArtistDiscovery.rows([{name:'林俊杰翻唱'},{name:'林俊杰'},{name:'Jay'}], '林俊杰');
  assert.equal((markup.match(/data-search-artist=/g)||[]).length,1);
  assert.ok(markup.includes('data-search-artist="林俊杰"'));
});
