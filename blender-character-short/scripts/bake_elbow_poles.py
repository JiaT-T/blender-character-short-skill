"""Repose an existing arm around the original wrist, then verify protected data.

This changes elbow/upper-arm acting, not wrist choreography or character weights.
Surface clearance and visual quality must be checked separately after the bake.
"""
import argparse,hashlib,json,math,sys
from pathlib import Path
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy,numpy as np
from mathutils import Matrix,Vector
from build_performance import two_bone
from elbow_pole_plan import load_json,validate_plan

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def angle(q):
    if not all(math.isfinite(v) for v in q) or not math.isfinite(q.magnitude) or q.magnitude<1e-8:raise ValueError('Invalid evaluated wrist quaternion')
    return math.degrees(2*math.acos(min(1.,abs(q.normalized().w))))

def checked(value):
    array=np.asarray(value,dtype=np.float64)
    if not np.isfinite(array).all():raise ValueError('Nonfinite evaluated elbow-stage matrix or pose')
    return array
def dependency_bones(arm,changed):
    result=set(changed)
    while True:
        old=set(result)
        for bone in arm.pose.bones:
            if bone.parent and bone.parent.name in result or any(not c.mute and c.influence>0 and getattr(c,'target',None)==arm and getattr(c,'subtarget',None) in result for c in bone.constraints):result.add(bone.name)
        if result==old:return result

def orient(arm,bone,q_world):
    q=arm.matrix_world.to_quaternion().inverted()@q_world
    desired=Matrix.Translation(bone.head)@q.to_matrix().to_4x4()
    bone.matrix_basis=bone.bone.convert_local_to_pose(desired,bone.bone.matrix_local,parent_matrix=bone.parent.matrix if bone.parent else Matrix.Identity(4),parent_matrix_local=bone.parent.bone.matrix_local if bone.parent else Matrix.Identity(4),invert=True)
    bpy.context.view_layer.update()

def bake(scene,arm,character,plan):
    first,last=scene.frame_start,scene.frame_end;count=last-first+1
    if not 1<=count<=1200 or count*len(arm.pose.bones)>500000:raise ValueError('Bake exceeds 1200 frames or 500000 evaluated bone-frames')
    plan=validate_plan(plan,first,last,character['height'],character['ground']);h=float(character['height']);side=plan['side'];names=[character['bones'][side+suffix] for suffix in ('_arm','_elbow','_wrist')]
    if len(set(names))!=3 or any(n not in arm.pose.bones for n in names):raise ValueError('Missing/distinct arm, elbow or wrist mapping')
    a,b,c=[arm.pose.bones[n] for n in names]
    if a not in b.parent_recursive or b not in c.parent_recursive:raise ValueError('Mapped arm/elbow/wrist must follow the existing ancestor chain')
    if any(not con.mute and con.influence>0 and con.type=='IK' for bone in [a,b,c] for con in bone.constraints):raise ValueError('Active arm IK is unsupported; this tool does not mute it')
    if not arm.animation_data or not arm.animation_data.action:raise ValueError('An existing authored arm action is required')
    allowed=dependency_bones(arm,names);protected=[n for n in arm.pose.bones.keys() if n not in allowed];objects=[o for o in scene.objects if o!=arm];states=[]
    if count*(len(arm.pose.bones)+len(objects))>500000:raise ValueError('Combined bone/object-frame budget exceeded')
    for f in range(first,last+1):
        scene.frame_set(f);bpy.context.view_layer.update();scale=arm.matrix_world.to_scale()
        if min(scale)<=1e-6 or max(scale)>1e6 or max(scale)-min(scale)>1e-5*max(scale) or arm.matrix_world.determinant()<=0:raise ValueError('A positive uniform armature world scale is required')
        state={'basis':{n:arm.pose.bones[n].matrix_basis.copy() for n in names},'wrist':(arm.matrix_world@c.matrix).copy(),'elbow':arm.matrix_world@b.head,'protected':checked([list(map(list,arm.matrix_world@arm.pose.bones[n].matrix)) for n in protected]),'changed':checked([list(map(list,arm.matrix_world@arm.pose.bones[n].matrix)) for n in names]),'objects':checked([list(map(list,o.matrix_world)) for o in objects])}
        checked(list(map(list,state['wrist'])));checked([list(map(list,m)) for m in state['basis'].values()]);checked(state['elbow']);states.append(state)
    previous={};records=[]
    for f,state in zip(range(first,last+1),states):
        scene.frame_set(f)
        for n in names:arm.pose.bones[n].matrix_basis=state['basis'][n]
        bpy.context.view_layer.update()
        if plan['start']<=f<=plan['end']:
            u=(f-plan['start'])/(plan['blend_end']-plan['start']) if plan['blend_end']>plan['start'] else 1.;u=max(0.,min(1.,u));w=u*u*(3-2*u)
            if plan['schema']==2 and f>plan['release_start']:
                release=(f-plan['release_start'])/(plan['end']-plan['release_start']);w*=1-release*release*(3-2*release)
            pole=state['elbow'].lerp(Vector(plan['pole_world']),w);inverse=arm.matrix_world.inverted()
            answer=two_bone(a,b,c,inverse@state['wrist'].translation,inverse@pole,reach_fraction=1)
            if answer['clamped']:raise ValueError('Existing wrist point is unreachable at frame '+str(f))
            orient(arm,c,state['wrist'].to_quaternion())
        for n in names:
            bone=arm.pose.bones[n];bone.rotation_mode='QUATERNION';q=bone.rotation_quaternion.copy()
            checked([*q,*bone.location,*bone.scale])
            if n in previous and q.dot(previous[n])<0:q.negate()
            bone.rotation_quaternion=q;previous[n]=q.copy();bone.keyframe_insert('rotation_quaternion',frame=f);bone.keyframe_insert('location',frame=f)
    for curve in arm.animation_data.action.fcurves:
        if any(curve.data_path.startswith('pose.bones["'+n+'"]') for n in names):
            for key in curve.keyframe_points:key.interpolation='LINEAR'
    maxima={'wrist_endpoint_H':0.,'wrist_rotation_degrees':0.,'protected_bone_world':0.,'outside_window_changed_bone_world':0.,'object_world':0.}
    for f,state in zip(range(first,last+1),states):
        scene.frame_set(f);bpy.context.view_layer.update();now=arm.matrix_world@c.matrix;checked(list(map(list,now)));pos=(now.translation-state['wrist'].translation).length/h;rotation=angle(now.to_quaternion().rotation_difference(state['wrist'].to_quaternion()));maxima['wrist_endpoint_H']=max(maxima['wrist_endpoint_H'],pos);maxima['wrist_rotation_degrees']=max(maxima['wrist_rotation_degrees'],rotation)
        if protected:maxima['protected_bone_world']=max(maxima['protected_bone_world'],float(np.max(np.abs(checked([list(map(list,arm.matrix_world@arm.pose.bones[n].matrix)) for n in protected])-state['protected']))))
        if objects:maxima['object_world']=max(maxima['object_world'],float(np.max(np.abs(checked([list(map(list,o.matrix_world)) for o in objects])-state['objects']))))
        boundary=plan['schema']==2 and (f==plan['end'] or f==plan['start'] and plan['start']<plan['blend_end'])
        if f<plan['start'] or f>plan['end'] or boundary:maxima['outside_window_changed_bone_world']=max(maxima['outside_window_changed_bone_world'],float(np.max(np.abs(checked([list(map(list,arm.matrix_world@arm.pose.bones[n].matrix)) for n in names])-state['changed']))))
        records.append({'frame':f,'wrist_endpoint_error_H':pos,'wrist_rotation_difference_degrees':rotation})
    if not all(math.isfinite(v) for v in maxima.values()) or maxima['wrist_endpoint_H']>1e-5 or maxima['wrist_rotation_degrees']>.05 or max(maxima[k] for k in ('protected_bone_world','outside_window_changed_bone_world','object_world'))>1e-5:raise ValueError('Protection verification failed: '+json.dumps(maxima))
    scene.frame_set(first)
    return {'plan':plan,'protected_bones':protected,'allowed_dependency_bones':sorted(allowed),'maximum_errors':maxima,'frames':count,'records':records,'scope':'Original three arm controls reposed with original segment lengths; wrist world position/orientation, other object matrices and protected/outside-window bone matrices verified at integer frames. No mesh intersection, palm contact, subframe, naturalness or continuous viewing acceptance. Constraints, mesh vertices/weights and rig rest hierarchy are not edited.'}

