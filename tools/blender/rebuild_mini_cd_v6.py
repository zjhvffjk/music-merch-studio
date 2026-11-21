"""Independent, fully geometric Mini CD study; no shell photo textures.

Run in a NEW background Blender process. Dimensions in mm converted to metres.
All unmeasured moulding details are visual estimates, not manufacturing CAD.
"""
import argparse
import json
import math
import sys
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector

P = argparse.ArgumentParser()
P.add_argument('--resolution', type=int, default=1200)
P.add_argument('--samples', type=int, default=96)
P.add_argument('--views', default='front,oblique,open,dark,clay')
P.add_argument('--out', default='blender/rebuild-20261119-v6')
A = P.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / A.out
OUT.mkdir(parents=True, exist_ok=True)
MM = .001

# This process starts from factory settings, not the user's live Blender file.
bpy.ops.wm.read_factory_settings(use_empty=True)
S = bpy.context.scene
S.unit_settings.system = 'METRIC'
S.unit_settings.scale_length = 1
S.unit_settings.length_unit = 'MILLIMETERS'
MODEL = bpy.data.collections.new('01 · 实体样机')
STUDIO = bpy.data.collections.new('02 · 可切换摄影棚')
for c in [MODEL, STUDIO]:
    S.collection.children.link(c)


def empty(name, parent=None, pos=(0, 0, 0)):
    ob = bpy.data.objects.new(name, None)
    MODEL.objects.link(ob)
    ob.parent = parent
    ob.location = Vector(pos) * MM
    ob.empty_display_size = .004
    return ob


model = empty('MiniCD · 主体53×45×8mm')
model['body_mm'] = [53., 45., 8.]
model['estimated'] = '壁厚、挂孔、铰链与卡扣细部为照片估算；不是制造CAD'
base = empty('盒底与固定侧槽', model)
pivot = empty('盒盖转轴 · Y · 可开合', model, (-22.5, 0, 4))
lid = empty('盒盖与双面封面', pivot, (22.5, 0, -4))
model['opening_degrees'] = 0.0
model.id_properties_ui('opening_degrees').update(min=0., max=180., description='盒盖开合角度，0闭合，180平铺')
driver = pivot.driver_add('rotation_euler', 1).driver
driver.expression = '-angle*0.017453292519943295'
var = driver.variables.new()
var.name = 'angle'
var.targets[0].id = model
var.targets[0].data_path = '["opening_degrees"]'
carrier = empty('透明盘托 · 仅一套', base)
disc = empty('光盘 · 直径40 · 孔5mm', base, (3.5, 0, 2.32))
prints = []
primary = []


def material(name, color, rough=.3, transmission=0, metallic=0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bs = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    bs.inputs['Base Color'].default_value = (*color, 1)
    bs.inputs['Roughness'].default_value = rough
    bs.inputs['Metallic'].default_value = metallic
    bs.inputs['Transmission Weight'].default_value = transmission
    bs.inputs['IOR'].default_value = 1.49
    if transmission:
        bs.inputs['Coat Weight'].default_value = .12
        bs.inputs['Coat Roughness'].default_value = .03
        # Cycles' default shadow integrator otherwise treats several nested
        # clear walls as an opaque blocker when refractive caustics are off.
        # Camera/glossy rays retain the real glass BSDF and its full thickness.
        nodes, links = m.node_tree.nodes, m.node_tree.links
        path = nodes.new('ShaderNodeLightPath')
        transparent = nodes.new('ShaderNodeBsdfTransparent')
        transparent.inputs['Color'].default_value = (.94, .94, .94, 1)
        mix = nodes.new('ShaderNodeMixShader')
        output = next(n for n in nodes if n.type == 'OUTPUT_MATERIAL')
        links.new(path.outputs['Is Shadow Ray'], mix.inputs[0])
        links.new(bs.outputs['BSDF'], mix.inputs[1])
        links.new(transparent.outputs[0], mix.inputs[2])
        links.new(mix.outputs[0], output.inputs['Surface'])
    m.diffuse_color = (*color, 1)
    return m


clear = material('透明塑料 · IOR1.49估算 · 实体折射', (.985, .993, 1), .025, 1)
aluminium = material('光盘铝反射层', (.68, .72, .78), .2, metallic=1)
next(n for n in aluminium.node_tree.nodes if n.type == 'BSDF_PRINCIPLED').inputs['Anisotropic'].default_value = .7
clay = material('结构检查 · 中性灰', (.42, .47, .52), .28)
floor_mat = material('摄影台 · 可切换', (.72, .74, .77), .29)


def rr(w, h, r, steps=24):
    points = []
    for cx, cy, a0 in [(w/2-r, h/2-r, 0), (-w/2+r, h/2-r, 90),
                       (-w/2+r, -h/2+r, 180), (w/2-r, -h/2+r, 270)]:
        for j in range(steps+1):
            a = math.radians(a0 + 90*j/steps)
            points.append((cx+r*math.cos(a), cy+r*math.sin(a)))
    return points


def circle(r, n=128):
    return [(r*math.cos(i*math.tau/n), r*math.sin(i*math.tau/n)) for i in range(n)]


def mesh(name, vertices, faces, parent=base, mat=clear, bevel=.065):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v*MM for v in p) for p in vertices], [], faces)
    me.update()
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    MODEL.objects.link(ob)
    ob.parent = parent
    ob.data.materials.append(mat)
    # Flat broad panels stay optically flat; only real bevels catch highlights.
    if bevel:
        mod = ob.modifiers.new('注塑圆角', 'BEVEL')
        mod.width = bevel*MM
        mod.segments = 3
        mod.harden_normals = True
        mod = ob.modifiers.new('平面法线', 'WEIGHTED_NORMAL')
        mod.keep_sharp = True
    return ob


def connect(faces, n, a, b):
    for i in range(n):
        j = (i+1) % n
        faces.append((a+i, a+j, b+j, b+i))


