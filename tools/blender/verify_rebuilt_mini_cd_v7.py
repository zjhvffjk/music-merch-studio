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

expected_parts={'01 · 左盖','02 · 右底壳','03 · 透明盘托','04 · 光盘'}
check('总装分为四个独立组件集合',{c.name for c in collection.children}==expected_parts)
all_members=[o for c in collection.children for o in c.all_objects if o.type=='MESH']
check('每个实体只属于一个组件集合',len(all_members)==len(set(all_members)))
springs=[o for o in collection.all_objects if o.name.startswith('盘芯弹性扣 · 薄壁弧形弹舌')]
check('使用两片弧形弹舌',len(springs)==2)
for ob in springs:
    n=ob['top_vertex_count']
    thickness=[(ob.data.vertices[i].co-ob.data.vertices[i+n].co).length*1000 for i in range(n)]
    check(ob.name+' 片厚0.18mm',max(abs(t-.18) for t in thickness)<.0001)
    check(ob.name+' 外侧根部低于盘片',max(v.co.z for v in ob.data.vertices[:33])*1000<3.18)
check('已删除厚块式旧扣头',not any(o.name.startswith('盘芯弹性扣 · 缩颈与圆头') for o in collection.all_objects))


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
        check('展开铰接臂伸至窄区右侧',abs(right_edge+.0185)<.0001)

root['opening_degrees'] = 0.
root.update_tag()
scene.frame_set(scene.frame_current)
bpy.context.view_layer.update()
depsgraph = bpy.context.evaluated_depsgraph_get()
bad = []
for ob in collection.all_objects:
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

front_shell=bpy.data.objects['盒盖 · 连续方框与透明面板']
front_tree=BVHTree.FromObject(front_shell,depsgraph)
def side_hit(x,y,z,direction):
    hit=front_tree.ray_cast(Vector((x/1000,y/1000,z/1000)),Vector(direction),.15)[0]
    return hit
panel_left=side_hit(-40,0,7.7,(1,0,0))
panel_right=side_hit(40,0,7.7,(-1,0,0))
check('左盖方形面板主体45mm',abs((panel_right.x-panel_left.x)*1000-45)<.01)
for y in [-21.875,21.875]:
    arm=side_hit(-40,y,5.5,(1,0,0))
    check('左盖上下臂超出方盖8mm '+str(y),arm is not None and abs(arm.x*1000+26.5)<.05)
check('两臂之间保持敞开',front_tree.ray_cast(Vector((-.0225,0,.012)),Vector((0,0,-1)),.025)[0] is None)
bm=bmesh.new()
bm.from_mesh(front_shell.data)
remaining=set(bm.verts)
components=0
while remaining:
    components+=1
    stack=[remaining.pop()]
    while stack:
        vertex=stack.pop()
        for edge in vertex.link_edges:
            other=edge.other_vert(vertex)
            if other in remaining:
                remaining.remove(other)
                stack.append(other)
bm.free()
check('两条铰接臂已与左盖合成单一连通网格',components==1)
def top_hit(tree,x,y,z=12):
    hit=tree.ray_cast(Vector((x/1000,y/1000,z/1000)),Vector((0,0,-1)),.03)[0]
    assert hit is not None,(x,y)
    return hit.z*1000
outer_track=top_hit(front_tree,4,22.0)
inner_track=top_hit(front_tree,4,21.51)
plain_face=top_hit(front_tree,4,20.8)
check('外框第一道凹槽实际低于面板',plain_face-outer_track>.10)
check('外框第二道凹槽实际低于面板',plain_face-inner_track>.05)
seat_tree=BVHTree.FromObject(bpy.data.objects['盒底铰链支座'],depsgraph)
seat_outer=top_hit(seat_tree,-22.02,-19.6)
seat_inner=top_hit(seat_tree,-22.5,-19.6)
print('DETAIL_DEPTHS',outer_track,inner_track,plain_face,seat_outer,seat_inner,flush=True)
check('铰链支座凹腔具有实际深度',seat_outer-seat_inner>2)
hub_tree=BVHTree.FromObject(bpy.data.objects['盘芯承托圆台 · 薄壁过渡'],depsgraph)
check('盘扣承托圆台环形浅槽具有实际深度',top_hit(hub_tree,3.5+6.1,0)-top_hit(hub_tree,3.5+6.46,0)>.04)

