import * as THREE from 'three'
import {GLTFLoader} from 'three/examples/jsm/loaders/GLTFLoader.js'
import type {ShellFinish} from './shell-model'

export const BLENDER_MODEL_URL='/mini3d/assets/mini-cd-blender.glb'
let source:Promise<ArrayBuffer>|undefined
export async function loadBlenderModel(finish:ShellFinish){
  source??=fetch(BLENDER_MODEL_URL,{cache:'no-store'}).then(r=>{if(!r.ok)throw Error('Blender 模型读取失败');return r.arrayBuffer()})
  const gltf=await new GLTFLoader().parseAsync((await source).slice(0),'')
  const asset=gltf.scene
  const node=(name:string)=>{const found=asset.getObjectByName(name);if(!found)throw Error('模型缺少零件：'+name);return found}
  const base=node('盒底_含固定窄侧槽'),lid=node('盒盖_方形窗'),pivot=node('铰链转轴_Y'),disc=node('空白光盘_40mm_孔5mm')
  const root=new THREE.Group();root.name='Blender_shell_review_mm';root.rotation.x=Math.PI/2;root.scale.setScalar(1000);root.add(asset)
  root.userData={source:'Blender',bodyDimensionsMm:[53,45,8],displayUnits:'millimetres',previewMaterial:true}
  const geometries=new Set<THREE.BufferGeometry>(),materials=new Set<THREE.Material>()
  asset.traverse(obj=>{
    if(!(obj instanceof THREE.Mesh))return
    geometries.add(obj.geometry)
    const prior=Array.isArray(obj.material)?obj.material:[obj.material];prior.forEach(m=>materials.add(m))
    const isWindow=prior.some(m=>m.name.includes('薄盖板'))
    const isDisc=prior.some(m=>m.name.includes('反射层'))
    const mat=finish==='clay'?new THREE.MeshStandardMaterial({color:'#a4aeb5',roughness:.45}):isDisc?new THREE.MeshStandardMaterial({color:'#b8c3cd',metalness:.85,roughness:.25}):new THREE.MeshPhysicalMaterial({color:isWindow?'#eef2f5':'#7f8c96',roughness:.08,metalness:0,transparent:true,opacity:isWindow?.035:.32,depthWrite:false,clearcoat:1,clearcoatRoughness:.025,side:THREE.DoubleSide})
    materials.add(mat);obj.material=mat
  })
  const update=(degrees:number,lift:number,showDisc:boolean)=>{
    // Blender's Y hinge becomes glTF's -Z. The outer wrapper converts the
    // glTF Y-up asset back to the existing XY-facing review camera system.
    pivot.rotation.set(0,0,THREE.MathUtils.degToRad(degrees))
    const released=Math.max(0,(lift-7)/15)
    disc.position.set((2.5+35*released)/1000,(2.9+Math.min(lift,7))/1000,31*released/1000)
    disc.visible=showDisc;root.updateMatrixWorld(true)
  }
  update(0,0,false)
  const dimensions=()=>{
    update(0,0,false)
    return new THREE.Box3().setFromObject(node('盒底外墙_53x45')).union(new THREE.Box3().setFromObject(node('盒盖45mm方框'))).getSize(new THREE.Vector3()).toArray()
  }
  return {root,base,lid,pivot,disc,update,dimensions,dispose:()=>{geometries.forEach(g=>g.dispose());materials.forEach(m=>m.dispose())}}
}
