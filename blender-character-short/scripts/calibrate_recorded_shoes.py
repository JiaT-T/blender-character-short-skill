"""Experimental recorded shoe-height adaptation using existing original IK/FK.

Requires a reviewed external geometric heel/toe trajectory and original-rig
mapping. No physical contact inference, new controller, MMR generation, plugin
modification, subframe or naturalness acceptance. Original files stay unchanged.
"""
from pathlib import Path
import argparse,datetime,hashlib,json,math,sys
import bpy,numpy as np
from mathutils import Matrix,Quaternion,Vector
sys.dont_write_bytecode=True;sys.path.insert(0,str(Path(__file__).resolve().parent))
from body_motion_runtime import character_rig,geometry_identity,bone_worlds,select_feet,foot_points as original_foot_points,orient_world
from bake_elbow_poles import dependency_bones
from recorded_shoe_plan import load

def foot_points(selection,side):
    points=list(original_foot_points(selection,side))
    if not points or not np.isfinite(np.asarray([p for _,_,p in points],dtype=np.float64)).all():raise ValueError('Finite evaluated weighted shoe vertices required')
    return points

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['blend','plan','output','report']:p.add_argument('--'+key,required=True,type=Path)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);source=a.blend.resolve();output=a.output.resolve();report=a.report.resolve();failure_path=report.with_name(report.stem+'-failed.json')
    if not bpy.app.background or source.suffix.lower()!='.blend' or source.stat().st_size>512*1024*1024 or output.suffix.lower()!='.blend' or report.suffix.lower()!='.json' or len({source,a.plan.resolve(),output,report,failure_path})!=5 or any(x.exists() for x in [output,report,failure_path]):raise ValueError('Isolated bounded original scene and distinct new outputs required')
    if any(str(x).startswith(chr(92)*2) or str(x).startswith('//') for x in [source,a.plan.resolve(),output,report]):raise ValueError('Reviewed local paths required')
    cfg=load(a.plan);sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    if sha(source)!=cfg['blend_sha256']:raise ValueError('Reviewed original scene identity differs')
    output.parent.mkdir(parents=True,exist_ok=True);report.parent.mkdir(parents=True,exist_ok=True)
    debug={'stage':'starting'}
    try:
        bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False);scene=bpy.context.scene;arm,_=character_rig(scene);root=arm.pose.bones[cfg['root_bone']];h=cfg['height'];first,last=cfg['frames']
        if (last-first+1)*len(arm.pose.bones)>500000 or scene.render.fps/scene.render.fps_base!=cfg['fps']:raise ValueError('Original motion frame-rate/bone-frame budget differs')
        world_rotation=np.asarray(arm.matrix_world.to_3x3())
        if not np.allclose(world_rotation@world_rotation.T,np.eye(3),atol=1e-6) or abs(np.linalg.det(world_rotation)-1)>1e-6:raise ValueError('Unit-scale proper original armature transform required')
        if scene.rigidbody_world or [scene.frame_start,scene.frame_end]!=[first,last] or last-first+1>240:raise ValueError('Bounded pre-physics source interval required')
        identity=geometry_identity(scene,arm);names=list(arm.pose.bones.keys());lookup={n:i for i,n in enumerate(names)};selection=select_feet(scene,arm,cfg)
        legs={s:[arm.pose.bones[n] for n in cfg['legs'][s]] for s in ['left','right']};changed={b.name for chain in legs.values() for b in chain};allowed=dependency_bones(arm,changed);protected=[n for n in names if n not in allowed]
        root_dependencies=dependency_bones(arm,[root.name]);controls={};settings=[]
        for entry in cfg['existing_IK']:
            c=arm.pose.bones[entry['bone']].constraints.get(entry['constraint'])
            if c is None or c.type!='IK' or c.target!=arm or c.subtarget!=entry['target_bone'] or c.chain_count!=entry['chain_count'] or not c.mute:raise ValueError('Reviewed existing original IK differs')
            settings.append((c,c.mute,c.use_stretch));controls[c.subtarget]=arm.pose.bones[c.subtarget]
        if len(settings)!=4 or len(controls)!=4:raise ValueError('Exactly four existing original leg/toe IK constraints required')
        foot_goals={e['side']:controls[e['target_bone']] for e in cfg['existing_IK'] if e['chain_count']==2}
        goal_rest={s:(arm.matrix_world@b.bone.matrix_local).to_quaternion() for s,b in foot_goals.items()};ankle_rest={s:(arm.matrix_world@chain[2].bone.matrix_local).to_quaternion() for s,chain in legs.items()}
        scene.frame_set(first);bpy.context.view_layer.update();bias=dict(cfg['ankle_pitch_bias_degrees']);toe_pitch={}
        for side in ['left','right']:
            ankle=arm.matrix_world@legs[side][2].head;forward=arm.matrix_world@legs[side][3].head-ankle;forward.z=0
            if forward.length<1e-6:raise ValueError('No original horizontal toe direction')
            forward.normalize();points=[p for _,_,p in foot_points(selection,side)];scores=[(p-ankle).dot(forward) for p in points];cutoff=float(np.quantile(scores,.95));front=[p for p,score in zip(points,scores) if score>=cutoff];toe=min(front,key=lambda p:p.z);v=toe-ankle
            toe_pitch[side]=math.degrees(math.atan2(-v.z,math.hypot(v.x,v.y)))
            if bias[side] is None:bias[side]=cfg['desired_initial_toe_direction_pitch_degrees'][side]-toe_pitch[side]
            if not math.isfinite(bias[side]) or abs(bias[side])>cfg['maximum_ankle_pitch_bias_degrees']:raise ValueError('Mesh-measured ankle bias exceeds original trial limit: '+str([side,bias[side],toe_pitch[side]]))
        debug.update(stage='source-capture',ankle_bias=bias,target_toe_pitch=toe_pitch)
        states={};needed_lower=0.;arm_inv=arm.matrix_world.inverted()
        for row in cfg['rows']:
            f=row['frame'];scene.frame_set(f);bpy.context.view_layer.update();state={'worlds':bone_worlds(arm,names),'root_world':(arm.matrix_world@root.matrix).copy(),'control_basis':{n:b.matrix_basis.copy() for n,b in controls.items()},'feet':{}}
            for side,chain in legs.items():
                hip,knee,ankle,toe=chain;hip_point=arm.matrix_world@hip.head;knee_point=arm.matrix_world@knee.head;ankle_point=arm.matrix_world@ankle.head;lengths=[(knee_point-hip_point).length,(ankle_point-knee_point).length]
                rotation=(arm.matrix_world@ankle.matrix).to_quaternion()@Quaternion(Vector(cfg['ankle_pitch_axis_local']),math.radians(bias[side]));orient_world(arm,ankle,rotation)
                low=min(p.z for _,_,p in foot_points(selection,side));desired_z=row['feet'][side]['target_lowest_sole_z_m'];xy=hip_point+Vector(((ankle_point.x-hip_point.x)*cfg['stride_scale'],(ankle_point.y-hip_point.y)*cfg['stride_scale'],0))
                predicted_ankle_z=desired_z+(ankle_point.z-low);horizontal=(xy.x-hip_point.x)**2+(xy.y-hip_point.y)**2;reach=sum(lengths)*cfg['reach_fraction']
                if horizontal>=reach*reach:raise ValueError('Source horizontal stride exceeds original leg reach')
                needed_lower=max(needed_lower,hip_point.z-predicted_ankle_z-math.sqrt(reach*reach-horizontal))
                state['feet'][side]={'xy':(xy.x,xy.y),'initial_z':predicted_ankle_z,'sole_z':desired_z,'rotation':rotation,'lengths':lengths}
            states[f]=state
        lowering=max(0.,needed_lower)+(cfg['reach_margin_H']*h if needed_lower>0 else 0.)
        if lowering>cfg['maximum_root_lowering_H']*h:raise ValueError('Required constant body-height adaptation exceeds trial bound: '+str(lowering))
        debug.update(stage='existing-IK-solve',constant_root_lowering_m=lowering)
        def lower_root(state):
            world=state['root_world'].copy();world.translation.z-=lowering;desired=arm_inv@world
            basis=root.bone.convert_local_to_pose(desired,root.bone.matrix_local,parent_matrix=root.parent.matrix if root.parent else Matrix.Identity(4),parent_matrix_local=root.parent.bone.matrix_local if root.parent else Matrix.Identity(4),invert=True)
            root.location=basis.to_translation();bpy.context.view_layer.update()
        def set_world(b,matrix):
            b.matrix_basis=b.bone.convert_local_to_pose(arm_inv@matrix,b.bone.matrix_local,parent_matrix=b.parent.matrix if b.parent else Matrix.Identity(4),parent_matrix_local=b.parent.bone.matrix_local if b.parent else Matrix.Identity(4),invert=True);bpy.context.view_layer.update()
        solved={};height_tol=cfg['maximum_height_error_H']*h;xy_tol=cfg['maximum_horizontal_error_H']*h;rows=[]
        for c,_,_ in settings:c.mute=False;c.use_stretch=False
        for f,state in states.items():
            scene.frame_set(f)
            for n,b in controls.items():b.matrix_basis=state['control_basis'][n]
            lower_root(state);goal_positions={};goal_rotations={}
            for side,goal in foot_goals.items():
                foot=state['feet'][side];goal_positions[side]=Vector((*foot['xy'],foot['initial_z']));goal_rotations[side]=foot['rotation']@ankle_rest[side].inverted()@goal_rest[side]
                set_world(goal,Matrix.Translation(goal_positions[side])@goal_rotations[side].to_matrix().to_4x4())
            details={}
            for iteration in range(cfg['iterations_per_frame']):
                bpy.context.view_layer.update();all_ok=True
                for side,goal in foot_goals.items():
                    foot=state['feet'][side];ankle=arm.matrix_world@legs[side][2].head;low=min(p.z for _,_,p in foot_points(selection,side));error=Vector((foot['xy'][0]-ankle.x,foot['xy'][1]-ankle.y,foot['sole_z']-low))
                    details[side]={'height_error_m':abs(error.z),'horizontal_error_m':math.hypot(error.x,error.y),'actual_lowest_sole_z_m':low,'desired_lowest_sole_z_m':foot['sole_z']}
                    if abs(error.z)>height_tol or math.hypot(error.x,error.y)>xy_tol:
                        all_ok=False;goal_positions[side]+=error;set_world(goal,Matrix.Translation(goal_positions[side])@goal_rotations[side].to_matrix().to_4x4())
                if all_ok:break
            if not all_ok:raise ValueError('Original IK did not converge: '+str([f,details]))
            for side,chain in legs.items():
                points=[arm.matrix_world@b.head for b in chain[:3]];actual=[(points[1]-points[0]).length,(points[2]-points[1]).length]
                if max(abs(a-b) for a,b in zip(actual,state['feet'][side]['lengths']))>cfg['maximum_segment_length_error_H']*h:raise ValueError('Original IK changed anatomical segment length')
            solved[f]={n:(arm.matrix_world@arm.pose.bones[n].matrix).copy() for n in changed};rows.append({'frame':f,'iterations':iteration+1,'feet':details});print('FOOT_NATIVE_IK_SOLVED',f,flush=True)
        for c,mute,stretch in settings:c.mute=mute;c.use_stretch=stretch
        previous={};maximum_protected=0.;maximum_height=0.;maximum_fk_world=0.;maximum_fk_position=0.;maximum_fk_angle=0.;maximum_fk_scale=0.
        for f,state in states.items():
            scene.frame_set(f)
            for n,b in controls.items():b.matrix_basis=state['control_basis'][n]
            lower_root(state);root.keyframe_insert('location',frame=f)
            for side,chain in legs.items():
                for b in chain:
                    desired=solved[f][b.name].copy();u,s,v=np.linalg.svd(np.asarray(desired)[:3,:3]);rotation=u@v
                    if np.linalg.det(rotation)<0:raise ValueError('Reflected native IK result')
                    for ri in range(3):
                        for ci in range(3):desired[ri][ci]=float(rotation[ri,ci])
                    set_world(b,desired);q=b.rotation_quaternion.copy()
                    if b.name in previous and q.dot(previous[b.name])<0:q.negate()
                    b.rotation_quaternion=q;previous[b.name]=q.copy()
                    for prop in ['location','rotation_quaternion','scale']:b.keyframe_insert(prop,frame=f)
            expected=state['worlds'].copy()
            for i,n in enumerate(names):
                if n in root_dependencies:expected[i,2,3]-=lowering
            actual=bone_worlds(arm,names);indices=[lookup[n] for n in protected];maximum_protected=max(maximum_protected,float(np.max(np.abs(actual[indices]-expected[indices]))))
            for n in changed:
                observed=actual[lookup[n]];wanted=np.asarray(solved[f][n]);maximum_fk_world=max(maximum_fk_world,float(np.max(np.abs(observed-wanted))))
                maximum_fk_position=max(maximum_fk_position,float(np.linalg.norm(observed[:3,3]-wanted[:3,3])))
                rotations=[];scales=[]
                for matrix in [observed,wanted]:
                    u,s,v=np.linalg.svd(matrix[:3,:3]);r=u@v
                    if np.linalg.det(r)<0:raise ValueError('Reflected FK bone transform')
                    rotations.append(r);scales.append(s)
                cosine=float(np.clip((np.trace(rotations[0]@rotations[1].T)-1)/2,-1,1))
                maximum_fk_angle=max(maximum_fk_angle,math.degrees(math.acos(cosine)));maximum_fk_scale=max(maximum_fk_scale,float(np.max(np.abs(scales[0]-1.))))
            for side in ['left','right']:
                maximum_height=max(maximum_height,abs(min(p.z for _,_,p in foot_points(selection,side))-state['feet'][side]['sole_z']))
                points=[arm.matrix_world@b.head for b in legs[side][:3]];lengths=[(points[1]-points[0]).length,(points[2]-points[1]).length]
                if max(abs(a-b) for a,b in zip(lengths,state['feet'][side]['lengths']))>cfg['maximum_segment_length_error_H']*h:raise ValueError('Rigid FK changed anatomical segment length')
        if maximum_protected>1e-5 or maximum_fk_position>1e-5 or maximum_fk_angle>.01 or maximum_fk_scale>1e-5 or maximum_height>height_tol or geometry_identity(scene,arm)!=identity or sha(source)!=cfg['blend_sha256']:raise ValueError('Baked FK/body/skin/source preservation failed: '+str([maximum_protected,maximum_fk_world,maximum_fk_position,maximum_fk_angle,maximum_fk_scale,maximum_height]))
        for c in arm.animation_data.action.fcurves:
            for key in c.keyframe_points:key.interpolation='LINEAR'
        scene.frame_set(first);bpy.ops.wm.save_as_mainfile(filepath=str(output),check_existing=False)
        result={'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'source-proxy-feet-calibrated-original-FK-await-independent-reopen-and-visuals','source_sha256':cfg['blend_sha256'],'output_sha256':sha(output),'writer_sha256':sha(Path(__file__)),'plan_sha256':sha(a.plan),'validator_sha256':sha(Path(__file__).with_name('recorded_shoe_plan.py')),'runtime_sha256':sha(Path(__file__).with_name('body_motion_runtime.py')),'dependency_sha256':sha(Path(__file__).with_name('bake_elbow_poles.py')),'contact_runtime_sha256':sha(Path(__file__).with_name('contact_motion.py')),'integer_frame_technical_pass':True,'half_frame_inspection_performed':False,'ankle_bias_degrees':bias,'measured_target_initial_toe_pitch_degrees':toe_pitch,'constant_root_lowering_m':lowering,'geometry_identity':identity,'maximum_protected_bone_error':maximum_protected,'maximum_native_IK_to_FK_world_error':maximum_fk_world,'maximum_IK_to_FK_position_error_m':maximum_fk_position,'maximum_IK_to_FK_rotation_error_degrees':maximum_fk_angle,'maximum_IK_to_FK_scale_error':maximum_fk_scale,'IK_to_FK_unit_specific_limits':{'position_m':1e-5,'rotation_degrees':.01,'scale':1e-5},'maximum_proxy_sole_height_error_m':maximum_height,'original_IK_mute_stretch_restored':True,'FK_rotation_projection':'Native IK rotations projected to proper SO3 before FK write; original matrix-component residual retained, actual FK unit scale checked. Native no-stretch segment-length check remains.','rows':rows,'normal_speed_continuous_viewing':False,'scope':'Experimental source geometric heel/toe proxy and model-shoe calibration, existing original IK temporarily solved without stretch, original leg FK baked. Recorded upper motion retained with constant global height offset. Not MMR generation, true contact/force labels, collision or naturalness acceptance.'}
        result['declared_height_proxy']=cfg.get('height_proxy',{'kind':'legacy-explicit-height-proxy','source_endpoint_truth_verified':False})
        report.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8');print(json.dumps({k:v for k,v in result.items() if k!='rows'},ensure_ascii=True))
    except Exception as exc:
        for item in locals().get('settings',[]):
            try:item[0].mute=item[1];item[0].use_stretch=item[2]
            except ReferenceError:pass
        failure={'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'trial-rejected','reason':str(exc),'debug':debug,'output_exists':output.exists(),'source_unchanged':sha(source)==cfg['blend_sha256'],'normal_speed_continuous_viewing':False}
        failure_path.write_text(json.dumps(failure,ensure_ascii=False,indent=2),encoding='utf-8');raise

if __name__=='__main__':main()
