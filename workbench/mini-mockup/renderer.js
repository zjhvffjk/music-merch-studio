import * as online from './online-reference-v30/renderer.js';
import {drawWatermark} from './watermark.js';
import{views,viewScale,widestViewScale,loadImage,REMOVED_DISC_VIEW,removedDiscCase,mapRemovedDiscCase}from'./model.js';
export const BASE=1254;
const imgCache=new Map();const textureCache=new Map();let localResolution=1200;
export function shellThumbnail(view){const shell=imgCache.get(view===8?'shell-flat':`shell-${view}`);return shell?.toDataURL?.('image/png')||shell?.src||null}
// Use a single continuous photo so case highlights do not break at seams.
export function frontX(x,inverse=false){return x}
function calibrateFront(canvas){const copy=document.createElement('canvas');copy.width=canvas.width;copy.height=canvas.height;copy.getContext('2d').drawImage(canvas,0,0);const s=canvas.width/BASE,x=canvas.getContext('2d');x.save();x.setTransform(s,0,0,s,0,0);const a=[0,164,277,1090,BASE],b=a.map(v=>frontX(v));for(let i=0;i<4;i++)x.drawImage(copy,a[i]*s,0,(a[i+1]-a[i])*s,canvas.height,b[i],0,b[i+1]-b[i],BASE);x.restore()}
function repairFrontClip(c){const patch=document.createElement('canvas');patch.width=patch.height=BASE;const p=patch.getContext('2d');p.translate(423+890,0);p.scale(-1,1);p.drawImage(c,0,0);p.setTransform(1,0,0,1,0,0);p.globalCompositeOperation='destination-in';const g=p.createRadialGradient(890,320,28,890,320,72);g.addColorStop(0,'rgba(0,0,0,1)');g.addColorStop(.75,'rgba(0,0,0,1)');g.addColorStop(1,'rgba(0,0,0,0)');p.fillStyle=g;p.fillRect(818,248,144,144);c.getContext('2d').drawImage(patch,0,0)}
export async function preloadShells(){await online.preloadShells();await Promise.all(views.filter((v,i)=>v.onlineIndex===undefined&&i!==REMOVED_DISC_VIEW).map(async(v,i)=>{
  if(i!==0){const raw=await loadImage(`assets/shell-${i}.webp`);if(i!==1){imgCache.set(`shell-${i}`,raw);return}
    const c=document.createElement('canvas');c.width=raw.width;c.height=raw.height;const x=c.getContext('2d');x.drawImage(raw,0,0);
    // Match the eyelets to the front relative to case height, retaining the photographed rail.
    for(const cx of [367,881]){const left=cx-70,top=325,width=140,height=90,base=top+height,factor=.96;x.fillStyle='#fff';x.fillRect(left,top,width,height);x.imageSmoothingQuality='high';x.drawImage(raw,left,top,width,height,cx-width*factor/2,base-height*factor,width*factor,height*factor)}
    imgCache.set(`shell-${i}`,c);return}
  // Keep the photographed frame, hanger and left slot from the supplied
  // reference. The generated blank replaces only the printed central window.
  const img=await loadImage('assets/online-front-cover-hq-v3.png');
  const c=document.createElement('canvas');c.width=c.height=BASE;const x=c.getContext('2d');
  x.fillStyle='#fff';x.fillRect(0,0,BASE,BASE);
  const [bx,by,bw,bh]=[170,285,910,745], [dx,dy,dw,dh]=[.15,.23,.70,.70*45/53].map(n=>n*BASE),cut=290,sy=dh/bh,spineWidth=dw*8/53,leftScale=spineWidth/(cut-bx),rightScale=(dw-spineWidth)/(bx+bw-cut);
  x.drawImage(img,0,0,cut,img.height,dx-bx*leftScale,dy-by*sy,cut*leftScale,img.height*sy);
  x.drawImage(img,cut,0,img.width-cut,img.height,dx+spineWidth,dy-by*sy,(img.width-cut)*rightScale,img.height*sy);
  imgCache.set('shell-0',c);
}));
  // The flat view uses the installed view's photographed case. Replace only
  // the right carrier with the empty inner shell, keeping the lid identical.
  const empty=await loadImage('online-reference-v30/assets/open-inner-reference.png');
  const flat=document.createElement('canvas');flat.width=flat.height=BASE;
  const fx=flat.getContext('2d');fx.drawImage(imgCache.get('shell-1'),0,0);
  const patch=document.createElement('canvas');patch.width=530;patch.height=500;
  const px=patch.getContext('2d',{willReadFrequently:true});px.drawImage(empty,830,170,835,650,0,0,530,500);
  const pixels=px.getImageData(0,0,530,500),fade=18;
  for(let y=0;y<500;y++)for(let x=0;x<530;x++){
    const edge=Math.min(x,529-x,y,499-y),t=Math.min(1,edge/fade),alpha=t*t*(3-2*t);
    pixels.data[(y*530+x)*4+3]=Math.round(pixels.data[(y*530+x)*4+3]*alpha);
  }
  px.putImageData(pixels,0,0);fx.drawImage(patch,660,415);
  imgCache.set('shell-flat',flat);
}
const onlineId=id=>({sideL:'leftSpine',sideR:'rightSpine',sideLB:'leftSpineInner'}[id]||id);
export async function prepareAsset(id,src){await online.prepareAsset(onlineId(id),src);textureCache.delete(id);if(src)imgCache.set(id,await loadImage(src));else imgCache.delete(id)}
export async function prepareProjectAssets(assets){await online.prepareProjectAssets(Object.fromEntries(Object.entries(assets).map(([id,a])=>[onlineId(id),a])));const entries=await Promise.all(Object.entries(assets).map(async([id,a])=>[id,a.src?await loadImage(a.src):null]));for(const[id,img]of entries){textureCache.delete(id);if(img)imgCache.set(id,img);else imgCache.delete(id)}}
export function invalidate(id){online.invalidate(onlineId(id));textureCache.delete(id)}
export function getQuad(state,view,slot){
 const custom=state.quads[`${view}:${slot.id}`];
 if(custom)return custom;
 if(view===REMOVED_DISC_VIEW&&slot.id!=='disc'){
   const installedSlot=views[1].slots.find(s=>s.id===slot.id);
   return mapRemovedDiscCase(getQuad(state,1,installedSlot));
 }
 return slot.q;
}
function texture(state,id,plain=false){const a=state.assets[id],img=imgCache.get(id);if(!a?.src||!img)return null;const sz=Math.min(8192,Math.max(1200,Math.min(localResolution,Math.max(img.width,img.height)))),key=JSON.stringify([a,state.lighting,plain,sz]);const cached=textureCache.get(id);if(cached?.key===key)return cached.canvas;
const c=document.createElement('canvas');const w=id.startsWith('side')?Math.round(sz*4.4/38):['back','tray'].includes(id)?Math.round(sz*49/38):sz;c.width=w;c.height=sz;const x=c.getContext('2d');const factor=(a.fit==='contain'?Math.min(w/img.width,sz/img.height):Math.max(w/img.width,sz/img.height))*a.scale/100;
x.save();x.translate(w/2+a.x/100*w/2,sz/2+a.y/100*sz/2);x.rotate(a.rotation*Math.PI/180);x.drawImage(img,-img.width*factor/2,-img.height*factor/2,img.width*factor,img.height*factor);x.restore();
if(id!=='disc'&&id!=='inside'&&!plain&&state.lighting){
  // Light falls on the inserted paper as well as the case. Keep this subtle:
  // the uploaded artwork remains the source of its colour and detail.
  x.save();x.globalCompositeOperation='source-atop';
  const shade=x.createLinearGradient(0,0,w,sz);shade.addColorStop(0,'rgba(0,0,0,.035)');shade.addColorStop(.48,'rgba(0,0,0,0)');shade.addColorStop(1,'rgba(0,0,0,.055)');x.fillStyle=shade;x.fillRect(0,0,w,sz);
  const reflection=x.createLinearGradient(0,0,w,sz*.45);reflection.addColorStop(0,'rgba(255,255,255,0)');reflection.addColorStop(.22,'rgba(255,255,255,.065)');reflection.addColorStop(.48,'rgba(255,255,255,0)');x.fillStyle=reflection;x.fillRect(0,0,w,sz);
  const edge=x.createLinearGradient(0,0,0,sz);edge.addColorStop(0,'rgba(0,0,0,.16)');edge.addColorStop(.014,'rgba(0,0,0,0)');edge.addColorStop(.985,'rgba(0,0,0,0)');edge.addColorStop(1,'rgba(0,0,0,.10)');x.fillStyle=edge;x.fillRect(0,0,w,sz);x.restore();
}
if(id==='disc'){
  if(state.lighting&&!plain){x.save();x.globalCompositeOperation='source-atop';const g=x.createLinearGradient(0,0,sz,sz*.7);g.addColorStop(0,'rgba(0,0,0,.12)');g.addColorStop(.38,'rgba(255,255,255,.13)');g.addColorStop(.55,'rgba(255,255,255,0)');g.addColorStop(1,'rgba(0,0,0,.12)');x.fillStyle=g;x.fillRect(0,0,sz,sz);x.strokeStyle='rgba(255,255,255,.55)';x.lineWidth=3;x.beginPath();x.arc(sz/2,sz/2,sz*.487,0,Math.PI*2);x.stroke();x.restore()}
  x.globalCompositeOperation='destination-in';x.beginPath();x.arc(sz/2,sz/2,sz*.492,0,Math.PI*2);x.fill();x.globalCompositeOperation='destination-out';x.beginPath();x.arc(sz/2,sz/2,sz*.0625,0,Math.PI*2);x.fill();
}
textureCache.set(id,{key,canvas:c});while(textureCache.size>3)textureCache.delete(textureCache.keys().next().value);return c}
function project(q,u,v){const [p0,p1,p2,p3]=q;const dx1=p1[0]-p2[0],dx2=p3[0]-p2[0],dx3=p0[0]-p1[0]+p2[0]-p3[0],dy1=p1[1]-p2[1],dy2=p3[1]-p2[1],dy3=p0[1]-p1[1]+p2[1]-p3[1];let g=0,h=0;const den=dx1*dy2-dx2*dy1;if(Math.abs(den)>1e-9){g=(dx3*dy2-dx2*dy3)/den;h=(dx1*dy3-dx3*dy1)/den}const a=p1[0]-p0[0]+g*p1[0],b=p3[0]-p0[0]+h*p3[0],d=p1[1]-p0[1]+g*p1[1],e=p3[1]-p0[1]+h*p3[1];const z=g*u+h*v+1;return[(a*u+b*v+p0[0])/z,(d*u+e*v+p0[1])/z]}
function triangle(ctx,img,s,d){const[x0,y0]=s[0],[x1,y1]=s[1],[x2,y2]=s[2],[u0,v0]=d[0],[u1,v1]=d[1],[u2,v2]=d[2];const den=x0*(y1-y2)+x1*(y2-y0)+x2*(y0-y1);if(Math.abs(den)<1e-9)return;const a=(u0*(y1-y2)+u1*(y2-y0)+u2*(y0-y1))/den,b=(v0*(y1-y2)+v1*(y2-y0)+v2*(y0-y1))/den,c=(u0*(x2-x1)+u1*(x0-x2)+u2*(x1-x0))/den,dv=(v0*(x2-x1)+v1*(x0-x2)+v2*(x1-x0))/den,e=(u0*(x1*y2-x2*y1)+u1*(x2*y0-x0*y2)+u2*(x0*y1-x1*y0))/den,f=(v0*(x1*y2-x2*y1)+v1*(x2*y0-x0*y2)+v2*(x0*y1-x1*y0))/den;
ctx.save();ctx.beginPath();const mx=(u0+u1+u2)/3,my=(v0+v1+v2)/3;const grow=(u,v)=>{const l=Math.hypot(u-mx,v-my)||1;return[u+(u-mx)/l*.8,v+(v-my)/l*.8]};ctx.moveTo(...grow(u0,v0));ctx.lineTo(...grow(u1,v1));ctx.lineTo(...grow(u2,v2));ctx.closePath();ctx.clip();ctx.transform(a,b,c,dv,e,f);ctx.drawImage(img,0,0);ctx.restore()}
export function warp(ctx,img,quad,sourceX=0){const n=14,q=quad.map(p=>p.map(x=>x*BASE));ctx.save();ctx.beginPath();q.forEach((p,i)=>i?ctx.lineTo(...p):ctx.moveTo(...p));ctx.closePath();ctx.clip();for(let row=0;row<n;row++)for(let col=0;col<n;col++){const u=col/n,v=row/n,un=(col+1)/n,vn=(row+1)/n;const uv=[[u,v],[un,v],[un,vn],[u,vn]],src=uv.map(([s,t])=>[(sourceX+(1-sourceX)*s)*img.width,t*img.height]),dst=uv.map(([s,t])=>project(q,s,t));triangle(ctx,img,[src[0],src[1],src[2]],[dst[0],dst[1],dst[2]]);triangle(ctx,img,[src[0],src[2],src[3]],[dst[0],dst[2],dst[3]])}ctx.restore()}
function blankDisc(){const c=document.createElement('canvas');c.width=c.height=1200;const x=c.getContext('2d'),g=x.createLinearGradient(0,0,1200,1200);g.addColorStop(0,'#c6ccd1');g.addColorStop(.3,'#eef0f0');g.addColorStop(.5,'#b4bac2');g.addColorStop(.72,'#dce2e4');g.addColorStop(1,'#b1b9bf');x.fillStyle=g;x.beginPath();x.arc(600,600,590,0,Math.PI*2);x.fill();x.globalCompositeOperation='destination-out';x.beginPath();x.arc(600,600,86,0,Math.PI*2);x.fill();return c}const blank=blankDisc();
let frontGlass;
const opticsCache=new Map();
function photoOptics(shell,view){
  if(opticsCache.has(view))return opticsCache.get(view);
  const c=document.createElement('canvas');c.width=c.height=BASE;const x=c.getContext('2d',{willReadFrequently:true});x.drawImage(shell,0,0,BASE,BASE);const d=x.getImageData(0,0,BASE,BASE);
  let diffuse;
  if(view>=3){const blur=document.createElement('canvas');blur.width=blur.height=BASE;const bx=blur.getContext('2d',{willReadFrequently:true});bx.filter='blur(14px)';bx.drawImage(shell,0,0,BASE,BASE);diffuse=bx.getImageData(0,0,BASE,BASE).data}
  // Empty photographic panels have a neutral grey backing. Remove that
  // backing while retaining the photographed plastic reflections and relief.
  for(let i=0;i<d.data.length;i+=4){
    const l=.2126*d.data[i]+.7152*d.data[i+1]+.0722*d.data[i+2];
    const neutral=diffuse ? .2126*diffuse[i]+.7152*diffuse[i+1]+.0722*diffuse[i+2] : 234;
    const delta=l-neutral,hi=delta>0;let a=hi?delta/Math.max(24,255-neutral)*.75:-delta/Math.max(90,neutral)*.95;
    if(view>=3)a=1-Math.exp(-2.3*a);
    d.data[i]=d.data[i+1]=d.data[i+2]=hi?255:0;d.data[i+3]=Math.round(Math.min(1,a)*255);
  }
  x.putImageData(d,0,0);opticsCache.set(view,c);return c;
}
function clipQuad(ctx,q){ctx.beginPath();q.forEach((p,i)=>i?ctx.lineTo(p[0]*BASE,p[1]*BASE):ctx.moveTo(p[0]*BASE,p[1]*BASE));ctx.closePath();ctx.clip()}
const surfaceLayer=document.createElement('canvas');surfaceLayer.width=surfaceLayer.height=BASE;
const discRelief=document.createElement('canvas');discRelief.width=discRelief.height=BASE;
function insertSurface(ctx,tx,q,id,sourceX=0){
  // Draw the artwork at the export resolution, not through the preview-sized layer.
  if(id!=='disc'){warp(ctx,tx,q,sourceX);return}
  const x=surfaceLayer.getContext('2d');x.clearRect(0,0,BASE,BASE);warp(x,tx,q);
  // Paper sits behind the clear shell: a drop shadow on the shell would
  // imply that the print floats above it. Only the raised disc casts one.
  ctx.save();if(id==='disc'){ctx.shadowColor='rgba(16,20,24,.22)';ctx.shadowBlur=1.4;ctx.shadowOffsetY=.7}ctx.drawImage(surfaceLayer,0,0);ctx.restore();
}
const insideMasks=new Map();
const insideRelief=document.createElement('canvas');insideRelief.width=insideRelief.height=BASE;
const projectedInsideMask=document.createElement('canvas');projectedInsideMask.width=projectedInsideMask.height=BASE;
function insideHardwareMask(view){
  if(insideMasks.has(view))return insideMasks.get(view);
  const c=document.createElement('canvas');c.width=c.height=1200;const x=c.getContext('2d');
  x.fillRect(0,0,1200,18);x.fillRect(0,1182,1200,18);x.fillRect(0,0,18,1200);x.fillRect(1182,0,18,1200);
  const centers=view===3?[.20,.88]:view===2?[.15,.87]:[.17,.87];
  for(const u of centers){for(const v of [0,1]){x.beginPath();x.ellipse(u*1200,v*1200,78,120,0,0,Math.PI*2);x.fill()}}
  insideMasks.set(view,c);return c;
}
function exposedPaperHardware(ctx,state,view,slot,shell){
  const q=getQuad(state,view,slot);
  // The reverse of the cover faces the open case directly. Only retaining
  // hardware and the rim sit in front of it; the broad lid lies behind it.
  warp(ctx,online.paperRecess(view,'inside',false),q);
  if(view===1||view===8){online.drawInsideRetainersOnQuad(ctx,q);return}
  const mask=projectedInsideMask.getContext('2d');mask.clearRect(0,0,BASE,BASE);warp(mask,insideHardwareMask(view),q);
  const x=insideRelief.getContext('2d');x.globalCompositeOperation='source-over';x.clearRect(0,0,BASE,BASE);x.drawImage(photoOptics(shell,view),0,0);
  x.globalCompositeOperation='destination-in';x.drawImage(projectedInsideMask,0,0);ctx.drawImage(insideRelief,0,0);
}
function overlayPlastic(ctx,state,view,slot,shell){
  const q=getQuad(state,view,slot);ctx.save();clipQuad(ctx,q);
  if(slot.id==='inside'){exposedPaperHardware(ctx,state,view,slot,shell);ctx.restore();return}
  if(view>=3)warp(ctx,online.paperRecess(view,slot.id,state.lighting),q);
  else if(view===0&&slot.id==='front'){
    // The cover is held beneath the rim, so its contact shadow falls inward.
    ctx.save();ctx.globalAlpha=.42;warp(ctx,online.paperRecess(view,slot.id,false),q);ctx.restore();
  }
  if(slot.id.startsWith('side')||(slot.id==='front'&&view===4)||slot.id==='tray'){
    ctx.drawImage(photoOptics(shell,view),0,0);
  }else if(slot.id==='back'){
    // An opaque back insert hides the tray ring and hub behind it.
    // Only the rim in front of the sheet contributes here.
    const inner=[[.025,.025],[.975,.025],[.975,.975],[.025,.975]].map(([u,v])=>project(q,u,v));
    ctx.beginPath();ctx.rect(0,0,BASE,BASE);inner.forEach((p,i)=>i?ctx.lineTo(p[0]*BASE,p[1]*BASE):ctx.moveTo(p[0]*BASE,p[1]*BASE));ctx.closePath();ctx.clip('evenodd');ctx.drawImage(photoOptics(shell,view),0,0);
  }
  ctx.restore();
}
function frontRetainers(shell){
  if(frontGlass)return frontGlass;
  const c=document.createElement('canvas');c.width=c.height=BASE;const x=c.getContext('2d',{willReadFrequently:true});x.drawImage(shell,0,0,BASE,BASE);
  const data=x.getImageData(0,0,BASE,BASE);
  const smooth=document.createElement('canvas');smooth.width=smooth.height=BASE;const sx=smooth.getContext('2d',{willReadFrequently:true});sx.filter='blur(7px)';sx.drawImage(shell,0,0,BASE,BASE);const soft=sx.getImageData(0,0,BASE,BASE).data;
  // Preserve the local outlines and highlights, removing the underlying
  // neutral backing so the paper stays visible through each retainer.
  for(let i=0;i<data.data.length;i+=4){const l=.2126*data.data[i]+.7152*data.data[i+1]+.0722*data.data[i+2];const b=.2126*soft[i]+.7152*soft[i+1]+.0722*soft[i+2];const d=l-b,light=d>0;const alpha=light?Math.min(.52,d/45):Math.min(.70,-d/75);data.data[i]=data.data[i+1]=data.data[i+2]=light?255:0;data.data[i+3]=Math.round(alpha*255)}
  x.putImageData(data,0,0);
  // Only the actual retaining tabs sit in front of the insert. The empty
  // case's tray ring and hub must never be projected through opaque paper.
  const mask=document.createElement('canvas');mask.width=mask.height=BASE;const m=mask.getContext('2d');
  m.beginPath();
  // Trace the retaining tabs themselves, rather than a large rounded patch
  // that also collects the neighbouring circular tray grooves.
  for(const cx of [427,903]){
    // Upper tabs are drawn separately as clean translucent arcs. Sampling
    // this area picks up dark printing and creates the stray black fragments.
    m.moveTo(cx-58,1022);m.lineTo(cx-58,995);
    m.bezierCurveTo(cx-58,965,cx-35,944,cx,943);
    m.bezierCurveTo(cx+35,944,cx+58,965,cx+58,995);
    m.lineTo(cx+58,1022);m.closePath();
  }
  m.fill();
  x.globalCompositeOperation='destination-in';x.filter='blur(1.2px)';x.drawImage(mask,0,0);x.filter='none';
  frontGlass=c;return c;
}
function drawDisc(ctx,state,quad){
 warp(ctx,online.clearDisc(1200),quad);
 const label=state.showDesign?texture(state,'disc',true):null;
 if(label)warp(ctx,label,quad);
 warp(ctx,online.clearDisc(1200,true),quad);
}
export function render(canvas,state,view=state.view,size=1254){
  localResolution=size;
  if(view===0||(views[view].onlineIndex!==undefined&&view!==8)){const onlineView=view===0?0:views[view].onlineIndex,assets=Object.fromEntries(Object.entries(state.assets).map(([id,a])=>[onlineId(id),a])),quads={};for(const slot of views[view].slots){const q=state.quads[`${view}:${slot.id}`];if(q)quads[`${onlineView}:${onlineId(slot.id)}`]=q}return online.render(canvas,{...state,assets,quads},onlineView,size)}
  if(canvas.width!==size||canvas.height!==size)canvas.width=canvas.height=size;
  const ctx=canvas.getContext('2d');ctx.setTransform(size/BASE,0,0,size/BASE,0,0);ctx.globalCompositeOperation='source-over';ctx.fillStyle=state.background;ctx.fillRect(0,0,BASE,BASE);
  const removed=view===REMOVED_DISC_VIEW,caseView=removed?1:view;
  const shell=imgCache.get(caseView===8?'shell-flat':`shell-${caseView}`);if(!shell)return;
  if(caseView===1||caseView===8){
    let caseState=state;
    if(removed){
      const {scale,x,y}=removedDiscCase;
      ctx.save();ctx.translate(x*BASE,y*BASE);ctx.scale(scale,scale);
      const quads={...state.quads};
      for(const slot of views[view].slots){
        const custom=quads[`${view}:${slot.id}`];
        if(slot.id!=='disc'&&custom)quads[`1:${slot.id}`]=mapRemovedDiscCase(custom,true);
      }
      caseState={...state,quads};
    }
    ctx.save();ctx.globalCompositeOperation='multiply';ctx.drawImage(shell,0,0,BASE,BASE);ctx.restore();
    if(state.showDesign){
      // The tray insert is one continuous sheet beneath the clear hinge.
      for(const slot of views[caseView].slots.filter(s=>s.id!=='disc')){
        const tx=texture(state,slot.id);if(!tx)continue;
        insertSurface(ctx,tx,getQuad(caseState,caseView,slot),slot.id);
        if(caseView===1||slot.id==='inside')overlayPlastic(ctx,caseState,caseView,slot,shell);
      }
    }
    if(view===1&&state.discVisible){
      const hub=[.724,.532,.067,.064,0];
      ctx.save();ctx.beginPath();ctx.ellipse(hub[0]*BASE,hub[1]*BASE,hub[2]*BASE,hub[3]*BASE,hub[4],0,Math.PI*2);ctx.clip();ctx.drawImage(photoOptics(shell,1),0,0);ctx.restore();
      const slot=views[1].slots.find(s=>s.id==='disc'),q=getQuad(state,1,slot);
      drawDisc(ctx,state,q);
    }
    if(removed){
      ctx.restore();
      const slot=views[view].slots.find(s=>s.id==='disc');
      drawDisc(ctx,state,getQuad(state,view,slot));
    }
    ctx.setTransform(1,0,0,1,0,0);return;
  }
  if(view===0){
    ctx.save();ctx.globalCompositeOperation='multiply';ctx.drawImage(shell,0,0,BASE,BASE);ctx.restore();
    if(state.showDesign){
      for(const slot of views[0].slots){const tx=texture(state,slot.id,slot.id==='front');if(tx)warp(ctx,tx,getQuad(state,0,slot))}
      if(state.lighting){ctx.save();ctx.globalCompositeOperation='multiply';ctx.drawImage(shell,0,0,BASE,BASE);ctx.restore()}
    }
    ctx.setTransform(1,0,0,1,0,0);return;
  }
  ctx.save();ctx.globalCompositeOperation='multiply';ctx.drawImage(shell,0,0,BASE,BASE);ctx.restore();
  if(state.showDesign){
    for(const slot of [...views[view].slots].sort((a,b)=>Number(b.id.startsWith('side'))-Number(a.id.startsWith('side')))){
      if(slot.inBox&&!state.discVisible)continue;let tx=texture(state,slot.id);if(!tx&&slot.inBox)tx=blank;if(!tx)continue;
      insertSurface(ctx,tx,getQuad(state,view,slot),slot.id);
      if(slot.id!=='disc')overlayPlastic(ctx,state,view,slot,shell);
      else if(view===2){const x=discRelief.getContext('2d');x.clearRect(0,0,BASE,BASE);x.globalCompositeOperation='source-over';x.drawImage(photoOptics(shell,view),0,0);x.globalCompositeOperation='destination-in';x.drawImage(surfaceLayer,0,0);ctx.drawImage(discRelief,0,0)}
    }
    // The real spindle is in front of both the tray insert and an installed
    // disc. Drawing it last prevents the artwork from erasing the holder.
    if(state.discVisible&&[1,3].includes(view)){
      const hub=view===1?[.724,.532,.067,.064,0]:[.713,.45,.066,.052,.20];
      ctx.save();ctx.beginPath();ctx.ellipse(hub[0]*BASE,hub[1]*BASE,hub[2]*BASE,hub[3]*BASE,hub[4],0,Math.PI*2);ctx.clip();ctx.drawImage(photoOptics(shell,view),0,0);ctx.restore();
    }
    if(view===0&&state.assets.front.src){
      // Foreground plastic clips remain visible even if studio lighting is off.
      ctx.save();ctx.beginPath();getQuad(state,view,views[view].slots[0]).forEach((p,i)=>i?ctx.lineTo(p[0]*BASE,p[1]*BASE):ctx.moveTo(p[0]*BASE,p[1]*BASE));ctx.closePath();ctx.clip();ctx.drawImage(frontRetainers(shell),0,0);ctx.restore();
      // Narrow specular outlines make the transparent retainers legible over
      // either light or dark artwork without covering the printed paper.
      ctx.save();clipQuad(ctx,getQuad(state,view,views[view].slots[0]));
      ctx.lineWidth=1.2;ctx.strokeStyle='rgba(255,255,255,.78)';
      for(const cx of [427,903]){
        ctx.beginPath();ctx.ellipse(cx,313,43,37,0,.12,Math.PI-.12);ctx.stroke();
        ctx.beginPath();ctx.ellipse(cx,999,43,36,0,Math.PI+.12,Math.PI*2-.12);ctx.stroke();
      }
      ctx.restore();
    }
  }
  ctx.setTransform(1,0,0,1,0,0);
  if(view===0)calibrateFront(canvas);
}
// Bounds of the photographed shell, including the hanger. The removed-disc
// bounds include the separate disc on the right.
const overviewBounds={
  0:[.148,.136,.850,.850],
  1:[.054,.269,.946,.742],
  5:[.150,.137,.850,.844],
  6:[.446,.154,.559,.873],
  7:[.446,.153,.555,.876],
  8:[.054,.269,.945,.743],
  9:[.103,.286,.897,.688],
  10:[.165,.086,.837,.894],
  [REMOVED_DISC_VIEW]:[.060,.340,.944,.667],
};

