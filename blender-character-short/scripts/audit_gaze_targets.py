"""Evaluate final eye-bone axes against required static feedback objects."""
import argparse,bpy,json,math,pathlib,sys
from mathutils import Vector
p=argparse.ArgumentParser();p.add_argument('--blend',required=True);p.add_argument('--character',required=True);p.add_argument('--story',required=True);p.add_argument('--output',required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
cfg=json.loads(pathlib.Path(a.character).read_text('utf-8'));story=json.loads(pathlib.Path(a.story).read_text('utf-8'))
def finite(value,label,positive=False):
 if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or (positive and value<=0):raise ValueError(label+' must be a finite '+('positive ' if positive else '')+'number')
 return float(value)
height=finite(cfg['height'],'Character height',True);finite(cfg['ground'],'Ground')
eye_limit=finite(cfg['gaze']['max_angle'],'Eye limit',True)
head_limit=finite(cfg['head_angle_limit'],'Head limit',True)
if eye_limit>45 or head_limit>180:raise ValueError('Control limits outside supported ranges')
finite(story['duration'],'Story duration',True)
for pose in story['poses']:
 if 'gaze_required' in pose and not isinstance(pose['gaze_required'],bool):raise ValueError('gaze_required must be boolean')
 finite(pose['t'],'Pose time')
poses=[v for v in story['poses'] if v.get('gaze_required')]
destination=pathlib.Path(a.output).resolve()
if destination in {pathlib.Path(v).resolve() for v in [a.blend,a.character,a.story]}:raise ValueError('Report must not overwrite an input')
if destination.suffix.lower()!='.json':raise ValueError('Use a separate JSON report path')
if not poses:raise ValueError('No explicitly required gaze keys supplied')
objects={o['name']:o for o in story['set']['objects']}
for pose in poses:
 if pose['gaze_target_object'] not in objects or pose['eye_look']!=objects[pose['gaze_target_object']]['position']:
  raise ValueError('Required gaze target must match its real authored feedback object center')
bpy.ops.wm.open_mainfile(filepath=str(pathlib.Path(a.blend).resolve()))
s=bpy.context.scene;arms=[o for o in s.objects if o.type=='ARMATURE']
if len(arms)!=1:raise ValueError('Expected one character armature')
arm=arms[0];head=arm.pose.bones[cfg['bones']['head']];control=arm.pose.bones[cfg['gaze']['control']]
eyes=[arm.pose.bones[cfg['gaze'][side]] for side in ['left','right']]
forward=Vector(cfg['gaze']['forward']);fps=s.render.fps/s.render.fps_base
scale=(s.frame_end-s.frame_start+1)/(fps*story['duration'])
frame=lambda t:max(s.frame_start,min(s.frame_end,round(t*scale*fps)+1))
keys=sorted([(frame(v['t']),v['gaze_target_object']) for v in poses])
if len({k for k,n in keys})!=len(keys):raise ValueError('Required keys overlap on an integer frame')
def angle(q):
 q=q.normalized();return math.degrees(2*math.acos(min(1.,abs(q.w))))
records=[];key_records=[]
for current in range(keys[0][0],keys[-1][0]+1):
 s.frame_set(current);bpy.context.view_layer.update()
 left=max(i for i,(f,n) in enumerate(keys) if f<=current);right=min(left+1,len(keys)-1)
 f0,n0=keys[left];f1,n1=keys[right]
 alpha=(current-f0)/(f1-f0) if f1>f0 else 0
 target=s.objects[n0].matrix_world.translation.lerp(s.objects[n1].matrix_world.translation,alpha)
 axes=[];errors=[]
 for eye in eyes:
  origin=arm.matrix_world@eye.head
  axis=(arm.matrix_world.to_3x3()@eye.matrix.to_3x3()@eye.bone.matrix_local.to_3x3().inverted()@forward).normalized()
  axes.append(axis);errors.append(math.degrees(axis.angle((target-origin).normalized())))
 midpoint=arm.matrix_world@((eyes[0].head+eyes[1].head)*.5)
 middle=(axes[0]+axes[1]).normalized();error=math.degrees(middle.angle((target-midpoint).normalized()))
 head_angle=angle((head.matrix.to_3x3()@head.bone.matrix_local.to_3x3().inverted()).to_quaternion())
 control_angle=angle(control.matrix_basis.to_quaternion())
 row={'frame':current,'target_bracket':[n0,n1],'mid_axis_error_degrees':error,
      'individual_eye_axis_error_degrees':errors,'head_deformation_angle_degrees':head_angle,'control_basis_angle_degrees':control_angle}
 records.append(row)
 if current in {f for f,n in keys}:
  name=next(n for f,n in keys if f==current);obj=s.objects[name]
  actual=obj.matrix_world.translation
  authored=Vector(objects[name]['position'])*cfg['height']+Vector((0,0,cfg['ground']))
  if (actual-authored).length>cfg['height']*1e-6:raise ValueError('Actual feedback object moved away from its authored gaze target')
  shader=obj.data.materials[0].node_tree.nodes['Principled BSDF']
  key_records.append(dict(row,object=name,actual_center=list(actual),actual_emission=shader.inputs['Emission Strength'].default_value))
report={'scope':'Project-specific final evaluated original eye-bone inferred forward axes and actual feedback object centers, all integer reaction frames after saved layers. No actual iris-ray, visual occlusion, normal-speed viewing or timing acceptance.',
 'frames':len(records),'required_key_count':len(keys),'fixed_limits':{'mid_axis_error_degrees':5.,'eye_control_degrees':cfg['gaze']['max_angle'],'head_deformation_degrees':cfg['head_angle_limit']},
 'maximum_mid_axis_error_degrees':max(v['mid_axis_error_degrees'] for v in records),
 'maximum_head_deformation_degrees':max(v['head_deformation_angle_degrees'] for v in records),
 'maximum_control_basis_degrees':max(v['control_basis_angle_degrees'] for v in records),
 'key_records':key_records,'records':records}
report['within_declared_geometry_limits']=(report['maximum_mid_axis_error_degrees']<=5. and report['maximum_head_deformation_degrees']<=cfg['head_angle_limit']+.001 and report['maximum_control_basis_degrees']<=cfg['gaze']['max_angle']+.001)
out=pathlib.Path(a.output).resolve();out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,indent=2,allow_nan=False),'utf-8')
print('VISIBLE_FEEDBACK_GEOMETRY',report['within_declared_geometry_limits'],report['maximum_mid_axis_error_degrees'],report['maximum_head_deformation_degrees'],report['maximum_control_basis_degrees'],flush=True)
if not report['within_declared_geometry_limits']:raise SystemExit(1)
