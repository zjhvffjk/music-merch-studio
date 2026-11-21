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
        check('展开内页位于左侧方盖内', abs(local_centre.x+.049) < 1e-6)
        lid_shell = bpy.data.objects['盒盖 · 连续方框与透明面板']
        corners = [root.matrix_world.inverted() @ lid_shell.matrix_world @ Vector(v)
                   for v in lid_shell.bound_box]
        right_edge = max(v.x for v in corners)
        check('展开中间仅保留一段8mm侧槽', abs((-.0185-right_edge)*1000-8) < .01)
        check('展开左侧盒盖宽高相同', abs((max(v.x for v in corners)-min(v.x for v in corners)) /
                                              (max(v.y for v in corners)-min(v.y for v in corners))-1) < .001)

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
carrier = bpy.data.objects['透明盘托 · 仅一套']
disc_root = bpy.data.objects['光盘 · 直径40 · 孔5mm']
check('盘托窄侧条属于可拆盘托', bpy.data.objects['盘托左侧窄条透明窗'].parent == carrier)
check('光盘与盘托是独立组件', disc_root.parent != carrier and carrier not in disc_root.children_recursive)
check('透明光盘没有不透明铝层', not any(o.name.startswith('光盘铝层') for o in collection.objects))
check('已去除参考没有的盘芯小圆环', '盘芯中孔承托圈' not in bpy.data.objects)

def world_bvh(ob):
    evaluated=ob.evaluated_get(depsgraph)
    data=evaluated.to_mesh()
    vertices=[evaluated.matrix_world@v.co for v in data.vertices]
    polygons=[tuple(p.vertices) for p in data.polygons]
    tree=BVHTree.FromPolygons(vertices,polygons)
    evaluated.to_mesh_clear()
    return tree

clip_trees=[world_bvh(o) for o in carrier.children_recursive
            if o.type=='MESH' and o.name.startswith('盘芯弹性扣')]
disc_trees=[world_bvh(o) for o in disc_root.children_recursive
            if o.type=='MESH' and not o.name.startswith('盘面印刷')]
intersections=sum(bool(a.overlap(b)) for a in clip_trees for b in disc_trees)
check('中央弹扣与透明盘片及孔口无表面穿插',intersections==0)
root['opening_degrees']=180.
root.update_tag()
scene.frame_set(scene.frame_current)
bpy.context.view_layer.update()
spine_frames=[world_bvh(o) for o in carrier.children_recursive
              if o.type=='MESH' and o.name.startswith('盘托窄条侧框')]
lid_frames=[world_bvh(o) for o in collection.objects
            if o.type=='MESH' and o.name.startswith('盖侧窄框')]
check('180度展开时盘托侧框与盖侧框无穿插',
      not any(a.overlap(b) for a in spine_frames for b in lid_frames))
file_images = [im for im in bpy.data.images if im.source == 'FILE']
check('七张纸面图案均已打包', len(file_images) == 7 and all(im.packed_file for im in file_images))
check('模型没有照片壳体材质', {Path(bpy.path.abspath(im.filepath)).stem for im in file_images} == {'front', 'inside', 'back', 'tray', 'disc', 'left', 'right'})
report = {'checks_passed': len(checks), 'checks': checks, 'bad_solids': bad,
          'source_blend': bpy.data.filepath, 'objects': len(collection.objects)}
path = Path(bpy.data.filepath).parent/'重新打开验证.json'
path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print('REOPEN_CHECKS_PASS', len(checks), flush=True)
