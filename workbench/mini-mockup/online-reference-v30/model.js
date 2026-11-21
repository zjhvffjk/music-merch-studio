import { frontFrame, frontPaperQuad, frontTrayQuad, rebaseFrontQuad } from '../front-shell.js';

export const surfaces=[{id:'front',name:'封面',hint:'封面显示在闭合正面、45°斜视及更多展示角度',view:0},{id:'back',name:'封底',printSize:[49,38],hint:'后视图与展开外侧左边共用封底；49×38mm纸放在53×45mm背壳内',view:1},{id:'inside',name:'封面背面（内页）',hint:'封面纸的背面，显示在展开内侧左边；展开外侧右边是封面',view:7},{id:'tray',name:'内盘底',printSize:[49,38],hint:'完整图用于内部盘底；闭合正面左侧只露出同一张图的左端局部',view:7},{id:'disc',name:'盘面',hint:'盘面显示在展开图或更多角度中的取盘展示',view:8},{id:'leftSpine',name:'左侧封',hint:'左侧封4.4×38mm，显示在左视图及闭合斜视图的左侧面',view:2},{id:'rightSpine',name:'右侧封',hint:'右侧封4.4×38mm，显示在右视图',view:3},{id:'leftSpineInner',name:'左侧封（内折）',hint:'左侧封背面，折入内部后不可见；作为打印展开稿组件保留',hiddenInAssembly:true,view:7}];
export const MAIN_VIEW_COUNT=8;
export const DISC={diameter:40,holeDiameter:5,labelDiameter:39.2};
export function defaultPreviewZoom(view){return [2,3].includes(view)?135:100}
// Open pairs use a wide camera frame instead of sitting inside a mostly empty square.
export function previewFrame(view){return [4,5,7].includes(view)?[.03,.23,.94,.50]:[0,0,1,1]}
export function previewPixelWidth(cssWidth,pixelRatio=1){return Math.min(4096,Math.max(640,Math.ceil(cssWidth*Math.max(1,pixelRatio))))}
// Both open references use the same photo-to-canvas mapping. Parts stay on their photographed face.
const openFrame={body:[0,0,1774,887],destination:[.05,.25,.9,.45]};
const openQuad=([x,y,w,h])=>[[x,y],[x+w,y],[x+w,y+h],[x,y+h]].map(([a,b])=>[.05+.9*a/1774,.25+.45*b/887]);
const outerEyelets = [
 { center: 507, clearLeft: 380, clearRight: 634 },
 { center: 1265, clearLeft: 1129, clearRight: 1398 },
];
export const views=[
{name:'正视图（闭合）',shell:'assets/front-shell-measured.webp',frame:frontFrame,slots:[{id:'front',q:frontPaperQuad},{id:'tray',sourceCrop:[0,0,.08,1],label:'内盘底左端露出',q:frontTrayQuad}]},
{name:'后视图（封底）',shell:'online-reference-v30/assets/open-outer-reference.png',frame:{source:[65,0,870,870],body:[105,165,830,675],closeRightFromLeft:true,destination:[.15,.23,.70,.70*45/53]},eyelets:outerEyelets.slice(0,1),slots:[{id:'back',q:[[.15+.70*2/53,.23+.70*3.5/53],[.85-.70*2/53,.23+.70*3.5/53],[.85-.70*2/53,.23+.70*41.5/53],[.15+.70*2/53,.23+.70*41.5/53]]}]},
{name:'左视图',shell:'online-reference-v30/assets/edge-views-atlas.png',frame:{source:[180,0,270,760],body:[267,128,93,517],destination:[.5-.60*8/45/2,.24,.60*8/45,.60]},slots:[{id:'leftSpine',q:[[.4707,.2867],[.5293,.2867],[.5293,.7933],[.4707,.7933]]}]},
{name:'右视图',shell:'online-reference-v30/assets/edge-views-atlas.png',frame:{source:[807,0,270,760],body:[894,128,93,517],destination:[.5-.60*8/45/2,.24,.60*8/45,.60]},slots:[{id:'rightSpine',q:[[.4707,.2867],[.5293,.2867],[.5293,.7933],[.4707,.7933]]}]},
{name:'展开内侧（平铺）',shell:'online-reference-v30/assets/open-inner-reference.png',frame:openFrame,slots:[{id:'inside',q:openQuad([150,220,660,550])},{id:'tray',q:openQuad([875,230,740,540])}]},
{name:'展开外侧（平铺）',shell:'online-reference-v30/assets/open-outer-reference.png',frame:openFrame,eyelets:outerEyelets,slots:[{id:'back',q:openQuad([140,220,755,565])},{id:'front',q:openQuad([985,220,640,590])}]},
{name:'45°斜视图（闭合）',shell:'online-reference-v30/assets/closed-oblique.png',slots:[{id:'front',q:[[.306,.258],[.797,.208],[.796,.725],[.306,.785]]},{id:'leftSpine',q:[[.177,.284],[.202,.300],[.202,.786],[.177,.77]]},{id:'tray',sourceCrop:[0,0,.08,1],label:'内盘底左端露出',q:[[.221,.292],[.254,.285],[.254,.774],[.221,.789]]}]},
{name:'展开内侧（装盘）',shell:'online-reference-v30/assets/open-inner-reference.png',frame:openFrame,hardware:{shell:'online-reference-v30/assets/transparent-tray-reference.jpg',source:[140,65,1140,965],q:openQuad([850,195,795,610])},slots:[{id:'inside',q:openQuad([150,220,660,550])},{id:'tray',q:openQuad([875,230,740,540])},{id:'disc',q:openQuad([1301-740*40/49/2,503-540*40/38/2,740*40/49,540*40/38]),inBox:true}]},
{shell:'online-reference-v30/assets/shell-2.webp',name:'取盘展示',slots:[{id:'inside',q:[[.102,.337],[.417,.268],[.483,.546],[.173,.614]]},{id:'tray',q:[[.523,.247],[.824,.173],[.880,.448],[.569,.525]]},{id:'disc',q:[[.614,.571],[.932,.571],[.932,.885],[.614,.885]]}]},
{shell:'online-reference-v30/assets/shell-3.webp',name:'立体内侧',slots:[{id:'inside',q:[[.09,.448],[.437,.31],[.441,.551],[.115,.711]]},{id:'tray',q:[[.525,.30],[.910,.376],[.882,.638],[.526,.555]]},{id:'disc',q:[[.525,.30],[.910,.376],[.882,.638],[.526,.555]],inBox:true}]},
{shell:'online-reference-v30/assets/shell-4.webp',name:'立体外侧',slots:[{id:'back',q:[[.139,.273],[.431,.458],[.432,.707],[.162,.536]]},{id:'front',q:[[.526,.47],[.85,.338],[.838,.568],[.526,.715]]}]},
];
export const defaultTransform=()=>({fit:'cover',scale:100,x:0,y:0,rotation:0});
export function initialState(){return {version:1,layoutRevision:9,sideReferenceApplied:false,viewSet:'eight-v1',title:'未命名专辑',view:0,selected:'front',showDesign:true,lighting:true,discVisible:false,background:'#ffffff',assets:Object.fromEntries(surfaces.map(s=>[s.id,{src:null,...defaultTransform()}])),quads:{}}}
export function validQuad(q){if(!Array.isArray(q)||q.length!==4||!q.every(p=>Array.isArray(p)&&p.length===2&&p.every(n=>Number.isFinite(n)&&n>=0&&n<=1)))return false;const cross=q.map((p,i)=>{const b=q[(i+1)%4],c=q[(i+2)%4];return(b[0]-p[0])*(c[1]-b[1])-(b[1]-p[1])*(c[0]-b[0])});return cross.every(n=>n>.0002)||cross.every(n=>n<-.0002)}
export function sanitizeState(data){
 if(!data||data.version!==1||!data.assets)throw Error('这不是有效的 Mini CD 项目文件');
 const st=initialState();st.sideReferenceApplied=data.sideReferenceApplied===true;st.title=String(data.title||st.title).slice(0,60);const legacy=data.viewSet!=='eight-v1',map=[0,7,8,9,10],rawView=Number.isInteger(data.view)?data.view:0;st.view=legacy?(map[rawView]??0):(rawView===11?5:rawView>=0&&rawView<views.length?rawView:0);st.selected=surfaces.some(s=>s.id===data.selected)?data.selected:'front';
 for(const key of ['showDesign','lighting','discVisible'])if(typeof data[key]==='boolean')st[key]=data[key];if(['#ffffff','#f0efec','#e8edf0'].includes(data.background))st.background=data.background;
 for(const s of surfaces){const a=data.assets[s.id];if(!a)continue;const t=st.assets[s.id];if(typeof a.src==='string'&&/^data:image\/(png|jpeg|webp);base64,/.test(a.src)&&a.src.length<30000000)t.src=a.src;t.fit=a.fit==='contain'?'contain':'cover';for(const [key,min,max]of[['scale',25,250],['x',-100,100],['y',-100,100],['rotation',-180,180]])t[key]=Math.min(max,Math.max(min,Number(a[key])|| (key==='scale'?100:0)));}
 for(const [key,q]of Object.entries(data.quads||{})){const match=/^(\d{1,2}):(front|back|inside|tray|disc|leftSpine|rightSpine|leftSpineInner)$/.exec(key);if(!match)continue;const index=legacy?map[+match[1]]:(+match[1]===11?5:+match[1]),id=match[2];if(!views[index]?.slots.some(s=>s.id===id))continue;if(index===0&&data.layoutRevision<4)continue;if([1,7].includes(index)&&data.layoutRevision<7)continue;if(!validQuad(q))continue;const mapped=index===0&&data.layoutRevision<9?rebaseFrontQuad(id,q):q;if(validQuad(mapped))st.quads[`${index}:${id}`]=mapped;}
 return st;
}
const dbReady=new Promise((resolve,reject)=>{const req=indexedDB.open('mini-cd-studio',1);req.onupgradeneeded=()=>req.result.createObjectStore('projects');req.onsuccess=()=>resolve(req.result);req.onerror=()=>reject(req.error)});dbReady.catch(()=>{});
export async function persist(state){const db=await dbReady;await new Promise((resolve,reject)=>{const tx=db.transaction('projects','readwrite');tx.objectStore('projects').put(state,'current');tx.oncomplete=resolve;tx.onerror=()=>reject(tx.error)})}
export async function restore(){const db=await dbReady;return new Promise((resolve,reject)=>{const r=db.transaction('projects').objectStore('projects').get('current');r.onsuccess=()=>resolve(r.result?sanitizeState(r.result):null);r.onerror=()=>reject(r.error)})}
export function loadImage(src){return new Promise((resolve,reject)=>{const img=new Image();img.onload=()=>resolve(img);img.onerror=()=>reject(Error('图片无法读取'));img.src=src})}
export async function readUpload(file){if(!['image/png','image/jpeg','image/webp'].includes(file.type))throw Error('请选择 PNG、JPG 或 WebP 图片');if(file.size>20*1024*1024)throw Error('图片不能超过20MB');const url=URL.createObjectURL(file);try{const img=await loadImage(url);const factor=Math.min(1,2400/Math.max(img.width,img.height));const c=document.createElement('canvas');c.width=Math.round(img.width*factor);c.height=Math.round(img.height*factor);c.getContext('2d').drawImage(img,0,0,c.width,c.height);return c.toDataURL(file.type==='image/png'?'image/png':'image/jpeg',.94)}finally{URL.revokeObjectURL(url)}}
