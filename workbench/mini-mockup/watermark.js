const defaults={enabled:false,mode:'text',text:'',logo:null,color:'#666666',size:20,opacity:25,rotation:0,position:'bottom-right',tile:false};
const positions=['top-left','top','top-right','left','center','right','bottom-left','bottom','bottom-right'];
const logos=new Map();let dbPromise;
export function normalizeWatermark(value={}){
 const w={...defaults},v=value&&typeof value==='object'?value:{};
 for(const k of ['enabled','tile'])w[k]=v[k]===true;
 if(['text','logo','both'].includes(v.mode))w.mode=v.mode;
 w.text=String(v.text||'').replace(/[\r\n]+/g,' ').slice(0,100);
 if(typeof v.logo==='string'&&/^data:image\/(png|jpeg|webp);base64,/.test(v.logo)&&v.logo.length<3000000)w.logo=v.logo;
 if(/^#[\da-f]{6}$/i.test(v.color))w.color=v.color;
 if(positions.includes(v.position))w.position=v.position;
 for(const [k,min,max] of [['size',5,35],['opacity',5,100],['rotation',-60,60]])if(Number.isFinite(Number(v[k])))w[k]=Math.max(min,Math.min(max,Number(v[k])));
 return w;
}
export async function prepareWatermark(value){
 const w=normalizeWatermark(value);if(!w.logo||logos.has(w.logo))return;
 const img=new Image();await new Promise((resolve,reject)=>{img.onload=resolve;img.onerror=()=>reject(Error('Logo 图片无法读取'));img.src=w.logo});
 logos.set(w.logo,img);
}
export function drawWatermark(canvas,value){
 const w=normalizeWatermark(value);if(!w.enabled)return;
 const text=w.mode!=='logo'?w.text:'',logo=w.mode!=='text'?logos.get(w.logo):null;if(!text&&!logo)return;
 const ctx=canvas.getContext('2d'),unit=Math.min(canvas.width,canvas.height),width=unit*w.size/100;
 ctx.save();ctx.setTransform(1,0,0,1,0,0);ctx.globalCompositeOperation='source-over';ctx.globalAlpha=w.opacity/100;
 ctx.fillStyle=w.color;ctx.textAlign='center';ctx.textBaseline='middle';ctx.font=`500 ${unit*.04}px "Microsoft YaHei",sans-serif`;
 let fontSize=unit*.04;if(text){fontSize*=width/Math.max(1,ctx.measureText(text).width);ctx.font=`500 ${fontSize}px "Microsoft YaHei",sans-serif`}
 const lw=logo?Math.min(width,unit*.20*logo.width/logo.height):0,lh=logo?lw*logo.height/logo.width:0;
 const gap=text&&logo?unit*.012:0,height=lh+gap+(text?fontSize*1.3:0),textWidth=text?ctx.measureText(text).width:0;
 const angle=w.rotation*Math.PI/180,boxW=Math.max(lw,textWidth),boxH=height;
 const boundX=(Math.abs(Math.cos(angle))*boxW+Math.abs(Math.sin(angle))*boxH)/2;
 const boundY=(Math.abs(Math.sin(angle))*boxW+Math.abs(Math.cos(angle))*boxH)/2;
 const stamp=(px,py)=>{ctx.save();ctx.translate(px,py);ctx.rotate(angle);if(logo)ctx.drawImage(logo,-lw/2,-height/2,lw,lh);if(text)ctx.fillText(text,0,-height/2+lh+gap+fontSize*.65);ctx.restore()};
 if(w.tile){const dx=Math.max(boxW*1.6,unit*.24),dy=Math.max(boxH*2.2,unit*.20);for(let row=0,py=dy/2;py<canvas.height;row++,py+=dy)for(let px=dx/2+(row%2)*dx/2;px<canvas.width;px+=dx)stamp(px,py)}
 else{const margin=unit*.035;const px=w.position.includes('left')?margin+boundX:w.position.includes('right')?canvas.width-margin-boundX:canvas.width/2;const py=w.position.startsWith('top')?margin+boundY:w.position.startsWith('bottom')?canvas.height-margin-boundY:canvas.height/2;stamp(px,py)}
 ctx.restore();
}
function database(){return dbPromise??=new Promise((resolve,reject)=>{const req=indexedDB.open('mini-cd-watermark',1);req.onupgradeneeded=()=>req.result.createObjectStore('settings');req.onsuccess=()=>resolve(req.result);req.onerror=()=>reject(req.error)})}
export async function loadWatermark(){const db=await database();return new Promise((resolve,reject)=>{const r=db.transaction('settings').objectStore('settings').get('shared');r.onsuccess=()=>resolve(normalizeWatermark(r.result));r.onerror=()=>reject(r.error)})}
export async function saveWatermark(value){const db=await database();await new Promise((resolve,reject)=>{const tx=db.transaction('settings','readwrite');tx.objectStore('settings').put(normalizeWatermark(value),'shared');tx.oncomplete=resolve;tx.onerror=()=>reject(tx.error)});try{localStorage.setItem('product-watermark-revision',Date.now()+':'+Math.random())}catch{}}
export function subscribeWatermark(callback){const listener=e=>{if(e.key==='product-watermark-revision')callback()};window.addEventListener('storage',listener);return()=>window.removeEventListener('storage',listener)}
