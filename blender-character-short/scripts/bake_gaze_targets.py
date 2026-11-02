"""Bake an existing gaze control against real objects in a new scene.

Only the configured control quaternion curves may change. Every other curve
stays byte-equivalent as serialized RNA values; existing limits still apply.
"""
import argparse,bpy,hashlib,json,math,pathlib,sys
from mathutils import Vector
p=argparse.ArgumentParser();p.add_argument('--blend',required=True,type=pathlib.Path);p.add_argument('--character',required=True,type=pathlib.Path);p.add_argument('--plan',required=True,type=pathlib.Path);p.add_argument('--output',required=True,type=pathlib.Path);p.add_argument('--report',required=True,type=pathlib.Path);
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);a.blend=a.blend.resolve();a.output=a.output.resolve();a.report=a.report.resolve()
inputs={a.blend,a.character.resolve(),a.plan.resolve(),pathlib.Path(__file__).resolve()}
if a.output.exists() or a.report.exists() or a.output in inputs or a.report in inputs or a.report==a.output:raise ValueError('Require new output scene and report, separate from all inputs')
if a.output.suffix.lower()!='.blend' or a.report.suffix.lower()!='.json':raise ValueError('Output must be.blend with a separate.json report')
cfg=json.loads(a.character.read_text('utf-8'));plan=json.loads(a.plan.read_text('utf-8'))
head_limit=float(cfg['head_angle_limit']);eye_limit=float(cfg['gaze']['max_angle'])
if not math.isfinite(head_limit) or not 0<head_limit<=90:raise ValueError('Explicit finite head_angle_limit in(0,90] is required')
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent));from gaze_control import aim_existing_control
from gaze_plan import parse_plan,return_weight
source_hash=hashlib.sha256(a.blend.read_bytes()).hexdigest()
bpy.ops.wm.open_mainfile(filepath=str(a.blend))
s=bpy.context.scene;arms=[o for o in s.objects if o.type=='ARMATURE']
if len(arms)!=1:raise ValueError('This route requires one armature')
arm=arms[0];control=arm.pose.bones[cfg['gaze']['control']];action=arm.animation_data.action
if control.rotation_mode!='QUATERNION':raise ValueError('Existing control must use quaternion rotation')
path=control.path_from_id('rotation_quaternion')
targets,returns=parse_plan(plan,s.frame_start,s.frame_end,set(s.objects.keys()))
def curve_state(fc):
    return {'path':fc.data_path,'index':fc.array_index,'extrapolation':fc.extrapolation,'points':[(list(k.co),list(k.handle_left),list(k.handle_right),k.interpolation,k.handle_left_type,k.handle_right_type) for k in fc.keyframe_points]}
def other_curves():return [curve_state(fc) for fc in action.fcurves if fc.data_path!=path]
before=other_curves();quaternions={};records=[]
# Sample the unmodified action first. Assigning a property must not influence
# later frames' original values or evaluated moving object positions.
samples={}
for f in range(s.frame_start,s.frame_end+1):
    s.frame_set(f);bpy.context.view_layer.update()
    samples[f]={'quaternion':control.rotation_quaternion.copy()}
    if f in targets:samples[f]['target']=s.objects[targets[f]].matrix_world.translation.copy()
for f,sample in samples.items():
    s.frame_set(f);bpy.context.view_layer.update()
    if f in targets:
        rec=aim_existing_control(arm,cfg['gaze'],arm.matrix_world.inverted()@sample['target'])
        records.append(dict(frame=f,object=targets[f],**rec));q=control.rotation_quaternion.copy()
    else:q=sample['quaternion'].copy()
    if not all(math.isfinite(v) for v in q):raise ValueError('Nonfinite control solution')
    if quaternions and q.dot(quaternions[f-1])<0:q.negate()
    quaternions[f]=q
return_records=[]
for row in returns:
    source=quaternions[row['source_frame']].normalized()
    for f in range(row['start'],row['end']+1):
        original=samples[f]['quaternion'].copy()
        if sum(v*v for v in original)<1e-16:raise ValueError('Cannot return to a zero authored control quaternion')
        original.normalize();weight=return_weight(f,row)
        if source.dot(original)<0:original.negate()
        q=source.slerp(original,weight).normalized()
        if not all(math.isfinite(v) for v in q):raise ValueError('Nonfinite gaze return solution')
        quaternions[f]=q
        return_records.append({'frame':f,'source_frame':row['source_frame'],'weight':weight,'control_quaternion':list(q)})
if returns:
    previous=None
    for f,q in quaternions.items():
        if previous is not None and q.dot(previous)<0:q.negate()
        previous=q
max_shortfall=max(r['requested_degrees']-r['applied_degrees'] for r in records)
report={'schema':1,'character_sha256':hashlib.sha256(a.character.read_bytes()).hexdigest(),'plan_sha256':hashlib.sha256(a.plan.read_bytes()).hexdigest(),'writer_sha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),'status':'planned-control-solution-only','input_scene_sha256':source_hash,'frames':len(samples),'target_frames':len(records),
        'scope':'Existing control only; real evaluated object centers; integer frames. Does not certify iris appearance, continuous viewing, subframes or general retargeting.',
        'maximum_requested_eye_control_degrees':max(r['requested_degrees'] for r in records),'maximum_control_shortfall_degrees':max_shortfall,
        'unchanged_limit_degrees':cfg['gaze']['max_angle'],'records':records}
