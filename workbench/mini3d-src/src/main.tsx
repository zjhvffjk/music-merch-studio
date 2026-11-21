import React, { Suspense, useEffect, useMemo, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { Canvas, useThree } from '@react-three/fiber'
import { OrbitControls, useTexture } from '@react-three/drei'
import * as THREE from 'three'
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js'
import { GLTFExporter } from 'three/examples/jsm/exporters/GLTFExporter.js'
import './style.css'
import ShellReview from './ShellReview'

type Slot = '盘面'|'封面'|'封面背面'|'封底'|'右侧封'|'左侧封'|'左侧封背面'|'内盘底'
const SLOTS: Slot[] = ['盘面','封面','封面背面','封底','右侧封','左侧封','左侧封背面','内盘底']
const REFERENCE_SHOTS = [
  {label:'① 闭合正面',file:'final/01.png'},
  {label:'② 闭合背面',file:'final/03.png'},
  {label:'③ 平铺展开',file:'final/04.png'},
  {label:'④ 斜向打开',file:'final/05.png'},
  {label:'⑤ 展开取盘',file:'final/07.png'},
]
const jid = new URLSearchParams(location.search).get('jid') || ''
const fileUrl = (slot: Slot) => `/api/design/file?jid=${encodeURIComponent(jid)}&name=${encodeURIComponent(slot+'.png')}`
const initial = Object.fromEntries(SLOTS.map(slot=>[slot,fileUrl(slot)])) as Record<Slot,string>

function roundedShape(w:number,h:number,r:number) {
  const s=new THREE.Shape(), x=-w/2,y=-h/2
  s.moveTo(x+r,y);s.lineTo(x+w-r,y);s.quadraticCurveTo(x+w,y,x+w,y+r)
  s.lineTo(x+w,y+h-r);s.quadraticCurveTo(x+w,y+h,x+w-r,y+h)
  s.lineTo(x+r,y+h);s.quadraticCurveTo(x,y+h,x,y+h-r)
  s.lineTo(x,y+r);s.quadraticCurveTo(x,y,x+r,y)
  return s
}
function shellGeometry(w:number,h:number,wall:number,depth:number) {
  const s=roundedShape(w,h,2.6), hole=roundedShape(w-2*wall,h-2*wall,1.6)
  s.holes.push(new THREE.Path(hole.getPoints().reverse()))
  const g=new THREE.ExtrudeGeometry(s,{depth,bevelEnabled:true,bevelSegments:2,steps:1,bevelSize:.3,bevelThickness:.3,curveSegments:6})
  g.computeVertexNormals();return g
}
function Plastic({panel=false}:{panel?:boolean}){return panel
  ? <meshBasicMaterial color="#edf3f6" transparent opacity={.035} depthWrite={false} side={THREE.DoubleSide}/>
  : <meshPhysicalMaterial color="#e6ecef" roughness={.025} metalness={0} transmission={.88} thickness={.9} ior={1.49} clearcoat={1} clearcoatRoughness={.015} envMapIntensity={2.5} side={THREE.DoubleSide}/>
}
function MoldLine(){return <meshStandardMaterial color="#5e6b70" metalness={.18} roughness={.16} transparent opacity={.17} depthWrite={false} side={THREE.DoubleSide}/>}
function StudioEnvironment(){
  const {gl,scene}=useThree()
  useEffect(()=>{const pmrem=new THREE.PMREMGenerator(gl),room=new RoomEnvironment()
    for(const x of [-7,7]){const card=new THREE.Mesh(new THREE.PlaneGeometry(2.2,12),new THREE.MeshBasicMaterial({color:'#20272b',side:THREE.DoubleSide}));card.position.set(x,5,12);room.add(card)}
    const env=pmrem.fromScene(room)
    scene.environment=env.texture
    return()=>{scene.environment=null;env.dispose();room.dispose();pmrem.dispose()}
  },[gl,scene])
  return null
}
function StudioShadow({open}:{open:number}){
  const texture=useMemo(()=>{const canvas=document.createElement('canvas');canvas.width=512;canvas.height=128
    const ctx=canvas.getContext('2d')!,gradient=ctx.createRadialGradient(64,64,0,64,64,64)
    gradient.addColorStop(0,'rgba(24,26,28,.32)');gradient.addColorStop(.55,'rgba(24,26,28,.13)');gradient.addColorStop(1,'rgba(24,26,28,0)')
    ctx.setTransform(4,0,0,1,0,0);ctx.fillStyle=gradient;ctx.fillRect(0,0,128,128)
    const result=new THREE.CanvasTexture(canvas);result.colorSpace=THREE.SRGBColorSpace;return result
  },[])
  useEffect(()=>()=>texture.dispose(),[texture])
  return <mesh position={[-26.5*open,-26,-7]} scale={[1+open*.8,1,1]}>
    <planeGeometry args={[100,19]}/><meshBasicMaterial map={texture} transparent depthWrite={false} toneMapped={false}/>
  </mesh>
}
function Plate({w,h,z,texture,flip=false}: {w:number,h:number,z:number,texture:THREE.Texture,flip?:boolean}) {
  return <mesh position={[0,0,z]} rotation={flip?[0,Math.PI,0]:undefined}>
    <planeGeometry args={[w,h]}/><meshBasicMaterial map={texture} toneMapped={false} side={THREE.DoubleSide}/>
  </mesh>
}
function MoldedDetails({z}:{z:number}){
  return <group position={[0,0,z]}>
    {[-1,1].flatMap(y=>[-1,1].map(x=><group key={`${x}-${y}`} position={[x*15,y*21.7,0]} rotation={[0,0,y===1?Math.PI:0]}>
      <mesh><torusGeometry args={[2.15,.43,8,28,Math.PI]}/><Plastic/></mesh>
      <mesh position={[0,-.35,.15]}><torusGeometry args={[1.55,.16,8,28,Math.PI]}/><meshBasicMaterial color="#607077" transparent opacity={.24} depthWrite={false}/></mesh>
    </group>))}
    {[-1,1].map(x=><mesh key={x} position={[x*24.6,0,0]}><boxGeometry args={[.5,37,.45]}/><Plastic/></mesh>)}
    {[-1,1].flatMap(y=>[-1,1].map(x=><mesh key={`tab-${x}-${y}`} position={[x*14.8,y*21.2,.1]}><boxGeometry args={[5.8,.55,.6]}/><Plastic/></mesh>))}
  </group>
}
function CaseEdges({z,depth}:{z:number,depth:number}){
  const geometry=useMemo(()=>new THREE.EdgesGeometry(new THREE.BoxGeometry(52.4,44.4,depth)),[depth])
  useEffect(()=>()=>geometry.dispose(),[geometry])
  return <lineSegments geometry={geometry} position={[0,0,z]}><lineBasicMaterial color="#566168" transparent opacity={.35} depthWrite={false}/></lineSegments>
}
function MoldOutline({geometry,position,opacity=.18}:{geometry:THREE.BufferGeometry,position:[number,number,number],opacity?:number}){
  const edges=useMemo(()=>new THREE.EdgesGeometry(geometry,32),[geometry])
  useEffect(()=>()=>edges.dispose(),[edges])
  return <lineSegments geometry={edges} position={position}><lineBasicMaterial color="#34464c" transparent opacity={opacity} depthWrite={false}/></lineSegments>
}
function Disc({texture,lift}: {texture:THREE.Texture,lift:number}) {
  const geo=useMemo(()=>{
    const g=new THREE.RingGeometry(2.5,20,96)
    const p=g.getAttribute('position'), uv=g.getAttribute('uv')
    for(let i=0;i<p.count;i++)uv.setXY(i,p.getX(i)/40+.5,p.getY(i)/40+.5)
    return g
  },[])
  useEffect(()=>()=>geo.dispose(),[geo])
  const released=Math.max(0,(lift-8)/12)
  return <group position={[3+22*released,-34*released,-.5+Math.min(lift,8)]}>
    <mesh geometry={geo}><meshStandardMaterial map={texture} color="#ffffff" metalness={.08} roughness={.5} side={THREE.DoubleSide}/></mesh>
    <mesh position={[0,0,-.25]}><ringGeometry args={[2.5,20,96]}/><meshStandardMaterial color="#c4d3dd" metalness={.75} roughness={.24} side={THREE.DoubleSide}/></mesh>
    <mesh><ringGeometry args={[18.9,20,96]}/><meshStandardMaterial color="#dce8ee" metalness={.55} roughness={.25} side={THREE.DoubleSide}/></mesh>
  </group>
}
function Case({images,open,lift,explode,showArtwork}: {images:Record<Slot,string>,open:number,lift:number,explode:number,showArtwork:boolean}) {
  const tex=useTexture(images) as Record<Slot,THREE.Texture>
  useMemo(()=>Object.values(tex).forEach(t=>{t.colorSpace=THREE.SRGBColorSpace;t.anisotropy=8;t.needsUpdate=true}),[tex])
  const baseShell=useMemo(()=>shellGeometry(53,45,1.1,3.5),[])
  const lidShell=useMemo(()=>shellGeometry(53,45,1.1,3.2),[])
  const innerMolding=useMemo(()=>shellGeometry(50.5,42.5,.55,.4),[])
  const outerMolding=useMemo(()=>shellGeometry(51.6,43.6,.35,.24),[])
  const hanger=useMemo(()=>{const s=new THREE.Shape();s.moveTo(-4,-4);s.lineTo(4,-4);s.lineTo(4,0);s.absarc(0,0,4,0,Math.PI,false);s.lineTo(-4,-4)
    s.holes.push(new THREE.Path().absarc(0,0,2.15,0,Math.PI*2,true))
    return new THREE.ExtrudeGeometry(s,{depth:1.1,bevelEnabled:true,bevelThickness:.15,bevelSize:.15,bevelSegments:3,curveSegments:24})
  },[])
  useEffect(()=>()=>{baseShell.dispose();lidShell.dispose();innerMolding.dispose();outerMolding.dispose();hanger.dispose()},[baseShell,lidShell,innerMolding,outerMolding,hanger])
  return <group name="mini-cd-case">
    {/* Bottom tray: back sheet, lip and molded disc retention hub. */}
    <group position={[0,0,-explode*.32]}>
      <mesh position={[0,0,-3.4]}><boxGeometry args={[52,44,1.2]}/><Plastic panel/></mesh>
      <mesh geometry={baseShell} position={[0,0,-3]}><Plastic/></mesh>
      <MoldOutline geometry={baseShell} position={[0,0,-3]}/>
      <mesh geometry={innerMolding} position={[0,0,-.16]}><MoldLine/></mesh>
      <mesh geometry={outerMolding} position={[0,0,-2.86]}><MoldLine/></mesh>
      <CaseEdges z={-1.25} depth={3.5}/><MoldedDetails z={.5}/>
      {showArtwork&&<group position={[0,0,-2.9]}><Plate w={49} h={38} z={.6} texture={tex['内盘底']}/></group>}
      {showArtwork&&<group position={[0,0,-4.28]}><Plate w={49} h={38} z={0} texture={tex['封底']} flip/></group>}
      <group position={[3,0,0]}>
        <mesh position={[0,0,-2.12]}><ringGeometry args={[19.4,20.75,96]}/><Plastic panel/></mesh>
        <mesh position={[0,0,-1.5]}><cylinderGeometry args={[4.2,4.2,1.3,48]}/><Plastic/></mesh>
        <mesh position={[0,0,-1.6]}><torusGeometry args={[20.55,.48,10,96]}/><Plastic/></mesh>
        <mesh position={[0,0,-1.23]}><ringGeometry args={[20.48,20.56,96]}/><meshBasicMaterial color="#3f5057" transparent opacity={.24} depthWrite={false} side={THREE.DoubleSide}/></mesh>
        <mesh position={[0,0,-1.38]}><torusGeometry args={[19.82,.16,8,96]}/><MoldLine/></mesh>
        <mesh position={[0,0,-1.9]}><torusGeometry args={[5.1,.34,10,64]}/><Plastic/></mesh>
        {[-1,1].map(y=><group key={'hub'+y} position={[0,y*2.85,-.15]} rotation={[0,0,y===1?Math.PI:0]}>
          <mesh><torusGeometry args={[1.32,.36,8,28,Math.PI]}/><Plastic/></mesh>
          <mesh position={[0,-.7,.32]}><boxGeometry args={[2.1,.65,.55]}/><Plastic/></mesh>
        </group>)}
      </group>
      <mesh geometry={hanger} position={[0,25.6,-.55]}><Plastic/></mesh>
      <MoldOutline geometry={hanger} position={[0,25.6,-.55]} opacity={.24}/>
      {[-17,17].map(y=><mesh key={'latch'+y} position={[26.1,y,-1.6]}><boxGeometry args={[1.2,3.8,1.3]}/><Plastic/></mesh>)}
      {showArtwork&&([-1,1] as const).map(side=><group key={side} position={[side*26.15,0,-.3]} rotation={[0,side*Math.PI/2,0]}>
        <Plate w={4.4} h={38} z={.17} texture={tex[side===1?'右侧封':'左侧封']}/>
        {side===-1&&<Plate w={4.4} h={38} z={-.19} texture={tex['左侧封背面']} flip/>}
      </group>)}
    </group>
    {showArtwork&&<Disc texture={tex['盘面']} lift={lift+explode*10}/>}
    {/* The real case opens left-to-right around its left vertical spine. */}
    {[-15,15].map(y=><mesh key={y} position={[-26.5,y,1]}><cylinderGeometry args={[1.35,1.35,6,32]}/><Plastic/></mesh>)}
    {[-15,15].map(y=><mesh key={'pin'+y} position={[-26.5,y,1]}><cylinderGeometry args={[.68,.68,6.3,32]}/><meshStandardMaterial color="#8d9fa7" metalness={.45} roughness={.2} transparent opacity={.42}/></mesh>)}
    <mesh position={[-24.8,0,-.7]}><boxGeometry args={[2.4,38,3.3]}/><Plastic/></mesh>
    <mesh position={[-23.7,0,-2.65]}><boxGeometry args={[4.4,41,.55]}/><Plastic/></mesh>
    {[-25.8,-21.6].map(x=><mesh key={'spine-'+x} position={[x,0,-1.45]}><boxGeometry args={[.38,40,2.3]}/><MoldLine/></mesh>)}
    <group position={[-26.5,0,1+explode*.6]} rotation={[0,-open*Math.PI,0]}>
      <group position={[26.5,0,0]}>
        <mesh position={[0,0,2.5]}><boxGeometry args={[52,44,1]}/><Plastic panel/></mesh>
        <mesh geometry={lidShell} position={[0,0,-.8]}><Plastic/></mesh>
        <MoldOutline geometry={lidShell} position={[0,0,-.8]}/>
        <mesh geometry={innerMolding} position={[0,0,-.42]}><MoldLine/></mesh>
        <mesh geometry={outerMolding} position={[0,0,1.9]}><MoldLine/></mesh>
        <CaseEdges z={.8} depth={3.2}/><MoldedDetails z={-.86}/>
        {showArtwork&&<group position={[2,0,0]}><Plate w={41} h={41} z={1.85} texture={tex['封面']}/></group>}
        {showArtwork&&<Plate w={41} h={41} z={-.9} texture={tex['封面背面']} flip/>}
        <mesh geometry={hanger} position={[0,25.6,-1.35]}><Plastic/></mesh>
        <MoldOutline geometry={hanger} position={[0,25.6,-1.35]} opacity={.24}/>
      </group>
    </group>
  </group>
}
function Capture({captureRef}:{captureRef:React.MutableRefObject<((size:number,transparent:boolean)=>void)|null>}){
  const {gl,scene,camera}=useThree()
  useEffect(()=>{captureRef.current=(size,transparent)=>{
    const old=gl.getSize(new THREE.Vector2()),ratio=gl.getPixelRatio(),background=scene.background
    const cam=camera as THREE.PerspectiveCamera,aspect=cam.aspect
    try{
      if(transparent)scene.background=null
      gl.setPixelRatio(1);gl.setSize(size,size,false);cam.aspect=1;cam.updateProjectionMatrix();gl.render(scene,camera)
      const a=document.createElement('a');a.href=gl.domElement.toDataURL('image/png');a.download=`Mini-CD-3D-${size}px.png`;a.click()
    }finally{
      scene.background=background;cam.aspect=aspect;cam.updateProjectionMatrix()
      gl.setPixelRatio(ratio);gl.setSize(old.x,old.y,false);gl.render(scene,camera)
    }
  };return()=>{captureRef.current=null}},[gl,scene,camera,captureRef])
  return null
}
function ModelExport({exportRef}:{exportRef:React.MutableRefObject<(()=>Promise<void>)|null>}){
  const {scene}=useThree()
  useEffect(()=>{exportRef.current=async()=>{
    const object=scene.getObjectByName('mini-cd-case')
    if(!object)throw Error('3D 模型尚未载入')
    const file=await new GLTFExporter().parseAsync(object,{binary:true,onlyVisible:true})
    const url=URL.createObjectURL(new Blob([file as ArrayBuffer],{type:'model/gltf-binary'}))
    const a=document.createElement('a');a.href=url;a.download='Mini-CD-53x45x8.glb';a.click()
    setTimeout(()=>URL.revokeObjectURL(url),60000)
  };return()=>{exportRef.current=null}},[scene,exportRef])
  return null
}
function App(){
  const [images,setImages]=useState(initial),[open,setOpen]=useState(0),[lift,setLift]=useState(0),[explode,setExplode]=useState(0)
  const [status,setStatus]=useState('读取专辑组件…'),[album,setAlbum]=useState('Mini-CD'),[active,setActive]=useState<Slot>('封面'),[ready,setReady]=useState(false)
  const [autoRotate,setAutoRotate]=useState(false),[imageSize,setImageSize]=useState(2048),[transparent,setTransparent]=useState(false)
  const [studioBackground,setStudioBackground]=useState<'gray'|'white'>('gray')
  const [showArtwork,setShowArtwork]=useState(false)
  const [referenceIndex,setReferenceIndex]=useState<number|null>(null)
  const captureRef=useRef<((size:number,transparent:boolean)=>void)|null>(null), controlsRef=useRef<any>(null)
  const exportRef=useRef<(()=>Promise<void>)|null>(null)
  useEffect(()=>{if(!jid){setStatus('请先在设计工作台生成一套组件，再打开 3D 展示。');return}
    fetch('/api/design/state?jid='+encodeURIComponent(jid)).then(r=>{if(!r.ok)throw Error('项目不存在');return r.json()}).then(m=>{
      setAlbum([m.artist,m.album].filter(Boolean).join(' · ')||'Mini-CD')
      return fetch('/api/design/3d-config?jid='+encodeURIComponent(jid))
    }).then(r=>{if(!r.ok)throw Error('3D 项目配置读取失败');return r.json()}).then(d=>{
      setImages(d.images);setOpen(d.state?.open||0);setLift(d.state?.lift||0);setExplode(d.state?.explode||0)
      setReady(true);setStatus('已载入八张组件 · 外壳外尺寸 53×45×8 mm')
    }).catch(e=>setStatus(e.message))},[])
  const upload=async(slot:Slot,file?:File)=>{if(!file)return
    if(!file.type.startsWith('image/')){setStatus('请选择图片文件');return}
    setStatus(`正在保存 ${slot}…`)
    try{
      const up=await fetch('/api/upload?name='+encodeURIComponent(file.name),{method:'POST',body:await file.arrayBuffer()})
      const u=await up.json();if(!up.ok)throw Error(u.error||'上传失败')
      const saved=await fetch('/api/design/3d-config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({jid,slot,upload:u.upload})})
      const d=await saved.json();if(!saved.ok)throw Error(d.error||'保存失败')
      setImages(prev=>({...prev,[slot]:`/api/design/file?jid=${encodeURIComponent(jid)}&name=${encodeURIComponent('3d-'+slot+'.png')}&v=${Date.now()}`}))
      setStatus(`${slot}已保存到项目；2D 印刷图保持原样`)
    }catch(e){setStatus(e instanceof Error?e.message:'上传失败')}
  }
  const saveScene=async()=>{try{const r=await fetch('/api/design/3d-config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({jid,state:{open,lift,explode}})})
    const d=await r.json();if(!r.ok)throw Error(d.error||'保存失败');setStatus('开合、取盘与分解状态已保存到项目')
  }catch(e){setStatus(e instanceof Error?e.message:'保存失败')}}
  const view=(x:number,y:number,z:number,targetX=0,targetY=0)=>{const c=controlsRef.current;if(!c)return;c.object.position.set(x,y,z);c.target.set(targetX,targetY,0);c.update()}
  const productShot=(kind:'front'|'back'|'flat'|'angle'|'disc')=>{setReferenceIndex(null);setShowArtwork(true);setExplode(0);setAutoRotate(false)
    if(kind==='front'){setOpen(0);setLift(0);setStudioBackground('gray');view(0,0,105)}
    if(kind==='back'){setOpen(0);setLift(0);setStudioBackground('white');view(0,0,-105)}
    if(kind==='flat'){setOpen(1);setLift(0);setStudioBackground('white');view(-26.5,0,145,-26.5)}
    if(kind==='angle'){setOpen(.55);setLift(0);setStudioBackground('white');view(28,22,174,-14)}
    if(kind==='disc'){setOpen(1);setLift(20);setStudioBackground('white');view(-6,-10,200,-6,-12)}
  }
  return <div className="app">
    <header><div><strong>MINI-CD <span>3D STUDIO</span></strong><small>{album}</small></div><button className="shellToggle" onClick={()=>{setReferenceIndex(null);setShowArtwork(v=>!v)}}>{showArtwork?'查看透明空盒':'显示专辑贴图'}</button><a href={jid?`/design.html?jid=${encodeURIComponent(jid)}`:'/design.html'}>返回 2D 设计</a></header>
    <aside className="assets"><h2>组件贴图</h2><p>来自当前项目的八张独立印刷图。单件替换会保存在本项目的 3D 展示中。</p><div className="assetList">{SLOTS.map(s=><label key={s} className={'asset '+(active===s?'on':'')}><input type="radio" checked={active===s} onChange={()=>setActive(s)}/><img src={images[s]} alt=""/><span>{s}</span><input type="file" accept="image/png,image/jpeg,image/webp" onChange={e=>upload(s,e.target.files?.[0])}/></label>)}</div></aside>
    <main><div className="viewport"><Canvas gl={{antialias:true,preserveDrawingBuffer:true,alpha:true}} camera={{position:[66,52,97],fov:38}} dpr={[1,2]}>
      <color attach="background" args={[studioBackground==='white'?'#ffffff':'#c9c9c9']}/><ambientLight intensity={.65}/><directionalLight position={[25,50,65]} intensity={1.2}/><directionalLight position={[-40,20,-35]} intensity={.7}/>
      <StudioEnvironment/>{ready&&<Suspense fallback={null}><StudioShadow open={open}/><Case images={images} open={open} lift={lift} explode={explode} showArtwork={showArtwork}/></Suspense>}
      <OrbitControls ref={controlsRef} enableDamping autoRotate={autoRotate} autoRotateSpeed={.8} minDistance={56} maxDistance={240}/><Capture captureRef={captureRef}/><ModelExport exportRef={exportRef}/>
    </Canvas>{referenceIndex!==null&&<div className="referencePreview"><img src={`/mini3d/reference/${REFERENCE_SHOTS[referenceIndex].file}`} alt={REFERENCE_SHOTS[referenceIndex].label}/><div><strong>用户提供的效果参考图 · {REFERENCE_SHOTS[referenceIndex].label}</strong><span>这是参考图片，不是当前 3D 模型的渲染结果。</span><button onClick={()=>setReferenceIndex(null)}>返回交互 3D</button></div></div>}<span className="viewTag">交互式 3D · 53×45×8 mm</span></div><div className="status">{status}</div></main>
    <aside className="settings"><h2>展示控制</h2><section className="shellPresets"><h3>最终效果参考</h3><p>以下五张是你提供的照片；当前 3D 渲染仍需按它们重做。</p>{REFERENCE_SHOTS.map((shot,index)=><button key={shot.file} onClick={()=>setReferenceIndex(index)}>{shot.label}</button>)}</section><section className="shellPresets"><h3>同一模型的五个 3D 状态</h3><p>以下按钮切换真实 3D 模型的开合、光盘和机位；出图仍是预览质量。</p><button onClick={()=>productShot('front')}>① 闭合正面 · 3D</button><button onClick={()=>productShot('back')}>② 闭合背面 · 3D</button><button onClick={()=>productShot('flat')}>③ 平铺展开 · 3D</button><button onClick={()=>productShot('angle')}>④ 斜向打开 · 3D</button><button onClick={()=>productShot('disc')}>⑤ 展开取盘 · 3D</button></section><h3>模型手动调整</h3><label>盒盖开合 <output>{Math.round(open*180)}°</output><input type="range" min="0" max="1" step=".01" value={open} onChange={e=>setOpen(+e.target.value)}/></label><label>取出光盘 <output>{Math.round(lift/20*100)}%</output><input type="range" min="0" max="20" step=".2" value={lift} onChange={e=>setLift(+e.target.value)}/></label><label>分解视图 <output>{Math.round(explode*100)}%</output><input type="range" min="0" max="1" step=".01" value={explode} onChange={e=>setExplode(+e.target.value)}/></label><div className="viewButtons"><button onClick={()=>view(0,0,105)}>正面</button><button onClick={()=>view(0,0,-105)}>背面</button><button onClick={()=>view(105,0,0)}>侧面</button><button onClick={()=>view(0,105,.1)}>俯视</button></div><button onClick={()=>setAutoRotate(v=>!v)}>{autoRotate?'停止旋转':'自动旋转'}</button><button onClick={()=>controlsRef.current?.reset()}>重置视角</button><button onClick={saveScene} disabled={!ready}>保存项目设置</button><button onClick={()=>exportRef.current?.().then(()=>setStatus('已导出可旋转的 GLB 预览模型')).catch(e=>setStatus(e instanceof Error?e.message:'GLB 导出失败'))} disabled={!ready}>下载 GLB 预览模型</button><label>图片尺寸<select value={imageSize} onChange={e=>setImageSize(+e.target.value)}><option value={2048}>2K · 2048 × 2048</option><option value={4096}>4K · 4096 × 4096</option></select></label><label className="check"><input type="checkbox" checked={transparent} onChange={e=>setTransparent(e.target.checked)}/> 透明背景</label><button className="primary" onClick={()=>captureRef.current?.(imageSize,transparent)} disabled={!ready||referenceIndex!==null}>保存 PNG 预览图</button><p className="note">实物外尺寸 53×45×8 mm（不含挂孔）；印刷件沿用原有尺寸。</p></aside>
  </div>
}
createRoot(document.getElementById('root')!).render(new URLSearchParams(location.search).get('review')==='shell'?<ShellReview/>:<App/>)
