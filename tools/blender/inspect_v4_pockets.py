import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

seat=bpy.data.objects['盒底铰链支座']
print('SEAT',len(seat.data.vertices),[(m.name,m.type) for m in seat.modifiers])
points=[v.co for v in seat.data.vertices if abs(v.co.z-.00125)<.00001]
print('POCKET_FLOOR',len(points),[sum(p[i] for p in points)/len(points) if points else None for i in range(3)])
print('LARGE_FACES',[(len(p.vertices),tuple(p.center),tuple(p.normal)) for p in seat.data.polygons if len(p.vertices)>20])
raw=BVHTree.FromPolygons([v.co for v in seat.data.vertices],[tuple(p.vertices) for p in seat.data.polygons])
print('RAW_HIT',raw.ray_cast(Vector((-.025,-.0196,.012)),Vector((0,0,-1)),.03)[0])
for mod in seat.modifiers: mod.show_viewport=False
bpy.context.view_layer.update()
raw=BVHTree.FromObject(seat,bpy.context.evaluated_depsgraph_get())
print('NO_MOD_HIT',raw.ray_cast(Vector((-.025,-.0196,.012)),Vector((0,0,-1)),.03)[0])
for mod in seat.modifiers: mod.show_viewport=True
bpy.context.view_layer.update()
tri=seat.modifiers.new('诊断三角化','TRIANGULATE')
bpy.context.view_layer.objects.active=seat
while seat.modifiers.find(tri.name)>0: bpy.ops.object.modifier_move_up(modifier=tri.name)
bpy.context.view_layer.update()
raw=BVHTree.FromObject(seat,bpy.context.evaluated_depsgraph_get())
print('TRI_MOD_HIT',raw.ray_cast(Vector((-.025,-.0196,.012)),Vector((0,0,-1)),.03)[0])
for name in ['盒底铰链支座','盒底铰链支座.001','盒盖侧向挡纸筋','盒底锁扣凹座']:
    ob=bpy.data.objects.get(name)
    print('GEOMETRY',name,len(ob.data.vertices))
base=seat.parent
bpy.ops.mesh.primitive_cube_add(size=1)
cutter=bpy.context.object
cutter.name='临时诊断凹腔'
cutter.parent=base
cutter.location=(-.025,-.0196,.0025)
cutter.scale=(.00064,.00215,.0025)
bpy.context.view_layer.update()
mod=seat.modifiers.new('诊断凹腔','BOOLEAN')
mod.operation='DIFFERENCE'
mod.solver='EXACT'
mod.object=cutter
bpy.context.view_layer.objects.active=seat
while seat.modifiers.find(mod.name)>0:
    bpy.ops.object.modifier_move_up(modifier=mod.name)
bpy.ops.object.modifier_apply(modifier=mod.name)
bpy.data.objects.remove(cutter,do_unlink=True)
bpy.context.view_layer.update()
tree=BVHTree.FromObject(seat,bpy.context.evaluated_depsgraph_get())
print('AFTER',len(seat.data.vertices),tree.ray_cast(Vector((-.025,-.0196,.012)),Vector((0,0,-1)),.03)[0])
