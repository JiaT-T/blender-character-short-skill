"""Read a saved import baseline and export rig/material/shape calibration data."""
import argparse,json,sys
from pathlib import Path
import bpy
from mathutils import Vector
p=argparse.ArgumentParser();p.add_argument('--blend',required=True);p.add_argument('--output',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);bpy.ops.wm.open_mainfile(filepath=str(Path(a.blend).resolve()));scene=bpy.context.scene;report={'blender':bpy.app.version_string,'blend':a.blend,'armatures':[],'meshes':[]};points=[]
for arm in [o for o in scene.objects if o.type=='ARMATURE']:
    bones=[]
    for b in arm.pose.bones:bones.append({'name':b.name,'parent':b.parent.name if b.parent else None,'head_world':list(arm.matrix_world@b.head),'tail_world':list(arm.matrix_world@b.tail),'rest_matrix_armature':list(map(list,b.bone.matrix_local)),'deform':b.bone.use_deform,'constraints':[{'type':c.type,'influence':c.influence} for c in b.constraints]})
    report['armatures'].append({'name':arm.name,'bones':bones})
for obj in [o for o in scene.objects if o.type=='MESH' and any(m.type=='ARMATURE' for m in o.modifiers)]:
    ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh();points.extend(ev.matrix_world@v.co for v in me.vertices);ev.to_mesh_clear();materials=[]
    for m in obj.data.materials:
        tex=m.node_tree.nodes.get('mmd_base_tex') if m and m.use_nodes else None;im=tex.image if tex else None
        materials.append({'name':m.name if m else None,'diffuse':list(m.diffuse_color) if m else None,'base_image':im.filepath if im else None,'image_size':list(im.size) if im else None})
    report['meshes'].append({'name':obj.name,'vertices':len(obj.data.vertices),'uv_layers':list(obj.data.uv_layers.keys()),'shape_keys':list(obj.data.shape_keys.key_blocks.keys()) if obj.data.shape_keys else [],'materials':materials})
if points:
    low=[min(p[i] for p in points) for i in range(3)];high=[max(p[i] for p in points) for i in range(3)];report['bounds_world']=[low,high];report['height']=high[2]-low[2];report['ground']=low[2]
path=Path(a.output);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print('INSPECTED',a.output)
