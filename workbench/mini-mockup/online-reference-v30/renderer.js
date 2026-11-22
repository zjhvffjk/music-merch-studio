import{views,surfaces,MAIN_VIEW_COUNT,DISC,loadImage,previewFrame}from'./model.js?rev=materials-23-neutral-tray';
import {
 composeFrontShell, frontRetainerMask, frontSideRetainerMask,
 frontSlotBounds, frontSlotWindow, prepareFrontEyelet,
} from '../front-shell.js';
import { replaceFlatCoverRetainers } from './flat-cover-retainers.js';
export const BASE=1254;
const imgCache=new Map();const textureCache=new Map();
let shellResolutionCache=null,textureResolution=1200;
export async function preloadShells(){await prepareInsideRetainers();
 const [front]=await Promise.all([loadImage(views[0].shell),prepareUnifiedHooks()]);
 imgCache.set('measured-eyelet',prepareFrontEyelet(front));
 return Promise.all(views.map(async(v,i)=>{
 let img=i===0?front:imgCache.get('unified-'+v.shell)||(v.shell==='online-reference-v30/assets/open-inner-reference.png'?imgCache.get('sharp-inner-shell'):await loadImage(v.shell||`online-reference-v30/assets/shell-${i}.webp`));
 if(v.redrawCoverRetainers)img=replaceFlatCoverRetainers(img,front);
 imgCache.set(`raw-shell-${i}`,img);imgCache.set(`shell-${i}`,composeShell(img,v,BASE));
 if(v.hardware){const raw=await loadImage(v.hardware.shell),[sx,sy,sw,sh]=v.hardware.source,c=document.createElement('canvas');c.width=sw;c.height=sh;c.getContext('2d').drawImage(raw,sx,sy,sw,sh,0,0,sw,sh);imgCache.set(`hardware-${i}`,transparentHardware(c))}
 }))}
