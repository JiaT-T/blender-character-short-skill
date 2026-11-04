"""Read saved body-story output: whole character/set surfaces, soles and attention.

Successful execution means the inspection completed. Its checks determine the
technical outcome; neither outcome certifies continuous visual naturalness.
"""
from pathlib import Path
import argparse,sys,json,math
sys.dont_write_bytecode=True;sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy,numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from body_motion_plan import load_json,load_plan,sha,finite,BODY_PRODUCER_NAMES,parse_framing_plan
from body_motion_runtime import character_rig,select_feet,foot_points,bone_worlds
from story_framing import select_features,projected_feature_bounds,bounds_inside

def tree(obj):
    ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh()
    try:
        mesh.calc_loop_triangles();points=[ev.matrix_world@v.co for v in mesh.vertices];triangles=[tuple(t.vertices) for t in mesh.loop_triangles]
        if not all(math.isfinite(v) for p in points for v in p):raise ValueError('Nonfinite evaluated mesh vertex')
        if len(points)>250000 or len(triangles)>500000:raise ValueError('Mesh exceeds surface inspection budget')
        return (BVHTree.FromPolygons(points,triangles,all_triangles=True) if triangles else None),points,len(triangles)
    finally:ev.to_mesh_clear()

def vertex(scene,key):
    obj=scene.objects[key[0]];ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh()
    try:return ev.matrix_world@mesh.vertices[key[1]].co
    finally:ev.to_mesh_clear()

def angle(quaternion):return math.degrees(2*math.acos(min(1.,abs(quaternion.normalized().w))))

