import {shellThumbnail as onlineThumbnail} from './online-reference-v30/renderer.js';
import{surfaces,views,viewScale,widestViewScale,initialState,defaultTransform,sanitizeState,validQuad,persist,restore,readUpload}from'./model.js';
import{preloadShells,prepareAsset,prepareProjectAssets,invalidate,render,getQuad,exportPNG,exportThreeViewPreview,frontX,shellThumbnail,BASE}from'./renderer.js';
import{createZip}from'./zip-store.js';
import{mountWatermarkControls}from'./watermark-controls.js';
let watermarkControls;
const embedded=new URLSearchParams(location.search).get('embed')==='1';
if(embedded)document.body.classList.add('embedded');
const $=s=>document.querySelector(s);let state=initialState(),calibrating=false,zoom=100,ready=false,initializing=true,saveTimer,toastTimer,drag=null,saveRevision=0;const imageIcon='<svg viewBox="0 0 28 28" aria-hidden="true"><rect x="3" y="3" width="22" height="22" rx="2"/><circle cx="10" cy="9" r="2"/><path d="m4 22 7-8 5 5 4-4 5 7"/></svg>';
function toast(message){$('#toast').textContent=message;$('#toast').classList.add('visible');clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('#toast').classList.remove('visible'),3400)}
function scheduleSave(){if(ready&&!initializing)tellParent({type:'minicd-mockup-changed'});clearTimeout(saveTimer);const revision=++saveRevision;$('#saveStatus').textContent='正在保存到此浏览器…';saveTimer=setTimeout(async()=>{try{await persist(structuredClone(state));if(revision===saveRevision)$('#saveStatus').textContent='已自动保存 · 仅在此浏览器'}catch{if(revision===saveRevision)$('#saveStatus').textContent='浏览器保存不可用，请保存项目文件'}},450)}
function draw(){if(!ready)return;const width=$('#canvasWrap').getBoundingClientRect().width;const resolution=Math.min(4096,Math.max(1254,Math.ceil(width*Math.max(1,window.devicePixelRatio||1))));render($('#preview'),state,state.view,resolution);drawAlignment();const overlay=$('#watermarkPreview'),stage=$('#stage'),ratio=Math.max(1,window.devicePixelRatio||1);if(overlay){overlay.width=Math.round(stage.clientWidth*ratio);overlay.height=Math.round(stage.clientHeight*ratio);watermarkControls?.draw(overlay)}}
function refreshAssets(){for(const s of surfaces){const row=$(`[data-surface="${s.id}"]`),a=state.assets[s.id];row.classList.toggle('active',state.selected===s.id);row.setAttribute('aria-pressed',state.selected===s.id);const thumb=row.querySelector('.asset-preview');thumb.replaceChildren();if(a.src){const img=document.createElement('img');img.src=a.src;img.alt=s.name;thumb.append(img)}else thumb.innerHTML=imageIcon;row.querySelector('.asset-action').textContent=a.src?'已上传':'＋ 上传'}$('#selectedName').textContent=surfaces.find(s=>s.id===state.selected).name;$('#assetHint').textContent=surfaces.find(s=>s.id===state.selected).hint;$('#uploadLabel').textContent=state.assets[state.selected].src?'替换当前图片':'点击上传图片';refreshControls()}
function refreshControls(){const a=state.assets[state.selected];for(const key of ['scale','x','y','rotation']){$(`#${key}`).value=a[key];$(`#${key}Value`).textContent=a[key]+(key==='rotation'?'°':'%')}document.querySelectorAll('[data-fit]').forEach(b=>{b.classList.toggle('active',b.dataset.fit===a.fit);b.setAttribute('aria-pressed',b.dataset.fit===a.fit)});$('#removeSelected').disabled=!a.src;$('#showDesign').checked=state.showDesign;$('#lighting').checked=state.lighting;$('#discVisible').checked=state.discVisible;$('#background').value=state.background;$('#emptyToggle').classList.toggle('active',!state.showDesign);$('#emptyToggle').textContent=state.showDesign?'查看空壳':'返回设计';$('#calibrate').classList.toggle('active',calibrating);$('#calibrate').textContent=calibrating?'完成四角校准':'贴图四角校准';$('#resetQuad').hidden=!calibrating}
function selectSurface(id,changeView=true){state.selected=id;calibrating=false;if(changeView){const visible=views[state.view].slots.some(s=>s.id===id);if(!visible)state.view=surfaces.find(s=>s.id===id).view}refreshAssets();refreshView();scheduleSave()}
function refreshView(){document.querySelectorAll('[data-view]').forEach(b=>{b.classList.toggle('active',+b.dataset.view===state.view);b.setAttribute('aria-current',+b.dataset.view===state.view?'true':'false')});$('#viewTitle').textContent=views[state.view].name;$('#stageNote').textContent=calibrating?'拖动四角校准':'原壳结构';updatePreviewScale();draw()}
function drawAlignment(){const svg=$('#alignment');svg.replaceChildren();if(!calibrating)return;const slot=views[state.view].slots.find(s=>s.id===state.selected);if(!slot)return;const q=getQuad(state,state.view,slot).map(([x,y])=>[state.view===0?frontX(x*BASE):x*BASE,y*BASE]);const poly=document.createElementNS(svg.namespaceURI,'polygon');poly.setAttribute('points',q.map(p=>p.join(',')).join(' '));svg.append(poly);q.forEach((p,i)=>{const circle=document.createElementNS(svg.namespaceURI,'circle');circle.setAttribute('cx',p[0]);circle.setAttribute('cy',p[1]);circle.setAttribute('r',11);circle.dataset.corner=i;svg.append(circle)})}
function updatePreviewScale(){
  const stage=$('#stage'),wrap=$('#canvasWrap'),size=Math.min(stage.clientWidth,stage.clientHeight,740);if(!size)return;
  const scale=viewScale(state.view);
  // Apply one common fit factor to every angle, so a narrow viewport does not
  // silently give the open and closed views different scales.
  const widest=widestViewScale();
  const common=Math.min(1,stage.clientWidth*.96/(size*widest));
  wrap.style.transform=`scale(${common*scale*zoom/100})`;
}
function setZoom(value){zoom=Math.max(60,Math.min(160,value));updatePreviewScale();$('#zoomReset').textContent=zoom+'%';draw()}
function download(blob,name){const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(a.href),10000)}
function fileName(){return(state.title||'Mini-CD').replace(/[<>:"/\\|?*\u0000-\u001f]/g,'-').slice(0,60)}
async function upload(file){try{const id=state.selected,src=await readUpload(file);await prepareAsset(id,src);state.assets[id]={src,...defaultTransform()};state.showDesign=true;if(id==='disc')state.discVisible=true;if(!views[state.view].slots.some(s=>s.id===id))state.view=surfaces.find(s=>s.id===id).view;refreshAssets();refreshView();scheduleSave();toast('图片已应用到样机')}catch(e){toast(e.message)}}
const workbenchJid=new URLSearchParams(location.search).get('jid');
const batchNo=new URLSearchParams(location.search).get('batchNo')||'';
const syncRevision=new URLSearchParams(location.search).get('syncRevision')||'';
let batchExporting=false;
function tellParent(message){if(embedded)parent.postMessage(message,location.origin)}
// Only substitute a freshly rendered insert when the user is still using the
// exact original workbench image. Uploaded or edited artwork remains untouched.
async function highresExportState(snapshot){
  snapshot.watermark=watermarkControls?.snapshot();
  if(!workbenchJid||batchNo||!snapshot.assets.back?.src)return snapshot;
  try{
    const query=encodeURIComponent(workbenchJid);
    const original=await fetch('/api/design/file?jid='+query+'&name='+encodeURIComponent('封底.png'));
    if(!original.ok)return snapshot;
    const src=await readUpload(new File([await original.blob()],'封底.png',{type:'image/png'}));
    if(src!==snapshot.assets.back.src)return snapshot;
    const response=await fetch('/api/design/highres-back?jid='+query);
    if(!response.ok)return snapshot;
    snapshot.assets.back.src=await readUpload(new File([await response.blob()],'封底.png',{type:'image/png'}));
    await prepareProjectAssets(snapshot.assets);
  }catch(error){console.warn('高清封底生成失败，使用原素材',error)}
  return snapshot;
}
window.addEventListener('message',async e=>{
  if(!embedded||e.origin!==location.origin||e.source!==parent||e.data?.type!=='minicd-export-eight'||String(e.data.jid)!==String(workbenchJid)||batchExporting)return;
  if(!ready){tellParent({type:'minicd-export-error',message:'样机还未加载完成，请重试。'});return}
  batchExporting=true;
  try{
    const snapshot=await highresExportState(structuredClone(state)),indices=views.map((v,i)=>v.hidden?-1:i).filter(i=>i>=0),files=[];
    tellParent({type:'minicd-export-progress',message:'正在生成三视图总预览图…'});
    await new Promise(resolve=>setTimeout(resolve,0));
    const three=await exportThreeViewPreview(snapshot),threeName='00-三视图总预览.png';
    files.push({name:'八视图商品图/'+threeName,blob:three});
    tellParent({type:'minicd-export-image',name:threeName,label:'三视图总预览',blob:three});
    tellParent({type:'minicd-export-progress',message:'正在生成八视图总预览图…'});
    await new Promise(resolve=>setTimeout(resolve,0));
    const overview=await exportPNG(snapshot,8192,'sheet'),overviewName='01-八视图总预览.png';
    files.push({name:'八视图商品图/'+overviewName,blob:overview});
    tellParent({type:'minicd-export-image',name:overviewName,label:'八视图总预览',blob:overview});
    for(let n=0;n<indices.length;n++){
      const i=indices[n];tellParent({type:'minicd-export-progress',message:`正在生成 ${n+1}/${indices.length}：${views[i].name}`});
      await new Promise(resolve=>setTimeout(resolve,0));
      const blob=await exportPNG({...snapshot,view:i},8192,'individual');
      const name=`${String(n+2).padStart(2,'0')}-${views[i].name}.png`;files.push({name:'八视图商品图/'+name,blob});tellParent({type:'minicd-export-image',name,label:views[i].name,blob});
    }
    if(e.data.imagesOnly){tellParent({type:'minicd-export-done'});return}
    tellParent({type:'minicd-export-progress',message:batchNo?'正在合并批量素材和当前专辑商品图…':'正在合并原有素材和商品图…'});
    const response=await fetch('/api/design/zip?jid='+encodeURIComponent(workbenchJid));if(!response.ok)throw Error('原有素材包获取失败，请稍后重试');
    const zip=await createZip(files,await response.blob());tellParent({type:'minicd-export-done',name:`${fileName()}-素材和商品图.zip`,blob:zip});
  }catch(error){tellParent({type:'minicd-export-error',message:'生成失败：'+error.message})}finally{await prepareProjectAssets(state.assets);batchExporting=false}
});
const workbenchSlots={front:'封面',back:'封底',inside:'封面背面',tray:'内盘底',disc:'盘面',sideR:'右侧封',sideL:'左侧封',sideLB:'左侧封背面'};
async function importWorkbenchAssets(missingAssemblyOnly=false){
  if(!workbenchJid)return;
  const btn=$('#syncWorkbench');btn.disabled=true;btn.textContent='正在同步…';
  try{
    const query=encodeURIComponent(workbenchJid),metaResponse=await fetch('/api/design/state?jid='+query);
    if(!metaResponse.ok)throw Error('找不到当前专辑项目');
    const meta=await metaResponse.json(),albumMeta=batchNo?(meta.albums||[]).find(a=>String(a.no)===batchNo):meta,nextAssets={},failed=[];if(!albumMeta)throw Error('找不到批量中的专辑');
    for(const [id,slot] of Object.entries(workbenchSlots)){
      if(missingAssemblyOnly&&(!id.startsWith('side')||state.assets[id]?.src))continue;
      try{
        const response=await fetch('/api/design/file?jid='+query+'&name='+encodeURIComponent((batchNo?batchNo+'-':'')+slot+'.png'));
        if(!response.ok)throw Error('图片不可用');
        const image=new File([await response.blob()],slot+'.png',{type:'image/png'});
        nextAssets[id]={src:await readUpload(image),...defaultTransform()};
      }catch{failed.push(slot)}
    }
    if(!Object.keys(nextAssets).length){if(missingAssemblyOnly){state.assemblyVersion=1;scheduleSave();return}throw Error('当前项目还没有可用的组件图')}
    for(const [id,asset] of Object.entries(nextAssets))state.assets[id]=asset;
    await prepareProjectAssets(state.assets);
    state.assemblyVersion=1;
    if(!missingAssemblyOnly){state.title=[albumMeta.artist,albumMeta.album].filter(Boolean).join(' · ')||state.title;state.view=0;state.selected='front';state.showDesign=true;state.discVisible=!!state.assets.disc.src}
    $('#projectName').value=state.title;refreshAssets();refreshView();scheduleSave();
    toast(`已${missingAssemblyOnly?'补入侧封':'从专辑工作台带入'} ${Object.keys(nextAssets).length} 张组件${failed.length?'；缺少：'+failed.join('、'):''}`);
  }finally{btn.disabled=false;btn.textContent='同步专辑组件'}
}
function buildUI(){
for(const s of surfaces){const b=document.createElement('button');b.className='asset-row';b.dataset.surface=s.id;b.innerHTML=`<span class="asset-preview">${imageIcon}</span><span class="asset-name">${s.name}</span><span class="asset-action">＋ 上传</span>`;b.onclick=()=>{if(state.selected===s.id){$('#imageInput').click()}else selectSurface(s.id)};$('#assetList').append(b)}
views.forEach((v,i)=>{if(v.hidden)return;const b=document.createElement('button');b.className='view-button';b.dataset.view=i;const shell=v.onlineIndex!==undefined?v.shell:(i===0?'assets/online-front-cover-hq-v3.png':`assets/shell-${i}.webp`);b.innerHTML=`<span class="view-image"><img src="${shell}" alt="${v.name}透明空壳" loading="eager"></span><span>${v.name}</span>`;b.onclick=()=>{state.view=i;calibrating=false;if(!v.slots.some(s=>s.id===state.selected))state.selected=v.slots[0].id;setZoom(100);refreshAssets();refreshView();scheduleSave()};$('#viewList').append(b)});
for(const[key,name,min,max,unit]of[['scale','缩放',25,250,'%'],['x','水平位置',-100,100,'%'],['y','垂直位置',-100,100,'%'],['rotation','旋转',-180,180,'°']]){const el=document.createElement('div');el.className='slider-control';el.innerHTML=`<div class="slider-label"><label for="${key}">${name}</label><output id="${key}Value" for="${key}">0${unit}</output></div><input id="${key}" type="range" min="${min}" max="${max}" step="1">`;$('#sliders').append(el);el.querySelector('input').oninput=e=>{state.assets[state.selected][key]=+e.target.value;invalidate(state.selected);refreshControls();draw();scheduleSave()}}
$('#uploadSelected').onclick=()=>$('#imageInput').click();$('#imageInput').onchange=e=>{if(e.target.files[0])upload(e.target.files[0]);e.target.value=''};
$('#uploadSelected').ondragover=e=>{e.preventDefault();$('#uploadSelected').style.borderColor='var(--accent)'};$('#uploadSelected').ondragleave=()=>$('#uploadSelected').style.borderColor='';$('#uploadSelected').ondrop=e=>{e.preventDefault();$('#uploadSelected').style.borderColor='';if(e.dataTransfer.files[0])upload(e.dataTransfer.files[0])};
document.querySelectorAll('[data-fit]').forEach(b=>b.onclick=()=>{state.assets[state.selected].fit=b.dataset.fit;invalidate(state.selected);refreshControls();draw();scheduleSave()});
$('#resetTransform').onclick=()=>{Object.assign(state.assets[state.selected],defaultTransform());invalidate(state.selected);refreshControls();draw();scheduleSave();toast('已重置当前素材的缩放与位置')};
$('#removeSelected').onclick=async()=>{state.assets[state.selected]={src:null,...defaultTransform()};await prepareAsset(state.selected,null);refreshAssets();draw();scheduleSave()};
for(const key of ['showDesign','lighting','discVisible'])$(`#${key}`).onchange=e=>{state[key]=e.target.checked;refreshControls();draw();scheduleSave()};$('#background').onchange=e=>{state.background=e.target.value;$('#stage').style.background=state.background;draw();scheduleSave()};$('#emptyToggle').onclick=()=>{state.showDesign=!state.showDesign;refreshControls();draw();scheduleSave()};
$('#zoomOut').onclick=()=>setZoom(zoom-10);$('#zoomIn').onclick=()=>setZoom(zoom+10);$('#zoomReset').onclick=()=>setZoom(100);
$('#projectName').oninput=e=>{state.title=e.target.value;scheduleSave()};$('#saveProject').onclick=()=>{download(new Blob([JSON.stringify(state,null,2)],{type:'application/json'}),fileName()+'.minicd.json');toast('项目文件已下载，包含全部图片和调整参数')};
$('#syncWorkbench').hidden=!workbenchJid;$('#syncWorkbench').onclick=()=>{if(surfaces.some(s=>state.assets[s.id].src)&&!confirm('重新同步会替换样机中已有的专辑组件图片，继续吗？'))return;importWorkbenchAssets().catch(e=>toast('同步失败：'+e.message))};
$('#backToDesign').hidden=!workbenchJid;if(workbenchJid)$('#backToDesign').href='/design.html?jid='+encodeURIComponent(workbenchJid);
$('#loadProject').onclick=()=>$('#projectInput').click();$('#projectInput').onchange=async e=>{const f=e.target.files[0];e.target.value='';if(!f)return;try{if(f.size>80*1024*1024)throw Error('项目文件过大');const next=sanitizeState(JSON.parse(await f.text()));await prepareProjectAssets(next.assets);state=next;calibrating=false;$('#projectName').value=state.title;$('#stage').style.background=state.background;refreshAssets();refreshView();scheduleSave();toast('项目已打开')}catch(error){toast(error.message)}};
$('#clearAll').onclick=async()=>{if(!surfaces.some(s=>state.assets[s.id].src)){toast('当前没有已上传的素材');return}if(!confirm('清空全部部位的素材？已下载的项目文件不受影响。'))return;for(const s of surfaces){state.assets[s.id]={src:null,...defaultTransform()};await prepareAsset(s.id,null)}refreshAssets();draw();scheduleSave();toast('素材已清空')};
$('#calibrate').onclick=()=>{const a=state.assets[state.selected];if(!a.src){toast('请先上传当前部位的设计图片');return}if(!views[state.view].slots.some(s=>s.id===state.selected))state.view=surfaces.find(s=>s.id===state.selected).view;state.showDesign=true;calibrating=!calibrating;refreshControls();refreshView()};
$('#resetQuad').onclick=()=>{delete state.quads[`${state.view}:${state.selected}`];draw();scheduleSave()};
$('#alignment').onpointerdown=e=>{if(e.target.dataset.corner===undefined)return;e.preventDefault();drag={index:+e.target.dataset.corner,id:e.pointerId};$('#alignment').setPointerCapture(e.pointerId)};$('#alignment').onpointermove=e=>{if(!drag)return;const svg=$('#alignment'),p=svg.createSVGPoint();p.x=e.clientX;p.y=e.clientY;const point=p.matrixTransform(svg.getScreenCTM().inverse());const slot=views[state.view].slots.find(s=>s.id===state.selected);const q=getQuad(state,state.view,slot).map(p=>[...p]);q[drag.index]=[Math.max(0,Math.min(1,(state.view===0?frontX(point.x,true):point.x)/BASE)),Math.max(0,Math.min(1,point.y/BASE))];if(validQuad(q)){state.quads[`${state.view}:${state.selected}`]=q;draw()}};for(const key of ['onpointerup','onpointercancel'])$('#alignment')[key]=()=>{if(drag){drag=null;scheduleSave()}};
$('#exportOpen').onclick=()=>$('#exportDialog').showModal();$('#exportConfirm').onclick=async()=>{const b=$('#exportConfirm');b.disabled=true;b.textContent='正在生成高清图片…';try{await new Promise(r=>setTimeout(r,30));const size=+$('#exportSize').value,mode=$('#exportMode').value,snapshot=await highresExportState(structuredClone(state)),blob=await exportPNG(snapshot,size,mode);download(blob,`${fileName()}-${mode==='sheet'?'八视角总览':views[state.view].name}-${size}.png`);$('#exportStatus').textContent=`PNG · ${size} × ${mode==='sheet'?Math.round(size/2):size}`;$('#exportDialog').close();toast('效果图已导出')}catch(e){toast('导出失败：'+e.message)}finally{await prepareProjectAssets(state.assets);b.disabled=false;b.textContent='下载 PNG'}};
document.querySelectorAll('[data-panel]').forEach(b=>b.onclick=()=>{document.querySelectorAll('[data-panel]').forEach(x=>x.classList.toggle('active',x===b));document.querySelectorAll('.assets-panel,.inspector-panel').forEach(x=>x.classList.toggle('mobile-visible',x.classList.contains(b.dataset.panel+'-panel')))});document.querySelector('[data-panel="assets"]').click();
$('#demo').onclick=loadDemo;
}
async function loadDemo(){if(surfaces.some(s=>state.assets[s.id].src)&&!confirm('使用黑银示例替换当前素材？建议先保存项目。'))return;for(const s of surfaces){const c=document.createElement('canvas');c.width=c.height=1200;const x=c.getContext('2d');x.fillStyle=s.id==='disc'?'#c7ccd1':s.id==='tray'?'#e0e1df':'#171d27';x.fillRect(0,0,1200,1200);x.strokeStyle=s.id==='disc'?'#f1f2f0':'#a7b4c5';x.lineWidth=1;x.beginPath();x.arc(610,580,380,0,Math.PI*2);x.stroke();x.beginPath();x.ellipse(610,580,460,160,-.6,0,Math.PI*2);x.stroke();if(s.id==='front'||s.id==='disc'){x.save();x.translate(s.id==='disc'?865:610,s.id==='disc'?880:580);const g=x.createLinearGradient(-200,-250,180,250);g.addColorStop(0,'#73808d');g.addColorStop(.5,'#ffffff');g.addColorStop(1,'#929ca6');x.fillStyle=g;x.beginPath();x.moveTo(0,-360);x.bezierCurveTo(22,-32,35,-20,280,0);x.bezierCurveTo(35,20,22,32,0,360);x.bezierCurveTo(-22,32,-35,20,-280,0);x.bezierCurveTo(-35,-20,-22,-32,0,-360);x.fill();x.restore()}else{x.strokeStyle='#8e9caa';for(let i=0;i<100;i++){x.globalAlpha=.1;x.beginPath();x.moveTo(-20,780+i*2);x.bezierCurveTo(400,650+i*2,650,1100-i,1220,1050+i);x.stroke()}x.globalAlpha=1}if(s.id==='back'){x.fillStyle='#d7dce2';x.font='20px sans-serif';['01 — FIRST LIGHT','02 — ORBIT','03 — AFTERGLOW','04 — STARDUST'].forEach((t,i)=>x.fillText(t,100,150+i*65))}const src=c.toDataURL('image/png');state.assets[s.id]={src,...defaultTransform()};await prepareAsset(s.id,src)}state.showDesign=true;state.discVisible=true;state.view=1;state.selected='inside';refreshAssets();refreshView();scheduleSave();toast('黑银示例已载入，可替换成你自己的设计')}
buildUI();refreshAssets();refreshView();
const watermarkPreview=document.createElement('canvas');watermarkPreview.id='watermarkPreview';watermarkPreview.setAttribute('aria-hidden','true');$('#stage').append(watermarkPreview);
watermarkControls=await mountWatermarkControls($('.inspector-panel'),{onChange:()=>{draw();scheduleSave()},onError:toast});
const stage=$('#stage');
const fitStage=()=>{stage.style.setProperty('--stage-size',Math.max(200,Math.min(stage.clientWidth,stage.clientHeight))+'px');updatePreviewScale();draw()};
new ResizeObserver(fitStage).observe(stage);fitStage();
try{await preloadShells();for(const [i,v] of views.entries()){if(v.onlineIndex!==undefined){const image=document.querySelector(`[data-view="${i}"] img`),src=i===8?shellThumbnail(i):onlineThumbnail(v.onlineIndex);if(image&&src)image.src=src}}ready=true;$('#exportOpen').disabled=false;$('#loading').hidden=true;const saved=await restore().catch(()=>null);if(saved){state=saved;await prepareProjectAssets(state.assets);$('#projectName').value=state.title;$('#stage').style.background=state.background;$('#saveStatus').textContent='已恢复上次项目 · 仅在此浏览器'}refreshAssets();refreshView();if(workbenchJid&&syncRevision&&state.syncRevision!==syncRevision){await importWorkbenchAssets(false);state.syncRevision=syncRevision;scheduleSave()}else if(workbenchJid&&(!saved||state.assemblyVersion!==1))await importWorkbenchAssets(!!saved).catch(e=>toast('自动带入失败：'+e.message));initializing=false;tellParent({type:'minicd-mockup-ready'})}catch(e){$('#loading').textContent='外壳加载失败，请刷新页面重试';toast(e.message);tellParent({type:'minicd-export-error',message:'样机加载失败：'+e.message})}
window.addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key==='s'){e.preventDefault();$('#saveProject').click()}});