function composeShell(img,v,size){
 if(v===views[0])return composeFrontShell(img,size);
 if(v.frame){const c=document.createElement('canvas');c.width=c.height=size;const x=c.getContext('2d');x.setTransform(size/BASE,0,0,size/BASE,0,0);x.imageSmoothingQuality='high';x.fillStyle='#ffffff';x.fillRect(0,0,BASE,BASE);
 const [bx,by,bw,bh]=v.frame.body,[dx,dy,dw,dh]=v.frame.destination.map(n=>n*BASE),sx=dw/bw,sy=dh/bh;
 if(v.frame.source){const [cx,cy,cw,ch]=v.frame.source;x.drawImage(img,cx,cy,cw,ch,dx+(cx-bx)*sx,dy+(cy-by)*sy,cw*sx,ch*sy)}
 else x.drawImage(img,dx-bx*sx,dy-by*sy,img.width*sx,img.height*sy);
 // The open photo continues into the hinge at right. Close the isolated rear with its own outer rail.
 if(v.frame.closeRightFromLeft){const rail=dw*2/53,cap=dh*3.5/45;
 x.drawImage(img,105,165,700,55,dx,dy,dw,cap);x.drawImage(img,105,785,700,55,dx,dy+dh-cap,dw,cap);
 // Flatten the old eyelet base in the stretched rear cap before mounting the measured one.
 x.drawImage(img,638,165,146,20,dx+(393-105)*dw/700,dy,(624-393)*dw/700,cap*20/55);
 x.drawImage(img,bx,by,45,bh,dx,dy,rail,dh);x.save();x.translate(dx+dw,dy);x.scale(-1,1);x.drawImage(img,bx,by,45,bh,0,0,rail,dh);x.restore();
 // Remove the remnant of the neighbouring open-shell rail above the rear's
 // top-right edge; keep the photographed border itself below the body line.
 x.fillStyle='#fff';x.fillRect(dx+dw*.72,dy-12,dw*.28+2,11.5)}
 if(v.eyelets){
   const eyelet=imgCache.get('measured-eyelet');
   const railY=dy+(165-by)*sy;
   // Both views use the same outside photograph, with a body 675 px tall.
   const pixelsPerMM=675*sy/45;
   x.fillStyle='#fff';
   for(const {center,clearLeft,clearRight} of v.eyelets){
     x.fillRect(dx+(clearLeft-bx)*sx,0,(clearRight-clearLeft)*sx,railY);
     const centerX=dx+(center-bx)*sx;
     x.drawImage(eyelet.canvas,centerX+eyelet.x*pixelsPerMM,railY+eyelet.y*pixelsPerMM,
       eyelet.width*pixelsPerMM,eyelet.height*pixelsPerMM);
   }
 }
 img=c}
 return img;
}
function renderShell(view,size){const raw=imgCache.get(`raw-shell-${view}`);if(!raw)return null;if(!views[view].frame)return raw;if(size===BASE)return imgCache.get(`shell-${view}`);if(shellResolutionCache?.view===view&&shellResolutionCache.size===size)return shellResolutionCache.canvas;const canvas=composeShell(raw,views[view],size);shellResolutionCache={view,size,canvas};return canvas}
export function shellThumbnail(view){
 const shell=imgCache.get(`shell-${view}`);
 return shell?.toDataURL?.('image/png')||shell?.src||null;
}
export async function prepareAsset(id,src){textureCache.delete(id);if(src)imgCache.set(id,await loadImage(src));else imgCache.delete(id)}
export async function prepareProjectAssets(assets){const entries=await Promise.all(Object.entries(assets).map(async([id,a])=>[id,a.src?await loadImage(a.src):null]));for(const[id,img]of entries){textureCache.delete(id);if(img)imgCache.set(id,img);else imgCache.delete(id)}}
export function invalidate(id){textureCache.delete(id)}
export function getQuad(state,view,slot){return state.quads[`${view}:${slot.id}`]||slot.q}
function texture(state,id){const a=state.assets[id],img=imgCache.get(id);if(!a?.src||!img)return null;const sz=Math.min(8192,Math.max(1200,Math.min(textureResolution,Math.max(img.width,img.height)))),key=sz+JSON.stringify(a);const cached=textureCache.get(id);if(cached?.key===key)return cached.canvas;
const c=document.createElement('canvas');const narrow=['leftSpine','rightSpine','leftSpineInner'].includes(id);const printSize=surfaces.find(s=>s.id===id)?.printSize,aspect=narrow?4.4/38:printSize?printSize[0]/printSize[1]:1;c.width=aspect<1?Math.round(sz*aspect):sz;c.height=aspect>1?Math.round(sz/aspect):sz;const x=c.getContext('2d'),tw=c.width,th=c.height; x.imageSmoothingQuality='high';const factor=(a.fit==='contain'?Math.min(tw/img.width,th/img.height):Math.max(tw/img.width,th/img.height))*a.scale/100;
if(narrow||printSize){x.fillStyle='#ffffff';x.fillRect(0,0,tw,th)}x.save();x.translate(tw/2+a.x/100*tw/2,th/2+a.y/100*th/2);x.rotate(a.rotation*Math.PI/180);x.drawImage(img,-img.width*factor/2,-img.height*factor/2,img.width*factor,img.height*factor);x.restore();
if(id==='disc'){x.globalCompositeOperation='destination-in';x.beginPath();x.arc(sz/2,sz/2,sz*DISC.labelDiameter/DISC.diameter/2,0,Math.PI*2);x.fill();x.globalCompositeOperation='destination-out';x.beginPath();x.arc(sz/2,sz/2,sz*DISC.holeDiameter/DISC.diameter/2,0,Math.PI*2);x.fill();}
textureCache.set(id,{key,canvas:c});while(textureCache.size>3)textureCache.delete(textureCache.keys().next().value);return c}
function slotTexture(state,slot){const full=texture(state,slot.id);if(!full||!slot.sourceCrop)return full;const key=slot.id+'-crop-'+slot.sourceCrop.join(','),cached=textureCache.get(key);if(cached?.source===full)return cached.canvas;const[x,y,w,h]=slot.sourceCrop,c=document.createElement('canvas');c.width=Math.max(1,Math.round(full.width*w));c.height=Math.max(1,Math.round(full.height*h));c.getContext('2d').drawImage(full,x*full.width,y*full.height,w*full.width,h*full.height,0,0,c.width,c.height);textureCache.set(key,{source:full,canvas:c});return c}
// Isolate local plastic edges and highlights from the photographed grey backdrop.
// A flat clear area becomes transparent, so adding the carrier cannot tint the paper below.
export function transparentHardware(c){const x=c.getContext('2d'),w=c.width,h=c.height,p=x.getImageData(0,0,w,h),stride=w+1,sum=new Float64Array(stride*(h+1)),gray=new Float32Array(w*h);
 for(let y=0;y<h;y++){let row=0;for(let a=0;a<w;a++){const i=y*w+a,k=i*4;gray[i]=(p.data[k]+p.data[k+1]+p.data[k+2])/3;row+=gray[i];sum[(y+1)*stride+a+1]=sum[y*stride+a+1]+row}}
 const localMean=(a,y,radius)=>{
   const l=Math.max(0,a-radius),r=Math.min(w,a+radius+1),t=Math.max(0,y-radius),b=Math.min(h,y+radius+1);
   return (sum[b*stride+r]-sum[t*stride+r]-sum[b*stride+l]+sum[t*stride+l])/((r-l)*(b-t));
 };
 for(let y=0;y<h;y++)for(let a=0;a<w;a++){
   const i=y*w+a,k=i*4,value=gray[i],delta=value-localMean(a,y,18),light=delta>0;
   const alpha=Math.min(light?210:190,Math.max(0,Math.abs(delta)-2)*(light?5:1.35));
   p.data[k]=p.data[k+1]=p.data[k+2]=light?255:55;
   p.data[k+3]=alpha;
 }
 x.putImageData(p,0,0);return c}

