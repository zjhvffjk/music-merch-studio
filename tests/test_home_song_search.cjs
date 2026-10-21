const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawn } = require('node:child_process');

const workbenchUrl = process.env.WORKBENCH_TEST_URL || 'http://127.0.0.1:8765/';
const profile = fs.mkdtempSync(path.join(process.cwd(), '.tmp-search-browser-'));
const browser = spawn('C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe', [
  '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
  '--remote-debugging-port=0', `--user-data-dir=${profile}`, workbenchUrl
], { stdio: 'ignore' });
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
async function main() {
  let port;
  for (let i = 0; i < 100; i++) {
    const file = path.join(profile, 'DevToolsActivePort');
    if (fs.existsSync(file)) { port = Number(fs.readFileSync(file, 'utf8').split('\n')[0]); break; }
    await sleep(100);
  }
  if (!port) throw new Error('Chrome debugging port did not start');
  const pages = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
  const target = pages.find(page => page.type === 'page' && page.url.startsWith(workbenchUrl));
  if (!target) throw new Error('Workbench page did not open');
  const socket = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => { socket.onopen = resolve; socket.onerror = reject; });
  let nextId = 0;
  const pending = new Map();
  socket.onmessage = event => {
    const message = JSON.parse(event.data);
    if (!message.id) return;
    const item = pending.get(message.id);
    if (!item) return;
    pending.delete(message.id);
    message.error ? item.reject(Error(message.error.message)) : item.resolve(message.result);
  };
  const send = (method, params={}) => new Promise((resolve,reject) => {
    const id = ++nextId;
    pending.set(id,{resolve,reject});
    socket.send(JSON.stringify({id,method,params}));
  });
  const evaluate = async expression => {
    const result = await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});
    if(result.exceptionDetails) throw Error(result.exceptionDetails.text);
    return result.result.value;
  };
  for (let i=0;i<40;i++) {
    if(await evaluate('!!document.querySelector("#globalSearch")')) break;
    await sleep(100);
  }
  async function search(query) {
    await evaluate(`(()=>{const input=document.querySelector('#globalSearch');input.value=${JSON.stringify(query)};input.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}));return true})()`);
    for(let i=0;i<120;i++){
      const state=await evaluate('({title:document.querySelector(".song-search-heading h2")?.textContent||"",count:document.querySelectorAll("#albStage .song-search-page .artist-track").length})');
      if(state.title.includes(query) && state.count>0) return state;
      await sleep(100);
    }
    throw new Error(`No visible song results for ${query}`);
  }
  console.log('晴天',await search('晴天'));
  const opened=await evaluate('(()=>{document.querySelector("#albStage .artist-track").click();return !!document.querySelector("#albStage .song-maker-page")})()');
  if(!opened) throw new Error('Clicking the song did not open the maker');
  console.log('单曲制作页',opened);
  console.log('小胡同',await search('小胡同'));
  socket.close();
}
main().then(()=>{console.log('PASS');process.exitCode=0},error=>{console.error(error);process.exitCode=1}).finally(async()=>{
  if(browser.exitCode===null){
    const exited=new Promise(resolve=>browser.once('exit',resolve));
    browser.kill();
    await Promise.race([exited,sleep(3000)]);
  }
  const resolved=path.resolve(profile), root=path.resolve(process.cwd())+path.sep;
  if(resolved.startsWith(root)) {
    try{fs.rmSync(resolved,{recursive:true,force:true,maxRetries:10,retryDelay:300})}
    catch(error){console.warn('Temporary browser profile could not be removed:',error.message)}
  }
});
