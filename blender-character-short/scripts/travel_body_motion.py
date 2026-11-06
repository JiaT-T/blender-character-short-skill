"""Add measured horizontal travel and signed foot-height correction to a fit."""
from pathlib import Path
import argparse,sys,json,math
sys.dont_write_bytecode=True;sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy,numpy as np
from mathutils import Vector
from body_motion_plan import load_json,load_plan,sha,finite
from body_motion_runtime import character_rig,geometry_identity,select_feet,foot_points,bone_worlds,linear_curves,linked_inputs_unchanged,producer_hashes,require_current_producer

def travel(scene,character,plan,fit_report):
    if plan.get('root_motion','legacy-measured-travel')=='recorded':raise ValueError('Recorded root motion is already retained by fitting; do not add measured constant travel')
    arm,actor=character_rig(scene);h=finite(character['height'],'height',True);ground=finite(character['ground'],'ground');first,last=scene.frame_start,scene.frame_end;count=last-first+1;fps=plan['fps']
    if first!=1 or not 2<=count<=240 or scene.render.fps/scene.render.fps_base!=fps or len(fit_report['rows'])!=count:raise ValueError('Fitted timeline/report mismatch')
    if actor.animation_data and actor.animation_data.action and len(actor.animation_data.action.fcurves):raise ValueError('Existing root animation must not be replaced')
    geometry=geometry_identity(scene,arm)
    if geometry!=fit_report['geometry_identity']:raise ValueError('Fitted rest/mesh data changed')
    selections=select_feet(scene,arm,plan);direction=np.asarray(plan['travel']['direction'],float);raw=fit_report['rows'];velocities=[]
    for previous,current in zip(raw,raw[1:]):
        for side in ('left','right'):
            if max(previous['feet'][side]['minimum_z_H'],current['feet'][side]['minimum_z_H'])<plan['travel']['fit_threshold_H']:
                delta=np.asarray(current['feet'][side]['ankle_world'])-np.asarray(previous['feet'][side]['ankle_world']);velocities.append(float(np.dot(delta,-direction)*fps))
    if not velocities or not all(math.isfinite(v) for v in velocities):raise ValueError('Insufficient finite near-stance samples for travel')
    speed=float(np.median(velocities));low,high=plan['travel']['speed_range_H_per_second']
    if not low<=speed/h<=high:raise ValueError('Measured forward speed outside configured range')
    names=sorted(arm.pose.bones.keys());states=[];duration=(count-1)/fps
    for frame in range(first,last+1):
        scene.frame_set(frame);bpy.context.view_layer.update();inverse=actor.matrix_world.inverted();relative=np.asarray([list(map(list,inverse@arm.matrix_world@arm.pose.bones[name].matrix)) for name in names]);states.append({'relative':relative,'root':actor.location.copy()})
    def curves():return [(c.data_path,c.array_index,[(list(k.co),k.interpolation,list(k.handle_left),list(k.handle_right)) for k in c.keyframe_points]) for c in arm.animation_data.action.fcurves]
    action_before=curves();rows=[];corrections=[];maximum_relative=0.;floor_error=0.
    for frame,state in enumerate(states,1):
        scene.frame_set(frame);height=ground/h+plan['travel']['sole_height']-min(raw[frame-1]['feet'][side]['minimum_z_H'] for side in ('left','right'))
        if plan['travel']['grounding_mode']=='raise-only':height=max(0.,height)
        if abs(height)>plan['travel']['maximum_vertical_change_H']:raise ValueError('Required root-height adaptation exceeds configured bound')
        offset=-direction*speed*(duration-(frame-1)/fps);offset[2]=height*h;actor.location=state['root']+Vector(offset.tolist());actor.keyframe_insert('location',frame=frame);bpy.context.view_layer.update();inverse=actor.matrix_world.inverted()
        current=np.asarray([list(map(list,inverse@arm.matrix_world@arm.pose.bones[name].matrix)) for name in names])
        if not np.isfinite(current).all():raise ValueError('Nonfinite actor-relative body matrix')
        maximum_relative=max(maximum_relative,float(np.max(np.abs(current-state['relative']))));bone_worlds(arm,names)
        row={'frame':frame,'root_location':list(actor.location),'root_vertical_correction_H':height,'feet':{}}
        for side in ('left','right'):
            values=foot_points(selections,side);ankle=plan['limbs'][side+'_leg']['bones'][2];row['feet'][side]={'minimum_z_H':min(p.z for _,_,p in values)/h,'ankle_world':list(arm.matrix_world@arm.pose.bones[ankle].head)}
        gap=min(x['minimum_z_H'] for x in row['feet'].values())-(ground/h+plan['travel']['sole_height'])
        error=abs(gap) if plan['travel']['grounding_mode']=='lowest-sole' else max(0.,-gap)
        floor_error=max(floor_error,error);corrections.append(height);rows.append(row)
    if maximum_relative>1e-5 or floor_error>1e-5 or action_before!=curves() or geometry_identity(scene,arm)!=geometry:raise ValueError('Travel protection or actual sole-height verification failed')
    linear_curves(actor.animation_data.action);scene.frame_set(1)
    return {'status':'measured-travel-and-signed-grounding-await-material-contacts','frames':count,'fps':fps,'geometry_identity':geometry,'grounding_mode':plan['travel']['grounding_mode'],'speed_world_units_per_second':speed,'travel_distance_H':speed*duration/h,'speed_fit_sample_count':len(velocities),'maximum_actor_relative_bone_matrix_error':maximum_relative,'maximum_lowest_sole_height_error_H':floor_error,'maximum_root_vertical_change_H':max(map(abs,corrections)),'arm_action_unchanged':True,'rows':rows,'rights':fit_report['rights'],'source_input_sha256':fit_report['source_input_sha256'],'scope':'Measured constant horizontal actor travel. Raise-only mode corrects floor penetration while preserving source flight; lowest-sole mode is an explicit signed rootZ adaptation forcing ground contact. The sole metric means penetration shortfall in raise-only mode, absolute floor error in lowest-sole mode. No fixed horizontal contact, stop, subframe, physics or naturalness acceptance. Original joint keys/rest/geometry/weights retained.'}

