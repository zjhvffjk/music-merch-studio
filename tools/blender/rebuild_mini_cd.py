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
P.add_argument('--out', default='blender/rebuild-20261118')
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
pivot = empty('盒盖转轴 · Y · 可开合', model, (-26.5, 0, 4))
lid = empty('盒盖与双面封面', pivot, (26.5, 0, -4))
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


def rr(w, h, r, steps=12):
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
    outer, inner = rr(w, h, .9), rr(w-2*wall, h-2*wall, .4)
    n = len(outer)
    x, y, z = pos
    rings = [(outer, 0), (outer, d), (inner, d), (inner, panel)]
    v = [(x+a, y+b, z+(d-c if inverted else c)) for points, c in rings for a, b in points]
    f = [tuple(reversed(range(n))), tuple(range(3*n, 4*n))]
    for a, b in [(0, n), (n, 2*n), (2*n, 3*n)]:
        connect(f, n, a, b)
    ob = mesh(name, v, f, parent, bevel=.11)
    primary.append(ob)
    return ob


bottom_cup = cup('盒底 · 连续薄壁与底板', 53, 45, 4.60, .72, .58, (0, 0, 0))
lid_cup = cup('盒盖 · 连续方框与透明面板', 45, 45, 3.30, .72, .58, (4, 0, 4.70), lid, True)
block('盒盖侧槽内隔墙', .65, 43.7, 7.3, (-18.87, 0, .65), lid)
block('盒盖侧槽外墙上半段', .72, 43.2, 3.4, (-26.14, 0, 4.6), lid)
block('盒盖侧槽透明顶窗', 6.0, 41, .55, (-22.5, 0, 7.45), lid, r=.35)
for y in [-21.9, 21.9]:
    block('盒盖侧槽端部封口', 7.6, 1.2, 3.4, (-22.5, y, 4.6), lid, r=.28)


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


groove(lid_cup, '盒盖外沿成型凹槽', 44.25, 44.25, 43.80, 43.80, 7.82, (4, 0))
groove(bottom_cup, '盒底口沿细凹槽', 52.45, 44.45, 52.02, 44.02, 4.38)
for y in [-21.45, 21.45]:
    for x in [-10.0, 4.0, 18.0]:
        ring('盒盖边沿桥形加强座', rr(3.2, .90, .22), rr(2.2, .32, .12), .65,
             (x, y, 6.65), lid, .04)


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


# Real interleaved hinge bearings around a shared Y axis.
for y in [-19.6, 19.6]:
    for dy in [-1.05, 1.05]:
        bearing = ring('盒底铰链轴套', circle(.78, 48), circle(.39, 48), .85, parent=base, bevel=.035)
        bearing.rotation_euler.x = math.pi/2
        bearing.location = Vector((-26.5, y+dy+.425, 4))*MM
    bearing = ring('盒盖铰链耳', circle(.76, 48), circle(.40, 48), 1.15, parent=lid, bevel=.04)
    bearing.rotation_euler.x = math.pi/2
    bearing.location = Vector((-26.5, y+.575, 4))*MM
    pin = solid('贯穿透明销轴', circle(.32, 48), 3.6, parent=base, bevel=.035)
    pin.rotation_euler.x = math.pi/2
    pin.location = Vector((-26.5, y+1.8, 4))*MM
    block('盒底铰链支座', 1.25, 3.4, 2.9, (-25.9, y, .65), r=.25)
    block('盒盖铰链连接桥', 1.4, 1.0, 1.4, (-26.0, y, 4), lid, r=.25)


def retainer(x, y, parent, z, inward):
    r = 2.05
    pts = [(r*math.cos(i*math.pi/36), -r*math.sin(i*math.pi/36)) for i in range(37)]
    pts = [(x+a, y+b*inward) for a, b in pts]
    solid('半圆压纸舌', pts, .25, (0, 0, z), parent, bevel=.035)
    points = [(x+r*math.cos(i*math.pi/48), y-r*math.sin(i*math.pi/48)*inward, z+.22) for i in range(49)]
    tube('压纸舌抛光圆唇', points, .13, parent)
    block('压纸舌根部', 4.6, .8, .65, (x, y+.20*inward, z-.2), parent, r=.2)


for x in [-10.7, 18.7]:
    for sign in [-1, 1]:
        retainer(x, sign*21.1, lid, 6.75, sign)
for x in [-17.8, 25.8]:
    for y in [-11.5, 11.5]:
        block('盒盖侧向挡纸筋', .38, 7.1, .55, (x, y, 6.75), lid, r=.12)
for y in [-16.0, 16.0]:
    block('盒底锁扣凹座', .60, 2.7, 1.3, (25.4, y, 2.8), r=.18)
    block('盒盖锁扣弹舌', .45, 2.2, .8, (25.6, y, 4.65), lid, r=.18)

