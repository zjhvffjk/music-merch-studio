import {mountWatermarkControls} from './watermark-controls.js';
import {isKeychainProduct,isProductImage,watermarkProductImage,exportProductZip} from './product-watermark.js';
import {encodeProductJpeg,hasProductJpegEncoder,productJpegFilename} from './product-export.js';
const notify=message=>window.toast?.(message);
let controls,revision=0,refreshTimer,cache=new Map();const tracked=new WeakMap(),objectUrls=new Set();
const button=document.createElement('button');button.type='button';button.className='btn';button.id='productWatermarkButton';button.textContent='商品图水印';
document.querySelector('#btnTheme')?.before(button);
const dialog=document.createElement('dialog');dialog.id='productWatermarkDialog';dialog.innerHTML='<button type="button" class="watermark-dialog-close">关闭</button><div class="watermark-dialog-body"></div>';document.body.append(dialog);
button.onclick=()=>dialog.showModal();dialog.querySelector('button').onclick=()=>dialog.close();
function download(blob,name){const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),30000)}
async function markedUrl(source,full){
 const key=source+':'+full;
 if(!cache.has(key)){const settings=controls.snapshot();cache.set(key,(async()=>{const response=await fetch(source);if(!response.ok)throw Error('商品图读取失败');const blob=await watermarkProductImage(await response.blob(),settings,new URL(source,location.href).pathname,full?Infinity:1200);const url=URL.createObjectURL(blob);objectUrls.add(url);return url})())}return cache.get(key);
}
function refreshImage(img){
 const declared=img.getAttribute('src');if(!declared)return;const old=tracked.get(img),source=old&&declared===old.output?old.source:declared;
 if(!isKeychainProduct(source))return;if(old&&old.source===source&&old.revision===revision&&declared===old.output)return;
 const token={source,output:source,revision};tracked.set(img,token);
 if(!controls.snapshot().enabled){if(declared!==source)img.src=source;return}
 markedUrl(source,img.id==='lbimg').then(url=>{if(tracked.get(img)!==token||token.revision!==revision)return;token.output=url;img.src=url}).catch(e=>{if(tracked.get(img)===token){img.src=source;notify(e.message)}});
}
function refresh(){if(!controls)return;revision++;cache.clear();for(const url of objectUrls)URL.revokeObjectURL(url);objectUrls.clear();document.querySelectorAll('img').forEach(refreshImage);button.textContent=controls.snapshot().enabled?'商品图水印 · 已开启':'商品图水印'}
controls=await mountWatermarkControls(dialog.querySelector('.watermark-dialog-body'),{onChange:()=>{clearTimeout(refreshTimer);refreshTimer=setTimeout(refresh,180)},onError:notify});refresh();
new MutationObserver(records=>{for(const record of records){if(record.type==='attributes')refreshImage(record.target);else for(const node of record.addedNodes)if(node.nodeType===1){if(node.matches('img'))refreshImage(node);node.querySelectorAll('img').forEach(refreshImage)}}}).observe(document.body,{childList:true,subtree:true,attributes:true,attributeFilter:['src']});
export async function downloadProductZip(url){
 const settings=controls.snapshot(),target=new URL(url,location.href);
 target.searchParams.set('format',settings.enabled?'product-source':'product-4k');
 try{
  if(!await hasProductJpegEncoder(target))throw Error('请重启工作台以启用商品图 ZIP 下载');
  notify('正在准备 ZIP…');
  if(!settings.enabled){
   const a=document.createElement('a');a.href=target;document.body.append(a);a.click();a.remove();
   return;
  }
  const archive=await fetch(target);
  if(!archive.ok)throw Error('下载失败，请稍后重试');
  const blob=await exportProductZip(await archive.blob(),settings);
  const header=archive.headers.get('content-disposition')||'';
  const match=header.match(/filename\*=UTF-8''([^;]+)/i);
  download(blob,match?decodeURIComponent(match[1]):'作品文件.zip');
  notify('ZIP 已导出');
 }catch(error){notify(error.message)}
}

document.addEventListener('click',async e=>{
 const a=e.target.closest('a[href]');
 if(!a)return;
 const url=new URL(a.href,location.href);
 if(!url.pathname.startsWith('/assets/')||!isProductImage(url.href))return;
 e.preventDefault();
 const settings=controls.snapshot();
 try{
  notify('正在导出商品图…');
  const response=await fetch(url);
  if(!response.ok)throw Error('下载失败，请稍后重试');
  const original=await response.blob();
  const marked=isKeychainProduct(url.href)
   ? await watermarkProductImage(original,settings,'image.png') : original;
  const name=decodeURIComponent(url.pathname.split('/').pop());
  download(await encodeProductJpeg(marked),productJpegFilename(name));
  notify('商品图已导出');
 }catch(error){notify(error.message)}
},true);