// A narrow ridge is lighter or darker than the pixels on both sides.
// Comparing both sides rejects the haze next to a dark edge in the photo.
function extractRetainerEdges(canvas){
 const ctx=canvas.getContext('2d');
 const {width,height}=canvas;
 const pixels=ctx.getImageData(0,0,width,height);
 const {data}=pixels;
 const luminance=new Float32Array(width*height);
 for(let i=0,k=0;i<luminance.length;i++,k+=4){
   luminance[i]=(data[k]+data[k+1]+data[k+2])/3;
 }
 const radius=4;
 const offsets=[radius,radius*width,radius*(width-1),radius*(width+1)];
 for(let y=0;y<height;y++)for(let x=0;x<width;x++){
   const i=y*width+x,k=i*4;
   let highlight=0,shadow=0;
   if(x>=radius&&x<width-radius&&y>=radius&&y<height-radius){
     for(const offset of offsets){
       const a=luminance[i-offset],b=luminance[i+offset],value=luminance[i];
       highlight=Math.max(highlight,value-Math.max(a,b));
       shadow=Math.max(shadow,Math.min(a,b)-value);
     }
   }
   const light=highlight>=shadow;
   const contrast=Math.max(0,(light?highlight:shadow)-5);
   data[k]=data[k+1]=data[k+2]=light?255:23;
   data[k+3]=Math.min(light?112:155,contrast*(light?2.7:2.15));
 }
 ctx.putImageData(pixels,0,0);
}
const recessCache=new Map();
export function paperRecess(view,id,lighting){
  const key=[view,id,lighting].join(':');if(recessCache.has(key))return recessCache.get(key);
  const c=document.createElement('canvas');c.width=c.height=1200;const x=c.getContext('2d');
  // The case lip casts inward onto the insert. This screen-independent
  // layer follows the receiving plane, not the uploaded image transform.
  const narrow=view===0&&id==='tray';
  for(const [x0,y0,x1,y1,depth,alpha]of[[0,0,0,1200,.024,.30],[0,1200,0,0,.018,.24],[0,0,1200,0,narrow?.12:.018,narrow?.34:.24],[1200,0,0,0,narrow?.10:.016,narrow?.30:.20]]){
    const g=x.createLinearGradient(x0,y0,x1,y1);g.addColorStop(0,`rgba(12,18,23,${alpha})`);g.addColorStop(depth,'rgba(12,18,23,0)');g.addColorStop(1,'rgba(12,18,23,0)');x.fillStyle=g;x.fillRect(0,0,1200,1200);
  }
  if(lighting&&id!=='back'){
    const g=x.createLinearGradient(0,0,1200,420);g.addColorStop(0,'rgba(255,255,255,.02)');g.addColorStop(.20,'rgba(255,255,255,.11)');g.addColorStop(.36,'rgba(255,255,255,.025)');g.addColorStop(.62,'rgba(255,255,255,0)');x.fillStyle=g;x.fillRect(0,0,1200,1200);
  }
  recessCache.set(key,c);return c;
}
function frontRimOptics(id='front'){
 const key=`front-rim-optics-${id}`;
 const cached=imgCache.get(key);
 if(cached)return cached;
 const canvas=document.createElement('canvas');canvas.width=canvas.height=BASE;
 const ctx=canvas.getContext('2d',{willReadFrequently:true});
 ctx.drawImage(imgCache.get('shell-0'),0,0);
 if(id==='front')extractRetainerEdges(canvas);
 else transparentHardware(canvas);
 const mask=document.createElement('canvas');mask.width=mask.height=BASE;
 const m=mask.getContext('2d');
 const [a,,c]=views[0].slots.find(slot=>slot.id===id).q;
 const [left,top]=a.map(n=>n*BASE),[right,bottom]=c.map(n=>n*BASE);
 const sideDepth=id==='tray'?5:10;
 for(const [x,y,dx,dy] of [[left,top,sideDepth,0],[right,top,-sideDepth,0],[left,top,0,12],[left,bottom,0,-10]]){
   const fade=m.createLinearGradient(x,y,x+dx,y+dy);
   fade.addColorStop(0,'#fff');fade.addColorStop(1,'#fff0');
   m.fillStyle=fade;
   m.fillRect(left,top,right-left,bottom-top);
 }
 if(id==='front'){
   m.fillStyle='#fff';
   m.fill(frontRetainerMask(BASE));
 }
 ctx.globalCompositeOperation='destination-in';
 ctx.drawImage(mask,0,0);
 imgCache.set(key,canvas);
 return canvas;
}
function drawFrontRecess(ctx,state){
 for(const slot of views[0].slots){
   if(!state.assets[slot.id].src)continue;
   const quad=getQuad(state,0,slot);
   ctx.save();
   ctx.clip(frontSlotWindow(slot.id,BASE));
   ctx.globalAlpha=slot.id==='tray'?.32:.48;
   warp(ctx,paperRecess(0,slot.id,false),quad);
   clipQuad(ctx,quad);
   // Match the open lid: white parts of the plastic do not tint the paper.
   ctx.globalCompositeOperation='multiply';
   ctx.globalAlpha=state.lighting?.72:.40;
   ctx.drawImage(frontRimOptics(slot.id),0,0);
   ctx.restore();
 }
}
function clipQuad(ctx,quad){
 ctx.beginPath();traceQuad(ctx,quad);ctx.clip();
}
function traceQuad(ctx,quad){
 quad.forEach(([x,y],i)=>i?ctx.lineTo(x*BASE,y*BASE):ctx.moveTo(x*BASE,y*BASE));
 ctx.closePath();
}
const exteriorPaper = new Set(['front','back','leftSpine','rightSpine','leftSpineInner']);
function hasExteriorRim(slot){
 return exteriorPaper.has(slot.id)||slot.sourceCrop;
}
function coverRimOptics(view){
 const key=`cover-rim-${view}`;
 const cached=imgCache.get(key);
 if(cached)return cached;

 // Keep the photographed clips and rails registered to their original angles.
 const edge=document.createElement('canvas');edge.width=edge.height=256;
 const e=edge.getContext('2d');
 const mask=document.createElement('canvas');mask.width=mask.height=BASE;
 const m=mask.getContext('2d');
 for(const slot of views[view].slots.filter(hasExteriorRim)){
   e.clearRect(0,0,256,256);
   const hasCoverClips=slot.id==='front';
   const depth=hasCoverClips?34:8, sides=hasCoverClips?22:8;
   for(const [x,y,dx,dy] of [[0,0,0,depth],[0,256,0,-depth],[0,0,sides,0],[256,0,-sides,0]]){
     const fade=e.createLinearGradient(x,y,x+dx,y+dy);
     fade.addColorStop(0,'#fff');fade.addColorStop(.75,'#fff');fade.addColorStop(1,'#fff0');
     e.fillStyle=fade;e.fillRect(0,0,256,256);
   }
   warp(m,edge,slot.q);
 }
 const rim=document.createElement('canvas');rim.width=rim.height=BASE;
 const r=rim.getContext('2d',{willReadFrequently:true});
 r.drawImage(imgCache.get(`shell-${view}`),0,0,BASE,BASE);
 extractRetainerEdges(rim);
 r.globalCompositeOperation='destination-in';
 r.drawImage(mask,0,0);
 imgCache.set(key,rim);
 return rim;
}
function obliqueSideRetainers(slot){
 const key='oblique-side-retainers';
 const cached=imgCache.get(key);
 if(cached)return cached;

 // Project the four measured side clips into the closed cover plane.
 const [x,y,w,h]=frontSlotBounds('front',BASE);
 const source=document.createElement('canvas');source.width=Math.ceil(w);source.height=Math.ceil(h);
 const s=source.getContext('2d');
 s.translate(-x,-y);
 s.clip(frontSideRetainerMask(BASE));
 s.drawImage(frontRimOptics(),0,0);
 const layer=document.createElement('canvas');layer.width=layer.height=BASE;
 warp(layer.getContext('2d'),source,slot.q);
 imgCache.set(key,layer);
 return layer;
}
function drawExteriorPaperRims(ctx,state,view){
 for(const slot of views[view].slots){
   if(!hasExteriorRim(slot))continue;
   const quad=state.showDesign&&state.assets[slot.id]?.src?getQuad(state,view,slot):null;
   const side=slot.measuredSideRetainers?obliqueSideRetainers(slot):null;
   if(quad){
     ctx.save();
     clipQuad(ctx,quad);
     ctx.globalCompositeOperation='multiply';
     ctx.globalAlpha=state.lighting?.95:.60;
     ctx.drawImage(coverRimOptics(view),0,0);
     if(side)ctx.drawImage(side,0,0);
     ctx.restore();
   }
   if(side){
     // The same clip may cross onto bare plastic when the paper is adjusted.
     ctx.save();
     if(quad){
       ctx.beginPath();ctx.rect(0,0,BASE,BASE);traceQuad(ctx,quad);ctx.clip('evenodd');
     }
     ctx.globalAlpha=state.lighting?.95:.60;
     ctx.drawImage(side,0,0);
     ctx.restore();
   }
 }
}
function drawFrontArtwork(ctx,state){
 if(!state.showDesign)return;
 for(const slot of views[0].slots){
   const image=slotTexture(state,slot);
   if(!image)continue;
   ctx.save();
   ctx.clip(frontSlotWindow(slot.id,BASE));
   warp(ctx,image,getQuad(state,0,slot));
   ctx.restore();
 }
 drawFrontRecess(ctx,state);
}
function drawHardware(ctx,view){const hw=views[view].hardware,img=imgCache.get(`hardware-${view}`);if(!hw||!img)return;ctx.save();ctx.globalCompositeOperation='source-over';warp(ctx,img,hw.q);ctx.restore()}
// The four retainers sit on the inner face of the cover paper. Extract only their shapes,
// so putting them over the print does not put the photo's grey base over the paper.
async function prepareInsideRetainers(){
 const [raw,sharp]=await Promise.all([loadImage('online-reference-v30/assets/open-inner-reference.png'),loadImage('online-reference-v30/assets/front-cover-hq-v3.png')]);
 const c=document.createElement('canvas');c.width=660;c.height=550;const x=c.getContext('2d');
 const shell=document.createElement('canvas');shell.width=raw.width;shell.height=raw.height;const s=shell.getContext('2d');s.drawImage(raw,0,0);
 const parts=[{dst:[226,218,88,46],bottom:false},{dst:[676,218,88,46],bottom:false},{dst:[226,728,88,46],bottom:true},{dst:[676,728,88,46],bottom:true}];
 for(const p of parts){const [dx,dy,w,h]=p.dst,patch=document.createElement('canvas');patch.width=w;patch.height=h;const px=patch.getContext('2d');if(p.bottom){px.translate(0,h);px.scale(1,-1)}px.beginPath();px.ellipse(w/2,0,w/2,w/2,0,0,Math.PI*2);px.clip();px.drawImage(sharp,394,330,88,46,0,0,w,h);
  // Replace the photographed blurred tab with the adjacent clear panel before applying the sharp tab.
  const left=s.getImageData(dx-2,dy,1,h).data,right=s.getImageData(dx+w+1,dy,1,h).data,fill=s.createImageData(w,h);
  for(let row=0;row<h;row++)for(let col=0;col<w;col++){const t=(col+1)/(w+1),idx=(row*w+col)*4;for(let channel=0;channel<3;channel++)fill.data[idx+channel]=Math.round(left[row*4+channel]*(1-t)+right[row*4+channel]*t);fill.data[idx+3]=255}s.putImageData(fill,dx,dy);
  s.save();s.globalCompositeOperation='multiply';s.drawImage(patch,dx,dy);s.restore();
  x.drawImage(patch,dx-150,dy-220);
 }
 imgCache.set('inside-retainers',c);imgCache.set('sharp-inner-shell',shell);
}
function drawInsideRetainers(ctx,state,view){const slot=views[view].slots.find(s=>s.id==='inside'),img=imgCache.get('inside-retainers');if(!slot||!img||!state.assets.inside.src)return;ctx.save();ctx.globalCompositeOperation='multiply';warp(ctx,img,getQuad(state,view,slot));ctx.restore()}
export function drawInsideRetainersOnQuad(ctx,quad){const img=imgCache.get('inside-retainers');if(!img)return;ctx.save();ctx.globalCompositeOperation='multiply';warp(ctx,img,quad);ctx.restore()}
// Preserve the established optical layers for the other camera angles.
async function prepareUnifiedHooks(){const front=await loadImage('online-reference-v30/assets/front-cover-hq-v3.png'),hook=document.createElement('canvas');hook.width=235;hook.height=145;hook.getContext('2d').drawImage(front,510,140,235,145,0,0,235,145);
 // Reduce the photographed oblique eyelet around its attachment point; the
 // sloping rail is excluded from the edit so its perspective stays intact.
 const angled=await loadImage('online-reference-v30/assets/closed-oblique.png'),adjusted=document.createElement('canvas');adjusted.width=angled.width;adjusted.height=angled.height;const ax=adjusted.getContext('2d');ax.drawImage(angled,0,0);ax.save();ax.beginPath();ax.moveTo(530,40);ax.lineTo(760,40);ax.lineTo(760,215);ax.lineTo(530,252);ax.closePath();ax.clip();ax.fillStyle='#fff';ax.fillRect(530,40,230,212);ax.imageSmoothingQuality='high';ax.translate(645,233);ax.scale(.82,.82);ax.translate(-645,-233);ax.drawImage(angled,0,0);ax.restore();imgCache.set('unified-online-reference-v30/assets/closed-oblique.png',adjusted);
 const specs=[
  {file:'online-reference-v30/assets/open-inner-reference.png',flat:[[425,20,205,153,525,173,215,130],[1130,20,235,153,1252,173,215,130]]},
  {file:'online-reference-v30/assets/shell-2.webp',projected:[{erase:[[285,242],[400,242],[400,315],[285,345]],q:[[280,264],[389,240],[395,317],[287,344]]},{erase:[[728,137],[855,137],[855,217],[728,252]],q:[[728,165],[838,138],[848,218],[738,250]]}]},
  {file:'online-reference-v30/assets/shell-3.webp',projected:[{erase:[[330,326],[448,326],[448,398],[330,453]],q:[[329,367],[421,326],[433,402],[342,447]]},{erase:[[790,260],[948,260],[948,377],[790,338]],q:[[804,265],[928,298],[928,375],[804,342]]}]},
  {file:'online-reference-v30/assets/shell-4.webp',projected:[{erase:[[295,340],[430,340],[430,480],[295,413]],q:[[300,337],[407,403],[416,483],[308,417]]},{erase:[[735,350],[863,350],[863,429],[735,485]],q:[[740,400],[840,356],[849,430],[749,482]]}]}
 ];
 await Promise.all(specs.map(async spec=>{const raw=spec.file==='online-reference-v30/assets/open-inner-reference.png'?imgCache.get('sharp-inner-shell'):await loadImage(spec.file),c=document.createElement('canvas');c.width=raw.width;c.height=raw.height;const x=c.getContext('2d');x.drawImage(raw,0,0);
  for(const [ex,ey,ew,eh,cx,base,w,h]of spec.flat||[]){x.fillStyle='#fff';x.fillRect(ex,ey,ew,eh);const flatFactor=.75,scaledW=w*flatFactor,scaledH=h*flatFactor;x.drawImage(hook,cx-scaledW/2,base-scaledH,scaledW,scaledH)}
  for(const p of spec.projected||[]){x.save();x.beginPath();p.erase.forEach(([a,b],i)=>i?x.lineTo(a,b):x.moveTo(a,b));x.closePath();x.fillStyle='#fff';x.fill();x.restore();warp(x,hook,p.q.map(([a,b])=>[a/BASE,b/BASE]))}
  imgCache.set('unified-'+spec.file,c);
 }));
}
function project(q,u,v){const [p0,p1,p2,p3]=q;const dx1=p1[0]-p2[0],dx2=p3[0]-p2[0],dx3=p0[0]-p1[0]+p2[0]-p3[0],dy1=p1[1]-p2[1],dy2=p3[1]-p2[1],dy3=p0[1]-p1[1]+p2[1]-p3[1];let g=0,h=0;const den=dx1*dy2-dx2*dy1;if(Math.abs(den)>1e-9){g=(dx3*dy2-dx2*dy3)/den;h=(dx1*dy3-dx3*dy1)/den}const a=p1[0]-p0[0]+g*p1[0],b=p3[0]-p0[0]+h*p3[0],d=p1[1]-p0[1]+g*p1[1],e=p3[1]-p0[1]+h*p3[1];const z=g*u+h*v+1;return[(a*u+b*v+p0[0])/z,(d*u+e*v+p0[1])/z]}
function overlapTriangleCorner([x,y],[px,py],[nx,ny]){
 const prevLength=Math.hypot(px-x,py-y), nextLength=Math.hypot(nx-x,ny-y);
 if(!prevLength||!nextLength)return [x,y];
 const ax=(px-x)/prevLength, ay=(py-y)/prevLength;
 const bx=(nx-x)/nextLength, by=(ny-y)/nextLength;
 // Pad perpendicular to the shared edges, including long, thin spine triangles.
 const distance=1.05/Math.max(.005,Math.abs(ax*by-ay*bx));
 return [x-(ax+bx)*distance,y-(ay+by)*distance];
}
function triangle(ctx,img,s,d){const[x0,y0]=s[0],[x1,y1]=s[1],[x2,y2]=s[2],[u0,v0]=d[0],[u1,v1]=d[1],[u2,v2]=d[2];const den=x0*(y1-y2)+x1*(y2-y0)+x2*(y0-y1);if(Math.abs(den)<1e-9)return;const a=(u0*(y1-y2)+u1*(y2-y0)+u2*(y0-y1))/den,b=(v0*(y1-y2)+v1*(y2-y0)+v2*(y0-y1))/den,c=(u0*(x2-x1)+u1*(x0-x2)+u2*(x1-x0))/den,dv=(v0*(x2-x1)+v1*(x0-x2)+v2*(x1-x0))/den,e=(u0*(x1*y2-x2*y1)+u1*(x2*y0-x0*y2)+u2*(x0*y1-x1*y0))/den,f=(v0*(x1*y2-x2*y1)+v1*(x2*y0-x0*y2)+v2*(x0*y1-x1*y0))/den;
ctx.save();ctx.beginPath();ctx.moveTo(...overlapTriangleCorner(d[0],d[2],d[1]));ctx.lineTo(...overlapTriangleCorner(d[1],d[0],d[2]));ctx.lineTo(...overlapTriangleCorner(d[2],d[1],d[0]));ctx.closePath();ctx.clip();ctx.transform(a,b,c,dv,e,f);ctx.drawImage(img,0,0);ctx.restore()}
export function warp(ctx,img,quad){const q=quad.map(p=>p.map(x=>x*BASE));if(Math.abs(q[0][1]-q[1][1])<.001&&Math.abs(q[2][1]-q[3][1])<.001&&Math.abs(q[0][0]-q[3][0])<.001&&Math.abs(q[1][0]-q[2][0])<.001){ctx.drawImage(img,q[0][0],q[0][1],q[1][0]-q[0][0],q[3][1]-q[0][1]);return}const n=14;ctx.save();ctx.beginPath();q.forEach((p,i)=>i?ctx.lineTo(...p):ctx.moveTo(...p));ctx.closePath();ctx.clip();for(let row=0;row<n;row++)for(let col=0;col<n;col++){const u=col/n,v=row/n,un=(col+1)/n,vn=(row+1)/n;const uv=[[u,v],[un,v],[un,vn],[u,vn]],src=uv.map(([s,t])=>[s*img.width,t*img.height]),dst=uv.map(([s,t])=>project(q,s,t));triangle(ctx,img,[src[0],src[1],src[2]],[dst[0],dst[1],dst[2]]);triangle(ctx,img,[src[0],src[2],src[3]],[dst[0],dst[2],dst[3]])}ctx.restore()}
// A separate transparent 40 mm disc sits on the carrier. Its label never replaces the disc.
export function clearDisc(size=1200,rimOnly=false){const key=`clear-disc-${rimOnly}`,cached=imgCache.get(key);if(cached?.width===size)return cached;const c=document.createElement('canvas');c.width=c.height=size;const x=c.getContext('2d'),s=size/1200,outer=598,hole=600*DISC.holeDiameter/DISC.diameter;x.scale(s,s);x.beginPath();x.arc(600,600,outer,0,Math.PI*2);x.arc(600,600,hole,0,Math.PI*2,true);x.clip('evenodd');
 if(!rimOnly){const g=x.createLinearGradient(120,80,1020,1130);g.addColorStop(0,'rgba(255,255,255,.10)');g.addColorStop(.4,'rgba(215,225,230,.025)');g.addColorStop(1,'rgba(120,137,148,.045)');x.fillStyle=g;x.fillRect(0,0,1200,1200)}
 const ring=(r,w,color)=>{x.strokeStyle=color;x.lineWidth=w;x.beginPath();x.arc(600,600,r,0,Math.PI*2);x.stroke()};for(const r of [591,hole+7]){ring(r,13,'rgba(91,110,121,.24)');ring(r-3,5,'rgba(255,255,255,.92)');ring(r+4,2,'rgba(61,78,91,.48)');ring(r-7,1.5,'rgba(146,166,178,.58)')}
 for(const [a,b]of [[3.5,4.55],[.15,1.1]]){x.strokeStyle='rgba(255,255,255,.95)';x.lineWidth=5;x.beginPath();x.arc(600,600,586,a,b);x.stroke()}imgCache.set(key,c);return c}