def main(arguments=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('pipeline','character','plan','report'):parser.add_argument('--'+key,required=True,type=Path)
    parser.add_argument('--gaze-plan',type=Path)
    parser.add_argument('--framing-plan',type=Path)
    a=parser.parse_args(arguments if arguments is not None else sys.argv[sys.argv.index('--')+1:]);out=a.pipeline.resolve();report=a.report.resolve()
    if report.exists() or report.suffix.lower()!='.json':raise ValueError('Choose a new JSON audit report')
    identity=load_json(out/'pipeline-inputs.json');progress=load_json(out/'pipeline-progress.json');compose=load_json(out/'body-compose/compose-report.json');plant=load_json(out/'body-plant/plant-report.json');character=load_json(a.character);plan,_=load_plan(a.plan)
    if progress.get('status')!='technical-complete' or identity['inputs'].get('character')!=sha(a.character) or identity['inputs'].get('body_approach_plan')!=sha(a.plan):raise ValueError('Completed pipeline/configuration identity mismatch')
    render=next(row for row in reversed(progress['events']) if row['stage']=='render');cmd=render['command'];source=Path(cmd[cmd.index('--blend')+1]).resolve();producer=Path(cmd[cmd.index('--python')+1]).resolve().parent
    if not source.is_relative_to(out) or render['returncode']!=0:raise ValueError('Final render source is outside this pipeline or failed')
    expected={name:identity['scripts'][name] for name in BODY_PRODUCER_NAMES}
    if compose.get('producer_sha256')!=expected or plant.get('producer_sha256')!=expected or any(sha(producer/name)!=value for name,value in expected.items()):raise ValueError('Actual body producer bytes differ from pipeline/stage evidence')
    travel_path=out/'body-travel/travel-report.json';travel=load_json(travel_path)
    if travel.get('producer_sha256')!=expected or plant.get('travel_report_sha256')!=sha(travel_path) or plant.get('input_scene_sha256')!=travel.get('output_scene_sha256'):raise ValueError('Original travel/root evidence is stale')
    before=sha(source);raw=load_json(out/'raw/render-job.json')
    if raw.get('blend_sha256')!=before:raise ValueError('Saved scene differs from the actual rendered scene')
    tempo=None
    if 'scene_tempo_plan' in identity['inputs']:
        tempo=load_json(out/'scene-tempo/bake-report.json')
        if tempo.get('output_scene_sha256')!=before or tempo.get('plan_sha256')!=identity['inputs']['scene_tempo_plan']:raise ValueError('Final time-map evidence is stale')
    gaze=load_json(a.gaze_plan) if a.gaze_plan else {'ranges':[]}
    if a.gaze_plan and identity['inputs'].get('gaze_plan')!=sha(a.gaze_plan):raise ValueError('Gaze plan differs from actual pipeline input')
    framing=parse_framing_plan(load_json(a.framing_plan),compose['frames']) if a.framing_plan else []
    bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False);scene=bpy.context.scene;arm,actor=character_rig(scene);h=finite(character['height'],'height',True);ground=finite(character['ground'],'ground');count=scene.frame_end
    times=tempo['plan']['source_times'] if tempo else list(range(1,count+1))
    if scene.frame_start!=1 or not 2<=count<=1200 or count*len(arm.pose.bones)>500000 or len(times)!=count or not all(type(t) in (int,float) and math.isfinite(t) and 1<=t<=compose['frames'] for t in times):raise ValueError('Final audit timeline exceeds supported bounds')
    selections=select_feet(scene,arm,plan);descendants={actor,*actor.children_recursive};characters=[o for o in scene.objects if o in descendants and o.type=='MESH' and not o.hide_render];external=[o for o in scene.objects if o not in descendants and o.type=='MESH' and not o.hide_render]
    if not characters or scene.objects.get('Studio floor') is None:raise ValueError('A visible character and the actual studio floor are required')
    feature_names={name for row in framing for name in row['features']};feature_selections=select_features(scene,arm,character,plan,feature_names);framing_failures=[];framing_count=0
    rows=[];collisions=[];anchor_groups={};stop_error=0.;triangle_work=0;head=arm.pose.bones[character['bones']['head']];control=arm.pose.bones[character['gaze']['control']];eyes=[arm.pose.bones[character['gaze'][side]] for side in ('left','right')];forward=Vector(character['gaze']['forward'])
    fractional_contact_frames=[];gait_anchor_error=0.;gait_anchor_samples=0;launch_anchor_error=0.;launch_anchor_samples=0
    for frame,time in enumerate(times,1):
        scene.frame_set(frame);bpy.context.view_layer.update();bone_worlds(arm,arm.pose.bones.keys());row={'frame':frame,'source_time':time,'feet':{}}
        character_trees={};external_trees={};all_z=[];world_points={}
        for obj in [*characters,*external]:
            bvh,points,triangles=tree(obj);triangle_work+=triangles
            world_points[obj.name]=points
            if triangle_work>50000000:raise ValueError('Audit exceeds50000000 evaluated triangle-frames')
            if obj in characters:character_trees[obj.name]=bvh;all_z.extend(p.z/h for p in points)
            else:external_trees[obj.name]=bvh
        row['minimum_character_vertex_z_H']=min(all_z) if all_z else None
        floor_object=scene.objects['Studio floor'];floor_z=[(floor_object.matrix_world@Vector(corner)).z/h for corner in floor_object.bound_box]
        if max(floor_z)-min(floor_z)>1e-6:raise ValueError('Actual studio floor must be a horizontal plane for this audit')
        row['actual_floor_z_H']=sum(floor_z)/len(floor_z);row['minimum_actual_floor_clearance_H']=row['minimum_character_vertex_z_H']-row['actual_floor_z_H']
        requirement=next((r for r in framing if r['start']<=time<=r['end']),None)
        if requirement:
            projected=projected_feature_bounds(scene,{key:feature_selections[key] for key in requirement['features']},world_points);row['framing']={'margin':requirement['margin'],'bounds':projected};framing_count+=1
            if not bounds_inside(projected,requirement['margin']):framing_failures.append({'frame':frame,'source_time':time,'camera':scene.camera.name,'margin':requirement['margin'],'bounds':projected})
        for name,bvh in character_trees.items():
            if bvh is None:continue
            for target,other in external_trees.items():
                if other is None:continue
                pairs=bvh.overlap(other)
                if pairs:collisions.append({'frame':frame,'source_time':time,'character_mesh':name,'external_mesh':target,'triangle_pair_count':len(pairs),'first_pairs':[list(pair) for pair in pairs[:4]]})
        for side in ('left','right'):row['feet'][side]={'minimum_z_H':min(p.z for _,_,p in foot_points(selections,side))/h}
        row['head_deformation_degrees']=angle((arm.matrix_world.to_3x3()@head.matrix.to_3x3()@head.bone.matrix_local.to_3x3().inverted()).to_quaternion());row['eye_control_degrees']=angle(control.matrix_basis.to_quaternion())
        required=next((r['object'] for r in gaze['ranges'] if r['start']<=time<=r['end']),None)
        if required:
            if required not in scene.objects:raise ValueError('Required actual gaze object missing')
            axes=[(arm.matrix_world.to_3x3()@eye.matrix.to_3x3()@eye.bone.matrix_local.to_3x3().inverted()@forward).normalized() for eye in eyes];origin=arm.matrix_world@((eyes[0].head+eyes[1].head)*.5);delta=scene.objects[required].matrix_world.translation-origin
            if delta.length<1e-8:raise ValueError('Required gaze target coincides with eye pivot')
            row['required_gaze_object']=required;row['required_gaze_error_degrees']=math.degrees((axes[0]+axes[1]).normalized().angle(delta.normalized()))
        integer_time=round(time)
        if abs(time-integer_time)<1e-6:
            local=integer_time-compose['gait_range'][0]
            if 0<=local<len(plant['rows']):
                for side,contact in plant['rows'][local]['feet'].items():
                    if contact['mode']!='material-pivot-contact':continue
                    interval=next(i for i,(start,end) in enumerate(plan['feet'][side]['contacts']) if start<=local+1<=end)
                    key=json.dumps([side,interval,contact['vertex'],contact['anchor_world']]);point=vertex(scene,contact['vertex'])
                    expected_anchor=Vector(contact['anchor_world'])+Vector(compose['rows'][integer_time-1]['root'])-Vector(travel['rows'][local]['root_location'])
                    error=(point-expected_anchor).length/h;gait_anchor_error=max(gait_anchor_error,error);gait_anchor_samples+=1
                    if key not in anchor_groups:anchor_groups[key]={'first':point.copy(),'maximum_drift_H':0.,'samples':0,'side':side}
                    group=anchor_groups[key];group['maximum_drift_H']=max(group['maximum_drift_H'],(point-group['first']).length/h);group['samples']+=1
            source_row=compose['rows'][integer_time-1]
            if 'reference_pivot' in source_row:
                error=(vertex(scene,source_row['reference_pivot'])-Vector(source_row['reference_anchor_world'])).length/h
                if source_row.get('reference_contact_phase')=='launch':row['launch_material_anchor_error_H']=error;launch_anchor_error=max(launch_anchor_error,error);launch_anchor_samples+=1
                else:row['stop_material_anchor_error_H']=error;stop_error=max(stop_error,error)
        elif compose['gait_range'][0]<=time<compose['stop_end']:fractional_contact_frames.append(frame)
        rows.append(row)
        if frame%48==0:print('BODY_SAVED_AUDIT',frame,'of',count,flush=True)
    groups=[{'side':g['side'],'samples':g['samples'],'maximum_drift_H':g['maximum_drift_H']} for g in anchor_groups.values()];checked_groups=[g for g in groups if g['samples']>=2];drift=max((g['maximum_drift_H'] for g in checked_groups),default=0.);gaze_error=max((r['required_gaze_error_degrees'] for r in rows if 'required_gaze_error_degrees' in r),default=None)
    minimum_sole=min(v['minimum_z_H'] for r in rows for v in r['feet'].values());minimum_mesh=min(r['minimum_character_vertex_z_H'] for r in rows if r['minimum_character_vertex_z_H'] is not None);maximum_head=max(r['head_deformation_degrees'] for r in rows);maximum_eye=max(r['eye_control_degrees'] for r in rows)
    checks={'source_scene_unchanged':sha(source)==before,'no_character_external_triangle_surface_pairs':not collisions,'selected_soles_not_below_ground':minimum_sole>=ground/h-1e-5,'whole_character_vertices_not_below_ground':minimum_mesh>=ground/h-1e-5,'head_within_original_limit':maximum_head<=character['head_angle_limit']+.001,'eyes_within_original_limit':maximum_eye<=character['gaze']['max_angle']+.001,'required_gaze_within5degrees':gaze_error is None or gaze_error<=5,'checked_integer_material_stance_drift_within_tolerance':drift<=.0002,'checked_integer_stop_anchor_within_tolerance':stop_error<=.0001}
    result={'schema':1,'status':'saved-scene-audit-complete','technical_checks_pass':all(checks.values()),'checks':checks,'scene_sha256':before,'character_sha256':sha(a.character),'plan_sha256':sha(a.plan),'writer_sha256':sha(Path(__file__)),'producer_sha256':expected,'frames':count,'evaluated_triangle_frames':triangle_work,'character_meshes':[o.name for o in characters],'external_meshes':[o.name for o in external],'minimum_selected_sole_z_H':minimum_sole,'minimum_all_character_vertex_z_H':minimum_mesh,'maximum_head_degrees':maximum_head,'maximum_eye_degrees':maximum_eye,'maximum_required_gaze_error_degrees':gaze_error,'maximum_checked_stance_material_drift_H':drift,'maximum_checked_stop_material_error_H':stop_error,'stance_anchor_groups':groups,'single_sample_stance_groups_unverified':sum(g['samples']==1 for g in groups),'fractional_contact_frames_unverified':fractional_contact_frames,'surface_intersections':collisions,'rows':rows,'scope':'All saved output integer frames: visible-render character mesh geometry against all external mesh triangle surfaces, including transparent geometry without alpha masking. BVH surface pairs do not establish closed-volume containment or self-collision; inspect reported contacts visually. Actual weighted soles, original head/eye limits, explicit required gaze and integer-mapped material-point stance/stop samples checked. Single-sample groups/fractional source contact mapping are explicitly unverified. No continuous playback, physical friction, full-volume, subframe, iris appearance, audio or naturalness acceptance.'}
    checks['selected_soles_not_below_reference_ground']=checks.pop('selected_soles_not_below_ground');checks['whole_character_vertices_not_below_reference_ground']=checks.pop('whole_character_vertices_not_below_ground')
    checks['whole_character_clear_of_actual_studio_floor']=min(r['minimum_actual_floor_clearance_H'] for r in rows)>=-1e-5
    checks['absolute_stance_anchor_samples_present']=gait_anchor_samples>0;checks['absolute_stance_anchor_within_tolerance']=gait_anchor_error<=.00002
    checks['stop_anchor_samples_present']=any('stop_material_anchor_error_H' in r for r in rows);checks['no_unverified_fractional_contact_mapping']=not fractional_contact_frames
    result.update(technical_checks_pass=all(checks.values()),maximum_absolute_stance_anchor_error_H=gait_anchor_error,absolute_stance_anchor_samples=gait_anchor_samples,reference_ground_H=ground/h,minimum_actual_floor_clearance_H=min(r['minimum_actual_floor_clearance_H'] for r in rows),single_sample_groups_without_drift_measurement=result.pop('single_sample_stance_groups_unverified'))
    result['scope']='All output integer frames: whole render-visible character mesh/external triangle surfaces (without alpha masking); reference-ground bounds and actual horizontal studio-floor clearance separately; source-anchored material stance/stop positions, repeated-point drift, original head/eye bounds and explicit required gaze. Single-sample groups have absolute-position checks but no drift measurement; fractional source contact mapping is unverified. No closed-volume containment, self-collision, subframe, physical friction, continuous playback, iris appearance, audio or naturalness acceptance.'
    if framing:checks['all_requested_framing_features_inside_margin']=not framing_failures;checks['framing_samples_present']=framing_count>0
    if compose.get('launch'):
        checks['launch_material_anchor_samples_present']=launch_anchor_samples>0;checks['launch_material_anchors_within_tolerance']=launch_anchor_error<=.0001
        result.update(maximum_checked_launch_material_error_H=launch_anchor_error,launch_material_anchor_samples=launch_anchor_samples,launch_scope='Explicit ready/ramp reference material point at mapped integer source times, separate from later gait and stop. No physical balance/subframe/naturalness acceptance.')
    result.update(technical_checks_pass=all(checks.values()),framing_plan_sha256=sha(a.framing_plan) if a.framing_plan else None,framing_checked_output_frames=framing_count,framing_unrequested_output_frames=count-framing_count,framing_failures=framing_failures,framing_scope='Actual deformed configured feature vertices inside the current orthographic frame only; no occlusion, alpha-aware visibility, iris readability or perceptual recognition claim.',auditor_dependency_sha256={name:sha(Path(__file__).with_name(name)) for name in ('body_motion_plan.py','body_motion_runtime.py','story_framing.py')},blender_version=bpy.app.version_string)
    if report==source or report in (a.character.resolve(),a.plan.resolve()):raise ValueError('Audit report must be separate from inputs')
    report.parent.mkdir(parents=True,exist_ok=True);report.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),'utf-8');print('BODY_SAVED_AUDIT_DONE',json.dumps({'technical_checks_pass':result['technical_checks_pass'],'surface_pairs_frames':len(collisions),'minimum_character_vertex_z_H':minimum_mesh,'stance_drift_H':drift,'stop_error_H':stop_error}),flush=True)

if __name__=='__main__':main()
