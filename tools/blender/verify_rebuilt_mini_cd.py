"""Reopen verification for the independent Mini CD prototype."""
import json
import math
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree

scene = bpy.context.scene
root = bpy.data.objects['MiniCD · 主体53×45×8mm']
pivot = bpy.data.objects['盒盖转轴 · Y · 可开合']
inside = bpy.data.objects['内页 · 同一封面纸背面41×41mm']
collection = bpy.data.collections['01 · 实体样机']
checks = []


def check(label, ok):
    assert ok, label
    checks.append(label)


for angle in [0., 90., 180.]:
    root['opening_degrees'] = angle
    root.update_tag()
    scene.frame_set(scene.frame_current)
    bpy.context.view_layer.update()
    check('铰链驱动角度 '+str(angle), abs(pivot.rotation_euler.y+math.radians(angle)) < 1e-5)
    local_centre = sum((root.matrix_world.inverted() @ inside.matrix_world @ v.co for v in inside.data.vertices), Vector())/len(inside.data.vertices)
    if angle == 0:
        check('闭合内页位置', abs(local_centre.x-.004) < 1e-6)
    if angle == 180:
        check('展开内页远离右侧盘托，不被侧槽遮挡', abs(local_centre.x+.057) < 1e-6)

root['opening_degrees'] = 0.
root.update_tag()
scene.frame_set(scene.frame_current)
bpy.context.view_layer.update()
depsgraph = bpy.context.evaluated_depsgraph_get()
bad = []
for ob in collection.objects:
    if ob.type != 'MESH' or ob.name.startswith(('封面 ·', '内页 ·', '封底 ·', '内盘底 ·', '侧封 ·')):
        continue
    evaluated = ob.evaluated_get(depsgraph)
    me = evaluated.to_mesh()
    bm = bmesh.new()
    bm.from_mesh(me)
    n = sum(not edge.is_manifold for edge in bm.edges)
    if n or bm.calc_volume() <= 0:
        bad.append((ob.name, n, bm.calc_volume()))
    bm.free()
    evaluated.to_mesh_clear()
check('全部实体网格应用圆角后闭合且体积为正', not bad)

body = bpy.data.objects['光盘聚碳酸酯基片 · 外径40孔5']
radii = [math.hypot(v.co.x, v.co.y)*1000 for v in body.data.vertices]
check('实际光盘外径40mm', abs(max(radii)*2-40) < .002)
check('实际光盘中孔5mm', abs(min(radii)*2-5) < .002)
bvh = BVHTree.FromObject(body, depsgraph)
check('光盘中孔射线贯通', bvh.ray_cast(Vector((0, 0, -.01)), Vector((0, 0, 1)), .02)[0] is None)
check('光盘孔外为实体', bvh.ray_cast(Vector((.003, 0, -.01)), Vector((0, 0, 1)), .02)[0] is not None)
for ob in [o for o in collection.objects if o.name.startswith('挂耳 ·')]:
    bvh = BVHTree.FromObject(ob, depsgraph)
    check(ob.name+' 孔心贯通', bvh.ray_cast(Vector((0, .02515, -.01)), Vector((0, 0, 1)), .03)[0] is None)
    check(ob.name+' 孔边为实体', bvh.ray_cast(Vector((.0021, .02515, -.01)), Vector((0, 0, 1)), .03)[0] is not None)
check('内盘底仅一张正面印刷网格', sum(o.name.startswith('内盘底 ·') for o in collection.objects) == 1)
file_images = [im for im in bpy.data.images if im.source == 'FILE']
check('七张纸面图案均已打包', len(file_images) == 7 and all(im.packed_file for im in file_images))
check('模型没有照片壳体材质', {Path(bpy.path.abspath(im.filepath)).stem for im in file_images} == {'front', 'inside', 'back', 'tray', 'disc', 'left', 'right'})
report = {'checks_passed': len(checks), 'checks': checks, 'bad_solids': bad,
          'source_blend': bpy.data.filepath, 'objects': len(collection.objects)}
path = Path(bpy.data.filepath).parent/'重新打开验证.json'
path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print('REOPEN_CHECKS_PASS', len(checks), flush=True)