def main(arguments=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('blend','character','plan','output','report'):parser.add_argument('--'+key,required=True,type=Path)
    if arguments is None:arguments=sys.argv[sys.argv.index('--')+1:]
    a=parser.parse_args(arguments);source=a.blend.resolve();character=a.character.resolve();plan=a.plan.resolve();destination=a.output.resolve();report=a.report.resolve()
    if destination.suffix.lower()!='.blend' or report.suffix.lower()!='.json':raise ValueError('Use a new .blend and a separate .json report')
    if len({source,character,plan,destination,report})!=5:raise ValueError('Inputs and outputs must be distinct')
    if destination.exists() or report.exists():raise FileExistsError('Preserve existing outputs; choose a new version')
    cfg=load_json(character);document=load_json(plan);input_hashes={str(p):sha(p) for p in (source,character,plan)}
    bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False);scene=bpy.context.scene;arms=[o for o in scene.objects if o.type=='ARMATURE']
    if len(arms)!=1:raise ValueError('Expected exactly one character armature')
    result=bake(scene,arms[0],cfg,document)
    if any(sha(Path(k))!=v for k,v in input_hashes.items()):raise ValueError('An input changed during the bake')
    destination.parent.mkdir(parents=True,exist_ok=True);report.parent.mkdir(parents=True,exist_ok=True);bpy.ops.wm.save_as_mainfile(filepath=str(destination))
    result.update(schema=1,status='new-scene-saved-wrist-preserved-await-clearance-and-visual-audits',input_scene_sha256=sha(source),output_scene_sha256=sha(destination),character_sha256=sha(character),plan_sha256=sha(plan),writer_sha256=sha(Path(__file__)),base_solver_sha256=sha(Path(__file__).with_name('build_performance.py')),plan_validator_sha256=sha(Path(__file__).with_name('elbow_pole_plan.py')))
    report.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),'utf-8');print('ELBOW_POLE_BAKE',json.dumps(result['maximum_errors']),flush=True)
if __name__=='__main__':main()
