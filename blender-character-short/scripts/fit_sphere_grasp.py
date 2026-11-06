"""Fit a bounded sphere to actual original-rig fingertip surfaces, not bone heads."""
from pathlib import Path
import sys,json,argparse,itertools,time,math,datetime
sys.dont_write_bytecode=True;sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy,numpy as np
from mathutils import Matrix,Vector
from mathutils.bvhtree import BVHTree
from hand_control_plan import profile,number
from hand_control_runtime import sha,bind,topology,evaluated_arrays,set_frame,rotation_delta,protection,worlds,check_work

def checked_center_grid(grid,bounds):
    if not isinstance(grid,list) or len(grid)!=3 or any(not isinstance(axis,list) or not axis or len(axis)>512 for axis in grid) or math.prod(len(axis) for axis in grid)>512:raise ValueError('At most512 three-dimensional center combinations required before allocation')
    for axis in grid:
        for value in axis:number(value,'center coordinate')
    centers=[np.asarray(c,dtype=float) for c in itertools.product(*grid)]
    if any(np.any(c<bounds[:,0]) or np.any(c>bounds[:,1]) for c in centers):raise ValueError('Center outside declared bounds')
    return centers

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ['blend','profile','spec','report']:parser.add_argument('--'+key,required=True,type=Path)
    a=parser.parse_args(sys.argv[sys.argv.index('--')+1:]);assert not a.report.exists();mapping=profile(json.loads(a.profile.read_text('utf-8')));spec=json.loads(a.spec.read_text('utf-8'));side=spec['side'];groups=spec['groups'];known={(j['id'],x['id']) for j in mapping['joints'] for x in j['axes']};seen=set()
    if side not in mapping['hands'] or not 1<=len(groups)<=6:raise ValueError('Explicit side and1..6 bounded parameter groups required')
    for group in groups:
        if not group['channels'] or not 1<=len(group['fractions'])<=8:raise ValueError('Bounded group channels/fractions required')
        for value in group['fractions']:
            if not 0<=number(value,'fraction')<=1:raise ValueError('Fraction outside0..1')
        for row in group['channels']:
            key=tuple(row)
            if key not in known or key in seen:raise ValueError('Unique known axis required')
            seen.add(key)
    pose_count=math.prod(len(g['fractions']) for g in groups)
    if pose_count>256 or not 1<=spec['max_seconds']<=240:raise ValueError('Fit exceeds pose/time budget')
    bounds=np.asarray(spec['center_bounds'],dtype=float);radius_min,radius_max=map(float,spec['radius_range_m']);clearance=float(spec['clearance_m']);gap_limit=float(spec['contact_max_gap_m']);dot_limit=float(spec['max_radial_dot'])
    if bounds.shape!=(3,2) or not np.isfinite(bounds).all() or not np.all(bounds[:,0]<bounds[:,1]) or not 0<radius_min<radius_max<=.1 or not 0<=clearance<gap_limit<=.003 or not -1<dot_limit<0:raise ValueError('Finite physical fit limits required')
    centers=checked_center_grid(spec['center_grid'],bounds)
    before=sha(a.blend);bpy.ops.wm.open_mainfile(filepath=str(a.blend.resolve()),load_ui=False,use_scripts=False);scene=bpy.context.scene;set_frame(scene,scene.frame_start);arm,meshes,selection,_,binding=bind(scene,mapping);joints=[j for j in mapping['joints'] if j['side']==side and any(k[0]==j['id'] for k in seen)];active=[j['bone'] for j in joints];allowed,protected,_,_=protection(arm,scene,active);protected_before=worlds(arm,protected);bases={j['bone']:arm.pose.bones[j['bone']].matrix_basis.copy() for j in joints};tops={o.name:topology(o.data) for o in meshes};W=arm.matrix_world@arm.pose.bones[mapping['hands'][side]].matrix;H=W@Matrix(spec['hand_frame_from_wrist']).inverted();inv=np.asarray(H.inverted(),dtype=float);allbones={mapping['hands'][side],*active};entries={};offset=0;full_triangles=[];region_triangles={name:[] for name in spec['contacts']}
    if not 2<=len(region_triangles)<=6:raise ValueError('2..6 explicit contact regions required')
    for obj in meshes:
        names={g.index:g.name for g in obj.vertex_groups};weights={v.index:{names[g.group]:g.weight for g in v.groups} for v in obj.data.vertices};ids=sorted(i for i,w in weights.items() if any(w.get(n,0)>1e-8 for n in allbones));remap={v:i+offset for i,v in enumerate(ids)};tris=[tuple(t.vertices) for t in obj.data.loop_triangles if all(i in remap for i in t.vertices)];full_triangles.extend(tuple(remap[i] for i in t) for t in tris);entries[obj.name]=ids
        for name,row in spec['contacts'].items():
            if not row['bones'] or any(n not in allbones for n in row['bones']) or not 0<row['min_weight']<=1:raise ValueError('Explicit selected-bone contact region required')
            vertices={i for i in ids if sum(weights[i].get(n,0) for n in row['bones'])>=row['min_weight']};region_triangles[name].extend(tuple(remap[i] for i in t) for t in tris if all(i in vertices for i in t))
        offset+=len(ids)
    if not full_triangles or any(not t for t in region_triangles.values()):raise ValueError('Actual complete hand/pad triangles required')
    check_work(arm,meshes,scene,range(pose_count));start=time.monotonic();best=None;completed=0;evaluations=0
    def apply(values):
        channels={tuple(key):[[1,float(value)],[2,float(value)]] for group,value in zip(groups,values) for key in group['channels']}
        for j in joints:
            bone=arm.pose.bones[j['bone']];bone.matrix_basis=bases[bone.name];bone.rotation_mode='QUATERNION';bone.rotation_quaternion=bases[bone.name].to_quaternion()@rotation_delta(j,channels,1)
        bpy.context.view_layer.update()
    for values in itertools.product(*(g['fractions'] for g in groups)):
        if time.monotonic()-start>spec['max_seconds']:break
        apply(values);points=evaluated_arrays(scene,meshes,tops);coords=np.concatenate([points[name][ids] for name,ids in entries.items()]);coords=coords@inv[:3,:3].T+inv[:3,3];trees={name:BVHTree.FromPolygons(coords,triangles,all_triangles=True) for name,triangles in {'all':full_triangles,**region_triangles}.items()}
        def evaluate(center):
            nonlocal evaluations
            evaluations+=1;query=Vector(center);point,normal,index,distance=trees['all'].find_nearest(query)
            if point is None or normal.dot(query-point)<-1e-6:return None
            radius=min(radius_max,distance-clearance)
            if radius<=0:return None
            contacts={};rays={};penalty=max(0,radius_min-radius)*5
            for name in region_triangles:
                p,n,tri,d=trees[name].find_nearest(query);ray=(p-query).normalized();rays[name]=ray;facing=n.dot(query-p)/max(d,1e-12);penalty+=max(0,.1-facing)*.02;contacts[name]={'gap_m':d-radius,'point_hand':list(p),'normal_hand':list(n),'triangle':list(region_triangles[name][tri]),'external_facing_cos':facing}
            opposing=[]
            for left,right in spec['opposition_pairs']:
                dot=rays[left].dot(rays[right]);penalty+=max(0,dot-dot_limit)*.04;opposing.append({'regions':[left,right],'radial_dot':dot})
            gaps=[r['gap_m'] for r in contacts.values()];score=max(gaps)+.25*sum(gaps)+penalty
            return {'score':score,'center_hand_m':list(map(float,center)),'radius_m':radius,'minimum_hand_surface_gap_m':distance-radius,'contacts':contacts,'opposition':opposing,'fractions':dict(zip((g['id'] for g in groups),values))}
        row=None
        for center in centers:
            result=evaluate(center)
            if result is not None and (row is None or result['score']<row['score']):row=result
        if row:
            for step in [.004,.002,.001,.0005,.00025]:
                for repeat in range(3):
                    previous=row['score']
                    for axis in range(3):
                        for sign in [-1,1]:
                            center=np.asarray(row['center_hand_m']);center[axis]+=sign*step
                            if np.any(center<bounds[:,0]) or np.any(center>bounds[:,1]):continue
                            result=evaluate(center)
                            if result is not None and result['score']<row['score']:row=result
                    if row['score']>=previous-1e-10:break
            if best is None or row['score']<best['score']:best=row;print('SPHERE_FIT_BEST',completed,row['score'],row['radius_m'],row['fractions'],flush=True)
        completed+=1
    if best is None:raise ValueError('No exterior hand-space sphere candidate found')
    apply([best['fractions'][g['id']] for g in groups]);error=float(np.max(np.abs(worlds(arm,protected)-protected_before)));checks={'bounded_radius':radius_min<=best['radius_m']<=radius_max,'all_declared_pads_near_surface':all(-1e-6<=r['gap_m']<=gap_limit for r in best['contacts'].values()),'declared_opposition':all(r['radial_dot']<=dot_limit for r in best['opposition']),'all_contacts_exterior_facing':all(r['external_facing_cos']>=.1 for r in best['contacts'].values()),'protected_bone_world':error<=1e-5,'source_unchanged':sha(a.blend)==before};a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps({'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'sphere-fit-inspection-complete','checks':checks,'static_candidate_pass':all(checks.values()),'source_sha256':before,'profile_sha256':sha(a.profile),'spec_sha256':sha(a.spec),'writer_sha256':sha(Path(__file__)),'runtime_sha256':sha(Path(__file__).with_name('hand_control_runtime.py')),'binding_sha256':binding,'best':best,'pose_candidates_completed':completed,'pose_candidates_planned':pose_count,'center_evaluations':evaluations,'elapsed_seconds':time.monotonic()-start,'protected_world_error':error,'scope':'Actual evaluated static hand/pad triangles. Sphere clearance and named-pad/opposition candidate only, not animated closure, whole-body/stand collision, stability, friction, dynamics or continuous naturalness acceptance. Exit0 means fitting inspection finished: read all booleans.'},ensure_ascii=False,indent=2),'utf-8');print('SPHERE_FIT_DONE',checks,flush=True)
if __name__=='__main__':main()
