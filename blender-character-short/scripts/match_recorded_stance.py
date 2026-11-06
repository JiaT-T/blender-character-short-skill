"""Match incoming stationary ankles to a reviewed outgoing stance on a copy.

Calibrated original-knee kinematics alter only the two leg chains. Existing
upper body, root, fingers and other protected motion remain. This is an explicit
source-performance adaptation, not preserved source leg rotations or friction.
"""
from pathlib import Path
import argparse,datetime,json,math,sys
sys.dont_write_bytecode=True;sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy,numpy as np
from mathutils import Matrix,Quaternion,Vector
from recorded_stance_plan import load,weight
from recorded_stance_math import matched_knee
from action_sequence_plan import sha
from body_motion_runtime import character_rig,geometry_identity,bone_worlds,orient_world
from bake_elbow_poles import dependency_bones
from build_performance import aim_bone
from limb_frame import hinge_alignment

def qangle(q):
    if not all(math.isfinite(v) for v in q):raise ValueError('Nonfinite stance quaternion')
    return math.degrees(2*math.acos(min(1.,abs(q.normalized().w))))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for k in ['blend','plan','output','report']:p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    if not bpy.app.background or a.output.exists() or a.report.exists() or a.output.suffix.lower()!='.blend' or a.report.suffix.lower()!='.json':raise ValueError('Isolated background process and new blend/report outputs required')
    cfg=load(a.plan)
    if sha(a.blend)!=cfg['source_sha256']:raise ValueError('Stance source changed')
    bpy.ops.wm.open_mainfile(filepath=str(a.blend.resolve()),load_ui=False,use_scripts=False)
    scene=bpy.context.scene;arm,actor=character_rig(scene);first,last=cfg['frames'];count=last-first+1;h=cfg['height'];tolerance=cfg['endpoint_tolerance_H']*h
    if scene.rigidbody_world or [scene.frame_start,scene.frame_end]!=[first,last] or scene.render.fps/scene.render.fps_base!=cfg['fps'] or count*len(arm.pose.bones)>500000:raise ValueError('Bounded full pre-physics interval required')
    ad=arm.animation_data
    if not ad or not ad.action or ad.nla_tracks:raise ValueError('One existing baked source action required')
    world3=arm.matrix_world.to_3x3();world_rot=arm.matrix_world.to_quaternion()
    if not np.allclose(np.asarray(world3)@np.asarray(world3).T,np.eye(3),atol=1e-6) or abs(world3.determinant()-1)>1e-6:raise ValueError('Unit-scale proper armature required')
    changed={n for item in cfg['limbs'].values() for n in item['bones']}
    if any(n not in arm.pose.bones for n in changed):raise ValueError('Mapped original leg bone missing')
    chains={s:[arm.pose.bones[n] for n in item['bones']] for s,item in cfg['limbs'].items()}
    rest={}
    for s,(u,k,e) in chains.items():
        if u not in k.parent_recursive or k not in e.parent_recursive or any(c.type=='IK' and not c.mute and c.influence>0 for b in [u,k,e] for c in b.constraints):raise ValueError('Existing ancestor leg chain without active IK required')
        rest[s]=(world3@(k.bone.head_local-u.bone.head_local),world3@k.bone.matrix_local.to_3x3()@Vector(cfg['limbs'][s]['axis_local']))
    allowed=dependency_bones(arm,changed);protected=[n for n in arm.pose.bones.keys() if n not in allowed];identity=geometry_identity(scene,arm);states={}
    for f in range(first,last+1):
        scene.frame_set(f);bpy.context.view_layer.update();bone_worlds(arm,arm.pose.bones.keys());state={'protected':bone_worlds(arm,protected),'legs':{}}
        for s,bones in chains.items():
            points=[arm.matrix_world@b.head for b in bones]
            state['legs'][s]={'points':points,'orientation':(arm.matrix_world@bones[2].matrix).to_quaternion(),
                             'rotations':[(arm.matrix_world@b.matrix).to_quaternion() for b in bones],
                             'locations':[b.location.copy() for b in bones],'scales':[b.scale.copy() for b in bones]}
        states[f]=state
    deltas={};turns={}
    for s in chains:
        reference=states[cfg['reference_frame']]['legs'][s];incoming=states[cfg['match_frames'][1]]['legs'][s]
        deltas[s]=reference['points'][2]-incoming['points'][2]
        turns[s]=reference['orientation']@incoming['orientation'].inverted() if cfg['align_ankle_orientation'] else Quaternion()
        if deltas[s].length>cfg['maximum_shift_H']*h or qangle(turns[s])>cfg['maximum_ankle_orientation_degrees']:raise ValueError('Reviewed stance difference exceeds adaptation bound')
    previous={};expected_targets={};maximum_endpoint=0.;maximum_protected=0.;maximum_rotation=0.;rows=[]
    for f,state in states.items():
        scene.frame_set(f);bpy.context.view_layer.update();w=weight(f,cfg['match_frames']);row={'frame':f,'weight':w,'legs':{}}
        expected_targets[f]={}
        for s,bones in chains.items():
            source=state['legs'][s];hip,knee,ankle=source['points'];target=ankle+deltas[s]*w;desired_q=Quaternion().slerp(turns[s],w)@source['orientation'];expected_targets[f][s]=(target.copy(),desired_q.copy())
            if w>0:
                upper,lower,end=bones
                desired_knee=Vector(matched_knee(hip,knee,ankle,target).tolist())
                delta,hinge=hinge_alignment(*rest[s],desired_knee-hip,target-desired_knee,cfg['limbs'][s]['bend_sign'])
                orient_world(arm,upper,Matrix(delta.tolist()).to_quaternion()@(world_rot@upper.bone.matrix_local.to_quaternion()))
                inv=arm.matrix_world.inverted().to_3x3()
                aim_bone(upper,inv@(desired_knee-hip),lower.head-upper.head)
                aim_bone(lower,inv@(target-desired_knee),end.head-lower.head)
                orient_world(arm,end,desired_q)
                for i,b in enumerate(bones):
                    b.location=source['locations'][i];b.scale=source['scales'][i]
                    q=b.rotation_quaternion.copy()
                    if b.name in previous and q.dot(previous[b.name])<0:q.negate()
                    b.rotation_quaternion=q;previous[b.name]=q.copy();b.keyframe_insert('rotation_quaternion',frame=f)
                bpy.context.view_layer.update()
            else:
                for b in bones:previous[b.name]=b.rotation_quaternion.copy()
            error=(arm.matrix_world@bones[2].head-target).length
            orientation_error=qangle((arm.matrix_world@bones[2].matrix).to_quaternion()@desired_q.inverted())
            changes=[qangle((arm.matrix_world@b.matrix).to_quaternion()@q.inverted()) for b,q in zip(bones,source['rotations'])]
            maximum_endpoint=max(maximum_endpoint,error);maximum_rotation=max(maximum_rotation,*changes)
            if error>tolerance or orientation_error>.05 or max(changes)>cfg['maximum_leg_rotation_degrees']:raise ValueError('Stance endpoint/orientation/rotation bound failed: '+str([f,s,error,orientation_error,changes]))
            row['legs'][s]={'endpoint_error_m':error,'orientation_error_degrees':orientation_error,'leg_world_rotation_changes_degrees':changes}
        maximum_protected=max(maximum_protected,float(np.max(np.abs(bone_worlds(arm,protected)-state['protected']))));rows.append(row)
    if maximum_protected>1e-5 or geometry_identity(scene,arm)!=identity or sha(a.blend)!=cfg['source_sha256']:raise ValueError('Stance adaptation changed protected original motion/skin/input')
    for c in ad.action.fcurves:
        if any(c.data_path==arm.pose.bones[n].path_from_id('rotation_quaternion') for n in changed):
            for key in c.keyframe_points:key.interpolation='LINEAR'
    scene.frame_set(first);a.output.parent.mkdir(parents=True,exist_ok=True);bpy.ops.wm.save_as_mainfile(filepath=str(a.output.resolve()),check_existing=False)
    bpy.ops.wm.open_mainfile(filepath=str(a.output.resolve()),load_ui=False,use_scripts=False);scene=bpy.context.scene;arm,_=character_rig(scene);saved_endpoint=0.;saved_protected=0.
    for f,state in states.items():
        scene.frame_set(f);bpy.context.view_layer.update();saved_protected=max(saved_protected,float(np.max(np.abs(bone_worlds(arm,protected)-state['protected']))))
        for s,item in cfg['limbs'].items():
            endpoint=arm.matrix_world@arm.pose.bones[item['bones'][2]].head;saved_endpoint=max(saved_endpoint,(endpoint-expected_targets[f][s][0]).length)
    if saved_endpoint>tolerance or saved_protected>1e-5 or sha(a.blend)!=cfg['source_sha256']:raise ValueError('Saved/reopened stance evidence differs')
    result={'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'stationary-join-ankles-matched-reopened-await-visuals','plan_sha256':sha(a.plan),'writer_sha256':sha(Path(__file__)),'input_sha256':cfg['source_sha256'],'output_sha256':sha(a.output),'frames':cfg['frames'],'fps':cfg['fps'],'geometry_identity':identity,'incoming_ankle_shifts_m':{s:list(v) for s,v in deltas.items()},'incoming_ankle_alignment_degrees':{s:qangle(v) for s,v in turns.items()},'maximum_changed_leg_world_rotation_degrees':maximum_rotation,'maximum_endpoint_error_m':maximum_endpoint,'maximum_protected_bone_error':maximum_protected,'reopened_endpoint_error_m':saved_endpoint,'reopened_protected_bone_error':saved_protected,'allowed_leg_dependencies':sorted(allowed),'rows':rows,'normal_speed_continuous_viewing':False,'scope':'Explicit stationary asset adaptation. Constant incoming ankle offsets/orientation calibration blend through a declared join, preserving later recorded ankle changes and protected upper body/root/fingers. Calibrated knee kinematics alter source leg rotations. No XY friction, automatic locomotion/step synthesis, physics, collision, subframe or naturalness acceptance.'}
    a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8');print(json.dumps({k:v for k,v in result.items() if k not in ['rows','allowed_leg_dependencies']},ensure_ascii=True))

if __name__=='__main__':main()
