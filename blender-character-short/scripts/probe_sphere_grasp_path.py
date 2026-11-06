"""Inspect explicit parameter poses against the real sphere and original skin."""
from pathlib import Path
import sys,argparse,json,datetime
sys.dont_write_bytecode=True;sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy,numpy as np
from mathutils.bvhtree import BVHTree
from hand_control_plan import profile,number
from hand_control_runtime import *
from audit_sphere_grasp import tree

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['blend','profile','spec','body-report','poses','report']:p.add_argument('--'+key,required=True,type=Path)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);assert not a.report.exists();mapping=profile(json.loads(a.profile.read_text('utf-8')));spec=json.loads(a.spec.read_text('utf-8'));body=json.loads(a.body_report.read_text('utf-8'));plan=json.loads(a.poses.read_text('utf-8'));poses=plan['poses']
    if not isinstance(poses,list) or not 1<=len(poses)<=256:raise ValueError('1..256 explicit poses required')
    groups={g['id']:g for g in spec['groups']};known={(j['id'],axis['id']) for j in mapping['joints'] for axis in j['axes']}
    for row in poses:
        if set(row['fractions'])!=set(groups) or any(not 0<=number(v,'pose fraction')<=1 for v in row['fractions'].values()):raise ValueError('Every known bounded parameter is required')
    if any(tuple(c) not in known for g in groups.values() for c in g['channels']):raise ValueError('Unknown axis channel')
    source_hash=sha(a.blend)
    if source_hash!=body['output_sha256']:raise ValueError('Stale body source')
    bpy.ops.wm.open_mainfile(filepath=str(a.blend.resolve()),load_ui=False,use_scripts=False);scene=bpy.context.scene;set_frame(scene,plan['frame']);arm,meshes,_,_,binding=bind(scene,mapping);tops={o.name:topology(o.data) for o in meshes};all_triangles={n:[tuple(map(int,t)) for t in data.reshape(-1,3)] for n,data in tops.items()};names={c[0] for g in groups.values() for c in g['channels']};joints=[j for j in mapping['joints'] if j['id'] in names];bases={j['bone']:arm.pose.bones[j['bone']].matrix_basis.copy() for j in joints};allowed,protected,_,_=protection(arm,scene,list(bases));original=worlds(arm,protected);sphere=scene.objects[body['sphere_name']];center=sphere.matrix_world.translation.copy();radius=body['radius_m'];regions={}
    for obj in meshes:
        groupnames={g.index:g.name for g in obj.vertex_groups};weights={v.index:{groupnames[g.group]:g.weight for g in v.groups} for v in obj.data.vertices}
        for region,row in spec['contacts'].items():
            ids={i for i,w in weights.items() if sum(w.get(n,0) for n in row['bones'])>=row['min_weight']};tris=[t for t in all_triangles[obj.name] if all(i in ids for i in t)]
            if tris:regions.setdefault(region,[]).append((obj.name,tris))
    check_work(arm,meshes,scene,poses);rows=[]
    for index,row in enumerate(poses):
        channels={tuple(c):[[1,row['fractions'][name]],[2,row['fractions'][name]]] for name,g in groups.items() for c in g['channels']}
        for j in joints:
            b=arm.pose.bones[j['bone']];b.matrix_basis=bases[b.name];b.rotation_mode='QUATERNION';b.rotation_quaternion=bases[b.name].to_quaternion()@rotation_delta(j,channels,1)
        bpy.context.view_layer.update();points=evaluated_arrays(scene,meshes,tops);minimum=min(tree(points[name],tris).find_nearest(center)[3]-radius for name,tris in all_triangles.items());gaps={region:min(tree(points[name],tris).find_nearest(center)[3]-radius for name,tris in chunks) for region,chunks in regions.items()};rows.append({'label':row.get('label',str(index)),'fractions':row['fractions'],'minimum_skin_sphere_gap_m':minimum,'pad_gaps_m':gaps})
        if index%16==0:print('GRASP_PATH_PROBE',index+1,'of',len(poses),minimum,flush=True)
    error=float(np.max(np.abs(worlds(arm,protected)-original)));assert sha(a.blend)==source_hash and error<=1e-5;a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps({'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'explicit-static-path-pose-inspection-complete','source_sha256':source_hash,'profile_sha256':sha(a.profile),'spec_sha256':sha(a.spec),'poses_sha256':sha(a.poses),'writer_sha256':sha(Path(__file__)),'runtime_sha256':sha(Path(__file__).with_name('hand_control_runtime.py')),'protected_world_error':error,'rows':rows,'scope':'Actual skin/sphere distance for explicit parameter poses at one wrist frame. Not interpolation/path/hand self-collision or continuous-motion acceptance; audit the saved clip after adopting a path.'},indent=2),'utf-8');print('GRASP_PATH_PROBE_DONE',len(rows),flush=True)
if __name__=='__main__':main()