def solid(name, profile, depth, pos=(0, 0, 0), parent=base, mat=clear, bevel=.065):
    x, y, z = pos
    n = len(profile)
    v = [(x+a, y+b, z+c) for c in [0, depth] for a, b in profile]
    f = [tuple(reversed(range(n))), tuple(range(n, n*2))]
    connect(f, n, 0, n)
    return mesh(name, v, f, parent, mat, bevel)


def ring(name, outer, inner, depth, pos=(0, 0, 0), parent=base, bevel=.045):
    assert len(outer) == len(inner)
    n = len(outer)
    x, y, z = pos
    v = [(x+a, y+b, z+c) for points, c in [(outer, 0), (outer, depth),
                                                           (inner, depth), (inner, 0)] for a, b in points]
    f = []
    for a, b in [(0, n), (n, 2*n), (2*n, 3*n), (3*n, 0)]:
        connect(f, n, a, b)
    return mesh(name, v, f, parent, clear, bevel)


def block(name, w, h, d, pos, parent=base, r=.2, mat=clear, bevel=.055):
    return solid(name, rr(w, h, min(r, w/2-.01, h/2-.01)), d, pos, parent, mat, bevel)


def cup(name, w, h, d, wall, panel, pos, parent=base, inverted=False):
    # Section follows the photo's rounded outside, recessed seam, projecting
    # lip and thin inner wall instead of one broad rectangular rim face.
    section = [(.15, 0), (0, .16), (0, d-.80),
               (.10, d-.65), (.22, d-.60), (.22, d-.43),
               (.03, d-.36), (.03, d-.13), (.16, d),
               (wall-.12, d), (wall, d-.15), (wall, panel+.18),
               (wall+.17, panel)]
    n = len(rr(w, h, 1.0))
    x, y, z = pos
    v = []
    for inset, c in section:
        v += [(x+a, y+b, z+(d-c if inverted else c))
              for a, b in rr(w-2*inset, h-2*inset, max(.25, 1.2-inset))]
    f = [tuple(reversed(range(n))), tuple(range((len(section)-1)*n, len(section)*n))]
    for i in range(len(section)-1):
        connect(f, n, i*n, (i+1)*n)
    ob = mesh(name, v, f, parent, bevel=.025)
    primary.append(ob)
    return ob


bottom_cup = cup('盒底 · 连续薄壁与底板', 53, 45, 4.60, 1.0, .72, (0, 0, 0))
lid_cup = cup('盒盖 · 连续方框与透明面板', 45, 45, 3.30, 1.50, .72, (4, 0, 4.70), lid, True)
block('底壳窄区内隔筋', .40, 41.6, 3.0, (-18.87, 0, 4.7), base, r=.16)
block('底壳窄区外框', .48, 41.6, 3.0, (-26.26, 0, 4.65), base, r=.16)
block('底壳窄区透明前窗',6.4,40.8,.45,(-22.5,0,7.3),base,r=.45)
block('盘托左侧窄条透明窗', 6.0, 38.8, .40, (-22.5, 0, 2.0), carrier, r=.45)
for x in [-25.65,-19.35]:
    block('盘托窄条侧框', .35,41.2,.85,(x,0,1.3),carrier,r=.15)
for y in [-20.1,20.1]:
    block('盘托窄条端框',7.25,1.0,.85,(-22.5,y,1.3),carrier,r=.25)
for x in [-25.55, -19.45]:
    block('盘托侧窗细长成型台阶', .26, 40.2, .28, (x, 0, 2.32), carrier, r=.12, bevel=.035)
# User's red outline identifies these two arms as part of the LEFT lid.
# They are united into the lid mesh below; the middle vertical strip remains
# an independent carrier/base component.
fork_arms=[block('左盖一体铰接臂',8.4,1.25,2.5,(-22.3,y,4.7),lid,r=.5,bevel=.045)
           for y in [-21.875,21.875]]


def hanger(parent, z):
    # Polar intersection of a flared foot/semicircular arch gives one solid
    # annular mesh with a real, unobstructed hole; no stacked opaque discs.
    cy, ro, ri = 25.15, 3.15, 1.65
    outline = [(-4.5, 22.30), (-3.5, 22.8), (-ro, 23.6), (-ro, cy)]
    outline += [(ro*math.cos(math.pi-i*math.pi/64), cy+ro*math.sin(math.pi-i*math.pi/64)) for i in range(65)]
    outline += [(ro, 23.6), (3.5, 22.8), (4.5, 22.30)]
    outer, inner = [], []
    for i in range(160):
        a = i*math.tau/160
        dx, dy = math.cos(a), math.sin(a)
        hits = []
        for j, (px, py) in enumerate(outline):
            qx, qy = outline[(j+1) % len(outline)]
            ex, ey = qx-px, qy-py
            det = dx*ey-dy*ex
            if abs(det) < 1e-9:
                continue
            t = (px*ey-(py-cy)*ex)/det
            u = (px*dy-(py-cy)*dx)/det
            if t > 0 and 0 <= u <= 1:
                hits.append(t)
        t = min(hits)
        outer.append((dx*t, cy+dy*t))
        inner.append((ri*dx, cy+ri*dy))
    ob = ring('挂耳 · 真实贯通孔3.3mm', outer, inner, 1.10, (0, 0, z), parent, .10)
    ob['hole_diameter_mm_estimated'] = 3.3
    return ob


hanger(base, 3.00)
hanger(lid, 4.15)


def groove(target, name, w, h, inner_w, inner_h, z, xy=(0, 0)):
    cutter = ring(name+'刀具', rr(w, h, .65), rr(inner_w, inner_h, .45), .42,
                  (xy[0], xy[1], z), target.parent, 0)
    mod = target.modifiers.new(name, 'BOOLEAN')
    mod.operation = 'DIFFERENCE'
    mod.object = cutter
    bpy.context.view_layer.objects.active = target
    # Cut the watertight mould first, then bevel the newly created groove lips.
    bpy.ops.object.modifier_move_up(modifier=mod.name)
    bpy.ops.object.modifier_move_up(modifier=mod.name)
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter, do_unlink=True)


