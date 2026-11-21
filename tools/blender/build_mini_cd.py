"""Reference-guided Mini-CD shell study, authored in Blender millimetres.

53/45/8 and 40/5 are measured/provided. Other dimensions remain estimates.
Creates an editable .blend, GLB and five Cycles renders, with no album art.
"""
import argparse
import json
import math
import sys
from pathlib import Path
import bpy
from mathutils import Vector

MM = .001
PROJECT = Path(__file__).resolve().parents[2]
OUT = PROJECT / 'blender'
IMAGES = OUT / 'renders'
parser = argparse.ArgumentParser()
parser.add_argument('--samples', type=int, default=96)
parser.add_argument('--resolution', type=int, default=1280)
parser.add_argument('--render', default='all')
parser.add_argument('--clay', action='store_true')
args = parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
OUT.mkdir(exist_ok=True)
IMAGES.mkdir(exist_ok=True)

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
for c in list(bpy.data.collections):
    if c.name != 'Collection' and not c.objects:
        bpy.data.collections.remove(c)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.unit_settings.scale_length = 1
scene.unit_settings.length_unit = 'MILLIMETERS'

def collection(name):
    c = bpy.data.collections.new(name)
    scene.collection.children.link(c)
    return c

model_collection = collection('01_迷你CD外壳（细部估算待校准）')
studio_collection = collection('02_摄影棚')
reference_collection = collection('03_实物参考（不参与渲染）')

def empty(name, parent=None, xyz=(0,0,0)):
    obj = bpy.data.objects.new(name, None)
    model_collection.objects.link(obj)
    obj.empty_display_type = 'PLAIN_AXES'
    obj.empty_display_size = .005
    obj.location = Vector(xyz)*MM
    obj.parent = parent
    return obj

root = empty('MiniCD_53x45x8mm')
root['measured_body_mm'] = [53.,45.,8.]
root['reference'] = '用户确认的五张空盒照片和实物拆装视频'
root['estimated_details'] = '壁厚、挂孔、卡扣、铰链截面仍为估算，非生产CAD'
base = empty('盒底_含固定窄侧槽', root)
hinge = empty('铰链转轴_Y', root, (-18.85,0,4.2))
lid = empty('盒盖_方形窗', hinge, (18.85,0,-4.2))
disc_root = empty('空白光盘_40mm_孔5mm', root, (3.5,0,2.9))

