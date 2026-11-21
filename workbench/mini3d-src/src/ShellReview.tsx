import React,{useEffect,useMemo,useRef,useState} from 'react'
import {Canvas,useThree} from '@react-three/fiber'
import {ContactShadows,OrbitControls} from '@react-three/drei'
import * as THREE from 'three'
import {RoomEnvironment} from 'three/examples/jsm/environments/RoomEnvironment.js'
import {ShellFinish,SHELL_MM} from './shell-model'
import {loadBlenderModel,BLENDER_MODEL_URL} from './blender-model'
import './shell-review.css'

const shots=[
  {id:'front',name:'闭合正面',open:0,lift:0,disc:false,camera:[0,0,133],target:[0,2,4]},
  {id:'flat',name:'平铺展开',open:180,lift:0,disc:false,camera:[-25,0,188],target:[-25,2,4]},
  {id:'inside',name:'立体内侧',open:112,lift:0,disc:false,camera:[82,62,142],target:[-15,1,12]},
  {id:'outside',name:'立体外侧',open:112,lift:0,disc:false,camera:[-106,65,-138],target:[-15,1,12]},
  {id:'disc',name:'展开取盘',open:180,lift:22,disc:true,camera:[-5,47,198],target:[-18,-5,8]},
]
function Environment(){
  const{gl,scene}=useThree()
  useEffect(()=>{
    const pmrem=new THREE.PMREMGenerator(gl),room=new RoomEnvironment()
    for(const x of [-8,8]){const mesh=new THREE.Mesh(new THREE.PlaneGeometry(1.3,10),new THREE.MeshBasicMaterial({color:'#11191d',side:THREE.DoubleSide}));mesh.position.set(x,5,10);room.add(mesh)}
    const texture=pmrem.fromScene(room,.015);scene.environment=texture.texture;scene.environmentIntensity=.65
    return()=>{scene.environment=null;texture.dispose();room.dispose();pmrem.dispose()}
  },[gl,scene]);return null
}
type Model=Awaited<ReturnType<typeof loadBlenderModel>>
function Scene({model,angle,lift,disc,shot,revision,auto,controls,api}:{model:Model,angle:number,lift:number,disc:boolean,shot:number,revision:number,auto:boolean,controls:React.MutableRefObject<any>,api:React.MutableRefObject<any>}){
  const{gl,scene,camera,invalidate}=useThree()
  useEffect(()=>{model.update(angle,lift,disc);invalidate()},[model,angle,lift,disc,invalidate])
  useEffect(()=>{const p=shots[shot],c=controls.current;if(c){camera.position.fromArray(p.camera);c.target.fromArray(p.target);c.update();invalidate()}},[shot,revision,camera,controls,invalidate])
  useEffect(()=>{
    api.current={capture:(size:number)=>{
      const rendererSize=gl.getSize(new THREE.Vector2()),dpr=gl.getPixelRatio(),cam=camera as THREE.PerspectiveCamera,aspect=cam.aspect
      try{gl.setPixelRatio(1);gl.setSize(size,size,false);cam.aspect=1;cam.updateProjectionMatrix();gl.render(scene,camera);const a=document.createElement('a');a.download=`Mini-CD-空盒-${shots[shot].id}-${size}.png`;a.href=gl.domElement.toDataURL('image/png');a.click()}
      finally{cam.aspect=aspect;cam.updateProjectionMatrix();gl.setPixelRatio(dpr);gl.setSize(rendererSize.x,rendererSize.y,false);gl.render(scene,camera)}
    }};return()=>{api.current=null}
  },[gl,scene,camera,shot,api])
  return <>
    <color attach="background" args={['#f1f2f3']}/>
    <ambientLight intensity={.3}/><directionalLight position={[35,65,100]} intensity={1.45}/><directionalLight position={[-75,15,-60]} intensity={.8}/>
    <Environment/><primitive object={model.root}/>
    <ContactShadows key={`${Math.round(angle)}-${Math.round(lift)}-${disc}-${model.root.uuid}`} position={[-15,-22.65,5]} opacity={.25} scale={200} blur={2.6} far={35} resolution={512} frames={1} color="#242b32"/>
    <OrbitControls ref={controls} enableDamping dampingFactor={.08} autoRotate={auto} autoRotateSpeed={.55} minDistance={60} maxDistance={320}/>
  </>
}
function download(buffer:ArrayBuffer,name:string){const url=URL.createObjectURL(new Blob([buffer],{type:'model/gltf-binary'}));const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),15000)}
export default function ShellReview(){
  const[finish,setFinish]=useState<ShellFinish>('clear'),[shot,setShot]=useState(2),[angle,setAngle]=useState(112),[lift,setLift]=useState(0),[disc,setDisc]=useState(false),[auto,setAuto]=useState(false),[size,setSize]=useState(2048),[revision,setRevision]=useState(0),[status,setStatus]=useState('空盒结构初稿 · 可拖动旋转检查'),[busy,setBusy]=useState(false)
  const controls=useRef<any>(null),api=useRef<any>(null),[model,setModel]=useState<Model|null>(null)
  useEffect(()=>{let cancelled=false;let current:Model|undefined;loadBlenderModel(finish).then(m=>{current=m;if(cancelled){m.dispose();return}setModel(m);setStatus('Blender 导出模型 · 网页透明材质为交互预览')}).catch(e=>setStatus(e.message));return()=>{cancelled=true;current?.dispose()}},[finish])
  const selectShot=(i:number)=>{const s=shots[i];setShot(i);setAngle(s.open);setLift(s.lift);setDisc(s.disc);setAuto(false);setRevision(v=>v+1)}
  const exportModel=async()=>{setBusy(true);try{
    const response=await fetch(BLENDER_MODEL_URL);if(!response.ok)throw Error('原始 GLB 读取失败')
    download(await response.arrayBuffer(),'Mini-CD-Blender-53x45x8.glb');setStatus('已下载 Blender 原始 GLB · 单位为米')
  }catch(e){setStatus(e instanceof Error?e.message:'模型导出失败')}finally{setBusy(false)}}
  const jid=new URLSearchParams(location.search).get('jid')
  return <div className="sr">
    <header className="sr-head"><div><span className="sr-kicker">MINI CD / STRUCTURE STUDY</span><h1>透明空盒 · 三维结构评审</h1></div><a href={'/mini-mockup/'+(jid?'?jid='+encodeURIComponent(jid):'')}>返回照片样机</a></header>
    <div className="sr-body"><main className="sr-main"><div className="sr-stage">
      <Canvas gl={{antialias:true,alpha:true,preserveDrawingBuffer:true}} dpr={[1,1.8]} camera={{position:[82,62,142],fov:34,near:.2,far:1000}} onCreated={({gl})=>{gl.toneMapping=THREE.ACESFilmicToneMapping;gl.toneMappingExposure=.95}}>
        {model&&<Scene model={model} angle={angle} lift={lift} disc={disc} shot={shot} revision={revision} auto={auto} controls={controls} api={api}/>}
      </Canvas>
      <div className="sr-stage-label"><span>Blender 三维结构稿</span><strong>{shots[shot].name}</strong></div><div className="sr-drag-hint">拖动旋转 · 滚轮缩放 · 右键平移</div>
    </div><div className="sr-status" role="status">{status}</div></main>
    <aside className="sr-tools"><section><h2>01 / 材质检查</h2><div className="sr-switch"><button aria-pressed={finish==='clear'} onClick={()=>setFinish('clear')}>透明塑料</button><button aria-pressed={finish==='clay'} onClick={()=>setFinish('clay')}>结构白模</button></div><p>透明看整体；白模看壁厚、凹槽和卡扣。</p></section>
    <section><h2>02 / 五个观察角度</h2><div className="sr-shots">{shots.map((s,i)=><button key={s.id} aria-pressed={shot===i} onClick={()=>selectShot(i)}><span>0{i+1}</span>{s.name}<b>↗</b></button>)}</div></section>
    <section><h2>03 / 手动检查</h2><label>盒盖开合 <output>{angle}°</output><input aria-label="盒盖开合" type="range" min={0} max={180} step={1} value={angle} onChange={e=>setAngle(+e.target.value)}/></label><label>光盘取出 <output>{Math.round(lift/22*100)}%</output><input aria-label="光盘取出" type="range" min={0} max={22} step={.2} value={lift} onChange={e=>{setDisc(true);setLift(+e.target.value)}}/></label><label className="sr-check"><input type="checkbox" checked={disc} onChange={e=>setDisc(e.target.checked)}/>显示空白光盘</label><div className="sr-row"><button onClick={()=>setAuto(v=>!v)}>{auto?'停止旋转':'自动旋转'}</button><button onClick={()=>setRevision(v=>v+1)}>重置机位</button></div></section>
    <section><h2>04 / 保存检查结果</h2><label className="sr-size">PNG 图片<select value={size} onChange={e=>setSize(+e.target.value)}><option value={2048}>2K · 2048 px</option><option value={4096}>4K · 4096 px</option></select></label><button className="sr-primary" onClick={()=>api.current?.capture(size)}>保存当前角度 PNG</button><button className="sr-full" disabled={busy} onClick={exportModel}>{busy?'正在导出…':'下载三维模型 GLB'}</button></section>
    <section className="sr-spec"><strong>53 × 45 × 8 <small>mm</small></strong><p>主体尺寸，不含顶部挂孔。光盘 Ø40 / 孔 Ø5 mm。</p><p>壁厚 {SHELL_MM.wall} mm、铰链、卡扣和挂孔细节为可调估算。当前用于外观与结构评审。</p></section></aside></div>
  </div>
}
