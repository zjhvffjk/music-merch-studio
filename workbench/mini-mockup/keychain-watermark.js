import {mountWatermarkControls} from './watermark-controls.js';
import {isKeychainProduct,watermarkProductImage,watermarkProductZip} from './product-watermark.js';
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
document.addEventListener('click',async e=>{
 const a=e.target.closest('a[href]');if(!a||!controls.snapshot().enabled)return;const u=new URL(a.href,location.href);
 const zip=/^\/api\/(zip|jobs\/zip)$/.test(u.pathname),product=isKeychainProduct(u.href);if(!zip&&!product)return;
 e.preventDefault();e.stopImmediatePropagation();const settings=controls.snapshot();
 try{notify(zip?'正在为商品图添加水印并打包…':'正在导出带水印商品图…');const response=await fetch(u.href);if(!response.ok)throw Error('下载失败，请稍后重试');const original=await response.blob();
  let blob,name;if(zip){blob=await watermarkProductZip(original,settings);const header=response.headers.get('content-disposition')||'',match=header.match(/filename\*=UTF-8''([^;]+)/i);name=match?decodeURIComponent(match[1]):'商品图-作品文件.zip'}else{blob=await watermarkProductImage(original,settings,u.pathname);name=decodeURIComponent(u.pathname.split('/').pop())}
  download(blob,name);notify('已导出，水印仅应用于商品图');
 }catch(error){notify(error.message)}
},true);