shadow_outputs=[]
def material(name, color, transmission=0, roughness=.3, metallic=0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = next((node for node in m.node_tree.nodes if node.type=='BSDF_PRINCIPLED'),None)
    if p is None:
        p=m.node_tree.nodes.new('ShaderNodeBsdfPrincipled')
        output=next((node for node in m.node_tree.nodes if node.type=='OUTPUT_MATERIAL'),None) or m.node_tree.nodes.new('ShaderNodeOutputMaterial')
        m.node_tree.links.new(p.outputs['BSDF'],output.inputs['Surface'])
    p.inputs['Base Color'].default_value = (*color,1)
    p.inputs['Roughness'].default_value = roughness
    p.inputs['Metallic'].default_value = metallic
    p.inputs['Transmission Weight'].default_value = transmission
    p.inputs['IOR'].default_value = 1.59
    if transmission:
        # Multi-layer polished plastic needs transmissive shadow rays. This
        # avoids an opaque black slab when the case lies on the white stage.
        # Camera and glossy rays still use the physical Principled surface.
        nodes=m.node_tree.nodes;links=m.node_tree.links
        output=next(n for n in nodes if n.type=='OUTPUT_MATERIAL')
        path=nodes.new('ShaderNodeLightPath')
        transparent=nodes.new('ShaderNodeBsdfTransparent');transparent.inputs['Color'].default_value=(.97,.97,.97,1)
        mix=nodes.new('ShaderNodeMixShader')
        links.new(path.outputs['Is Shadow Ray'],mix.inputs[0]);links.new(p.outputs['BSDF'],mix.inputs[1]);links.new(transparent.outputs[0],mix.inputs[2]);links.new(mix.outputs[0],output.inputs['Surface'])
        shadow_outputs.append((m,p,mix,output))
    return m

plastic = material('透明注塑塑料_IOR估算1.59',(.985,.990,.995),1,.012)
window_mat = material('透明薄盖板',(.995,.997,1),1,.003)
metal = material('空白盘铝反射层',(.69,.73,.78),0,.22,1)
next(n for n in metal.node_tree.nodes if n.type=='BSDF_PRINCIPLED').inputs['Anisotropic'].default_value = .65
floor_mat = material('摄影棚白底',(.85,.85,.85),0,.55)
flag_mat = material('反射黑旗',(.008,.011,.014),0,.7)

def rounded(w,h,r,steps=10):
    pts = []
    for cx,cy,start in [(w/2-r,h/2-r,0),(-w/2+r,h/2-r,90),(-w/2+r,-h/2+r,180),(w/2-r,-h/2+r,270)]:
        for j in range(steps+1):
            a = math.radians(start+j/steps*90)
            pts.append((cx+r*math.cos(a),cy+r*math.sin(a)))
    return pts

def circle(r, n=128, flat=None):
    return [(r*math.cos(i/n*math.tau),max(-flat,min(flat,r*math.sin(i/n*math.tau))) if flat else r*math.sin(i/n*math.tau)) for i in range(n)]

def extruded(name, outer, depth, xyz=(0,0,0), parent=base, holes=(), bevel=.06, mat=plastic):
    data = bpy.data.curves.new(name, 'CURVE')
    data.dimensions = '2D'
    data.resolution_u = 2
    data.fill_mode = 'BOTH'
    data.extrude = max(0,depth/2-bevel)*MM
    data.bevel_depth = bevel*MM
    data.bevel_resolution = 3
    for points in [outer]+[list(reversed(p)) for p in holes]:
        spl = data.splines.new('POLY')
        spl.points.add(len(points)-1)
        for co,(x,y) in zip(spl.points,points):
            co.co = (x*MM,y*MM,0,1)
        spl.use_cyclic_u = True
    obj = bpy.data.objects.new(name,data)
    model_collection.objects.link(obj)
    obj.parent = parent
    obj.location = Vector((xyz[0],xyz[1],xyz[2]+depth/2))*MM
    obj.data.materials.append(mat)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.convert(target='MESH')
    obj = bpy.context.object
    obj.select_set(False)
    obj.cycles.is_caustics_caster = False
    for poly in obj.data.polygons:
        poly.use_smooth = True
    # Smooth the small fillets while keeping the broad flat mould faces flat.
    normal = obj.modifiers.new('成型面加权法线','WEIGHTED_NORMAL')
    normal.keep_sharp = True
    normal.weight = 40
    return obj

def block(name,w,h,d,xyz,parent=base,r=.2,mat=plastic,bevel=.045):
    b = min(bevel,d/4,w/5,h/5)
    return extruded(name,rounded(w-2*b,h-2*b,max(.02,min(r-b,(w-2*b)/2,(h-2*b)/2))),d,xyz,parent,bevel=b,mat=mat)

def frame(name,w,h,wall,d,xyz,parent=base,r=.75,bevel=.07):
    b = bevel
    return extruded(name,rounded(w-2*b,h-2*b,r-b),d,xyz,parent,
        holes=[rounded(w-2*wall+2*b,h-2*wall+2*b,max(.12,r-wall+b))],bevel=b)

def tube(name,pts,r,xyz=(0,0,0),parent=base,mat=plastic):
    data = bpy.data.curves.new(name,'CURVE')
    data.dimensions = '3D'
    data.resolution_u = 2
    data.bevel_depth = r*MM
    data.bevel_resolution = 4
    spl = data.splines.new('POLY')
    spl.points.add(len(pts)-1)
    for p,co in zip(spl.points,pts):p.co = (*[c*MM for c in co],1)
    obj = bpy.data.objects.new(name,data)
    model_collection.objects.link(obj)
    obj.parent = parent
    obj.location = Vector(xyz)*MM
    obj.data.materials.append(mat)
    return obj

def pin(name,r,length,xyz,parent=base):
    obj=extruded(name,circle(r,48),length,xyz,parent,bevel=.04)
    # extruded() places the centre at z + length/2; replace for the Y-axis pin.
    obj.rotation_euler.x = math.pi/2
    obj.location = Vector(xyz)*MM
    return obj

# Shell bottom: a real thin plate inside a hollow double-step perimeter.
frame('盒底外墙_53x45',53,45,.75,4.60,(0,0,0),r=.85)
block('盒底透明底板',51.55,43.55,.65,(0,0,0),r=.55,mat=window_mat)
frame('盒底外沿圆角压筋',52.4,44.4,.25,.32,(0,0,.20),r=.7,bevel=.035)
frame('内圈座台_细台阶',50.9,42.9,.34,.40,(0,0,.72),r=.6,bevel=.045)
frame('盒底口沿细亮边',52.4,44.4,.26,.30,(0,0,4.15),r=.6,bevel=.035)
# Recessed moulding lines on both depth levels, kept within the 53 x 45 outline.
frame('盒底中层注塑台阶',51.85,43.85,.22,.24,(0,0,2.85),r=.65,bevel=.03)
frame('盒底底面内侧细棱',50.2,42.2,.20,.24,(0,0,.67),r=.55,bevel=.03)

# Fixed spine, with rounded upper/lower ear openings rather than a free ladder.
for x in [-26.12,-18.88]:
    block('固定侧槽竖壁',.76,35.4,7.8,(x,0,.05),r=.2)
    for y in [-21.75,21.75]:block('侧槽角座',.76,1.4,7.8,(x,y,.05),r=.2)
for y in [-22.12,22.12]:block('侧槽横向封边',7.4,.76,7.8,(-22.5,y,.05),r=.2)
block('侧槽正面薄窗',5.20,39.0,.55,(-22.5,0,7.25),r=.4,mat=window_mat)
frame('侧槽窗口抛光框',5.8,40.0,.35,.48,(-22.5,0,7.10),r=.65,bevel=.06)
block('侧封纸座台',5.6,38,.32,(-22.5,0,.82),r=.35,mat=window_mat)
for x in [-25.35,-19.45]:block('侧槽内压筋',.25,39.0,.45,(x,0,7.0),r=.1)

# Flattened circular tray mould, thin outside bead and inner relief groove.
extruded('盘槽外环_上下平口',circle(20.65,192,19.12),.62,(2.5,0,.85),holes=[circle(20.10,192,18.70)],bevel=.055)
extruded('盘槽内侧细筋',circle(19.85,192,18.55),.24,(2.5,0,.78),holes=[circle(19.63,192,18.38)],bevel=.035)
for y in [-20.75,20.75]:
    block('盘托长向加强筋',43.8,.38,.5,(2.5,y,1.0),r=.12)
    block('盘托上下成型横梁',43.6,1.05,1.3,(2.5,y,1.25),r=.32)

def clip(name,x,y,z,parent,flip=False,scale=1):
    group=empty(name,parent,(x,y,z))
    if flip:group.rotation_euler.z=math.pi
    # Broad transparent half-moon tongue and the nested polished U bead.
    radius=2.45*scale;stem=.55*scale
    pts=[(-radius,0),(radius,0),(radius,-stem)]+[(radius*math.cos(a),-stem-radius*math.sin(a)) for a in [i/40*math.pi for i in range(41)]]
    extruded('卡扣薄舌',pts,.30,(0,0,0),group,bevel=.035,mat=window_mat)
    arc=[(radius,0,.1),(radius,-stem,.1)]+[(radius*math.cos(i/60*math.pi),-stem-radius*math.sin(i/60*math.pi),.1) for i in range(61)]+[(-radius,0,.1)]
    tube('卡扣U形圆边',arc,.18*scale,parent=group)
    tube('卡扣内侧台阶',[(2.08*scale*math.cos(i/50*math.pi),-stem-2.08*scale*math.sin(i/50*math.pi),.09) for i in range(51)],.09*scale,parent=group)
    block('卡扣根部横梁',5.3*scale,.55,.55,(0,.18,-.10),group,r=.2)
    return group

for x in [-12.2,17.2]:
    for sign in [-1,1]:
        g=clip('盘托角部半圆座',x,sign*21.0,1.18,base,sign<0,1.03)
        for dx in [-2.45,2.45]:block('半圆座侧肩',.65,1.4,.7,(dx,-.15,-.08),g,r=.2)
        dx=1 if x<0 else -1
        tube('盘槽斜向连接筋',[(dx*2.25,-1.6,.05),(dx*4.0,-3.0,.05)],.20,parent=g)

# Disc hub: clear circular seat, two hollow split hooks and two small locators.
extruded('盘芯透明圆座',circle(6.3,96),.30,(2.5,0,.76),holes=[circle(2.5,96)],bevel=.035,mat=window_mat)
extruded('中心孔承托圈',circle(2.68,96),.8,(2.5,0,1.10),holes=[circle(2.43,96)],bevel=.035)
for sign in [-1,1]:
    g=empty('盘芯分叉弹片',base,(2.5,sign*1.42,1.47))
    if sign<0:g.rotation_euler.z=math.pi
    extruded('弹片中空圆角舌',rounded(2.55,1.70,.65),1.15,(0,0,0),g,holes=[rounded(1.65,.92,.35)],bevel=.045)
    block('弹片扣唇',2.3,.40,.35,(0,.62,1.02),g,r=.15)
for x in [.27,4.73]:extruded('盘芯小定位柱',circle(.28,32),.50,(x,0,1.0),bevel=.035)

def hanging_tab(name,z,parent):
    r=3.45
    points=[(-4.25,-3.7),(-r,-2.4),(-r,0)]
    points += [(r*math.cos(math.pi-i/64*math.pi),r*math.sin(math.pi-i/64*math.pi)) for i in range(65)]
    points += [(r,-2.4),(4.25,-3.7)]
    obj=extruded(name,points,1.05,(0,25.6,z),parent,holes=[circle(1.75,96)],bevel=.14)
    tube(name+'_孔口圆唇',[(1.86*math.cos(i/96*math.tau),1.86*math.sin(i/96*math.tau),0) for i in range(97)],.14,(0,25.6,z+.93),parent)
    tube(name+'_外轮廓圆唇',[(r*math.cos(math.pi-i/72*math.pi),r*math.sin(math.pi-i/72*math.pi),0) for i in range(73)],.16,(0,25.6,z+.93),parent)
    return obj

hanging_tab('盒底挂耳',1.25,base)
for y in [-16.8,16.8]:block('闭合锁扣接座',.8,3.2,1.5,(25.48,y,2.8),r=.25)

# Front lid: square clear window, receiving lip and four paper retainers.
frame('盒盖45mm方框',45,45,.75,3.30,(4,0,4.70),lid,r=.85)
block('盒盖透明窗板',43.55,43.55,.60,(4,0,7.40),lid,r=.6,mat=window_mat)
frame('盒盖内侧压边台阶',43.45,43.45,.28,.32,(4,0,6.92),lid,r=.6,bevel=.035)
frame('盒盖外缘抛光细筋',44.5,44.5,.22,.25,(4,0,7.64),lid,r=.7,bevel=.03)
frame('盒盖中层注塑台阶',44.15,44.15,.22,.24,(4,0,5.65),lid,r=.65,bevel=.03)
for x in [-12.2,17.2]:
    for sign in [-1,1]:clip('盒盖压纸半圆卡扣',x,sign*21.25,6.52,lid,sign<0)
for x in [-17.55,25.55]:
    for y in [-11.5,11.5]:block('纸片侧向挡条',.5,7.2,.62,(x,y,6.65),lid,r=.2)
hanging_tab('盒盖挂耳',6.30,lid)
for y in [-16.8,16.8]:block('盒盖闭合弹扣',.55,2.5,.55,(25.45,y,4.72),lid,r=.22)

# Pivot barrels share a Y axis. Arms connect to the left of the square lid.
for y in [-19.8,19.8]:
    pin('底座铰链轴套',.72,3.0,(-18.85,y,4.2))
    pin('铰链透明销轴',.38,4.0,(-18.85,y,4.2))
    block('铰链成型支座',1.35,3.8,2.0,(-19.35,y,1.7),r=.3)
    block('盒盖铰链连接耳',1.5,1.65,.95,(-18.3,y,4.52),lid,r=.3)
    eye=extruded('铰链耳孔',circle(.82,64),1.5,(-18.85,y,4.2),lid,holes=[circle(.43,64)],bevel=.045)
    eye.rotation_euler.x=math.pi/2
    eye.location=Vector((-18.85,y,4.2))*MM

# Optional blank disc; it remains a separate object in the saved project.
extruded('光盘金属反射层',circle(19.94,192),.18,(0,0,.15),disc_root,holes=[circle(2.5,128)],bevel=.02,mat=metal)
extruded('光盘聚碳酸酯外沿',circle(20,192),.50,(0,0,0),disc_root,holes=[circle(19.8,192)],bevel=.035)
extruded('光盘透明中心圈',circle(5.1,128),.48,(0,0,.01),disc_root,holes=[circle(2.5,128)],bevel=.035,mat=window_mat)

def track(obj,point):obj.rotation_euler=(Vector(point)-obj.location).to_track_quat('-Z','Y').to_euler()
def light(name,pos,power,size,size_y):
    data=bpy.data.lights.new(name,'AREA');data.energy=power;data.shape='RECTANGLE';data.size=size;data.size_y=size_y
    obj=bpy.data.objects.new(name,data);studio_collection.objects.link(obj);obj.location=Vector(pos)*MM;track(obj,(0,0,.015));return obj

light('主柔光箱',(-125,-95,75),14,.08,.16)
light('右侧条形反射',(115,15,65),7,.018,.12)
light('背部轮廓灯',(-15,130,65),9,.14,.018)
world=bpy.data.worlds.new('中性摄影棚环境');scene.world=world;world.use_nodes=True
background=next((n for n in world.node_tree.nodes if n.type=='BACKGROUND'),None)
if background is None:
    background=world.node_tree.nodes.new('ShaderNodeBackground')
    output=next((n for n in world.node_tree.nodes if n.type=='OUTPUT_WORLD'),None) or world.node_tree.nodes.new('ShaderNodeOutputWorld')
    world.node_tree.links.new(background.outputs['Background'],output.inputs['Surface'])
background.inputs['Color'].default_value=(.55,.55,.55,1)
background.inputs['Strength'].default_value=.18
bpy.ops.mesh.primitive_plane_add(size=2, location=(0,0,-.00025))
floor=bpy.context.object;floor.name='白色无缝摄影台';floor.data.materials.append(floor_mat)
for c in list(floor.users_collection):c.objects.unlink(floor)
studio_collection.objects.link(floor)
for x in [-95,95]:
    obj=block('反射黑旗',5,180,100,(x,0,10),None,r=.5,mat=flag_mat)
    for c in list(obj.users_collection):c.objects.unlink(obj)
    studio_collection.objects.link(obj)
    obj.visible_camera=False

camera_data=bpy.data.cameras.new('产品正交镜头');camera=bpy.data.objects.new('产品正交镜头',camera_data);studio_collection.objects.link(camera);scene.camera=camera
camera_data.type='ORTHO';camera_data.lens=70;camera_data.clip_start=.0001;camera_data.clip_end=10
scene.render.engine='CYCLES';scene.cycles.samples=args.samples;scene.cycles.use_denoising=True
scene.cycles.adaptive_threshold=.025
scene.cycles.max_bounces=20;scene.cycles.transmission_bounces=16;scene.cycles.transparent_max_bounces=20
scene.cycles.glossy_bounces=10
prefs=bpy.context.preferences.addons['cycles'].preferences
try:
    prefs.compute_device_type='OPTIX';prefs.get_devices()
    for device in prefs.devices:device.use=device.type=='OPTIX'
    scene.cycles.device='GPU'
except Exception:scene.cycles.device='CPU'
scene.render.resolution_x=scene.render.resolution_y=args.resolution
scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'
scene.view_settings.view_transform='AgX'
scene.view_settings.look='AgX - Medium High Contrast'
scene.view_settings.exposure=-2.6
scene.cycles.caustics_refractive=False

# Packed reference empties stay clearly labelled and are hidden from renders.
refs=PROJECT/'workbench'/'mini3d-src'/'public'/'reference'
for i,name in enumerate(['01-closed.jpg','02-flat-open.png','03-left-angle.png','04-right-angle.png','05-disc-out.png']):
    img=bpy.data.images.load(str(refs/name),check_existing=True);img.pack()
    obj=bpy.data.objects.new('实物照片_'+name,None);obj.empty_display_type='IMAGE';obj.data=img;obj.empty_display_size=.12;obj.location=(.23,i*.14,0);obj.hide_render=True;reference_collection.objects.link(obj)

POSES={
    '01-闭合正面':dict(open=0,stand=False,cam=(0,0,220),target=(0,1,4),scale=.080,disc=False),
    '02-平铺展开':dict(open=180,stand=False,cam=(-25,-5,240),target=(-25,0,3),scale=.135,disc=False),
    '03-立体内侧':dict(open=112,stand=True,cam=(110,-165,125),target=(-15,0,23),scale=.116,disc=False),
    '04-立体外侧':dict(open=112,stand=True,cam=(-120,165,120),target=(-15,0,23),scale=.116,disc=False),
    '05-展开取盘':dict(open=180,stand=False,cam=(-18,-70,235),target=(-18,-10,4),scale=.145,disc=True),
}
def pose(spec):
    hinge.rotation_euler.y=-math.radians(spec['open'])
    root.rotation_euler=(math.pi/2 if spec['stand'] else 0,0,0)
    root.location=(0,0,.0225 if spec['stand'] else 0)
    for obj in disc_root.children:obj.hide_render=not spec['disc'];obj.hide_set(not spec['disc'])
    disc_root.location=Vector((37,-32,.7) if spec['disc'] else (3.5,0,2.9))*MM
    camera.location=Vector(spec['cam'])*MM;track(camera,Vector(spec['target'])*MM);camera.data.ortho_scale=spec['scale']
    bpy.context.view_layer.update()

pose(POSES['03-立体内侧'])
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            area.spaces.active.clip_start=.0001
            area.spaces.active.region_3d.view_perspective='CAMERA'
            area.spaces.active.shading.type='MATERIAL'
if hasattr(scene,'blendermcp_auto_start_server'):scene.blendermcp_auto_start_server=True
blend=OUT/'迷你CD-透明外壳-结构初稿.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(blend))

# GLB is exported as a flat, open model in metres; references and lights excluded.
pose(POSES['02-平铺展开'])
bpy.ops.object.select_all(action='DESELECT')
for obj in model_collection.objects:
    obj.select_set(True)
for obj in disc_root.children:
    obj.hide_set(False);obj.hide_render=False;obj.select_set(True)
scene.render.filepath=str(IMAGES/'02-平铺展开.png')
for m,p,mix,output in shadow_outputs:m.node_tree.links.new(p.outputs['BSDF'],output.inputs['Surface'])
bpy.ops.export_scene.gltf(filepath=str(OUT/'迷你CD-透明外壳.glb'),export_format='GLB',use_selection=True,export_apply=True,export_animations=False,export_extras=True)
for m,p,mix,output in shadow_outputs:m.node_tree.links.new(mix.outputs[0],output.inputs['Surface'])
bpy.ops.object.select_all(action='DESELECT')

selected=POSES if args.render=='all' else {name:spec for name,spec in POSES.items() if name.startswith(args.render)}
original_slots=[]
if args.clay:
    clay=material('结构检查灰模',(.32,.35,.38),0,.4)
    for obj in model_collection.objects:
        if obj.type in {'MESH','CURVE'}:
            original_slots.append((obj,list(obj.data.materials)))
            obj.data.materials.clear();obj.data.materials.append(clay)
for name,spec in selected.items():
    pose(spec);scene.render.filepath=str(IMAGES/((('结构灰模-' if args.clay else '')+name)+'.png'))
    print('RENDER_START',name,flush=True)
    bpy.ops.render.render(write_still=True)
    print('RENDER_DONE',name,flush=True)
for obj,mats in original_slots:
    obj.data.materials.clear()
    for m in mats:obj.data.materials.append(m)
pose(POSES['03-立体内侧'])
bpy.ops.wm.save_as_mainfile(filepath=str(blend))
print('MINI_CD_BUILD_COMPLETE',json.dumps({'blend':str(blend),'renders':list(selected),'objects':len(model_collection.objects)},ensure_ascii=True),flush=True)