# One removable transparent carrier over a SINGLE continuous paper insert.
block('盘托 · 透明薄座', 42.7, 42.6, .32, (3.5, 0, 1.05), carrier, r=.55, bevel=.045)
ring('盘槽外唇 · 40mm圆盘定位', circle(20.55, 192), circle(20.10, 192), .60, (3.5, 0, 1.37), carrier, .055)
ring('盘槽内侧细棱', circle(19.95, 192), circle(19.78, 192), .22, (3.5, 0, 1.38), carrier, .03)
for y in [-20.45, 20.45]:
    block('盘托上下梁', 42.2, .65, .8, (3.5, y, 1.3), carrier, r=.2)
    for x in [-11.0, 18.0]:
        retainer(x, y, carrier, 1.5, 1 if y > 0 else -1)
        sign = 1 if x < 0 else -1
        tube('盘槽斜向连接筋', [(x+sign*1.7, y-math.copysign(1.8, y), 1.65),
                                       (x+sign*4.1, y-math.copysign(3.3, y), 1.65)], .16, carrier)
ring('盘芯承托透明圆台', circle(6.2, 128), circle(2.5, 128), .28, (3.5, 0, 1.4), carrier, .035)
ring('盘芯中孔承托圈', circle(2.47, 96), circle(2.20, 96), .7, (3.5, 0, 1.62), carrier, .035)
for sign in [-1, 1]:
    ring('盘芯中空弹性扣', rr(2.35, 1.3, .5), rr(1.55, .65, .25), 1.35,
         (3.5, sign*1.35, 1.6), carrier, .045)
    block('盘芯弹扣唇', 2.3, .35, .28, (3.5, sign*1.9, 2.7), carrier, r=.1, bevel=.035)
for x in [1.1, 5.9]:
    solid('盘芯定位柱', circle(.25, 32), .45, (x, 0, 1.7), carrier, bevel=.035)

disc_body = ring('光盘聚碳酸酯基片 · 外径40孔5', circle(20, 256), circle(2.5, 256), .55, parent=disc, bevel=.035)
reflective = ring('光盘铝层', circle(19.85, 256), circle(5.1, 256), .035, (0, 0, .10), disc, .008)
reflective.data.materials.clear()
reflective.data.materials.append(aluminium)


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


def aim(ob, xyz):
    ob.rotation_euler = (Vector(xyz)-ob.location).to_track_quat('-Z', 'Y').to_euler()


def area(name, xyz, watts, size, size_y):
    data = bpy.data.lights.new(name, 'AREA')
    data.energy = watts
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


def reflector(name, xyz, w, h):
    # Photographer's strip cards: reflect in polished plastic without
    # becoming a white rectangle in the camera or a panel behind the case.
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nodes, links = m.node_tree.nodes, m.node_tree.links
    output = next(n for n in nodes if n.type == 'OUTPUT_MATERIAL')
    emission = nodes.new('ShaderNodeEmission')
    emission.inputs['Color'].default_value = (1, 1, 1, 1)
    emission.inputs['Strength'].default_value = 7
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
S.view_settings.view_transform = 'Standard'
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
    world_bg.inputs['Strength'].default_value = .055 if dark else .12
    S.view_settings.exposure = -4.7 if grey else (-5.4 if not standing else -3.9 if dark else -4.1)
    # A level front camera sees the seamless backing rather than the floor;
    # keep that backing separate from the physically reflected environment.
    camera_bg.inputs['Color'].default_value = (.004, .014, .018, 1) if dark else (1, 1, 1, 1)
    camera_bg.inputs['Strength'].default_value = 2**(-S.view_settings.exposure)
    for ob in prints:
        ob.hide_render = grey
    for ob in descendants(disc):
        ob.hide_render = grey
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
    'open': (180, False, False, False, (-26.5, 0, 240), (-26.5, 0, 3), 128),
    'dark': (0, True, True, False, (-110, -175, 90), (0, 0, 27), 83),
    'clay': (125, True, False, True, (85, -175, 125), (-20, 0, 27), 140),
    'empty': (180, False, False, False, (-26.5, 0, 240), (-26.5, 0, 3), 128),
}
names = {'front': '01-正视图', 'oblique': '02-斜视图', 'open': '03-展开内侧装盘',
         'dark': '04-深色棚拍', 'clay': '05-结构灰模', 'empty': '06-空壳展开'}
for key in A.views.split(','):
    spec = POSES[key]
    pose(*spec[:4])
    if key == 'empty':
        for ob in [*prints, *descendants(disc)]:
            ob.hide_render = True
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
            area_ob.spaces.active.clip_start = .0001
            area_ob.spaces.active.region_3d.view_perspective = 'CAMERA'
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'迷你CD-重新建模.blend'))
bpy.ops.object.select_all(action='DESELECT')
for ob in MODEL.objects:
    ob.select_set(True)
bpy.ops.export_scene.gltf(filepath=str(OUT/'迷你CD-重新建模.glb'), export_format='GLB',
                         use_selection=True, export_apply=True, export_extras=True)
print('REBUILD_COMPLETE', str(OUT), flush=True)