body = bpy.data.objects['光盘聚碳酸酯基片 · 外径40孔5']
radii = [math.hypot(v.co.x, v.co.y)*1000 for v in body.data.vertices]
check('实际光盘外径40mm', abs(max(radii)*2-40) < .002)
check('实际光盘中孔5mm', abs(min(radii)*2-5) < .002)
bvh = BVHTree.FromObject(body, depsgraph)
check('光盘中孔射线贯通', bvh.ray_cast(Vector((0, 0, -.01)), Vector((0, 0, 1)), .02)[0] is None)
check('光盘孔外为实体', bvh.ray_cast(Vector((.003, 0, -.01)), Vector((0, 0, 1)), .02)[0] is not None)
for ob in [o for o in collection.all_objects if o.name.startswith('挂耳 ·')]:
    bvh = BVHTree.FromObject(ob, depsgraph)
    check(ob.name+' 孔心贯通', bvh.ray_cast(Vector((0, .02515, -.01)), Vector((0, 0, 1)), .03)[0] is None)
    check(ob.name+' 孔边为实体', bvh.ray_cast(Vector((.0021, .02515, -.01)), Vector((0, 0, 1)), .03)[0] is not None)
check('内盘底仅一张正面印刷网格', sum(o.name.startswith('内盘底 ·') for o in collection.all_objects) == 1)
bottom_shell=bpy.data.objects['盒底 · 连续薄壁与底板']
bottom_corners=[root.matrix_world.inverted()@bottom_shell.matrix_world@Vector(v) for v in bottom_shell.bound_box]
paper=bpy.data.objects['内盘底 · 单张完整49×38mm']
paper_corners=[root.matrix_world.inverted()@paper.matrix_world@v.co for v in paper.data.vertices]
check('53mm底壳完整支撑49mm底纸并保留两侧2mm边距',
      min(v.x for v in paper_corners)-min(v.x for v in bottom_corners)>.00199 and
      max(v.x for v in bottom_corners)-max(v.x for v in paper_corners)>.00199)
carrier = bpy.data.objects['透明盘托 · 仅一套']
disc_root = bpy.data.objects['光盘 · 直径40 · 孔5mm']
check('盘托窄侧条属于可拆盘托', bpy.data.objects['盘托左侧窄条透明窗'].parent == carrier)
check('光盘与盘托是独立组件', disc_root.parent != carrier and carrier not in disc_root.children_recursive)
check('透明光盘没有不透明铝层', not any(o.name.startswith('光盘铝层') for o in collection.all_objects))
check('已去除参考没有的盘芯小圆环', '盘芯中孔承托圈' not in bpy.data.objects)

def root_depths(objects):
    points=[root.matrix_world.inverted()@ob.matrix_world@v.co
            for ob in objects if ob.type=='MESH' for v in ob.data.vertices]
    return min(v.z for v in points)*1000,max(v.z for v in points)*1000

disc_depth=root_depths([o for o in disc_root.children_recursive if not o.name.startswith('盘面印刷')])
plate=bpy.data.objects['盘托 · 透明薄座']
tray_depth=root_depths([plate])
check('透明光盘总厚度1.16mm参考值',abs(disc_depth[1]-disc_depth[0]-1.16)<.002)
check('透明光盘层位z3.18至4.34mm',abs(disc_depth[0]-3.18)<.002 and abs(disc_depth[1]-4.34)<.002)
check('盘托底板层位z1.58至2.00mm',abs(tray_depth[0]-1.58)<.002 and abs(tray_depth[1]-2)<.002)
paper_depth=root_depths([bpy.data.objects['内盘底 · 单张完整49×38mm']])[0]
check('同一张内盘底位于盘托底板下方',paper_depth<tray_depth[0]<tray_depth[1]<disc_depth[0])
inside_z=root_depths([inside])[0]
lid_group=bpy.data.objects['盒盖与双面封面']
retainers=[o for o in collection.all_objects
    if o.type=='MESH' and o.parent==lid_group and o.name.startswith('曲面压纸舌')]
check('盖内压纸舌没有穿进内页纸面',root_depths(retainers)[1]<inside_z)

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
check('盒盖不再携带重复窄框',not any(o.name.startswith('盖侧窄框') for o in collection.all_objects))
check('中央窄区属于固定底壳',bpy.data.objects['底壳窄区外框'].parent==bpy.data.objects['盒底与固定侧槽'])
left_shape=bpy.data.objects['盒盖 · 连续方框与透明面板']
right_shape=bpy.data.objects['盒底 · 连续薄壁与底板']
check('两条伸臂使左盖总外廓达到53mm',abs(left_shape.dimensions.x*1000-53)<.05)
file_images = [im for im in bpy.data.images if im.source == 'FILE' and not im.get('reference_only')]
check('七张纸面图案均已打包', len(file_images) == 7 and all(im.packed_file for im in file_images))
check('模型没有照片壳体材质', {Path(bpy.path.abspath(im.filepath)).stem for im in file_images} == {'front', 'inside', 'back', 'tray', 'disc', 'left', 'right'})
report = {'checks_passed': len(checks), 'checks': checks, 'bad_solids': bad,
          'source_blend': bpy.data.filepath, 'objects': len(collection.all_objects)}
path = Path(bpy.data.filepath).parent/'重新打开验证.json'
path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print('REOPEN_CHECKS_PASS', len(checks), flush=True)
