"""Blend two recorded actions on an identical existing rig; preserve source files.

This route requires matching static actor roots, original geometry/constraints,
no source physics cache/NLA or extra animated objects, and unit-scale quaternion
bone channels with preserved near-unit scale. It does not solve contact or certify transition naturalness.
"""
from pathlib import Path
import argparse,datetime,json,math,sys
sys.dont_write_bytecode=True;sys.path.insert(0,str(Path(__file__).resolve().parent))
from action_sequence_plan import load,timeline,sha
import bpy,numpy as np
from mathutils import Quaternion,Vector
from body_motion_runtime import character_rig,geometry_identity,bone_worlds,linear_curves

def open_scene(path):
    bpy.ops.wm.open_mainfile(filepath=str(path),load_ui=False,use_scripts=False)
    scene=bpy.context.scene;arm,actor=character_rig(scene)
    if scene.rigidbody_world is not None:raise ValueError('Compose actions before original-data physics assembly/bake')
    ad=arm.animation_data
    if not ad or not ad.action or ad.nla_tracks:raise ValueError('One baked original-rig action without NLA required')
    if any(o!=arm and o.animation_data and o.animation_data.action for o in scene.objects):raise ValueError('Extra animated objects need a separately validated composition route')
    for o in scene.objects:
        if o.type=='MESH' and o.data.shape_keys and o.data.shape_keys.animation_data and o.data.shape_keys.animation_data.action:raise ValueError('Animated morphs need separate synchronized composition')
    paths={b.path_from_id(k):b.name for b in arm.pose.bones for k in ['rotation_quaternion','location','scale']}
    if any(c.data_path not in paths for c in ad.action.fcurves):raise ValueError('Unsupported source action channel')
    active=sorted({paths[c.data_path] for c in ad.action.fcurves})
    if any(arm.pose.bones[n].rotation_mode!='QUATERNION' for n in active):raise ValueError('Source bone channels must use quaternions')
    constraints=[(b.name,[(c.name,c.type,c.mute,c.influence,getattr(c,'subtarget',None),getattr(c,'target',None).name if getattr(c,'target',None) else None) for c in b.constraints]) for b in arm.pose.bones]
    morphs={o.name:{k.name:k.value for k in o.data.shape_keys.key_blocks} for o in scene.objects if o.type=='MESH' and o.data.shape_keys}
    return scene,arm,actor,{'active':active,'geometry':geometry_identity(scene,arm),'bones':list(arm.pose.bones.keys()),
                           'root':np.asarray(actor.matrix_world).tolist(),'constraints':constraints,'morphs':morphs}

def capture(clip,plan,names,expected):
    scene,arm,actor,meta=open_scene(clip['scene'])
    if any(meta[k]!=expected[k] for k in ['geometry','bones','root','constraints','morphs']):raise ValueError('Source character/rest/root/constraints/morphs differ')
    first,last=clip['frames']
    if not scene.frame_start<=first<last<=scene.frame_end or abs(scene.render.fps/scene.render.fps_base-plan['fps'])>1e-8:raise ValueError('Source range/fps differs from reviewed cut')
    result={}
    for frame in range(first,last+1):
        scene.frame_set(frame);bpy.context.view_layer.update();poses={}
        for n in names:
            b=arm.pose.bones[n];q=b.rotation_quaternion.copy()
            if q.magnitude<1e-8 or max(abs(s-1) for s in b.scale)>1e-4 or not all(math.isfinite(v) for v in [*b.location,*q,*b.scale]):raise ValueError('Finite quaternion and near-unit scale required at '+str(frame)+' / '+n+': '+str(list(b.scale)))
            q.normalize();poses[n]=(tuple(b.location),tuple(q),tuple(b.scale))
        current={o.name:{k.name:k.value for k in o.data.shape_keys.key_blocks} for o in scene.objects if o.type=='MESH' and o.data.shape_keys}
        if current!=meta['morphs']:raise ValueError('Source morph values change over cut')
        result[frame]={'poses':poses,'worlds':bone_worlds(arm,meta['bones']).astype(np.float32)}
    return result

