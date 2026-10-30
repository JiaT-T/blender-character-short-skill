"""Measure a configured palm anchor against actual deformed hand geometry.

The palm side is supplied by character calibration, never guessed from a bone
name. This suggests an offset across sampled poses, not full collision solving.
"""
import argparse,sys,json,math
from pathlib import Path
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
sys.path.insert(0,str(Path(__file__).parent))
from contact_motion import anchor_world

def measure(scene,arm,anchor,height,ray_length,min_weight):
    if any(abs(v-1)>1e-6 for v in arm.scale):raise ValueError('Surface calibration currently requires unit-scale armature object')
    start=arm.pose.bones[anchor['start_bone']];end=arm.pose.bones[anchor['end_bone']];normal=(arm.matrix_world.to_3x3()@start.matrix.to_3x3()@Vector(anchor['normal_local'])).normalized();center=anchor_world(arm,dict(anchor,normal_offset=0),height);allowed={start.name,*[b.name for b in start.children_recursive]};hits=[];dg=bpy.context.evaluated_depsgraph_get()
    for obj in scene.objects:
        if obj.type!='MESH' or not any(m.type=='ARMATURE' and m.object==arm for m in obj.modifiers):continue
        groups={g.index for g in obj.vertex_groups if g.name in allowed};selected={v.index for v in obj.data.vertices if sum(g.weight for g in v.groups if g.group in groups)>min_weight};ev=obj.evaluated_get(dg);mesh=ev.to_mesh()
        try:
            if len(mesh.vertices)!=len(obj.data.vertices):raise ValueError('Surface calibration does not support topology-changing modifiers')
            faces=[p for p in mesh.polygons if all(i in selected for i in p.vertices)]
            if not faces:continue
            bvh=BVHTree.FromPolygons([obj.matrix_world@v.co for v in mesh.vertices],[tuple(p.vertices) for p in faces]);hit,n,index,distance=bvh.ray_cast(center+normal*height*ray_length,-normal,height*ray_length*2)
            if hit is not None:hits.append({'mesh':obj.name,'point':list(hit),'normal':list(n),'normal_dot':n.dot(normal),'offset_height':(hit-center).dot(normal)/height,'material':obj.data.materials[faces[index].material_index].name,'selected_faces':len(faces)})
        finally:ev.to_mesh_clear()
    if not hits:raise ValueError('No hand surface hit: inspect anchor location, palm side, vertex weights and ray extent')
    hit=max(hits,key=lambda x:x['offset_height'])
    if hit['normal_dot']<.25:raise ValueError('Grazing or reversed surface hit; inspect palm calibration instead of accepting this offset')
    return {'anchor_center':list(center),'palm_normal_world':list(normal),'actual_finger_direction':list((arm.matrix_world.to_3x3()@(end.head-start.head)).normalized()),'selected_hit':hit,'all_hits':hits}

def main():
    p=argparse.ArgumentParser();p.add_argument('--blend',required=True);p.add_argument('--character',required=True);p.add_argument('--frames',required=True);p.add_argument('--output',required=True);p.add_argument('--clearance',type=float,default=.001);p.add_argument('--ray-length',type=float,default=.08);p.add_argument('--min-weight',type=float,default=.35);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);cfg=json.loads(Path(a.character).read_text('utf-8'));bpy.ops.wm.open_mainfile(filepath=str(Path(a.blend).resolve()));scene=bpy.context.scene;arms=[o for o in scene.objects if o.type=='ARMATURE']
    if len(arms)!=1:raise ValueError('Expected one character armature')
    if not cfg.get('contact_anchors'):raise ValueError('Character has no configured contact anchors')
    frames=[int(f) for f in a.frames.split(',')];records=[];recommendations={}
    for name,anchor in cfg['contact_anchors'].items():
        measured=[]
        for frame in frames:
            scene.frame_set(frame);bpy.context.view_layer.update();record=measure(scene,arms[0],anchor,cfg['height'],a.ray_length,a.min_weight);record.update(frame=frame,anchor=name);records.append(record);measured.append(record['selected_hit']['offset_height'])
        recommendations[name]={'sampled_surface_offsets':measured,'suggested_normal_offset':max(measured)+a.clearance,'clearance_height':a.clearance,'prior_normal_offset':anchor.get('normal_offset',0)}
    report={'frames':frames,'records':records,'recommendations':recommendations,'scope':'Surface at the anchor ray in sampled poses only. Inspect prop footprint, palm side, fingers and transition frames in actual renders; not full mesh collision acceptance.'};out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8');print('CONTACT_SURFACE_MEASURED',json.dumps(recommendations))

if __name__=='__main__':main()