def recess(target,name,w,h,depth,pos,r=.18):
    cutter=block(name+' · 刀具',w,h,depth,pos,target.parent,r=r,bevel=0)
    modifier=target.modifiers.new(name,'BOOLEAN')
    modifier.operation='DIFFERENCE'
    modifier.solver='EXACT'
    modifier.object=cutter
    bpy.context.view_layer.objects.active=target
    while target.modifiers.find(modifier.name)>0:
        bpy.ops.object.modifier_move_up(modifier=modifier.name)
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    bpy.data.objects.remove(cutter,do_unlink=True)
    # Bevel can incorrectly bridge a long Boolean n-gon across its pocket.
    # Tessellate that face first; the cavity then remains open after beveling.
    triangulate=target.modifiers.new('凹腔面三角化 · 防止倒角封口','TRIANGULATE')
    while target.modifiers.find(triangulate.name)>0:
        bpy.ops.object.modifier_move_up(modifier=triangulate.name)


def unite(target,part):
    bpy.context.view_layer.update()
    modifier=target.modifiers.new('一体成型铰接臂','BOOLEAN')
    modifier.operation='UNION'
    modifier.solver='EXACT'
    modifier.object=part
    bpy.context.view_layer.objects.active=target
    while target.modifiers.find(modifier.name)>0:
        bpy.ops.object.modifier_move_up(modifier=modifier.name)
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    bpy.data.objects.remove(part,do_unlink=True)


for arm,y in zip(fork_arms,[-21.875,21.875]):
    recess(arm,'铰接臂内侧成型凹口',6.4,.52,.65,(-22.3,y,4.50),r=.18)
    unite(lid_cup,arm)
    # The base retains its full 53mm back panel, but its top/bottom ledges
    # need actual receiving reliefs rather than occupying the arm volume.
    recess(bottom_cup,'底壳铰接臂让位',8.4,1.9,4.5,(-22.4,math.copysign(21.9,y),.76),r=.25)
lid_cup['component']='45mm square window + two integral 8mm arms; open middle'


# Two real recessed tracks in the front face. Previous section details were
# mostly on the hidden back rim, leaving a broad blank face in the grey model.
groove(lid_cup,'前框外层成型凹槽',44.20,44.20,43.82,43.82,7.86,(4,0))
groove(lid_cup,'前框内层成型凹槽',43.15,43.15,42.89,42.89,7.91,(4,0))
groove(bottom_cup,'后框外层成型凹槽',52.10,44.10,51.72,43.72,-.28)


# Recessed seam and lip are part of the continuous section above. No Boolean
# rings cutting straight through that thin lip.
for y in [-21.45, 21.45]:
    # Discrete bridge blocks and the polished seam remain visible in the
    # reference even when the insert covers the broad back panel.
    for x in [-15.7, -10.0, 4.0, 18.0, 23.7]:
        ring('盒盖边沿桥形加强座', rr(3.2, .90, .22), rr(2.2, .32, .12), .65,
             (x, y, 6.65), lid, .04)
    for x in [-12.0, -3.0, 6.0, 15.0, 22.0]:
        block('盒底边沿分段卡座', 3.7, .78, .48, (x,y,3.86),base,r=.25,bevel=.055)


def tube(name, points, radius, parent=base):
    # Mesh tube with capped ends. Each fillet is an actual round section.
    n = 10
    v, f = [], []
    for i, p in enumerate(points):
        tangent = Vector(points[min(i+1, len(points)-1)])-Vector(points[max(i-1, 0)])
        tangent.normalize()
        u = tangent.cross(Vector((0, 0, 1)))
        if u.length < .01:
            u = tangent.cross(Vector((0, 1, 0)))
        u.normalize()
        w = tangent.cross(u).normalized()
        for j in range(n):
            v.append(Vector(p)+radius*(u*math.cos(j*math.tau/n)+w*math.sin(j*math.tau/n)))
        if i:
            connect(f, n, (i-1)*n, i*n)
    f += [tuple(reversed(range(n))), tuple(range((len(points)-1)*n, len(points)*n))]
    ob = mesh(name, v, f, parent, bevel=0)
    for poly in ob.data.polygons:
        poly.use_smooth = True
    return ob


# Continuous edge beads, distinct from the straight wall. Positions follow
# the empty-case reference; the paper sits below the inner formed ledge.
for w,h,xy,z,parent in [(44.0,44.0,(4,0),5.02,lid),
                       (51.9,43.9,(0,0),4.32,base)]:
    contour=rr(w,h,.85,24)
    tube('外框抛光连续圆唇',[(xy[0]+x,xy[1]+y,z) for x,y in contour+[contour[0]]],.105,parent)
for x in [-17.0,25.0]:
    tube('盖内纵向挡纸细棱',[(x,-18.5,6.95),(x,18.5,6.95)],.105,lid)


# Real interleaved hinge bearings around a shared Y axis.
for y in [-19.6, 19.6]:
    for dy in [-1.05, 1.05]:
        bearing = ring('盒底铰链轴套', circle(.88, 48), circle(.45, 48), .85, parent=base, bevel=.035)
        bearing.rotation_euler.x = math.pi/2
        bearing.location = Vector((-22.5, y+dy+.425, 4))*MM
    bearing = ring('盒盖铰链耳', circle(.88, 48), circle(.45, 48), 1.15, parent=lid, bevel=.04)
    bearing.rotation_euler.x = math.pi/2
    bearing.location = Vector((-22.5, y+.575, 4))*MM
    pin = solid('贯穿透明销轴', circle(.39, 48), 3.6, parent=base, bevel=.035)
    pin.rotation_euler.x = math.pi/2
    pin.location = Vector((-22.5, y+1.8, 4))*MM
    seat=block('盒底铰链支座', 1.25, 3.4, 2.9, (-22.5, y, .65), r=.25)
    recess(seat,'铰链支座上开减料凹腔',.64,2.15,2.5,(-22.5,y,1.25),r=.20)
    block('盒盖铰链连接桥', 4.4, 1.0, .80, (-20.4, y, 4.35), lid, r=.25)
    ring('铰链端部窗口座',rr(5.40,2.15,.48),rr(4.25,1.12,.30),.42,
         (-22.0,y,3.80),base,.045)
    for sign in [-1,1]:
        ob=ring('销轴端面倒角唇',circle(.91,64),circle(.52,64),.16,parent=base,bevel=.025)
        ob.rotation_euler.x=math.pi/2
        ob.location=Vector((-22.5,y+sign*1.92,4))*MM