def main(arguments=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('blend','fit-report','character','plan','output','report'):parser.add_argument('--'+key,required=True,type=Path)
    a=parser.parse_args(arguments if arguments is not None else sys.argv[sys.argv.index('--')+1:]);paths={key:getattr(a,key).resolve() for key in ('blend','fit_report','character','plan','output','report')}
    if len(set(paths.values()))!=6 or paths['output'].suffix.lower()!='.blend' or paths['report'].suffix.lower()!='.json' or paths['output'].exists() or paths['report'].exists():raise ValueError('Distinct inputs and new blend/report outputs required')
    plan,files=load_plan(paths['plan']);record=load_json(paths['fit_report']);character=load_json(paths['character']);hashes={p:sha(p) for p in [paths['blend'],paths['fit_report'],paths['character'],paths['plan'],*files.values()]}
    if record.get('status')!='proportional-body-FK-fitted-await-travel-contact-and-visuals' or record.get('output_scene_sha256')!=hashes[paths['blend']] or record.get('character_sha256')!=hashes[paths['character']] or record.get('plan_sha256')!=hashes[paths['plan']] or record.get('writer_sha256')!=sha(Path(__file__).with_name('fit_body_motion.py')):raise ValueError('Stale fitted scene/producer evidence')
    require_current_producer(record)
    bpy.ops.wm.open_mainfile(filepath=str(paths['blend']),load_ui=False,use_scripts=False);result=travel(bpy.context.scene,character,plan,record);linked_inputs_unchanged(hashes)
    paths['output'].parent.mkdir(parents=True,exist_ok=True);paths['report'].parent.mkdir(parents=True,exist_ok=True);bpy.ops.wm.save_as_mainfile(filepath=str(paths['output']))
    result.update(schema=1,producer_sha256=producer_hashes(),input_scene_sha256=hashes[paths['blend']],fit_report_sha256=hashes[paths['fit_report']],output_scene_sha256=sha(paths['output']),character_sha256=hashes[paths['character']],plan_sha256=hashes[paths['plan']],writer_sha256=sha(Path(__file__)),runtime_sha256=sha(Path(__file__).with_name('body_motion_runtime.py')),validator_sha256=sha(Path(__file__).with_name('body_motion_plan.py')))
    paths['report'].write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),'utf-8');print('BODY_TRAVEL',result['travel_distance_H'],result['maximum_lowest_sole_height_error_H'],flush=True)

if __name__=='__main__':main()
