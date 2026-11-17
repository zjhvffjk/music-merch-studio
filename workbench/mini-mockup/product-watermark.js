import {normalizeWatermark,prepareWatermark,drawWatermark} from './watermark.js';
import {createZip} from './zip-store.js';
export function isKeychainProduct(value){
 let path;try{const raw=String(value);path=/^(https?:)?\/\//.test(raw)||raw.startsWith('/')?decodeURIComponent(new URL(raw,'http://local/').pathname):raw.replace(/\\/g,'/')}catch{return false}
 return /\.(png|jpe?g|webp)$/i.test(path)&&(/(^|\/)(keychain|shop|钥匙扣商品图|白底与透明底商品图)\//.test(path)||/(^|\/)总览-(钥匙扣|商品图)[^/]*$/.test(path));
}
export async function watermarkProductImage(blob,settings,name='image.png',maxSide=Infinity){
 const w=normalizeWatermark(settings);if(!w.enabled)return blob;await prepareWatermark(w);
 const bitmap=await createImageBitmap(blob),c=document.createElement('canvas'),scale=Math.min(1,maxSide/Math.max(bitmap.width,bitmap.height));c.width=Math.max(1,Math.round(bitmap.width*scale));c.height=Math.max(1,Math.round(bitmap.height*scale));
 const x=c.getContext('2d'),mime=/\.jpe?g$/i.test(name)?'image/jpeg':/\.webp$/i.test(name)?'image/webp':'image/png';
 if(mime==='image/jpeg'){x.fillStyle='#fff';x.fillRect(0,0,c.width,c.height)}x.drawImage(bitmap,0,0,c.width,c.height);bitmap.close();drawWatermark(c,w);
 return new Promise((resolve,reject)=>c.toBlob(b=>{c.width=c.height=0;b?resolve(b):reject(Error('商品图水印生成失败'))},mime,mime==='image/jpeg'?.98:1));
}
export async function zipEntries(blob){
 const bytes=new Uint8Array(await blob.arrayBuffer()),v=new DataView(bytes.buffer);let end=-1;
 for(let p=bytes.length-22;p>=Math.max(0,bytes.length-65557);p--)if(v.getUint32(p,true)===0x06054b50&&p+22+v.getUint16(p+20,true)===bytes.length){end=p;break}
 if(end<0)throw Error('ZIP 无法读取');const count=v.getUint16(end+10,true);let pos=v.getUint32(end+16,true);const entries=[];
 if(count===65535||v.getUint16(end+4,true)||v.getUint16(end+6,true))throw Error('ZIP 格式不支持');
 for(let i=0;i<count;i++){
  if(pos+46>end||v.getUint32(pos,true)!==0x02014b50)throw Error('ZIP 目录损坏');
  const flags=v.getUint16(pos+8,true),method=v.getUint16(pos+10,true),length=v.getUint32(pos+20,true),nl=v.getUint16(pos+28,true),el=v.getUint16(pos+30,true),cl=v.getUint16(pos+32,true),local=v.getUint32(pos+42,true);
  if(pos+46+nl+el+cl>end||local+30>bytes.length||v.getUint32(local,true)!==0x04034b50)throw Error('ZIP 内容损坏');
  const name=new TextDecoder('utf-8',{fatal:true}).decode(bytes.subarray(pos+46,pos+46+nl));const start=local+30+v.getUint16(local+26,true)+v.getUint16(local+28,true);
  if(start+length>bytes.length||flags&1)throw Error('ZIP 内容不支持');
  const packed=new Blob([bytes.subarray(start,start+length)]);
  entries.push({name,async blob(){if(method===0)return packed;if(method===8&&typeof DecompressionStream==='function')return new Response(packed.stream().pipeThrough(new DecompressionStream('deflate-raw'))).blob();throw Error('浏览器无法解压，请更新浏览器后重试')}});pos+=46+nl+el+cl;
 }
 return entries;
}
export async function watermarkProductZip(blob,settings,onProgress=()=>{},depth=0){
 const w=normalizeWatermark(settings);if(!w.enabled)return blob;if(depth>3)throw Error('ZIP 嵌套层数过多');
 const entries=await zipEntries(blob),files=[],exclude=[];
 for(const entry of entries){let replacement;
  if(isKeychainProduct(entry.name)){onProgress(entry.name);replacement=await watermarkProductImage(await entry.blob(),w,entry.name)}
  else if(/\.zip$/i.test(entry.name)){const original=await entry.blob();replacement=await watermarkProductZip(original,w,onProgress,depth+1);if(replacement===original)replacement=null}
  if(replacement){files.push({name:entry.name,blob:replacement});exclude.push(entry.name)}
 }
 return files.length?createZip(files,[{blob,prefix:'',exclude}]):blob;
}