def retainer(x, y, parent, z, inward, radius=2.4):
    # Shallow dished tongue, with a raised curved perimeter and a recessed
    # centre; reference has a formed thin shell rather than a flat coin.
    r, steps = radius, 48
    outer = [(r*math.cos(i*math.pi/steps), -r*math.sin(i*math.pi/steps)) for i in range(steps+1)]
    inner = [((r-.32)*math.cos(i*math.pi/steps), -(r-.32)*math.sin(i*math.pi/steps)) for i in range(steps+1)]
    n = len(outer)
    v = [(x+a,y+b*inward,z+c) for shape,c in
         [(outer,0),(outer,.16),(inner,.24),(inner,.10)] for a,b in shape]
    f = [tuple(reversed(range(n))), tuple(range(3*n,4*n))]
    for i in range(3): connect(f,n,i*n,(i+1)*n)
    mesh('曲面压纸舌 · 薄壳凹心',v,f,parent,bevel=.025)
    points = [(x+r*math.cos(i*math.pi/48), y-r*math.sin(i*math.pi/48)*inward, z+.15) for i in range(49)]
    tube('压纸舌弧口圆边', points, .085, parent)
    tube('压纸舌内侧成型细槽边',[(x+(r-.32)*math.cos(i*math.pi/48),
         y-(r-.32)*math.sin(i*math.pi/48)*inward,z+.225) for i in range(49)],.035,parent)
    for sign in [-1,1]:
        block('压纸舌两端连接脚', .55, .85, .40,
              (x+sign*(r-.11), y+.1*inward, z-.2), parent,r=.18,bevel=.035)


for x in [-10.7, 17.0]:
    for sign in [-1, 1]:
        retainer(x, sign*21.1, lid, 6.75, sign)
for x in [-17.8, 25.8]:
    for y in [-11.5, 11.5]:
        guide=block('盒盖侧向挡纸筋', .38, 7.1, .55, (x, y, 6.75), lid, r=.12)
        recess(guide,'挡纸筋中部减料槽',.16,5.7,.50,(x,y,6.98),r=.065)
for y in [-16.0, 16.0]:
    catch=block('盒底锁扣凹座', .60, 2.7, 1.3, (25.4, y, 2.8), r=.18)
    recess(catch,'锁扣承接凹口',.34,1.85,1.0,(25.4,y,3.28),r=.12)
    tongue=solid('盒盖锁扣弹舌 · 斜面扣头',
        [(25.2,4.65),(25.8,4.65),(26.0,4.95),(26.0,5.25),(25.55,5.45),(25.45,5.45)],
        2.2,parent=lid,bevel=.045)
    tongue.rotation_euler.x=math.pi/2
    tongue.location.y=(y+1.1)*MM

# One removable transparent carrier over a SINGLE continuous paper insert.
block('盘托 · 透明薄座', 42.7, 42.6, .25, (3.5, 0, 1.05), carrier, r=.55, bevel=.035)
for x in [-17.85,24.85]:
    block('盘托纵向成型边框',.55,42.5,.72,(x,0,1.30),carrier,r=.22)
    for y in [-17.2,0,17.2]:
        block('盘托边框定位凸座',.95,1.7,.55,(x,y,1.45),carrier,r=.28)
for y in [-20.75,20.75]:
    block('盘托窄条端部连接桥',2.25,1.1,.75,(-18.5,y,1.3),carrier,r=.25)


def lathe(name, section, xy, parent, segments=192):
    v = [(xy[0]+r*math.cos(i*math.tau/segments),
          xy[1]+r*math.sin(i*math.tau/segments), z)
         for r,z in section for i in range(segments)]
    f=[]
    for k in range(len(section)):
        connect(f,segments,k*segments,((k+1)%len(section))*segments)
    ob=mesh(name,v,f,parent,bevel=0)
    for p in ob.data.polygons: p.use_smooth=True
    return ob


lathe('盘槽 · 成型斜壁与圆唇',
      [(20.75,1.30),(20.75,1.42),(20.54,1.55),(20.40,1.82),
       (20.24,1.87),(20.12,1.80),(20.10,1.57),(19.94,1.40),(19.94,1.30)],
      (3.5,0),carrier)
for y in [-20.45, 20.45]:
    block('盘托上下梁', 42.2, .65, .8, (3.5, y, 1.3), carrier, r=.2)
    for x in [-11.0, 18.0]:
        retainer(x, y, carrier, 1.5, 1 if y > 0 else -1,radius=2.85)
        sign = 1 if x < 0 else -1
        a=Vector((x+sign*1.7,y-math.copysign(1.8,y)))
        b=Vector((x+sign*4.1,y-math.copysign(3.3,y)))
        direction=(b-a).normalized()
        normal=Vector((-direction.y,direction.x))*.28
        points=[a+normal,a-normal,b-normal,b+normal]
        solid('盘槽斜向片状加强筋',[tuple(p) for p in points],.28,
              (0,0,1.30),carrier,bevel=.045)
hub_platform=lathe('盘芯承托圆台 · 薄壁过渡',[(6.8,1.30),(7.0,1.42),(6.9,1.61),
      (6.7,1.68),(.35,1.68),(.35,1.30)],(3.5,0),carrier,128)
groove_cutter=ring('盘芯圆台细凹槽刀具',circle(6.55,128),circle(6.38,128),.22,
                  (3.5,0,1.61),carrier,0)