report.update(plan_validator_sha256=hashlib.sha256(pathlib.Path(__file__).with_name('gaze_plan.py').read_bytes()).hexdigest(),return_frames=len(return_records),return_plan=returns,return_records=return_records,return_scope='Optional control return to original authored per-frame rotations. No object-fixation requirement or tracking claim during return frames.')
a.report.parent.mkdir(parents=True,exist_ok=True)
if max_shortfall>.01:
    report['status']='failed-before-save-original-limit';a.report.write_text(json.dumps(report,indent=2,allow_nan=False),'utf-8');print('REFINE_GAZE_REJECTED',max_shortfall,flush=True);raise SystemExit(1)
for fc in list(action.fcurves):
    if fc.data_path==path:action.fcurves.remove(fc)
control.rotation_mode='QUATERNION'
for f,q in quaternions.items():
    control.rotation_quaternion=q;control.keyframe_insert('rotation_quaternion',frame=f)
for fc in action.fcurves:
    if fc.data_path==path:
        for key in fc.keyframe_points:key.interpolation='LINEAR'
assert before==other_curves(),'Unexpected non-control animation mutation'
assert hashlib.sha256(a.blend.read_bytes()).hexdigest()==source_hash
# Check the final graph after all new curves, rather than accepting the
# control's requested angle as proof that the original eye constraints worked.
head=arm.pose.bones[cfg['bones']['head']];eyes=[arm.pose.bones[cfg['gaze'][side]] for side in ['left','right']]
forward=Vector(cfg['gaze']['forward']);geometry=[]
def degrees(q):return math.degrees(2*math.acos(min(1.,abs(q.normalized().w))))
for f,name in targets.items():
    s.frame_set(f);bpy.context.view_layer.update();target=s.objects[name].matrix_world.translation
    axes=[(arm.matrix_world.to_3x3()@eye.matrix.to_3x3()@eye.bone.matrix_local.to_3x3().inverted()@forward).normalized() for eye in eyes]
    origin=arm.matrix_world@((eyes[0].head+eyes[1].head)*.5)
    error=math.degrees((axes[0]+axes[1]).normalized().angle((target-origin).normalized()))
    geometry.append({'frame':f,'object':name,'mid_axis_error_degrees':error,'control_degrees':degrees(control.matrix_basis.to_quaternion()),'head_deformation_degrees':degrees((head.matrix.to_3x3()@head.bone.matrix_local.to_3x3().inverted()).to_quaternion())})
report['final_geometry']={'scope':'Integer-frame inferred bone axes, not iris rays or visual occlusion','maximum_mid_axis_error_degrees':max(r['mid_axis_error_degrees'] for r in geometry),'maximum_control_degrees':max(r['control_degrees'] for r in geometry),'maximum_head_deformation_degrees':max(r['head_deformation_degrees'] for r in geometry),'mid_axis_error_limit_degrees':5,'records':geometry}
valid=all(math.isfinite(v) for r in geometry for v in [r['mid_axis_error_degrees'],r['control_degrees'],r['head_deformation_degrees']])
valid=valid and all(r['mid_axis_error_degrees']<=5 and r['control_degrees']<=eye_limit+.001 and r['head_deformation_degrees']<=head_limit+.001 for r in geometry)
return_geometry=[]
for row in return_records:
    f=row['frame'];s.frame_set(f);bpy.context.view_layer.update()
    return_geometry.append({'frame':f,'control_degrees':degrees(control.matrix_basis.to_quaternion()),'head_deformation_degrees':degrees((head.matrix.to_3x3()@head.bone.matrix_local.to_3x3().inverted()).to_quaternion())})
report['final_return_geometry']={'scope':'Original head/control bounds during optional return only; not fixation or iris visibility. Whole-film checks remain separate.','records':return_geometry}
valid=valid and all(math.isfinite(r['control_degrees']) and math.isfinite(r['head_deformation_degrees']) and r['control_degrees']<=eye_limit+.001 and r['head_deformation_degrees']<=head_limit+.001 for r in return_geometry)
if not valid:
    report['status']='failed-final-evaluated-before-save';a.report.write_text(json.dumps(report,indent=2,allow_nan=False),'utf-8');print('REFINE_GAZE_FINAL_GRAPH_REJECTED',flush=True);raise SystemExit(1)
a.output.parent.mkdir(parents=True,exist_ok=True);s.frame_set(s.frame_start);bpy.ops.wm.save_as_mainfile(filepath=str(a.output))
report.update(status='new-scene-saved-control-only-await-final-audit',other_animation_curves_unchanged=True,input_bytes_unchanged=True,output_scene_sha256=hashlib.sha256(a.output.read_bytes()).hexdigest())
a.report.write_text(json.dumps(report,indent=2,allow_nan=False),'utf-8');print('REFINE_GAZE_SAVED',len(records),'target frames',flush=True)
