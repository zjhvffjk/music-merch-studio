import {normalizeWatermark,prepareWatermark,loadWatermark,saveWatermark,drawWatermark,subscribeWatermark} from './watermark.js';
export async function mountWatermarkControls(panel,{onChange,onError}){
 if(!document.querySelector('link[data-watermark-style]')){const style=document.createElement('link');style.rel='stylesheet';style.href=new URL('./watermark-controls.css',import.meta.url).href;style.dataset.watermarkStyle='';document.head.append(style)}
 let current=normalizeWatermark(),saveQueue=Promise.resolve(),revision=0;
 try{current=await loadWatermark();await prepareWatermark(current)}catch(e){onError('水印设置读取失败：'+e.message)}
 const section=document.createElement('section');section.className='control-section watermark-controls';section.setAttribute('aria-label','商品图水印');
 section.innerHTML=`<div class="section-title"><h3>商品图水印</h3></div>
 <label class="toggle-row">启用水印<input type="checkbox" data-wm="enabled"><span class="switch"></span></label>
 <div class="watermark-fields"><label>水印内容<select data-wm="mode"><option value="text">文字</option><option value="logo">Logo 图片</option><option value="both">文字 + Logo</option></select></label>
 <label data-text-field>水印文字<input type="text" data-wm="text" maxlength="100" placeholder="输入店铺名或品牌名"></label>
 <div data-logo-field><button type="button" class="watermark-upload">上传 Logo</button><input type="file" class="watermark-file" accept="image/png,image/jpeg,image/webp" hidden><div class="watermark-logo-row"><img alt="水印 Logo" hidden><button type="button" class="text-button watermark-remove" hidden>移除 Logo</button></div><small>支持透明 PNG / WebP，最大 2 MB</small></div>
 <label>文字颜色<input type="color" data-wm="color"></label>
 <label>位置<select data-wm="position"><option value="top-left">左上</option><option value="top">上方居中</option><option value="top-right">右上</option><option value="left">左侧居中</option><option value="center">正中</option><option value="right">右侧居中</option><option value="bottom-left">左下</option><option value="bottom">下方居中</option><option value="bottom-right">右下</option></select></label>
 <div class="watermark-ranges"></div>
 <label class="toggle-row">平铺水印<input type="checkbox" data-wm="tile"><span class="switch"></span></label></div>
 <p class="watermark-hint">设置用于全部专辑的商品图；原素材和印刷文件不加水印。</p>`;
 for(const [key,name,min,max,unit] of [['size','大小',5,35,'%'],['opacity','不透明度',5,100,'%'],['rotation','旋转',-60,60,'°']]){
  const row=document.createElement('label');row.className='watermark-range';row.innerHTML=`<span>${name}<output data-value="${key}"></output></span><input type="range" aria-label="水印${name}" data-wm="${key}" min="${min}" max="${max}" step="1">`;row.dataset.unit=unit;section.querySelector('.watermark-ranges').append(row);
 }
 panel.append(section);
 function refresh(){for(const el of section.querySelectorAll('[data-wm]')){const key=el.dataset.wm;if(el.type==='checkbox')el.checked=current[key];else el.value=current[key]}
  for(const key of ['size','opacity','rotation'])section.querySelector(`[data-value="${key}"]`).textContent=current[key]+(key==='rotation'?'°':'%');
  section.querySelector('[data-text-field]').hidden=current.mode==='logo';section.querySelector('[data-logo-field]').hidden=current.mode==='text';
  section.querySelector('[data-wm="color"]').closest('label').hidden=current.mode==='logo';section.querySelector('[data-wm="position"]').disabled=current.tile;
  const img=section.querySelector('.watermark-logo-row img');img.hidden=!current.logo;if(current.logo)img.src=current.logo;else img.removeAttribute('src');section.querySelector('.watermark-remove').hidden=!current.logo;
 }
 function changed(){revision++;refresh();const snapshot=structuredClone(current);saveQueue=saveQueue.then(()=>saveWatermark(snapshot)).catch(e=>onError('水印保存失败：'+e.message));onChange()}
 section.addEventListener('input',e=>{const key=e.target.dataset.wm;if(!key)return;current=normalizeWatermark({...current,[key]:e.target.type==='checkbox'?e.target.checked:e.target.value});changed()});
 const input=section.querySelector('.watermark-file');section.querySelector('.watermark-upload').onclick=()=>input.click();
 input.onchange=async()=>{const file=input.files[0];input.value='';if(!file)return;const expected=revision;try{if(!['image/png','image/jpeg','image/webp'].includes(file.type)||file.size>2*1024*1024)throw Error('请选择 2 MB 以内的 PNG、JPG 或 WebP 图片');const src=await new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result);r.onerror=()=>reject(Error('Logo 读取失败'));r.readAsDataURL(file)});await prepareWatermark({logo:src});if(expected!==revision)return;current={...current,logo:src,enabled:true};changed()}catch(e){onError(e.message)}};
 section.querySelector('.watermark-remove').onclick=()=>{current.logo=null;changed()};
 subscribeWatermark(async()=>{const expected=revision;try{const next=await loadWatermark();await prepareWatermark(next);if(expected!==revision)return;current=next;refresh();onChange()}catch(e){onError('水印同步失败：'+e.message)}});
 refresh();return {snapshot:()=>structuredClone(current),draw:canvas=>drawWatermark(canvas,current)};
}