function drawDisc(ctx,state,view,slot){const q=getQuad(state,view,slot),size=Math.min(3000,Math.max(1200,textureResolution));warp(ctx,clearDisc(size),q);const label=state.showDesign?slotTexture(state,slot):null;if(label)warp(ctx,label,q);warp(ctx,clearDisc(size,true),q)}
export function render(canvas,state,view=state.view,size=1254,camera=[0,0,1,1]){const [cx,cy,cw,ch]=camera,height=Math.round(size*ch/cw),scale=size/(BASE*cw);if(canvas.width!==size||canvas.height!==height){canvas.width=size;canvas.height=height}const ctx=canvas.getContext('2d');ctx.setTransform(scale,0,0,scale,-cx*BASE*scale,-cy*BASE*scale);ctx.imageSmoothingQuality='high';ctx.globalCompositeOperation='source-over';ctx.fillStyle=state.background;ctx.fillRect(0,0,BASE,BASE);textureResolution=Math.ceil(size/cw);const shell=renderShell(view,textureResolution);if(!shell)return;ctx.save();ctx.globalCompositeOperation='multiply';ctx.drawImage(shell,0,0,BASE,BASE);ctx.restore();
if(view===0)drawFrontArtwork(ctx,state);
else if(state.showDesign){for(const slot of views[view].slots){if(slot.id==='disc')drawHardware(ctx,view);if(slot.inBox&&!state.discVisible)continue;if(slot.id==='disc'){drawDisc(ctx,state,view,slot);continue}const tx=slotTexture(state,slot);if(tx)warp(ctx,tx,getQuad(state,view,slot))}if(state.lighting){ctx.save();ctx.beginPath();ctx.rect(0,0,BASE,BASE);for(const slot of views[view].slots){if((slot.id==='disc'||slot.sourceCrop||(view===4&&slot.id==='tray')||['front','back','inside','leftSpine','rightSpine','leftSpineInner'].includes(slot.id))&&state.assets[slot.id].src){const q=getQuad(state,view,slot);q.forEach((p,i)=>i?ctx.lineTo(p[0]*BASE,p[1]*BASE):ctx.moveTo(p[0]*BASE,p[1]*BASE));ctx.closePath()}}ctx.clip('evenodd');ctx.globalCompositeOperation='multiply';ctx.drawImage(shell,0,0,BASE,BASE);ctx.restore()}drawInsideRetainers(ctx,state,view)}else{drawHardware(ctx,view);if(state.discVisible)for(const slot of views[view].slots)if(slot.id==='disc'&&slot.inBox)drawDisc(ctx,state,view,slot);}
if(view!==0)drawExteriorPaperRims(ctx,state,view);
ctx.setTransform(1,0,0,1,0,0);}
export function sheetLayout(size){const header=Math.round(size*.055);return{columns:4,rows:2,cell:size/4,header,width:size,height:Math.round(size/2)+header}}
export function renderPreview(canvas,state,size=BASE){render(canvas,state,state.view,size,previewFrame(state.view))}
export async function exportPNG(state,size,mode){const c=document.createElement('canvas');if(mode==='current')render(c,state,state.view,size);else{const cell=document.createElement('canvas'),l=sheetLayout(size);c.width=l.width;c.height=l.height;const x=c.getContext('2d');x.fillStyle=state.background;x.fillRect(0,0,c.width,c.height);x.fillStyle='#33312c';x.textAlign='left';x.font=`600 ${Math.round(size*.013)}px sans-serif`;x.fillText(`${state.title||'Mini CD'} · 八视图`,size*.025,l.header*.5);x.textAlign='right';x.font=`${Math.round(size*.009)}px sans-serif`;x.fillStyle='#777';x.fillText('外壳53 × 45 × 8 mm · 内衬49 × 38 mm · 高度不含挂孔',size*.975,l.header*.5);for(let i=0;i<MAIN_VIEW_COUNT;i++){render(cell,state,i,Math.ceil(l.cell));const px=(i%4)*l.cell,py=l.header+Math.floor(i/4)*l.cell;x.drawImage(cell,px,py,l.cell,l.cell);x.strokeStyle='#e4e3df';x.lineWidth=1;x.strokeRect(px+.5,py+.5,l.cell-1,l.cell-1);x.fillStyle='#55534e';x.font=`${Math.round(l.cell*.032)}px sans-serif`;x.textAlign='center';x.fillText(views[i].name,px+l.cell/2,py+l.cell-l.cell*.045)}}
return new Promise((resolve,reject)=>c.toBlob(b=>b?resolve(b):reject(Error('导出失败，请尝试较小分辨率')),'image/png'))}