modifier=hub_platform.modifiers.new('盘芯圆台环形浅槽','BOOLEAN')
modifier.operation='DIFFERENCE'
modifier.object=groove_cutter
bpy.context.view_layer.objects.active=hub_platform
bpy.ops.object.modifier_apply(modifier=modifier.name)
bpy.data.objects.remove(groove_cutter,do_unlink=True)
for sign in [-1, 1]:
    # Tapered hollow clips: smaller footprint, relieved throat and projecting
    # rounded head. The earlier straight extruded rectangular loops are gone.
    profiles=[(rr(3.8,3.0,.85),1.60,3.0),
              (rr(2.00,1.10,.43),2.25,1.35),
              (rr(2.00,1.10,.43),2.98,1.35),
              (rr(3.8,3.0,.85),3.06,3.0),
              (rr(3.8,3.0,.85),3.25,3.0),
              (rr(2.8,2.10,.65),3.25,3.0),
              (rr(1.28,.56,.23),2.98,1.35),
              (rr(1.28,.56,.23),2.25,1.35),
              (rr(2.8,2.10,.65),1.60,3.0)]
    n=len(profiles[0][0])
    vertices=[(3.5+a,sign*cy+b,z) for shape,z,cy in profiles for a,b in shape]
    faces=[]
    for k in range(len(profiles)):
        connect(faces,n,k*n,((k+1)%len(profiles))*n)
    mesh('盘芯弹性扣 · 缩颈与圆头',vertices,faces,carrier,bevel=.035)
for x in [.2, 6.8]:
    lathe('盘芯定位圆点 · 圆根',[(.50,1.68),(.43,1.86),(.30,2.00),(.16,2.06),
          (.08,1.98),(.08,1.68)],(x,0),carrier,48)

disc_body = ring('光盘聚碳酸酯基片 · 外径40孔5', circle(20, 256), circle(2.5, 256), .55, parent=disc, bevel=.035)
lathe('透明光盘外缘圆唇',[(20,.10),(20,.48),(19.94,.61),(19.78,.65),
      (19.60,.58),(19.57,.48),(19.65,.10)],(0,0),disc,256)
lathe('透明光盘孔口圆唇',[(2.5,.10),(2.5,.49),(2.58,.61),(2.80,.65),
      (3.26,.59),(3.48,.50),(3.48,.10)],(0,0),disc,128)
# Reference component is a transparent acrylic disc. No opaque aluminium
# layer is introduced under the artwork.


def printed_material(slot):
    m = material('印刷 · '+slot, (1, 1, 1), .64)
    path = OUT/'textures'/(slot+'.png')
    if path.exists():
        bs = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
        bs.inputs['Specular IOR Level'].default_value = 0
        bs.inputs['Roughness'].default_value = .9
        tex = m.node_tree.nodes.new('ShaderNodeTexImage')
        tex.image = bpy.data.images.load(str(path), check_existing=True)
        tex.image.pack()
        m.node_tree.links.new(tex.outputs['Color'], bs.inputs['Base Color'])
    return m


def paper(name, vertices, slot, parent, reverse=False, flip_u=False, disc_uv=False):
    faces = [tuple(reversed(range(len(vertices)))) if reverse else tuple(range(len(vertices)))]
    ob = mesh(name, vertices, faces, parent, printed_material(slot), bevel=0)
    uv = ob.data.uv_layers.new(name='纸张原始比例')
    # Explicit per-coordinate UVs keep reverse prints readable after opening.
    xs, ys = [v[0] for v in vertices], [v[1] for v in vertices]
    for poly in ob.data.polygons:
        for li in poly.loop_indices:
            vi = ob.data.loops[li].vertex_index
            x, y = vertices[vi][:2]
            u = (x-min(xs))/(max(xs)-min(xs))
            v = (y-min(ys))/(max(ys)-min(ys))
            uv.data[li].uv = (1-u if flip_u else u, v)
    prints.append(ob)
    return ob


def rectangle(w, h, x, y, z):
    return [(x-w/2, y-h/2, z), (x+w/2, y-h/2, z),
            (x+w/2, y+h/2, z), (x-w/2, y+h/2, z)]


paper('封面 · 41×41mm', rectangle(41, 41, 4, 0, 7.25), 'front', lid)
paper('内页 · 同一封面纸背面41×41mm', rectangle(41, 41, 4, 0, 7.15), 'inside', lid, True, True)
paper('内盘底 · 单张完整49×38mm', rectangle(49, 38, 0, 0, .82), 'tray', base)
paper('封底 · 同一底纸背面49×38mm', rectangle(49, 38, 0, 0, .72), 'back', base, True, True)
for slot, sign in [('left', -1), ('right', 1)]:
    x = 24.5*sign
    ob = mesh('侧封 · 与底纸连续折起4.4mm · '+slot,
              [(x, -19, .82), (x, -19, 5.22), (x, 19, 5.22), (x, 19, .82)],
              [(0, 1, 2, 3)] if sign < 0 else [(3, 2, 1, 0)], base, printed_material(slot), bevel=0)
    uv = ob.data.uv_layers.new(name='4.4×38mm')
    coords = [(0, 0), (1, 0), (1, 1), (0, 1)]
    for poly in ob.data.polygons:
        for li in poly.loop_indices:
            uv.data[li].uv = coords[ob.data.loops[li].vertex_index]
    prints.append(ob)

# Circular label shares the disc's physical 5mm centre opening.
label = ring('盘面印刷 · 标签39.2mm孔5mm', circle(19.6, 256), circle(2.5, 256), .012, (0, 0, .552), disc, 0)
label.data.materials.clear()
label.data.materials.append(printed_material('disc'))
uv = label.data.uv_layers.new(name='圆盘无拉伸')
for poly in label.data.polygons:
    for li in poly.loop_indices:
        vi = label.data.loops[li].vertex_index
        x, y, _ = label.data.vertices[vi].co/MM
        uv.data[li].uv = ((x+20)/40, (y+20)/40)
prints.append(label)


def interpolate(value, anchors):
    for (a,b),(c,d) in zip(anchors,anchors[1:]):
        if value<=c:
            return b+(value-a)*(d-b)/(c-a)
    return anchors[-1][1]


