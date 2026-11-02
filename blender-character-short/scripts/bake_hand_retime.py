"""Retime an existing post-contact arm path into a separately saved candidate."""
import argparse,datetime,hashlib,json,math,pathlib,sys
import bpy
from mathutils import Matrix
p=argparse.ArgumentParser();p.add_argument('--blend',required=True,type=pathlib.Path);p.add_argument('--character',required=True,type=pathlib.Path);p.add_argument('--build-report',required=True,type=pathlib.Path);p.add_argument('--plan',required=True,type=pathlib.Path);p.add_argument('--output',required=True,type=pathlib.Path);p.add_argument('--report',required=True,type=pathlib.Path);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);assert not a.output.exists() and not a.report.exists(),'Preserve existing outputs; choose a new version';sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent));from build_performance import two_bone;from hand_retime_plan import validate_plan,source_time
outputs={a.output.resolve(),a.report.resolve()};inputs={v.resolve() for v in [a.blend,a.character,a.build_report,a.plan]};assert len(outputs)==2 and not outputs.intersection(inputs),'Outputs must be distinct from one another and all inputs';sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest();source_hash=sha(a.blend);cfg=json.loads(a.character.read_text('utf-8'));plan=json.loads(a.plan.read_text('utf-8'));build=json.loads(a.build_report.read_text('utf-8'));side=plan.get('side');bpy.ops.wm.open_mainfile(filepath=str(a.blend.resolve()));s=bpy.context.scene;arms=[o for o in s.objects if o.type=='ARMATURE'];assert len(arms)==1;arm=arms[0];assert all(abs(v-1)<1e-5 for v in arm.matrix_world.to_scale()),'Unit world-scale rig required';assert build['frames']==s.frame_end and build['fps']==s.render.fps
contact_frames=[r['frame'] for r in build.get('prop_contact',{}).get('frames',[]) if r.get('weight',0)>1e-8];contact_end=max(contact_frames,default=s.frame_start-1);(source_first,source_last),(begin,end)=validate_plan(plan,s.frame_start,s.frame_end,contact_end);keys=[side+'_arm',side+'_elbow',side+'_wrist'];bones={key:arm.pose.bones[cfg['bones'][key]] for key in keys}
for pb in bones.values():
    assert pb.rotation_mode=='QUATERNION';assert not any(not c.mute and c.influence>1e-8 for c in pb.constraints),'Active target-bone constraints need a separately verified route'
def local_snapshot():return {key:{'q':pb.rotation_quaternion.copy(),'location':pb.location.copy(),'scale':pb.scale.copy()} for key,pb in bones.items()}
base={}
for frame in range(s.frame_start,s.frame_end+1):
    s.frame_set(frame);bpy.context.view_layer.update();base[frame]=local_snapshot();assert all(abs(v-1)<1e-5 for pb in bones.values() for v in pb.scale),'Unit target-bone scales required'
desired={}
for frame in range(begin,end+1):
    source_frame=source_time(frame,(source_first,source_last),(begin,end),plan['timing']);integer=math.floor(source_frame);s.frame_set(integer,subframe=source_frame-integer);bpy.context.view_layer.update();desired[frame]={'source_frame':source_frame,'wrist_world':(arm.matrix_world@bones[side+'_wrist'].matrix).copy(),'elbow_world':arm.matrix_world@bones[side+'_elbow'].head}
output={};errors=[]
for frame in range(s.frame_start,s.frame_end+1):
    s.frame_set(frame);bpy.context.view_layer.update()
    for key,pb in bones.items():pb.rotation_quaternion=base[frame][key]['q'];pb.location=base[frame][key]['location'];pb.scale=base[frame][key]['scale']
    bpy.context.view_layer.update()
    if frame in desired:
        sample=desired[frame];inv=arm.matrix_world.inverted();goal=inv@sample['wrist_world'].translation;pole=inv@sample['elbow_world'];reach=two_bone(bones[side+'_arm'],bones[side+'_elbow'],bones[side+'_wrist'],goal,pole,cfg.get('reach_fraction',.96));assert not reach['clamped'],'Retimed source path unreachable from current shoulder'
        for key,pb in bones.items():pb.location=base[frame][key]['location'];pb.scale=base[frame][key]['scale']
        bpy.context.view_layer.update();wrist=bones[side+'_wrist'];q=arm.matrix_world.to_quaternion().inverted()@sample['wrist_world'].to_quaternion();matrix=Matrix.Translation(wrist.head)@q.to_matrix().to_4x4();basis=wrist.bone.convert_local_to_pose(matrix,wrist.bone.matrix_local,parent_matrix=wrist.parent.matrix,parent_matrix_local=wrist.parent.bone.matrix_local,invert=True);wrist.rotation_quaternion=basis.to_quaternion().normalized();wrist.location=base[frame][side+'_wrist']['location'];wrist.scale=base[frame][side+'_wrist']['scale'];bpy.context.view_layer.update();error=((arm.matrix_world@wrist.head)-sample['wrist_world'].translation).length/cfg['height'];assert error<1e-5,('Wrist path error',frame,error);errors.append(error)
    output[frame]=local_snapshot()
action=arm.animation_data.action;paths={pb.path_from_id(field) for pb in bones.values() for field in ['rotation_quaternion','location','scale']}
for curve in list(action.fcurves):
    if curve.data_path in paths:action.fcurves.remove(curve)
previous={}
for frame,values in output.items():
    for key,pb in bones.items():
        q=values[key]['q'].normalized()
        if key in previous and q.dot(previous[key])<0:q.negate()
        previous[key]=q.copy();pb.rotation_quaternion=q;pb.location=values[key]['location'];pb.scale=values[key]['scale']
        for field in ['rotation_quaternion','location','scale']:assert pb.keyframe_insert(field,frame=frame)
for curve in action.fcurves:
    if curve.data_path in paths:
        for point in curve.keyframe_points:point.interpolation='LINEAR'
assert sha(a.blend)==source_hash;a.output.parent.mkdir(parents=True,exist_ok=True);a.report.parent.mkdir(parents=True,exist_ok=True);s['hand_retime_plan']=json.dumps(plan,sort_keys=True);s.frame_set(1);bpy.context.view_layer.update();scene=a.output;bpy.ops.wm.save_as_mainfile(filepath=str(scene.resolve()));assert sha(a.blend)==source_hash
report={'schema':1,'status':'new-scene-saved-retimed-arm-await-protection-and-visual-audits','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'input_scene_sha256':source_hash,'output_scene_sha256':sha(scene),'character_sha256':sha(a.character),'plan_sha256':sha(a.plan),'writer_sha256':sha(pathlib.Path(__file__)),'base_solver_sha256':sha(pathlib.Path(__file__).with_name('build_performance.py')),'plan_validator_sha256':sha(pathlib.Path(__file__).with_name('hand_retime_plan.py')),'build_report_sha256':sha(a.build_report),'plan':plan,'last_active_contact_transition_frame':contact_end,'maximum_wrist_source_path_error_H':max(errors),'sampled_source_times':{str(f):v['source_frame'] for f,v in desired.items()},'scope':'Only configured original arm/elbow/wrist local channels rewritten at integerframes. Original props/cameras/otherchannels untouched in writer; final evaluated preservation and clearance need separateaudit. Full source curves sampled before any writes; normalized hemisphere-continuous quaternions. No subframe, volume, naturalness or full-library claim.'};a.report.write_text(json.dumps(report,indent=2),'utf-8');print('HAND_RETIME_SCENE_SAVED',max(errors),contact_end,flush=True)
