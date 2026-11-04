"""Join a configured material-planted approach to an authored story in a new scene."""
from pathlib import Path
import argparse,sys,json,math
sys.dont_write_bytecode=True;sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy,numpy as np
from mathutils import Vector,Matrix
from body_motion_plan import load_json,load_plan,sha,finite,integer
from body_motion_runtime import character_rig,geometry_identity,key_bones,linear_curves,bone_worlds,linked_inputs_unchanged,orient_world,producer_hashes,require_current_producer,select_feet,foot_points
from body_approach_pose import smooth,blend_basis,keyed_bones,mesh_point,solve_ankle,aim_head,restore_prop,constraint_signature
from body_launch_pose import prepare_launch,apply_launch,launch_report
from build_performance import two_bone
from contact_motion import bake_contacts

def capture(scene,arm,actor,names,legs):
    return {'basis':{n:arm.pose.bones[n].matrix_basis.copy() for n in names},'root':actor.location.copy(),'world':bone_worlds(arm,names),
            'feet':{side:{'ankle':arm.matrix_world@arm.pose.bones[item['bones'][2]].head,'rotation':arm.matrix_world.to_quaternion()@arm.pose.bones[item['bones'][2]].matrix.to_quaternion()} for side,item in legs.items()}}

def compose(gait_scene,base_scene,character,story,plan,plant_report):
    h=finite(character['height'],'height',True);ground=finite(character['ground'],'ground');fps=plan['fps'];legs={side:plan['limbs'][side+'_leg'] for side in ('left','right')}
    bpy.ops.wm.open_mainfile(filepath=str(gait_scene),load_ui=False,use_scripts=False);scene=bpy.context.scene;arm,actor=character_rig(scene);names=sorted(arm.pose.bones.keys());geometry=geometry_identity(scene,arm);gait_controls=keyed_bones(arm);gait=[]
    if geometry!=plant_report['geometry_identity'] or scene.frame_end!=plant_report['frames'] or scene.frame_start!=1:raise ValueError('Planted source rig/timeline identity mismatch')
    for side,item in legs.items():
        if any(not c.mute and c.influence>0 and c.type=='IK' for n in item['bones'][1:3] for c in arm.pose.bones[n].constraints):raise ValueError('Planted leg IK must already be explicitly muted')
    side=plan['compose']['reference_side'];last_record=plant_report['rows'][-1]['feet'][side]
    if last_record['mode']!='material-pivot-contact':raise ValueError('Reference foot must end in an explicit material stance')
    pivot=last_record['vertex']
    for frame in range(1,scene.frame_end+1):
        scene.frame_set(frame);bpy.context.view_layer.update();gait.append(capture(scene,arm,actor,names,legs))
    gait_point=mesh_point(scene,pivot);gait_end_root=gait[-1]['root'];gait_relative_point=gait_point-gait_end_root;rig_constraints=constraint_signature(arm);arm_relative=np.asarray(actor.matrix_world.inverted()@arm.matrix_world)
    launch_pivot=None;launch_anchor=None
    if plan['schema']==2:
        first_contact=plant_report['rows'][0]['feet'][plan['launch']['reference_side']]
        if first_contact['mode']!='material-pivot-contact':raise ValueError('Launch source-first foot must have an actual material stance')
        launch_pivot=first_contact['vertex'];scene.frame_set(1);bpy.context.view_layer.update();launch_anchor=mesh_point(scene,launch_pivot)
    bpy.ops.wm.open_mainfile(filepath=str(base_scene),load_ui=False,use_scripts=False);scene=bpy.context.scene;arm,actor=character_rig(scene)
    if geometry_identity(scene,arm)!=geometry or names!=sorted(arm.pose.bones.keys()):raise ValueError('Authored and source scenes must share identical original rest/mesh/weight/morph data')
    if not np.allclose(np.asarray(actor.matrix_world.inverted()@arm.matrix_world),arm_relative,atol=1e-6) or constraint_signature(arm)!=rig_constraints:raise ValueError('Authored/source rig transform or original constraint configuration differs')
    if scene.frame_start!=1 or not 2<=scene.frame_end<=1200 or scene.frame_end*len(names)>500000 or scene.render.fps/scene.render.fps_base!=fps:raise ValueError('Authored timeline outside supported bounds')
    if round(story['duration']*fps)!=scene.frame_end:raise ValueError('Body composition requires the original story duration, without duration scaling')
    interaction=integer(story.get('body_interaction_frame'),'explicit story body_interaction_frame',1,scene.frame_end)
    for side,item in legs.items():
        if any(not c.mute and c.influence>0 and c.type=='IK' for n in item['bones'][1:3] for c in arm.pose.bones[n].constraints):raise ValueError('Authored scene requires explicit stationary FK support')
    for obj in (arm,actor):
        if obj.animation_data and (len(obj.animation_data.drivers) or len(obj.animation_data.nla_tracks)):raise ValueError('Driven/NLA arm/root composition is unsupported')
    target_name=plan['compose']['target_object']
    if target_name not in scene.objects:raise ValueError('Actual narrative target object missing')
    prop=scene.objects[target_name]
    if target_name!='Story prop':raise ValueError('Current story contact contract requires the actual Story prop object')
    base_controls=keyed_bones(arm);controls=sorted(gait_controls|base_controls|{character['bones']['head'],character['gaze']['control']});base=[]
    if any(arm.pose.bones[n].rotation_mode!='QUATERNION' for n in controls):raise ValueError('Authored/source controls must already use quaternion rotations')
    for frame in range(1,scene.frame_end+1):
        scene.frame_set(frame);bpy.context.view_layer.update();row=capture(scene,arm,actor,names,legs);row['prop']=prop.matrix_world.copy();row['head_rotation']=arm.pose.bones[character['bones']['head']].matrix.to_quaternion();row['pivot']=mesh_point(scene,pivot);base.append(row)
    reference=base[interaction-1];shift=(reference['pivot']-reference['root'])-gait_relative_point;direction=Vector(plan['travel']['direction']);distance=-shift.dot(direction);speed=plant_report['speed_world_units_per_second']
    if any((state['root']-reference['root']).length>1e-6*h for state in base[:interaction]):raise ValueError('Authored root must be stationary before interaction; existing root motion is not replaced')
    if not math.isfinite(distance) or not 0<distance<.5*h or shift.length>.5*h:raise ValueError('Gait/author foot alignment does not support a bounded forward stop')
    stop_count=round(2*distance/speed*fps);settings=plan['compose'];start=settings['gait_start'];gait_last=start+len(gait)-1;stop_end=gait_last+stop_count
    if not settings['minimum_stop_frames']<=stop_count<=settings['maximum_stop_frames'] or stop_end>interaction:raise ValueError('Measured stop cannot finish before explicit interaction: '+json.dumps({'stop_count':stop_count,'stop_end':stop_end,'interaction':interaction}))
    if (base[stop_end-1]['pivot']-reference['pivot']).length>.0001*h:raise ValueError('Authored reference foot moves before the measured stop can join it')
    if any(round(row['start']*fps)+1<stop_end for row in story['prop'].get('contacts',[])):raise ValueError('Approach would overlap required held-prop contact')
    duration=stop_count/fps;power=speed*duration/distance-1
    if not .5<=power<=3:raise ValueError('Unsupported deceleration fit')
    for obj in (arm,actor):obj.animation_data_create();obj.animation_data.action=bpy.data.actions.new('Body approach / '+obj.name)
    restore_prop(prop,story,h,ground,fps,scene.frame_end);face=[m for m in bpy.data.materials if m.use_nodes and m.node_tree.nodes.get('FaceObjectY')];previous={};rows=[];maximum_pivot=0.;head=arm.pose.bones[character['bones']['head']]
    first_root=base[start-1]['root']+gait[0]['root']-gait_end_root+shift
    launch=prepare_launch(character,plan,gait,base,first_root,launch_pivot,launch_anchor);selection=select_feet(scene,arm,plan) if launch else None
    def pole(side):
        a,b,c=[arm.pose.bones[n] for n in legs[side]['bones'][:3]];axis=c.head-a.head;offset=b.head-a.head
        if axis.length<1e-8:raise ValueError('Collapsed transition leg')
        offset-=axis.normalized()*offset.dot(axis.normalized())
        if offset.length>.00001*h:return arm.matrix_world@b.head
        raw=character.get('stationary_support',{}).get(side,{}).get('pole')
        if raw is None:raise ValueError('Straight transition leg needs external fallback pole')
        return Vector((raw[0]*h,raw[1]*h,ground+raw[2]*h))
    for frame,authored in enumerate(base,1):
        scene.frame_set(frame);u=(frame-gait_last)/stop_count;weight=smooth(u);prelaunch=launch is not None and frame<start;active=prelaunch or start<=frame<stop_end
        for name in controls:
            if start<=frame<=gait_last:value=gait[frame-start]['basis'][name]
            elif gait_last<frame<stop_end:value=blend_basis(gait[-1]['basis'][name],authored['basis'][name],weight)
            else:value=authored['basis'][name]
            arm.pose.bones[name].matrix_basis=value
        if start<=frame<=gait_last:actor.location=authored['root']+gait[frame-start]['root']-gait_end_root+shift
        elif gait_last<frame<stop_end:
            backward=-direction*distance;lateral=shift-backward;actor.location=authored['root']+backward*(1-u)**(power+1)+lateral*(1-weight)
        else:actor.location=authored['root']
        record=apply_launch(scene,arm,actor,controls,legs,character,plan,selection,launch,frame) if prelaunch else {'frame':frame}
        actor.keyframe_insert('location',frame=frame);bpy.context.view_layer.update();record['root']=list(actor.location)
        if gait_last<frame<stop_end:
            names_ref=legs[side]['bones'][:3];q=gait[-1]['feet'][side]['rotation'].slerp(authored['feet'][side]['rotation'],weight);anchor=reference['pivot'];target=arm.matrix_world@arm.pose.bones[names_ref[2]].head;reference_pole=pole(side);orient_world(arm,arm.pose.bones[names_ref[2]],q)
            for iteration in range(12):
                error=anchor-mesh_point(scene,pivot)
                if error.length<.00003*h:break
                target+=error;solve_ankle(arm,names_ref,target,q,two_bone,h,reference_pole)
            error=(mesh_point(scene,pivot)-anchor).length/h
            if error>.0001:raise ValueError('Stop material-point error exceeded bound at frame'+str(frame))
            maximum_pivot=max(maximum_pivot,error);other='left' if side=='right' else 'right';names_other=legs[other]['bones'][:3];target=(authored['root']+gait[-1]['feet'][other]['ankle']-gait_end_root+shift).lerp(authored['feet'][other]['ankle'],weight);target.z+=settings['landing_lift_H']*h*math.sin(math.pi*weight);q=gait[-1]['feet'][other]['rotation'].slerp(authored['feet'][other]['rotation'],weight);solve_ankle(arm,names_other,target,q,two_bone,h,pole(other));record.update(reference_pivot=pivot,reference_anchor_world=list(anchor),reference_pivot_error_H=error)
        if active:aim_head(arm,character,prop.matrix_world.translation,authored['head_rotation'],smooth((frame-(stop_end-4))/4))
        key_bones(arm,controls,frame,previous);bpy.context.view_layer.update();rotation=arm.matrix_world.to_3x3()@head.matrix.to_3x3()@head.bone.matrix_local.to_3x3().inverted()
        for material in face:
            for node,key in (('FaceObjectY','face_rest_y'),('FaceObjectZ','face_rest_z')):
                axis=(rotation@Vector(character[key])).normalized()
                for index in range(3):material.node_tree.nodes[node].inputs[index].default_value=axis[index];material.node_tree.nodes[node].inputs[index].keyframe_insert('default_value',frame=frame)
        rows.append(record)
    linear_curves(arm.animation_data.action,controls);linear_curves(actor.animation_data.action);contact=bake_contacts(scene,arm,prop,character.get('contact_anchors',{}),story['prop'].get('contacts',[]),h,fps,1,scene.frame_end);maximum_late=0.;maximum_prop=0.
    for frame,authored in enumerate(base,1):
        scene.frame_set(frame);bpy.context.view_layer.update();now=bone_worlds(arm,names)
        if frame>=stop_end or frame<start and launch is None:maximum_late=max(maximum_late,float(np.max(np.abs(now-authored['world']))))
        if launch is not None and frame<=start:
            error=(mesh_point(scene,launch['reference_pivot'])-launch['reference_anchor']).length/h;minimum=min(p.z for label in ('left','right') for _,_,p in foot_points(selection,label))/h
            launch['maximum_reference_error_H']=max(launch['maximum_reference_error_H'],error);launch['minimum_sole_H']=min(launch['minimum_sole_H'],minimum)
            if error>.0001 or minimum<(ground/h+plan['travel']['sole_height'])-.00003:raise ValueError('Saved launch reference/sole verification failed at frame'+str(frame))
        prop_error=np.asarray(prop.matrix_world)-np.asarray(authored['prop'])
        if not np.isfinite(prop_error).all():raise ValueError('Nonfinite prop preservation metric')
        maximum_prop=max(maximum_prop,float(np.max(np.abs(prop_error))))
    if max(maximum_late,maximum_prop)>1e-5 or geometry_identity(scene,arm)!=geometry:raise ValueError('Authored performance/prop or rest/geometry protection failed')
    scene.frame_set(1)
    return {'status':'body-approach-composed-await-final-gaze-clearance-and-visuals','frames':scene.frame_end,'fps':fps,'source_gait_frames':len(gait),'gait_range':[start,gait_last],'stop_frames':stop_count,'stop_end':stop_end,'interaction_frame':interaction,'source_speed_world':speed,'alignment_shift_world':list(shift),'deceleration_power':power,'reference_material_pivot':pivot,'maximum_stop_material_pivot_error_H':maximum_pivot,'maximum_protected_authored_bone_world_error':maximum_late,'maximum_authored_prop_world_error':maximum_prop,'geometry_identity':geometry,'contact_rebake':contact,'rows':rows,'launch':launch_report(launch),'starts_already_moving':launch is None,'rights':plant_report['rights'],'source_input_sha256':plant_report['source_input_sha256'],'scope':'Configured source-body approach, optional explicit ready stance/launch, bounded measured deceleration and material-point reference-foot stop, followed by original authored acting; head attention authored toward actual prop. Original plot prop trajectory/contact and all bone world poses from stop end onward verified. Launch owns its declared pre-gait frames; schema1 protects them. No general walk-start, motion-matching/IK retarget, physics, full collision, subframe, independent-rig or continuous naturalness acceptance.'}