# Depth values from the locally available Dimension-Sketch / Sketch-Set,
# not the missing Mini-CD-Blender-Reference attachment. Those sheets mark
# detailed values as visual estimates. Their Y=0 mid-plane becomes z=4 here.
disc.location.z=3.18*MM
for ob in carrier.children_recursive:
    if ob.type!='MESH': continue
    for vertex in ob.data.vertices:
        z=vertex.co.z/MM
        if ob.name.startswith('盘托 · 透明薄座'):
            value=1.58+(z-1.05)*(.42/.25)
        elif ob.name.startswith('盘芯弹性扣'):
            value=interpolate(z,[(1.6,2.3),(2.25,3.05),(2.98,4.45),(3.06,4.53),(3.25,4.72)])
        else:
            value=z+.70
        vertex.co.z=value*MM
    ob.data.update()
for ob in disc.children_recursive:
    if ob.type!='MESH': continue
    for vertex in ob.data.vertices: vertex.co.z*=1.16/.65
    ob.data.update()
for ob in prints:
    if ob.name.startswith('封面 ·'): target=7.04
    elif ob.name.startswith('内页 ·'): target=6.90
    elif ob.name.startswith('内盘底 ·'): target=1.40
    elif ob.name.startswith('封底 ·'): target=1.01
    elif ob.name.startswith('侧封 ·'):
        for vertex in ob.data.vertices: vertex.co.z+=.58*MM
        ob.data.update()
        continue
    else: continue
    for vertex in ob.data.vertices: vertex.co.z=target*MM
    ob.data.update()
model['depth_reference']='Downloads/Mini-CD-Blender-Sketch-Set.pdf page2; asterisk values are estimates'
model['reference_conflict']='User confirmed 2026-11-18: retain two spring clips; new drawing supplements frame/side/hinge only'
for ob in lid.children_recursive:
    if ob.type=='MESH' and ob.name.startswith(('曲面压纸舌','压纸舌弧口圆边','压纸舌两端连接脚','压纸舌内侧')):
        for vertex in ob.data.vertices: vertex.co.z-=.16*MM
        ob.data.update()

# Actual supplied drawing is a viewport guide, never a rendered shell layer.
guide_path=OUT/'reference'/'shell-drawing.png'
if guide_path.exists():
    guide_collection=bpy.data.collections.new('03 · 结构图描线参考 · 非模型')
    S.collection.children.link(guide_collection)
    guide_collection.hide_render=True
    guide_image=bpy.data.images.load(str(guide_path),check_existing=False)
    guide_image.name='结构图描线参考'
    guide_image['reference_only']=True
    guide_image.pack()
    guide=bpy.data.objects.new('结构图 · 180度展开对照',None)
    guide_collection.objects.link(guide)
    guide.parent=model
    guide.empty_display_type='IMAGE'
    guide.data=guide_image
    guide.empty_display_size=.1029
    guide.empty_image_depth='BACK'
    guide.location=(-.0220917,.0005294,-.001)
    guide.scale.y=(45/340)/(98/720)
    guide.hide_render=True
    guide['calibration']='Image body ROI x15..735/y65..405 fitted to 98x45mm; reference proportions are approximate'


def aim(ob, xyz):
    ob.rotation_euler = (Vector(xyz)-ob.location).to_track_quat('-Z', 'Y').to_euler()


def area(name, xyz, watts, size, size_y):
    data = bpy.data.lights.new(name, 'AREA')
    data.energy = watts/64
    data.shape = 'RECTANGLE'
    data.size, data.size_y = size*MM, size_y*MM
    ob = bpy.data.objects.new(name, data)
    STUDIO.objects.link(ob)
    ob.location = Vector(xyz)*MM
    aim(ob, (0, 0, .025))
    return ob


area('左侧柔光箱', (-85, -65, 95), 5, 65, 130)
area('右侧轮廓条灯', (80, 0, 65), 4, 14, 110)
area('顶部轮廓条灯', (0, 75, 120), 6, 110, 18)
# Keep the broad softbox outside the cover's reflected camera field.
area('纸面侧前柔光', (-140, -50, 65), 1.5, 35, 90)


def reflector(name, xyz, w, h, color=(1,1,1), strength=1.5):
    # Photographer's strip cards: reflect in polished plastic without
    # becoming a white rectangle in the camera or a panel behind the case.
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nodes, links = m.node_tree.nodes, m.node_tree.links
    output = next(n for n in nodes if n.type == 'OUTPUT_MATERIAL')
    emission = nodes.new('ShaderNodeEmission')
    emission.inputs['Color'].default_value = (*color, 1)
    emission.inputs['Strength'].default_value = strength
    ray = nodes.new('ShaderNodeLightPath')
    transparent = nodes.new('ShaderNodeBsdfTransparent')
    mix = nodes.new('ShaderNodeMixShader')
    links.new(ray.outputs['Is Glossy Ray'], mix.inputs[0])
    links.new(transparent.outputs[0], mix.inputs[1])
    links.new(emission.outputs[0], mix.inputs[2])
    links.new(mix.outputs[0], output.inputs['Surface'])
    bpy.ops.mesh.primitive_plane_add(size=1, location=Vector(xyz)*MM)
    ob = bpy.context.object
    ob.name = name
    ob.scale = (w*MM, h*MM, 1)
    aim(ob, (0, 0, .025))
    ob.data.materials.append(m)
    ob.visible_camera = False
    ob.visible_diffuse = False
    ob.visible_shadow = False
    ob.visible_transmission = False
    for c in list(ob.users_collection):
        c.objects.unlink(ob)
    STUDIO.objects.link(ob)


