import * as THREE from 'three'

export const SHELL_MM = {
  width:53,height:45,depth:8,discDiameter:40,discHole:5,
  wall:.8,backPlate:.65,lidPlate:.65,baseDepth:4.6,
  hingeX:-24.3,hingeZ:4.1,hangerRadius:3.55,hangerHoleRadius:1.75,
} as const
export type ShellFinish='clear'|'clay'

function rounded(w:number,h:number,r:number){
  const s=new THREE.Shape(),x=-w/2,y=-h/2
  s.moveTo(x+r,y);s.lineTo(x+w-r,y);s.quadraticCurveTo(x+w,y,x+w,y+r)
  s.lineTo(x+w,y+h-r);s.quadraticCurveTo(x+w,y+h,x+w-r,y+h)
  s.lineTo(x+r,y+h);s.quadraticCurveTo(x,y+h,x,y+h-r)
  s.lineTo(x,y+r);s.quadraticCurveTo(x,y,x+r,y);s.closePath();return s
}
function extrude(s:THREE.Shape,depth:number,bevel=.1){
  const g=new THREE.ExtrudeGeometry(s,{depth:Math.max(.02,depth-2*bevel),steps:1,bevelEnabled:bevel>0,bevelThickness:bevel,bevelSize:bevel,bevelSegments:3,curveSegments:24})
  g.translate(0,0,bevel);g.computeVertexNormals();return g
}
function slab(w:number,h:number,d:number,r=.5,b=.1){return extrude(rounded(w-2*b,h-2*b,Math.max(.05,r-b)),d,b)}
function rim(w:number,h:number,wall:number,d:number,r=.7,b=.1){
  const s=rounded(w-2*b,h-2*b,r-b),inner=rounded(w-2*wall+2*b,h-2*wall+2*b,.3)
  s.holes.push(new THREE.Path(inner.getPoints(40).reverse()));return extrude(s,d,b)
}
function flatCircle(r:number,yLimit:number){const s=new THREE.Shape();for(let i=0;i<=160;i++){const a=i/160*Math.PI*2,x=Math.cos(a)*r,y=THREE.MathUtils.clamp(Math.sin(a)*r,-yLimit,yLimit);i?s.lineTo(x,y):s.moveTo(x,y)}s.closePath();return s}
function discChannel(outer:number,inner:number,flat:number,d:number){const s=flatCircle(outer,flat);s.holes.push(new THREE.Path(flatCircle(inner,flat-.35).getPoints().reverse()));return extrude(s,d,.07)}
function ring(inner:number,outer:number,d:number){const s=new THREE.Shape();s.absarc(0,0,outer,0,Math.PI*2,false);const h=new THREE.Path();h.absarc(0,0,inner,0,Math.PI*2,true);s.holes.push(h);return extrude(s,d,.045)}
function hanger(){
  const r=SHELL_MM.hangerRadius,s=new THREE.Shape();s.moveTo(-r-1,-3.8);s.quadraticCurveTo(-r,-3.5,-r,-1);s.lineTo(-r,0);s.absarc(0,0,r,Math.PI,0,true);s.lineTo(r,-1);s.quadraticCurveTo(r,-3.5,r+1,-3.8);s.closePath()
  const h=new THREE.Path();h.absarc(0,0,SHELL_MM.hangerHoleRadius,0,Math.PI*2,true);s.holes.push(h);return extrude(s,1,.1)
}
function tongue(){
  const s=new THREE.Shape();s.moveTo(-2.65,0);s.lineTo(2.65,0);s.bezierCurveTo(2.65,-1.6,1.6,-2.75,0,-2.75);s.bezierCurveTo(-1.6,-2.75,-2.65,-1.6,-2.65,0);s.closePath();return extrude(s,.34,.045)
}
function uBead(){
  const s=new THREE.Shape();s.moveTo(-2.63,0);s.bezierCurveTo(-2.63,-1.65,-1.6,-2.8,0,-2.8);s.bezierCurveTo(1.6,-2.8,2.63,-1.65,2.63,0);s.lineTo(2.23,0);s.bezierCurveTo(2.23,-1.4,1.35,-2.38,0,-2.38);s.bezierCurveTo(-1.35,-2.38,-2.23,-1.4,-2.23,0);s.closePath();return extrude(s,.50,.055)
}