def main(arguments=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('blend','gait','plant-report','character','story','plan','output','report'):parser.add_argument('--'+key,required=True,type=Path)
    a=parser.parse_args(arguments if arguments is not None else sys.argv[sys.argv.index('--')+1:]);paths={key:getattr(a,key).resolve() for key in ('blend','gait','plant_report','character','story','plan','output','report')}
    if len(set(paths.values()))!=8 or paths['output'].suffix.lower()!='.blend' or paths['report'].suffix.lower()!='.json' or paths['output'].exists() or paths['report'].exists():raise ValueError('Distinct inputs and new blend/report outputs required')
    plan,files=load_plan(paths['plan']);character=load_json(paths['character']);story=load_json(paths['story']);record=load_json(paths['plant_report']);hashes={p:sha(p) for p in [*list(paths.values())[:6],*files.values()]}
    if record.get('status')!='material-stance-baked-await-stop-and-complete-visuals' or record.get('output_scene_sha256')!=hashes[paths['gait']] or record.get('character_sha256')!=hashes[paths['character']] or record.get('plan_sha256')!=hashes[paths['plan']] or record.get('writer_sha256')!=sha(Path(__file__).with_name('plant_body_motion.py')):raise ValueError('Stale planted motion/configuration evidence')
    require_current_producer(record)
    result=compose(paths['gait'],paths['blend'],character,story,plan,record);linked_inputs_unchanged(hashes);paths['output'].parent.mkdir(parents=True,exist_ok=True);paths['report'].parent.mkdir(parents=True,exist_ok=True);bpy.ops.wm.save_as_mainfile(filepath=str(paths['output']))
    result.update(schema=1,producer_sha256=producer_hashes(),input_scene_sha256=hashes[paths['blend']],gait_scene_sha256=hashes[paths['gait']],plant_report_sha256=hashes[paths['plant_report']],output_scene_sha256=sha(paths['output']),character_sha256=hashes[paths['character']],story_sha256=hashes[paths['story']],plan_sha256=hashes[paths['plan']],writer_sha256=sha(Path(__file__)),pose_helper_sha256=sha(Path(__file__).with_name('body_approach_pose.py')),runtime_sha256=sha(Path(__file__).with_name('body_motion_runtime.py')),validator_sha256=sha(Path(__file__).with_name('body_motion_plan.py')))
    paths['report'].write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),'utf-8');print('BODY_APPROACH_COMPOSE',result['stop_end'],result['maximum_protected_authored_bone_world_error'],flush=True)

if __name__=='__main__':main()
