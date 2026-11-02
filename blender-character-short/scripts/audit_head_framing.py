"""Read all-frame weighted head/hair bounds from the actual saved scene."""
import argparse,bpy,json,math,numpy as np,pathlib,sys
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector
p=argparse.ArgumentParser();p.add_argument('--blend',required=True);p.add_argument('--character',required=True);p.add_argument('--output',required=True);p.add_argument('--margin',type=float,default=.02)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
if not math.isfinite(a.margin) or not 0<=a.margin<.5:raise ValueError('Margin must be finite and between 0 and .5')
cfg=json.loads(pathlib.Path(a.character).resolve().read_text('utf-8'))
output=pathlib.Path(a.output).resolve();bpy.ops.wm.open_mainfile(filepath=str(pathlib.Path(a.blend).resolve()))
s=bpy.context.scene;arms=[o for o in s.objects if o.type=='ARMATURE']
if len(arms)!=1:raise ValueError('Expected one configured character armature')
arm=arms[0]
head=arm.data.bones[cfg['bones']['head']]
bone_names={head.name,*[bone.name for bone in head.children_recursive]}
meshes=[]
for obj in s.objects:
    if obj.type!='MESH' or obj.hide_render or not any(m.type=='ARMATURE' and m.object==arm for m in obj.modifiers):continue
    groups={g.index for g in obj.vertex_groups if g.name in bone_names}
    ids=np.array([v.index for v in obj.data.vertices if sum(g.weight for g in v.groups if g.group in groups)>=.1],dtype=int)
    if len(ids):meshes.append((obj,ids))
if not meshes:raise ValueError('No reliably weighted head vertices found')
records=[];projector_checked=False
for frame in range(s.frame_start,s.frame_end+1):
    s.frame_set(frame);bpy.context.view_layer.update();graph=bpy.context.evaluated_depsgraph_get()
    camera=s.camera
    projection=np.array(camera.calc_matrix_camera(graph,x=s.render.resolution_x,y=s.render.resolution_y,
                       scale_x=s.render.pixel_aspect_x,scale_y=s.render.pixel_aspect_y))
    view=np.array(camera.matrix_world.inverted());bounds=[]
    for obj,ids in meshes:
        evaluated=obj.evaluated_get(graph);mesh=evaluated.to_mesh()
        if len(mesh.vertices)!=len(obj.data.vertices):raise ValueError('Changed topology invalidates the weighted vertex correspondence')
        xyz=np.empty(len(mesh.vertices)*3,np.float32);mesh.vertices.foreach_get('co',xyz)
        xyz=xyz.reshape(-1,3)[ids];homogeneous=np.column_stack((xyz,np.ones(len(xyz))))
        world=homogeneous@np.array(obj.matrix_world).T
        clip=world@(projection@view).T
        if (clip[:,3]<=0).any():raise ValueError('Selected head vertices behind camera')
        ndc=clip[:,:2]/clip[:,3,None]*.5+.5
        if not projector_checked:
            check=world_to_camera_view(s,camera,Vector(world[0,:3]))
            if not np.allclose(ndc[0],check[:2],atol=1e-6):raise ValueError('Projection convention mismatch')
            projector_checked=True
        bounds.append([float(ndc[:,0].min()),float(ndc[:,1].min()),float(ndc[:,0].max()),float(ndc[:,1].max())])
        evaluated.to_mesh_clear()
    minimum_x=min(b[0] for b in bounds);minimum_y=min(b[1] for b in bounds)
    maximum_x=max(b[2] for b in bounds);maximum_y=max(b[3] for b in bounds)
    margin=min(minimum_x,minimum_y,1-maximum_x,1-maximum_y)
    records.append({'frame':frame,'camera':camera.name,'bounds':[minimum_x,minimum_y,maximum_x,maximum_y],'minimum_edge_margin':margin})
report={'scope':'All integer frames of original vertices weighted >=.1 to mapped head/descendants; actual evaluated geometry and active production camera. No occlusion, normal-speed viewing, or generated-topology coverage claim.',
        'selected_vertices':{obj.name:len(ids) for obj,ids in meshes},'requested_margin':a.margin,
        'minimum_margin':min(r['minimum_edge_margin'] for r in records),
        'cropped_frames':[r['frame'] for r in records if r['minimum_edge_margin']<0],
        'below_requested_margin_frames':[r['frame'] for r in records if r['minimum_edge_margin']<a.margin],
        'worst_frame':min(records,key=lambda r:r['minimum_edge_margin']), 'records':records}
output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,indent=2),'utf-8')
print('HEAD_FRAMING',report['minimum_margin'],'cropped',len(report['cropped_frames']),flush=True)