function drawNineViewOverview(canvas,state,size){
 const rows=[[0,1,5],[8,6,9],[10,7,REMOVED_DISC_VIEW]].map(row=>row.map(view=>{
   const [left,top,right,bottom]=overviewBounds[view];
   const height=bottom-top;
   return {view,left,top,height,aspect:(right-left)/height};
 }));
 const margin=size*.038,gapX=size*.024,gapY=size*.034,bleed=.06;
 const labelSize=Math.round(size*.016),labelGap=size*.006;
 const labelHeight=labelSize*1.3+labelGap;
 const widestRow=Math.max(...rows.map(row=>row.reduce((sum,item)=>sum+item.aspect+2*bleed,0)));
 const height=Math.min(
   (size-2*margin-2*gapX)/widestRow,
   (size-2*margin-2*gapY-3*labelHeight)/(3*(1+2*bleed))
 );
 const padding=height*bleed,imageHeight=height+2*padding;
 const rowHeight=imageHeight+labelHeight;
 canvas.width=canvas.height=size;
 const ctx=canvas.getContext('2d'),cell=document.createElement('canvas');
 ctx.fillStyle=state.background;ctx.fillRect(0,0,size,size);
 ctx.imageSmoothingQuality='high';
 ctx.fillStyle='#55534e';ctx.font=`${labelSize}px sans-serif`;
 ctx.textAlign='center';ctx.textBaseline='top';
 let y=(size-3*rowHeight-2*gapY)/2;
 for(const row of rows){
   const widths=row.map(item=>item.aspect*height+2*padding);
   const rowWidth=widths.reduce((sum,width)=>sum+width,0)+2*gapX;
   let x=(size-rowWidth)/2;
   for(const [index,item] of row.entries()){
     const width=widths[index],factor=height/item.height,sourceSize=Math.ceil(factor);
     render(cell,state,item.view,sourceSize);
     const ratio=sourceSize/factor;
     ctx.drawImage(cell,item.left*sourceSize-padding*ratio,item.top*sourceSize-padding*ratio,
       width*ratio,imageHeight*ratio,x,y,width,imageHeight);
     ctx.fillText(views[item.view].name,x+width/2,y+imageHeight+labelGap);
     x+=width+gapX;
   }
   y+=rowHeight+gapY;
 }
 cell.width=cell.height=0;
}

