"""Create a clean viewing copy, preserving the source .blend and geometry."""
import bpy,hashlib,json
from pathlib import Path
from mathutils import Vector

scene=bpy.context.scene
source=Path(bpy.data.filepath)
model=bpy.data.objects['MiniCD · 主体53×45×8mm']
geometry=bpy.data.collections['01 · 实体样机']
studio=bpy.data.collections['02 · 可切换摄影棚']
def fingerprint():
    digest=hashlib.sha256()
    for ob in sorted((o for o in geometry.all_objects if o.type=='MESH'),key=lambda o:o.name):
        digest.update(ob.name.encode())
        for vertex in ob.data.vertices:
            digest.update(str(tuple(vertex.co)).encode())
        for polygon in ob.data.polygons:
            digest.update(str(tuple(polygon.vertices)).encode())
    return digest.hexdigest()
before=fingerprint()
for layer in scene.view_layers:
    def hide_studio(collection):
        if collection.collection==studio: collection.hide_viewport=True
        for child in collection.children: hide_studio(child)
    hide_studio(layer.layer_collection)
model['opening_degrees']=180.
model.update_tag()
scene.frame_set(scene.frame_current)
bpy.context.view_layer.update()
points=[ob.matrix_world@Vector(c) for ob in geometry.all_objects if ob.type=='MESH' for c in ob.bound_box]
centre=Vector([(min(p[i] for p in points)+max(p[i] for p in points))/2 for i in range(3)])
extent=max(max(p[i] for p in points)-min(p[i] for p in points) for i in range(3))
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            space=area.spaces.active
            space.clip_start=.005
            space.clip_end=10
            space.overlay.show_overlays=False
            space.region_3d.view_perspective='PERSP'
            space.region_3d.view_location=centre
            space.region_3d.view_distance=extent*1.7
            space.region_3d.view_rotation=scene.camera.rotation_euler.to_quaternion()
        elif area.type=='PROPERTIES':
            area.spaces.active.context='OBJECT'
for ob in bpy.context.selected_objects: ob.select_set(False)
model.select_set(True)
bpy.context.view_layer.objects.active=model
assert fingerprint()==before
assert not studio.hide_render
floor=bpy.data.objects['连续地面 · 接触阴影与真实反射']
assert not floor.hide_render
destination=source.with_name('迷你CD-查看版.blend')
bpy.ops.wm.save_as_mainfile(filepath=str(destination))
report={'source':str(source),'view_copy':str(destination),'mesh_sha256':before,
        'geometry_unchanged':True,'opening_degrees':180,
        'studio_hidden_in_viewport_only':True,'render_floor_retained':True,
        'viewport_clip_mm':[5,10000]}
(source.parent/'查看版验证.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print('CLEAN_VIEW_SAVED',str(destination),flush=True)
