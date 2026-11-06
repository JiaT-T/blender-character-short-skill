"""Bake external additive finger axes on existing bones in a new clip scene."""
from pathlib import Path
import argparse,json,sys,datetime,math
sys.dont_write_bytecode=True;sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy,numpy as np
from hand_control_plan import profile,motion
from hand_control_runtime import *

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['blend','profile','motion','output','report']:p.add_argument('--'+key,required=True,type=Path)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);source=a.blend.resolve();output=a.output.resolve();report=a.report.resolve()
    if output.exists() or report.exists() or len({source,output,report,a.profile.resolve(),a.motion.resolve()})!=5 or output.suffix.lower()!='.blend' or report.suffix.lower()!='.json':raise ValueError('Preserve inputs and choose distinct new blend/JSON report paths')
    mapping=profile(json.loads(a.profile.read_text('utf-8')));plan=motion(json.loads(a.motion.read_text('utf-8')),mapping);before=sha(source);bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False);scene=bpy.context.scene;set_frame(scene,plan['frames'][0]);arm,meshes,selections,regions,binding=bind(scene,mapping);first,last=plan['frames'];times=list(range(first,last+1));check_work(arm,meshes,scene,times)
    if first<scene.frame_start or last>scene.frame_end or scene.render.fps!=plan['fps']:raise ValueError('Clip must use an existing source frame interval and unchanged fps')
    identity=geometry_signature(arm,meshes);joints=active_joints(mapping,plan);active=[j['bone'] for j in joints];allowed,protected,objects,attached=protection(arm,scene,active);channels={(c['joint'],c['axis']):c['keys'] for c in plan['channels']};states=[]
    for f in times:
        set_frame(scene,f);worlds(arm,active);states.append({'basis':{n:arm.pose.bones[n].matrix_basis.copy() for n in active},'protected':worlds(arm,protected),'objects':object_worlds(objects),'morphs':morphology(meshes)})
    arm.animation_data_create();old_action=arm.animation_data.action
    if old_action:
        old_slot=arm.animation_data.action_slot.identifier if arm.animation_data.action_slot else None;arm.animation_data.action=old_action.copy()
        if old_slot:
            slots=[s for s in arm.animation_data.action.slots if s.identifier==old_slot]
            if len(slots)!=1:raise ValueError('Cannot preserve the existing source action slot')
            arm.animation_data.action_slot=slots[0]
    previous={};paths=set();maximum_requested=0.
    for f,state in zip(times,states):
        set_frame(scene,f)
        for j in joints:
            pose=arm.pose.bones[j['bone']];pose.matrix_basis=state['basis'][pose.name];pose.rotation_mode='QUATERNION';delta=rotation_delta(j,channels,f);maximum_requested=max(maximum_requested,quat_degrees(delta));q=state['basis'][pose.name].to_quaternion()@delta
            if pose.name in previous and q.dot(previous[pose.name])<0:q.negate()
            pose.rotation_quaternion=q;previous[pose.name]=q.copy();pose.keyframe_insert('rotation_quaternion',frame=f);paths.add(pose.path_from_id('rotation_quaternion'))
        if (f-first)%24==0:print('HAND_BAKE_KEY',f,flush=True)
    linear_new_keys(arm,paths,first,last);errors={'protected_bone_world':0.,'protected_object_world':0.,'selected_local_translation':0.,'selected_local_scale':0.,'morph_values':0.,'requested_local_rotation_matrix':0.}
    for f,state in zip(times,states):
        set_frame(scene,f);worlds(arm,active);errors['protected_bone_world']=max(errors['protected_bone_world'],float(np.max(np.abs(worlds(arm,protected)-state['protected']))));errors['protected_object_world']=max(errors['protected_object_world'],float(np.max(np.abs(object_worlds(objects)-state['objects']))));current=morphology(meshes);errors['morph_values']=max(errors['morph_values'],max((abs(current[k]-v) for k,v in state['morphs'].items()),default=0.))
        for j in joints:
            pose=arm.pose.bones[j['bone']];base=state['basis'][pose.name];errors['selected_local_translation']=max(errors['selected_local_translation'],(pose.location-base.to_translation()).length);errors['selected_local_scale']=max(errors['selected_local_scale'],(pose.scale-base.to_scale()).length);expected=(base.to_quaternion()@rotation_delta(j,channels,f)).to_matrix();errors['requested_local_rotation_matrix']=max(errors['requested_local_rotation_matrix'],float(np.max(np.abs(np.asarray(pose.matrix_basis.to_quaternion().to_matrix())-np.asarray(expected)))))
    if max(errors.values())>1e-5 or geometry_signature(arm,meshes)!=identity or sha(source)!=before:raise ValueError('Hand bake did not preserve required source state: '+repr(errors))
    scene.frame_start=first;scene.frame_end=last;set_frame(scene,first);output.parent.mkdir(parents=True,exist_ok=True);bpy.ops.wm.save_as_mainfile(filepath=str(output))
    result={'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'new-hand-clip-saved-await-independent-reopen-skin-surface-and-visual-audit','source':str(source),'source_sha256':before,'source_unchanged':True,'output_sha256':sha(output),'profile_sha256':sha(a.profile),'motion_sha256':sha(a.motion),'writer_sha256':sha(Path(__file__)),'runtime_sha256':sha(Path(__file__).with_name('hand_control_runtime.py')),'plan_module_sha256':sha(Path(__file__).with_name('hand_control_plan.py')),'binding_sha256':binding,'geometry_signature':identity,'plan':plan,'active_bones':active,'allowed_bones_exact':sorted(allowed),'protected_bone_count':len(protected),'attached_objects_exact':attached,'protected_object_names':[o.name for o in objects],'original_action_copied':old_action is not None,'maximum_requested_local_delta_degrees':maximum_requested,'errors':errors,'fps':scene.render.fps,'scope':'Existing FK controls only; original bones/weights/morphs retained. Only delivered clip interval is baked; no promise for selected-bone animation outside it. Quintic scalar target sampled densely; saved subframe interpolation and actual skin/surface/naturalness need separate audit.'};report.parent.mkdir(parents=True,exist_ok=True);report.write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf-8');print('HAND_BAKE_SAVED',json.dumps(errors),flush=True)
if __name__=='__main__':main()