export async function exportPNG(state,size,mode){const c=document.createElement('canvas');if(mode==='current')render(c,state,state.view,size);else if(mode==='individual'){const cell=document.createElement('canvas'),side=size*viewScale(state.view)*Math.min(1,.90/widestViewScale(state.view));c.width=c.height=size;const x=c.getContext('2d');x.fillStyle=state.background;x.fillRect(0,0,size,size);render(cell,state,state.view,Math.ceil(side));x.drawImage(cell,(size-side)/2,(size-side)/2,side,side);cell.width=cell.height=0}else drawNineViewOverview(c,state,size);
drawWatermark(c,state.watermark);
return new Promise((resolve,reject)=>c.toBlob(b=>{c.width=c.height=0;b?resolve(b):reject(Error('导出失败，请尝试较小分辨率'))},'image/png'))}
export async function exportThreeViewPreview(state,size=8192){
 const c=document.createElement('canvas');c.width=c.height=size;
 const x=c.getContext('2d');x.fillStyle=state.background;x.fillRect(0,0,size,size);
 const layoutSize=Math.round(size*.82),margin=(size-layoutSize)/2;
 x.translate(margin,margin);
 const cell=document.createElement('canvas'),top=Math.round(layoutSize*.54),bottom=layoutSize-top,half=layoutSize/2;
 const openSide=Math.round(layoutSize*.90);
 render(cell,state,1,openSide);
 x.drawImage(cell,0,Math.round(openSide*.205),openSide,top,(layoutSize-openSide)/2,0,openSide,top);
 // Match the visible shell rails, not the paper apertures used by viewScale.
 // The open-case photograph's body is about 4% shorter after that conversion.
 const closedSide=Math.round(openSide/viewScale(1)*.96);
 for(const [view,column] of [[0,0],[5,1]]){
  render(cell,state,view,closedSide);
  x.drawImage(cell,(closedSide-half)/2,(closedSide-bottom)/2,half,bottom,column*half,top,half,bottom);
 }
 x.fillStyle='#55534e';x.font=`${Math.round(layoutSize*.025)}px sans-serif`;
 x.textAlign='center';x.textBaseline='middle';
 x.fillText(views[1].name,layoutSize/2,top-layoutSize*.016);
 for(const [view,column] of [[0,0],[5,1]])x.fillText(views[view].name,column*half+half/2,layoutSize*1.022);
 cell.width=cell.height=0;
 drawWatermark(c,state.watermark);
 return new Promise((resolve,reject)=>c.toBlob(b=>{c.width=c.height=0;b?resolve(b):reject(Error('三视图预览导出失败'))},'image/png'));
}

