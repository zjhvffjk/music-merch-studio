const table=(()=>{const t=new Uint32Array(256);for(let n=0;n<256;n++){let c=n;for(let i=0;i<8;i++)c=(c&1)?0xedb88320^(c>>>1):c>>>1;t[n]=c>>>0}return t})();
function crc32(bytes){let c=0xffffffff;for(const b of bytes)c=table[(c^b)&255]^(c>>>8);return(c^0xffffffff)>>>0}
function header(size){const b=new Uint8Array(size);return[b,new DataView(b.buffer)]}
export async function createZip(files, baseBlob=null){
 const enc=new TextEncoder(),parts=[],central=[];let offset=0,baseCount=0;
 if(baseBlob){
  const bytes=new Uint8Array(await baseBlob.arrayBuffer()),v=new DataView(bytes.buffer);let end=-1;
  for(let i=bytes.length-22;i>=Math.max(0,bytes.length-65557);i--){if(v.getUint32(i,true)===0x06054b50&&i+22+v.getUint16(i+20,true)===bytes.length){end=i;break}}
  if(end<0||v.getUint16(end+4,true)||v.getUint16(end+6,true))throw Error('原有素材压缩包无法读取');
  baseCount=v.getUint16(end+10,true);const centralSize=v.getUint32(end+12,true),centralStart=v.getUint32(end+16,true);
  if(baseCount===65535||centralStart+centralSize>end)throw Error('原有素材压缩包格式不受支持');
  const entries=[];let pos=centralStart;
  for(let i=0;i<baseCount;i++){
   if(pos+46>centralStart+centralSize||v.getUint32(pos,true)!==0x02014b50)throw Error('原有素材压缩包目录损坏');
   const nl=v.getUint16(pos+28,true),el=v.getUint16(pos+30,true),cl=v.getUint16(pos+32,true),local=v.getUint32(pos+42,true),endPos=pos+46+nl+el+cl;
   if(endPos>centralStart+centralSize||local>=centralStart)throw Error('原有素材压缩包目录损坏');
   let original;try{original=new TextDecoder('utf-8',{fatal:true}).decode(bytes.subarray(pos+46,pos+46+nl))}catch{throw Error('原有素材文件名编码不支持')}
   const name=enc.encode('原有素材和打印文件/'+original);entries.push({pos,nl,el,cl,local,name});pos=endPos;
  }
  const sorted=[...entries].sort((a,b)=>a.local-b.local);
  for(let i=0;i<sorted.length;i++){
   const entry=sorted[i],p=entry.local,next=i+1<sorted.length?sorted[i+1].local:centralStart;
   if(p+30>next||v.getUint32(p,true)!==0x04034b50)throw Error('原有素材压缩包内容损坏');
   const oldName=v.getUint16(p+26,true),extra=v.getUint16(p+28,true),dataStart=p+30+oldName+extra;
   if(dataStart>next)throw Error('原有素材压缩包内容损坏');
   const h=bytes.slice(p,p+30),hd=new DataView(h.buffer);hd.setUint16(6,hd.getUint16(6,true)|0x800,true);hd.setUint16(26,entry.name.length,true);
   entry.newOffset=offset;parts.push(h,entry.name,bytes.subarray(p+30+oldName,dataStart),bytes.subarray(dataStart,next));offset+=h.length+entry.name.length+(next-(p+30+oldName));
  }
  for(const entry of entries){const h=bytes.slice(entry.pos,entry.pos+46),hd=new DataView(h.buffer);hd.setUint16(8,hd.getUint16(8,true)|0x800,true);hd.setUint16(28,entry.name.length,true);hd.setUint32(42,entry.newOffset,true);central.push(h,entry.name,bytes.subarray(entry.pos+46+entry.nl,entry.pos+46+entry.nl+entry.el+entry.cl))}
 }
 for(const file of files){const name=enc.encode(file.name),data=new Uint8Array(await file.blob.arrayBuffer()),crc=crc32(data),[lh,l]=header(30);l.setUint32(0,0x04034b50,true);l.setUint16(4,20,true);l.setUint16(6,0x800,true);l.setUint32(14,crc,true);l.setUint32(18,data.length,true);l.setUint32(22,data.length,true);l.setUint16(26,name.length,true);parts.push(lh,name,data);
 const [ch,d]=header(46);d.setUint32(0,0x02014b50,true);d.setUint16(4,20,true);d.setUint16(6,20,true);d.setUint16(8,0x800,true);d.setUint32(16,crc,true);d.setUint32(20,data.length,true);d.setUint32(24,data.length,true);d.setUint16(28,name.length,true);d.setUint32(42,offset,true);central.push(ch,name);offset+=lh.length+name.length+data.length;
 }
 const start=offset;for(const p of central)offset+=p.length;const [end,e]=header(22);e.setUint32(0,0x06054b50,true);e.setUint16(8,files.length+baseCount,true);e.setUint16(10,files.length+baseCount,true);e.setUint32(12,offset-start,true);e.setUint32(16,start,true);return new Blob([...parts,...central,end],{type:'application/zip'});
}