reflector('左侧反射条板', (-80, -30, 50), 13, 100)
reflector('右侧反射条板', (80, -30, 50), 13, 100)
reflector('左侧摄影黑旗',(-58,0,42),16,110,(.002,.002,.002),1)
reflector('右侧摄影黑旗',(58,0,42),16,110,(.002,.002,.002),1)
reflector('远端摄影黑旗',(0,65,40),95,12,(.002,.002,.002),1)
world = bpy.data.worlds.new('摄影棚环境')
world.use_nodes = True
S.world = world
world_bg = next(n for n in world.node_tree.nodes if n.type == 'BACKGROUND')
world_bg.inputs['Color'].default_value = (.55, .60, .68, 1)
world_bg.inputs['Strength'].default_value = .12
camera_bg = world.node_tree.nodes.new('ShaderNodeBackground')
world_path = world.node_tree.nodes.new('ShaderNodeLightPath')
world_mix = world.node_tree.nodes.new('ShaderNodeMixShader')
world_output = next(n for n in world.node_tree.nodes if n.type == 'OUTPUT_WORLD')
world.node_tree.links.new(world_path.outputs['Is Camera Ray'], world_mix.inputs[0])
world.node_tree.links.new(world_bg.outputs[0], world_mix.inputs[1])
world.node_tree.links.new(camera_bg.outputs[0], world_mix.inputs[2])
world.node_tree.links.new(world_mix.outputs[0], world_output.inputs['Surface'])
bpy.ops.mesh.primitive_plane_add(size=4, location=(0, 0, -.00025))
floor = bpy.context.object
floor.name = '连续地面 · 接触阴影与真实反射'
floor.data.materials.append(floor_mat)
for c in list(floor.users_collection):
    c.objects.unlink(floor)
STUDIO.objects.link(floor)
cam_data = bpy.data.cameras.new('产品镜头')
camera = bpy.data.objects.new('产品镜头', cam_data)
STUDIO.objects.link(camera)
S.camera = camera
cam_data.type = 'ORTHO'
cam_data.clip_start = .0001
cam_data.clip_end = 10
S.render.engine = 'CYCLES'
S.cycles.samples = A.samples
S.cycles.use_denoising = True
S.cycles.adaptive_threshold = .015
S.cycles.max_bounces = 24
S.cycles.transmission_bounces = 20
S.cycles.glossy_bounces = 12
S.cycles.transparent_max_bounces = 24
try:
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type = 'OPTIX'
    prefs.get_devices()
    for d in prefs.devices:
        d.use = d.type == 'OPTIX'
    S.cycles.device = 'GPU' if any(d.use for d in prefs.devices) else 'CPU'
except Exception as e:
    print('GPU_FALLBACK', str(e))
S.render.resolution_x = S.render.resolution_y = A.resolution
S.render.resolution_percentage = 100
S.render.image_settings.file_format = 'PNG'
S.render.image_settings.color_mode = 'RGBA'
S.view_settings.view_transform = 'AgX'
S.view_settings.exposure = -4.7


def descendants(root):
    return [root, *root.children_recursive]