def main():
    if not bpy.app.background:raise ValueError('Use an isolated background process; do not replace an interactive scene')
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ['plan','output','report']:parser.add_argument('--'+key,required=True,type=Path)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    if args.output.exists() or args.report.exists() or args.output.suffix.lower()!='.blend' or args.report.suffix.lower()!='.json' or args.output.resolve()==args.report.resolve():raise ValueError('New distinct blend/report outputs required')
    plan=load(args.plan);jobs=timeline(plan)
    _,_,_,a=open_scene(plan['clips'][0]['scene']);_,_,_,b=open_scene(plan['clips'][1]['scene'])
    if any(a[k]!=b[k] for k in ['geometry','bones','root','constraints','morphs']):raise ValueError('Two clips must share identical target rig, skin, root and constraint state')
    if len(jobs)*len(a['bones'])>500000:raise ValueError('Output bone-frame budget exceeded')
    names=sorted(set(a['active'])|set(b['active']))
    first=capture(plan['clips'][0],plan,names,a);second=capture(plan['clips'][1],plan,names,a)
    # capture(first) leaves its exact original scene as our editable base.
    scene,arm,actor,_=open_scene(plan['clips'][0]['scene'])
    arm.animation_data.action=bpy.data.actions.new('Composed recorded actions')
    previous={}
    for row in jobs:
        scene.frame_set(row['frame'])
        for name in names:
            pa=first[row['a']]['poses'][name] if row['a'] is not None else None
            pb=second[row['b']]['poses'][name] if row['b'] is not None else None
            if pa is None:location,q,scale=Vector(pb[0]),Quaternion(pb[1]),Vector(pb[2])
            elif pb is None:location,q,scale=Vector(pa[0]),Quaternion(pa[1]),Vector(pa[2])
            else:
                qa,qb=Quaternion(pa[1]),Quaternion(pb[1])
                if qa.dot(qb)<0:qb.negate()
                location=Vector(pa[0]).lerp(Vector(pb[0]),row['weight']);q=qa.slerp(qb,row['weight']);scale=Vector(pa[2]).lerp(Vector(pb[2]),row['weight'])
            if name in previous and q.dot(previous[name])<0:q.negate()
            bone=arm.pose.bones[name];bone.location=location;bone.rotation_mode='QUATERNION';bone.rotation_quaternion=q;bone.scale=scale
            bone.keyframe_insert('location',frame=row['frame']);bone.keyframe_insert('rotation_quaternion',frame=row['frame']);bone.keyframe_insert('scale',frame=row['frame']);previous[name]=q.copy()
    linear_curves(arm.animation_data.action)
    scene.frame_start=1;scene.frame_end=len(jobs);scene.render.fps=plan['fps'];scene.render.fps_base=1;scene.frame_set(1)
    if geometry_identity(scene,arm)!=a['geometry']:raise ValueError('Composition changed source rest/skin/morph data')
    args.output.parent.mkdir(parents=True,exist_ok=True);bpy.ops.wm.save_as_mainfile(filepath=str(args.output.resolve()),check_existing=False)
    # Independent reopen: every unmixed integer frame must preserve source worlds.
    bpy.ops.wm.open_mainfile(filepath=str(args.output.resolve()),load_ui=False,use_scripts=False)
    scene=bpy.context.scene;arm,actor=character_rig(scene);maximum=0.;checked=0
    for row in jobs:
        if row['a'] is not None and row['b'] is not None and row['weight'] not in [0.,1.]:continue
        expected=first[row['a']]['worlds'] if row['weight']==0 else second[row['b']]['worlds']
        scene.frame_set(row['frame']);bpy.context.view_layer.update()
        error=float(np.max(np.abs(bone_worlds(arm,a['bones'])-expected)))
        if not math.isfinite(error):raise ValueError('Nonfinite saved source-frame preservation error')
        maximum=max(maximum,error);checked+=1
    if maximum>1e-5:raise ValueError('Saved unmixed source poses differ: '+str(maximum))
    if any(sha(c['scene'])!=c['sha256'] for c in plan['clips']):raise ValueError('Input action scene changed')
    report={'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'recorded-action-sequence-saved-reopened-await-contact-and-visuals',
            'output':str(args.output.resolve()),'output_sha256':sha(args.output),'plan':plan,'plan_sha256':sha(args.plan),
            'writer_sha256':sha(Path(__file__)),'planner_sha256':sha(Path(__file__).with_name('action_sequence_plan.py')),
            'frames':len(jobs),'fps':plan['fps'],'active_bones':names,'geometry_identity':a['geometry'],
            'source_scale_max_unit_difference':max(abs(v-1) for data in [first,second] for state in data.values() for pose in state['poses'].values() for v in pose[2]),
            'source_scene_bytes_unchanged':True,'unmixed_integer_frames_reopened':checked,
            'unmixed_all_bone_world_max_component_error':maximum,'timeline':jobs,'normal_speed_continuous_viewing':False,
            'scope':'Two source-recorded actions on identical original rig, bone-local translation, preserved near-unit scale and shortest quaternion SLERP with quintic overlap weights. No authored replacement body poses, root realignment, footplant, physics, penetration, subframe or naturalness acceptance.'}
    args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ['timeline','plan','active_bones']}))

if __name__=='__main__':main()
