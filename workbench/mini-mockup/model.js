import {views as onlineViews} from './online-reference-v30/model.js';
export const surfaces=[{id:'front',name:'封面',hint:'封面显示在正面、展开外侧及闭合斜视图',view:0},{id:'back',name:'封底',hint:'封底显示在后视图及展开外侧',view:5},{id:'inside',name:'内页',hint:'内页显示在展开内侧的左侧盒盖',view:8},{id:'tray',name:'内盘底',hint:'内盘底显示在展开内侧右边',view:8},{id:'disc',name:'盘面',hint:'盘面显示在平展开视图',view:1}];
export const views=[
{name:'正视图（闭合）',slots:[{id:'front',q:[[.2647,.2659],[.8289,.2659],[.8289,.79],[.2647,.79]]}]},
{name:'展开内侧（装盘）',slots:[{id:'inside',q:[[.082,.351],[.456,.351],[.456,.711],[.082,.711]]},{id:'tray',q:[[.482,.357],[.924,.357],[.924,.708],[.482,.708]]},{id:'disc',q:[[.547,.352],[.907,.352],[.907,.712],[.547,.712]],inBox:true}]},
{name:'取盘展示',slots:[{id:'inside',q:[[.102,.337],[.417,.268],[.483,.546],[.173,.614]]},{id:'tray',q:[[.523,.247],[.824,.173],[.880,.448],[.569,.525]]},{id:'disc',q:[[.614,.571],[.932,.571],[.932,.885],[.614,.885]]}]},
{name:'立体内侧',slots:[{id:'inside',q:[[.083,.435],[.443,.284],[.445,.561],[.117,.722]]},{id:'tray',q:[[.525,.30],[.910,.376],[.882,.638],[.526,.555]]},{id:'disc',q:[[.546,.29],[.909,.365],[.884,.622],[.54,.545]],inBox:true}]},
{name:'立体外侧',slots:[{id:'back',q:[[.139,.273],[.431,.458],[.432,.707],[.162,.536]]},{id:'front',q:[[.517,.453],[.862,.322],[.845,.587],[.517,.730]]}]}
];
surfaces.push(
 {id:'sideR',name:'右侧封',hint:'封底外缘的折边，按 4.4 × 38 mm 读取',view:7},
 {id:'sideL',name:'左侧封',hint:'封底在铰链侧的折边，按 4.4 × 38 mm 读取',view:6},
 {id:'sideLB',name:'左侧封背面',hint:'侧封背面作为独立素材保留，不显示在平展开内侧',view:1}
);
// The rear insert folds around the tray; these narrow receiving planes
// connect the large printed faces instead of leaving a bare plastic spine.
// Align the printed fold with the inside of the replacement front shell's
// narrow channel. Dimensions here are photographic placement, not print mm.
views[0].slots.push({id:'tray',sourceCrop:[0,0,.08,1],q:[[.175,.273],[.223,.273],[.223,.787],[.175,.787]]});
views[2].slots.push({id:'sideLB',q:[[.452,.270],[.485,.259],[.549,.531],[.516,.542]]});
views[3].slots.push({id:'sideLB',q:[[.496,.282],[.520,.292],[.521,.555],[.498,.548]]});
views[4].slots.push(
 {id:'sideR',q:[[.124,.264],[.139,.273],[.162,.536],[.150,.531]]},
 {id:'sideL',q:[[.434,.468],[.457,.480],[.464,.738],[.443,.725]]}
);
for(const i of [2,3,4])views[i].hidden=true;
const onlineIds={leftSpine:'sideL',rightSpine:'sideR',leftSpineInner:'sideLB'};
for(let i=1;i<=6;i++){const v=onlineViews[i];views.push({...v,onlineIndex:i,slots:v.slots.map(slot=>({...slot,id:onlineIds[slot.id]||slot.id}))})}
// The flat interior is the same open case as the installed-disc view, with
// only the clear disc carrier and disc removed.
views[8].slots=views[1].slots.filter(slot=>slot.id!=='disc').map(slot=>({...slot,q:slot.q.map(p=>[...p])}));
// Shared visual scale for previews and multi-view exports.
export function viewScale(view){
 const bodyHeight=.70*45/53,paperHeight=bodyHeight*38/45;
 const installed=paperHeight/.351;
 const outsideFlat=paperHeight/(.45*565/887)*(651/629)*(722/815);
 const index=views[view]?.onlineIndex;
 return view===1||view===8?installed:index===5?outsideFlat:[2,3].includes(index)?bodyHeight/.60:1;
}
export function widestViewScale(){return Math.max(viewScale(1)*.90,viewScale(8)*.78,viewScale(9)*.78)}
export const defaultTransform=()=>({fit:'cover',scale:100,x:0,y:0,rotation:0});
export function initialState(){return {version:1,frontLayoutRevision:1,trayLayoutRevision:1,title:'未命名专辑',view:0,selected:'front',showDesign:true,lighting:true,discVisible:false,background:'#ffffff',assets:Object.fromEntries(surfaces.map(s=>[s.id,{src:null,...defaultTransform()}])),quads:{}}}
export function validQuad(q){if(!Array.isArray(q)||q.length!==4||!q.every(p=>Array.isArray(p)&&p.length===2&&p.every(n=>Number.isFinite(n)&&n>=0&&n<=1)))return false;const cross=q.map((p,i)=>{const b=q[(i+1)%4],c=q[(i+2)%4];return(b[0]-p[0])*(c[1]-b[1])-(b[1]-p[1])*(c[0]-b[0])});return cross.every(n=>n>.0002)||cross.every(n=>n<-.0002)}
export function sanitizeState(data){
 if(!data||data.version!==1||!data.assets)throw Error('这不是有效的 Mini CD 项目文件');
 const st=initialState();st.syncRevision=typeof data.syncRevision==='string'?data.syncRevision:'';st.assemblyVersion=data.assemblyVersion===1?1:0;st.title=String(data.title||st.title).slice(0,60);st.view=Number.isInteger(data.view)&&data.view>=0&&data.view<views.length&&!views[data.view].hidden?data.view:0;st.selected=surfaces.some(s=>s.id===data.selected)?data.selected:'front';
 for(const key of ['showDesign','lighting','discVisible'])if(typeof data[key]==='boolean')st[key]=data[key];if(['#ffffff','#f0efec','#e8edf0'].includes(data.background))st.background=data.background;
 for(const s of surfaces){const a=data.assets[s.id];if(!a)continue;const t=st.assets[s.id];if(typeof a.src==='string'&&/^data:image\/(png|jpeg|webp);base64,/.test(a.src)&&a.src.length<30000000)t.src=a.src;t.fit=a.fit==='contain'?'contain':'cover';for(const [key,min,max]of[['scale',25,250],['x',-100,100],['y',-100,100],['rotation',-180,180]])t[key]=Math.min(max,Math.max(min,Number(a[key])|| (key==='scale'?100:0)));}
 for(const [key,q]of Object.entries(data.quads||{})){if(!/^\d{1,2}:(front|back|inside|tray|disc|sideR|sideL|sideLB)$/.test(key))continue;if(key.startsWith('0:')&&data.frontLayoutRevision!==1)continue;if(!validQuad(q))continue;let mapped=q;if(key==='1:tray'&&data.trayLayoutRevision!==1){mapped=q.map((p,i)=>[i===0||i===3?Math.max(0,p[0]-.057):p[0],p[1]]);if(!validQuad(mapped))continue}st.quads[key]=mapped;}
 return st;
}
const dbReady=new Promise((resolve,reject)=>{const req=indexedDB.open('mini-cd-studio',1);req.onupgradeneeded=()=>req.result.createObjectStore('projects');req.onsuccess=()=>resolve(req.result);req.onerror=()=>reject(req.error)});dbReady.catch(()=>{});
const workbenchJid=new URLSearchParams(location.search).get('jid');
const batchNo=new URLSearchParams(location.search).get('batchNo')||'';
const projectKey=workbenchJid?'workbench:'+workbenchJid+(batchNo?':batch:'+batchNo:''):'current';
export async function persist(state){const db=await dbReady;await new Promise((resolve,reject)=>{const tx=db.transaction('projects','readwrite');tx.objectStore('projects').put(state,projectKey);tx.oncomplete=resolve;tx.onerror=()=>reject(tx.error)})}
export async function restore(){const db=await dbReady;return new Promise((resolve,reject)=>{const r=db.transaction('projects').objectStore('projects').get(projectKey);r.onsuccess=()=>resolve(r.result?sanitizeState(r.result):null);r.onerror=()=>reject(r.error)})}
export function loadImage(src){return new Promise((resolve,reject)=>{const img=new Image();img.onload=()=>resolve(img);img.onerror=()=>reject(Error('图片无法读取'));img.src=src})}
export async function readUpload(file){
 if(!['image/png','image/jpeg','image/webp'].includes(file.type))throw Error('请选择 PNG、JPG 或 WebP 图片');
 if(file.size>20*1024*1024)throw Error('图片不能超过20MB');
 const src=await new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result);r.onerror=()=>reject(Error('图片读取失败'));r.readAsDataURL(file)});
 await loadImage(src);return src;
}