def pose(open_degrees=0, standing=True, dark=False, grey=False):
    model['opening_degrees'] = float(open_degrees)
    model.update_tag()
    S.frame_set(S.frame_current)
    model.rotation_euler = (math.pi/2 if standing else 0, 0, 0)
    model.location = (0, 0, .0225 if standing else 0)
    bs = next(n for n in floor_mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    bs.inputs['Base Color'].default_value = (.012, .045, .048, 1) if dark else (.72, .74, .77, 1)
    bs.inputs['Roughness'].default_value = .24 if dark else .38
    # Keep exposure and transmitted environment in the same radiometric range.
    # A camera-only white backing against a dim world made transparent parts
    # appear grey/opaque and obscured the actual geometry during review.
    world_bg.inputs['Color'].default_value = (.65,.72,.80,1) if dark else (1,1,1,1)
    world_bg.inputs['Strength'].default_value = .12 if dark else .35
    S.view_settings.exposure = .6 if grey else 0
    # A level front camera sees the seamless backing rather than the floor;
    # keep that backing separate from the physically reflected environment.
    camera_bg.inputs['Color'].default_value = (.004, .014, .018, 1) if dark else (1, 1, 1, 1)
    camera_bg.inputs['Strength'].default_value = 2**(-S.view_settings.exposure)
    for ob in prints:
        ob.hide_render = grey
    for ob in descendants(disc):
        ob.hide_render = grey
    for ob in descendants(carrier):
        ob.hide_render = False
    for ob in MODEL.objects:
        if ob not in prints and ob not in descendants(disc) and ob not in descendants(carrier):
            ob.hide_render = False
    S.view_layers[0].material_override = clay if grey else None
    bpy.context.view_layer.update()


def validate():
    pose(0, False)
    coords = [ob.matrix_world@Vector(c) for ob in primary for c in ob.bound_box]
    dimensions = [(max(v[i] for v in coords)-min(v[i] for v in coords))/MM for i in range(3)]
    assert all(abs(a-b) < .002 for a, b in zip(dimensions, [53, 45, 8])), dimensions
    bad = []
    for ob in MODEL.objects:
        if ob.type != 'MESH' or ob in prints:
            continue
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        count = sum(not e.is_manifold for e in bm.edges)
        degenerate = sum(f.calc_area() < 1e-15 for f in bm.faces)
        bm.free()
        if count or degenerate:
            bad.append((ob.name, count, degenerate))
    assert not bad, bad
    assert len([o for o in prints if o.name.startswith('内盘底')]) == 1
    all_points = [ob.matrix_world@Vector(c) for ob in MODEL.objects if ob.type == 'MESH' and ob not in prints for c in ob.bound_box]
    whole_bounds = [(max(v[i] for v in all_points)-min(v[i] for v in all_points))/MM for i in range(3)]
    report = {'body_frame_mm': dimensions, 'whole_bounds_with_tabs_and_hinges_mm': whole_bounds,
              'disc_outer_mm': 40, 'disc_hole_mm': 5,
              'eyelet_hole_estimated_mm': 3.3, 'nonmanifold_solids': bad,
              'mesh_count': sum(o.type == 'MESH' for o in MODEL.objects),
              'single_tray_insert': True, 'separate_hinge_and_disc': True,
              'notes': '主体框53×45×8，挂孔及铰链凸出另计；细部尺寸估算，非生产CAD；印刷纸片为单面UV网格。'}
    (OUT/'结构验证.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('VALIDATION', json.dumps(report, ensure_ascii=True), flush=True)


validate()
POSES = {
    'front': (0, True, False, False, (0, -230, 27), (0, 0, 27), 78),
    'oblique': (0, True, False, False, (-110, -175, 90), (0, 0, 27), 83),
    'open': (180, False, False, False, (-22.5, 0, 240), (-22.5, 0, 3), 118),
    'dark': (0, True, True, False, (-110, -175, 90), (0, 0, 27), 83),
    'clay': (125, True, False, True, (85, -175, 125), (-20, 0, 27), 140),
    'empty': (180, False, False, False, (-22.5, 0, 240), (-22.5, 0, 3), 118),
    'flatgrey': (180, False, False, True, (-22.5, 0, 240), (-22.5, 0, 3), 115),
    'frontgrey': (0, True, False, True, (0, -230, 27), (0, 0, 27), 70),
    'bare': (180, False, False, False, (-22.5, 0, 240), (-22.5, 0, 3), 118),
    'trayonly': (0, False, False, False, (0,0,240),(0,0,2),64),
    'disconly': (0, False, False, False, (3.5,0,240),(3.5,0,2),52),
    'carrierinstalled': (180, False, False, False, (-22.5,0,240),(-22.5,0,3),118),
    'baregrey': (180,False,False,True,(-22.5,0,240),(-22.5,0,3),118),
    'traygrey': (0,False,False,True,(0,0,240),(0,0,2),64),
    'discgrey': (0,False,False,True,(3.5,0,240),(3.5,0,2),52),
    'sidegrey': (0,True,False,True,(-230,0,27),(0,0,27),70),
    'detail_frame':(0,False,False,True,(34,32,27),(24.5,20,7.6),10),
    'detail_hinge':(180,False,False,True,(-13,29,23),(-22.5,19.6,3.8),15),
    'detail_clip':(180,False,False,True,(-59,8,20),(-63.7,19.3,1.5),8),
    'detail_hub':(180,False,False,True,(13,-18,35),(3.5,0,3.1),20),
    'installedgrey':(180,False,False,True,(-22.5,0,240),(-22.5,0,3),115),
    'lidonly':(180,False,False,True,(-45,0,230),(-45,0,1.5),65),
    'lidangle':(180,False,False,True,(-75,-40,40),(-45,0,2),75),
}
names = {'front': '01-正视图', 'oblique': '02-斜视图', 'open': '03-展开内侧装盘',
         'dark': '04-深色棚拍', 'clay': '05-结构灰模', 'empty': '06-空壳展开',
         'flatgrey':'07-空壳正投影灰模','frontgrey':'08-闭合正投影灰模',
         'bare':'09-平铺空壳无盘托','trayonly':'10-独立透明盘托',
         'disconly':'11-独立透明光盘','carrierinstalled':'12-装入盘托未装盘',
         'baregrey':'13-平铺空壳灰模','traygrey':'14-独立盘托灰模','discgrey':'15-独立光盘灰模',
         'sidegrey':'16-闭合侧面灰模','detail_frame':'17-外框凹槽近景',
         'detail_hinge':'18-铰链端座近景','detail_clip':'19-压纸卡舌近景',
         'detail_hub':'20-双弹舌盘扣近景','installedgrey':'21-装盘结构正投影',
         'lidonly':'22-左盖独立正投影','lidangle':'23-左盖独立斜视'}
for key in A.views.split(','):
    spec = POSES[key]
    pose(*spec[:4])
    if key in ['lidonly','lidangle']:
        visible=descendants(lid)
        for ob in MODEL.objects:
            if ob.type=='MESH': ob.hide_render=ob not in visible
        for ob in prints: ob.hide_render=True
    if key=='installedgrey':
        for ob in descendants(disc): ob.hide_render=False
        for ob in prints: ob.hide_render=True
    if key == 'empty':
        for ob in [*prints, *descendants(disc)]:
            ob.hide_render = True
    if key in ['bare','baregrey','carrierinstalled']:
        for ob in [*prints,*descendants(disc)]: ob.hide_render=True
        if key in ['bare','baregrey']:
            for ob in descendants(carrier): ob.hide_render=True
    if key in ['trayonly','disconly','traygrey','discgrey']:
        visible=descendants(carrier if key in ['trayonly','traygrey'] else disc)
        for ob in MODEL.objects: ob.hide_render=ob not in visible
        for ob in prints: ob.hide_render=True
    camera.location = Vector(spec[4])*MM
    aim(camera, Vector(spec[5])*MM)
    camera.data.ortho_scale = spec[6]*MM
    S.render.filepath = str(OUT/(names[key]+'.png'))
    print('RENDER_START', key, flush=True)
    bpy.ops.render.render(write_still=True)
    print('RENDER_DONE', key, flush=True)

# The saved file opens at a useful front oblique angle with original materials.
spec = POSES['oblique']
pose(*spec[:4])
camera.location = Vector(spec[4])*MM
aim(camera, Vector(spec[5])*MM)
camera.data.ortho_scale = spec[6]*MM
for screen in bpy.data.screens:
    for area_ob in screen.areas:
        if area_ob.type == 'VIEW_3D':
            area_ob.spaces.active.clip_start = .005
            area_ob.spaces.active.clip_end = 10
            area_ob.spaces.active.overlay.show_overlays=False
            area_ob.spaces.active.region_3d.view_perspective = 'PERSP'
            area_ob.spaces.active.region_3d.view_location=(0,-.004,.026)
            area_ob.spaces.active.region_3d.view_distance=.13
            area_ob.spaces.active.region_3d.view_rotation=camera.rotation_euler.to_quaternion()
for ob in STUDIO.objects: ob.hide_set(True)
if '03 · 结构图描线参考 · 非模型' in S.view_layers[0].layer_collection.children:
    S.view_layers[0].layer_collection.children['03 · 结构图描线参考 · 非模型'].hide_viewport=True
bpy.ops.object.select_all(action='DESELECT')
model.select_set(True)
bpy.context.view_layer.objects.active=model
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'迷你CD-重新建模.blend'))
bpy.ops.object.select_all(action='DESELECT')
for ob in MODEL.objects:
    ob.select_set(True)
bpy.ops.export_scene.gltf(filepath=str(OUT/'迷你CD-重新建模.glb'), export_format='GLB',
                         use_selection=True, export_apply=True, export_extras=True)
print('REBUILD_COMPLETE', str(OUT), flush=True)