export function createShellModel(finish:ShellFinish='clear'){
  const geometries=new Set<THREE.BufferGeometry>(),materials=new Set<THREE.Material>()
  const plastic=finish==='clear'
    ? new THREE.MeshPhysicalMaterial({color:'#59646e',metalness:0,roughness:.09,transmission:0,transparent:true,opacity:.44,depthWrite:false,ior:1.49,thickness:.7,clearcoat:1,clearcoatRoughness:.025,envMapIntensity:1.3,side:THREE.DoubleSide})
    : new THREE.MeshStandardMaterial({color:'#86939d',metalness:0,roughness:.47})
  // Raster transmission cannot see another transmissive part behind the lid.
  // Thin alpha panels keep the actual tray geometry visible during review.
  const panel=plastic.clone();if(panel instanceof THREE.MeshPhysicalMaterial){panel.roughness=.035;panel.opacity=.035;panel.depthWrite=false}
  const pin=plastic.clone();if(pin instanceof THREE.MeshPhysicalMaterial)pin.roughness=.10
  const silver=new THREE.MeshStandardMaterial({color:'#c5cbd0',metalness:.88,roughness:.23})
  ;[plastic,panel,pin,silver].forEach(m=>materials.add(m))
  const root=new THREE.Group();root.name='MiniCD_53x45x8mm';root.userData={units:'millimetres',bodyDimensionsMm:[53,45,8],estimatedDetails:['wall','hinge','clips','hanger','hub']}
  const base=new THREE.Group();base.name='Case_bottom';root.add(base)
  const pivot=new THREE.Group();pivot.name='Lid_hinge_axis';pivot.position.set(SHELL_MM.hingeX,0,SHELL_MM.hingeZ);root.add(pivot)
  const lid=new THREE.Group();lid.name='Case_lid';lid.position.set(-SHELL_MM.hingeX,0,-SHELL_MM.hingeZ);pivot.add(lid)
  function add(parent:THREE.Object3D,name:string,geo:THREE.BufferGeometry,x=0,y=0,z=0,mat:THREE.Material=plastic){
    geometries.add(geo);const m=new THREE.Mesh(geo,mat);m.name=name;m.position.set(x,y,z);m.castShadow=true;m.receiveShadow=true;parent.add(m);return m
  }
  function bar(parent:THREE.Object3D,name:string,w:number,h:number,d:number,x:number,y:number,z:number,mat=plastic){return add(parent,name,slab(w,h,d,Math.min(.32,w/3,h/3),Math.min(.065,d/4,w/5,h/5)),x,y,z,mat)}
  // Base envelope: all body features stay inside the measured 53 x 45 x 8.
  add(base,'Bottom_wall_53x45',rim(53,45,.8,4.6),0,0,0)
  add(base,'Back_clear_plate',slab(51.5,43.5,.65,.55,.08),0,0,0,panel)
  add(base,'Inner_seating_rail',rim(50.8,42.8,.34,.45,.55,.055),0,0,.80)
  add(base,'Outer_moulded_edge_step',rim(52.3,44.3,.28,.45,.65,.045),0,0,.20)
  add(base,'Top_wall_polished_bead',rim(52.4,44.4,.25,.35,.6,.045),0,0,4.15)
  for(const y of [-20.8,20.8]){
    bar(base,'Long_moulded_rail',48,.42,.6,0,y,1.15)
    for(const x of [-14,17])bar(base,'Corner_bridge',5.2,1.0,1.1,x,y,1.3)
  }
  // The narrow fixed spine is a raised glazing channel, not two exposed
  // hinge rods. Leave the pivot-ear openings clear at its two ends.
  for(const x of [-26.1,-18.9]){
    bar(base,'Spine_full_height_wall',.8,35.0,7.8,x,0,.05)
    for(const y of [-21.8,21.8])bar(base,'Spine_end_wall',.8,1.25,7.8,x,y,.05)
  }
  for(const y of [-22.1,22.1])bar(base,'Spine_header',7.6,.8,7.8,-22.5,y,.05)
  bar(base,'Spine_front_clear_window',6.35,35.5,.5,-22.5,0,7.35,panel)
  bar(base,'Spine_label_recess',5.6,38,.35,-22.5,0,1.0,panel)
  for(const x of [-25.35,-19.45])bar(base,'Spine_border_rail',.30,35.5,.55,x,0,7.05)
  for(const y of [-17,17])bar(base,'Lid_snap_receiver',.8,3.1,1.6,25.45,y,2.7)
  // The disc groove is flattened at top and bottom, as in the reference.
  add(base,'Tray_disc_channel',discChannel(20.7,20.12,19.15,.65),3.5,0,1.10)
  add(base,'Tray_inner_bead',discChannel(19.85,19.62,18.63,.25),3.5,0,1.0)
  // Four semicircular corner saddles and their braces are prominent in the
  // real moulded tray; they are separate from the lid's paper clips.
  for(const x of [-11,18])for(const sign of [-1,1]){
    const g=new THREE.Group();g.name=`Tray_corner_saddle_${x}_${sign}`;g.position.set(x,sign*21.15,1.10);if(sign<0)g.rotation.z=Math.PI;base.add(g)
    add(g,'Saddle_outer_U',uBead(),0,0,0)
    add(g,'Saddle_clear_infill',tongue(),0,0,.05,panel)
    bar(g,'Saddle_base_crossbar',6.0,.45,.7,0,.25,-.05)
    for(const dx of [-3.2,3.2])bar(g,'Saddle_shoulder',1.0,1.7,.85,dx,-.05,-.05)
    const brace=bar(g,'Radial_channel_brace',3.5,.55,.5,x<0?2.9:-2.9,-2.1,-.1);brace.rotation.z=x<0?-.55:.55
  }
  add(base,'Hub_support_clear_ring',ring(2.5,5.7,.35),3.5,0,1.0,panel)
  add(base,'Hub_inner_bearing',ring(2.43,2.72,.9),3.5,0,1.20)
  // Split spring tongues leave a real slot between the two raised hooks.
  for(const sign of [-1,1]){
    const g=new THREE.Group();g.name='Hub_spring_'+sign;g.position.set(3.5,sign*1.45,1.55);if(sign<0)g.rotation.z=Math.PI;base.add(g)
    const spring=rounded(2.65,1.75,.65);spring.holes.push(new THREE.Path(rounded(1.70,1.0,.4).getPoints().reverse()))
    add(g,'Spring_hollow_rounded_tongue',extrude(spring,1.25,.055),0,0,0)
    bar(g,'Spring_catching_lip',2.3,.42,.35,0,.65,1.1)
  }
  for(const x of [1.25,5.75])add(base,'Hub_round_locator',new THREE.CylinderGeometry(.30,.40,.55,24).rotateX(Math.PI/2),x,0,1.55)
  add(base,'Bottom_hanger',hanger(),0,25.55,1.35)
  // Lid is the square window to the right of the narrow spine channel.
  add(lid,'Lid_rim_45x45',rim(45,45,.8,3.3),4,0,4.7)
  add(lid,'Front_clear_window',slab(43.4,43.4,.65,.55,.08),4,0,7.35,panel)
  add(lid,'Lid_inner_window_rib',rim(43.2,43.2,.30,.32,.5,.045),4,0,6.95)
  add(lid,'Lid_outer_edge_groove',rim(44.5,44.5,.22,.28,.6,.035),4,0,7.65)
  for(const x of [-17.55,25.55])for(const y of [-11.5,11.5])bar(lid,'Insert_side_guide',.6,7.2,.75,x,y,6.55)
  for(const x of [-11.5,18.5])for(const sign of [-1,1]){
    const g=new THREE.Group();g.name=`Paper_clip_${x}_${sign}`;g.position.set(x,sign*21.35,6.35);if(sign<0)g.rotation.z=Math.PI;lid.add(g)
    add(g,'Clip_translucent_tongue',tongue(),0,0,0,panel)
    add(g,'Clip_polished_U_rim',uBead(),0,0,-.05)
    bar(g,'Clip_anchor',5.8,.6,1.1,0,.1,-.35)
  }
  add(lid,'Lid_hanger',hanger(),0,25.55,6.35)
  // Two pivot barrels, joined to lid ears; both share the same Y axis.
  for(const y of [-19.8,19.8]){
    const cyl=(radius:number,len:number)=>new THREE.CylinderGeometry(radius,radius,len,40)
    add(base,'Hinge_base_barrel',cyl(1.05,3.9),SHELL_MM.hingeX,y,SHELL_MM.hingeZ,pin)
    add(base,'Hinge_axle',cyl(.48,5.1),SHELL_MM.hingeX,y,SHELL_MM.hingeZ,pin)
    bar(lid,'Lid_hinge_arm',6.7,1.8,1.1,-21.35,y,4.45)
    bar(base,'Hinge_support_shoulder',2.2,5.8,2.5,-25.1,y,1.6)
    const eye=add(lid,'Lid_hinge_eye',ring(.56,1.13,1.9),SHELL_MM.hingeX,y-.95,SHELL_MM.hingeZ,pin);eye.rotation.x=-Math.PI/2
  }
  for(const y of [-16,16])bar(lid,'Closing_snap',.65,2.6,.65,25.45,y,4.72)
  const disc=new THREE.Group();disc.name='Blank_disc_40mm_hole_5mm';root.add(disc)
  add(disc,'Disc_polycarbonate',ring(2.5,20,.45),0,0,0,silver)
  add(disc,'Disc_clear_centre',ring(2.5,5.0,.48),0,0,0,panel)
  add(disc,'Disc_outer_polished_edge',ring(19.8,20,.48),0,0,0,pin)
  disc.visible=false;disc.position.set(3.5,0,2.85)
  const update=(degrees:number,lift:number,showDisc:boolean)=>{pivot.rotation.y=-THREE.MathUtils.degToRad(degrees);disc.visible=showDisc;const released=Math.max(0,(lift-7)/15);disc.position.set(3.5+25*released,-31*released,2.85+Math.min(lift,7));disc.rotation.set(0,0,0);root.updateMatrixWorld(true)}
  update(0,0,false)
  const dimensions=()=>{const body=new THREE.Box3().setFromObject(base.getObjectByName('Bottom_wall_53x45')!);const cover=new THREE.Box3().setFromObject(lid.getObjectByName('Lid_rim_45x45')!);body.union(cover);return body.getSize(new THREE.Vector3()).toArray()}
  return {root,base,lid,pivot,disc,update,dimensions,dispose:()=>{geometries.forEach(g=>g.dispose());materials.forEach(m=>m.dispose())}}
}
