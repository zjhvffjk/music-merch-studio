import bpy
from math import pi
root=bpy.data.objects['MiniCD · 主体53×45×8mm']
assert root['opening_degrees']==180
bpy.context.view_layer.update()
assert abs(bpy.data.objects['盒盖转轴 · Y · 可开合'].rotation_euler.y+pi)<1e-5
studio=bpy.context.view_layer.layer_collection.children['02 · 可切换摄影棚']
assert studio.hide_viewport and not studio.exclude
assert not studio.collection.hide_render
assert not bpy.data.objects['连续地面 · 接触阴影与真实反射'].hide_render
spaces=[a.spaces.active for s in bpy.data.screens for a in s.areas if a.type=='VIEW_3D']
assert spaces and all(abs(s.clip_start-.005)<1e-7 and s.clip_end==10 for s in spaces)
assert all(not s.overlay.show_overlays for s in spaces)
print('VIEW_COPY_REOPEN_PASS',len(spaces),'3D view(s)',flush=True)