function drawBallChain(ctx,image,cx,cy,height){
 const width=height*image.naturalWidth/image.naturalHeight;
 ctx.save();
 ctx.shadowColor='rgba(24,28,32,.19)';
 ctx.shadowBlur=height*.017;
 ctx.shadowOffsetY=height*.009;
 ctx.translate(cx,cy);
 ctx.rotate(-Math.PI*50/180);
 ctx.drawImage(image,-width/2,-height/2,width,height);
 ctx.restore();
}

export async function exportAccessoryOverview(state,size=8192){
 const chain=imgCache.get('accessory-chain')||await loadImage('assets/silver-ball-chain.png');
 imgCache.set('accessory-chain',chain);
 const canvas=document.createElement('canvas');canvas.width=canvas.height=size;
 const ctx=canvas.getContext('2d');
 ctx.fillStyle=state.background;ctx.fillRect(0,0,size,size);
 ctx.imageSmoothingQuality='high';
 const cell=document.createElement('canvas');
 // Match the measured shell width in the two source photos and align their left rails.
 const scale=1.055;
 const horizontal=value=>.5+(value-.5)*scale;
 const vertical=value=>.5+(value-.51)*scale;
 const lower={side:.98*scale,x:horizontal(.01),y:vertical(.203)};
 const upperSide=.98*.607/.792;
 const upper={
   side:upperSide*scale,
   x:lower.x+lower.side*.066-upperSide*scale*.103,
   y:vertical(.137-upperSide*.306)
 };
 const rows=[
   {view:9,layout:upper,top:.22,bottom:.76},
   {view:REMOVED_DISC_VIEW,layout:lower,top:.28,bottom:.73}
 ];
 for(const {view,layout,top,bottom} of rows){
   const side=Math.round(size*layout.side),sourceSide=Math.min(size,side);
   const start=Math.floor(top*sourceSide),end=Math.ceil(bottom*sourceSide);
   const ratio=side/sourceSide;
   render(cell,state,view,sourceSide);
   ctx.drawImage(cell,0,start,sourceSide,end-start,size*layout.x,size*layout.y+start*ratio,side,(end-start)*ratio);
   cell.width=cell.height=0;
 }
 const disc=views[REMOVED_DISC_VIEW].slots.find(slot=>slot.id==='disc');
 const chainX=lower.x+lower.side*(disc.q[0][0]+disc.q[1][0])/2;
 drawBallChain(ctx,chain,chainX*size,vertical(.284)*size,.215*scale*size);
 const caseX=lower.x+lower.side*(.066+.673)/2;
 ctx.fillStyle='#55534e';
 ctx.font=`${Math.round(size*.020*scale)}px sans-serif`;
 ctx.textAlign='center';ctx.textBaseline='middle';
 ctx.fillText(views[9].name,caseX*size,vertical(.457)*size);
 ctx.fillText('银色珠链',chainX*size,vertical(.457)*size);
 ctx.fillText(views[REMOVED_DISC_VIEW].name,caseX*size,vertical(.888)*size);
 ctx.fillText('光盘',chainX*size,vertical(.888)*size);
 drawWatermark(canvas,state.watermark);
 return new Promise((resolve,reject)=>canvas.toBlob(blob=>{
   canvas.width=canvas.height=0;
   blob?resolve(blob):reject(Error('内外展开组合图导出失败'));
 },'image/png'));
}
