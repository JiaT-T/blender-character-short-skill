"""Kinematic material-point stance correction over a measured body clip."""
from pathlib import Path
import argparse,sys,json,math
sys.dont_write_bytecode=True;sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy,numpy as np
from mathutils import Matrix,Vector
from body_motion_plan import load_json,load_plan,sha,finite
from body_motion_runtime import character_rig,geometry_identity,select_feet,foot_points,orient_world,key_bones,linear_curves,bone_worlds,linked_inputs_unchanged,producer_hashes,require_current_producer
from bake_elbow_poles import dependency_bones
from build_performance import two_bone

def plant(scene,character,plan,travel_report):
    if any(not plan['feet'][side]['contacts'] for side in ('left','right')):raise ValueError('Material planting requires explicit reviewed contact intervals on both feet; undeclared recorded contacts cannot pass as planted')
    arm,actor=character_rig(scene);h=finite(character['height'],'height',True);ground=finite(character['ground'],'ground');floor=ground+plan['travel']['sole_height']*h;tol=.00003*h;count=scene.frame_end
    if scene.frame_start!=1 or not 2<=count<=240 or count!=travel_report['frames'] or scene.render.fps/scene.render.fps_base!=plan['fps']:raise ValueError('Body travel timeline mismatch')
    geometry=geometry_identity(scene,arm)
    if geometry!=travel_report['geometry_identity']:raise ValueError('Original rest/mesh identity changed')
    selections=select_feet(scene,arm,plan);controls={side:plan['limbs'][side+'_leg']['bones'][:3] for side in ('left','right')};changed={n for names in controls.values() for n in names};allowed=dependency_bones(arm,changed);protected=[n for n in arm.pose.bones.keys() if n not in allowed];states=[]
    for frame in range(1,count+1):
        scene.frame_set(frame);bpy.context.view_layer.update();row={'protected':bone_worlds(arm,protected),'feet':{}}
        for side,names in controls.items():
            a,b,c=[arm.pose.bones[n] for n in names];row['feet'][side]={'hip':arm.matrix_world@a.head,'knee':arm.matrix_world@b.head,'ankle':arm.matrix_world@c.head,'rotation':arm.matrix_world.to_quaternion()@c.matrix.to_quaternion()}
        states.append(row)
    def vertex(side,key):return next(p for name,index,p in foot_points(selections,side) if (name,index)==key)
    def solve(side,target,state):
        a,b,c=[arm.pose.bones[n] for n in controls[side]];inverse=arm.matrix_world.inverted();axis=state['ankle']-state['hip'];pole=state['knee'];offset=pole-state['hip']
        if axis.length<1e-8:raise ValueError('Collapsed source leg')
        offset-=axis.normalized()*offset.dot(axis.normalized())
        if offset.length<.00001*h:
            support=character.get('stationary_support',{}).get(side,{})
            if 'pole' not in support:raise ValueError('Straight leg needs an external fallback pole')
            p=support['pole'];pole=Vector((p[0]*h,p[1]*h,ground+p[2]*h))
        answer=two_bone(a,b,c,inverse@target,inverse@pole,reach_fraction=1)
        if answer['clamped']:raise ValueError('Unreachable configured stance '+side+' frame'+str(scene.frame_current)+' '+json.dumps(answer))
        orient_world(arm,c,state['rotation']);return arm.matrix_world@c.head
    contacts={};deltas={};previous={};rows=[];max_protected=0.;max_pivot=0.;minimum=1e9
    for frame,state in enumerate(states,1):
        scene.frame_set(frame);bpy.context.view_layer.update();row={'frame':frame,'feet':{}}
        for side,names in controls.items():
            source=state['feet'][side];interval=next((x for x in plan['feet'][side]['contacts'] if x[0]<=frame<=x[1]),None);release=next((x for x in plan['feet'][side]['contacts'] if x[1]<frame<=x[1]+plan['release_frames']),None);record={'mode':'source-swing'}
            if interval:
                if frame==interval[0]:
                    name,index,p=min(foot_points(selections,side),key=lambda x:x[2].z);anchor=p.copy();anchor.z=floor;contacts[side]={'vertex':(name,index),'anchor':anchor}
                contact=contacts[side];target=source['ankle'].copy();switches=[]
                for iteration in range(12):
                    error=contact['anchor']-vertex(side,contact['vertex'])
                    if error.length>tol:target+=error;solve(side,target,source);continue
                    name,index,low=min(foot_points(selections,side),key=lambda x:x[2].z)
                    if low.z<floor-tol:
                        contact['vertex']=(name,index);contact['anchor']=low.copy();contact['anchor'].z=floor;switches.append({'mesh':name,'vertex':index});continue
                    break
                error=(vertex(side,contact['vertex'])-contact['anchor']).length/h
                if error>.0001:raise ValueError('Material stance failed to converge '+side+' frame'+str(frame)+' errorH'+str(error))
                max_pivot=max(max_pivot,error);record={'mode':'material-pivot-contact','vertex':list(contact['vertex']),'anchor_world':list(contact['anchor']),'error_H':error,'pivot_switches':switches}
                if frame==interval[1]:deltas[(side,interval[1])]=arm.matrix_world@arm.pose.bones[names[2]].head-source['ankle']
            elif release:
                u=(frame-release[1])/plan['release_frames'];weight=1-u*u*(3-2*u);solve(side,source['ankle']+deltas[(side,release[1])]*weight,source);record={'mode':'swing-residual-release','weight':weight}
            if interval or release:
                low=min(p.z for _,_,p in foot_points(selections,side))
                if low<floor-tol:
                    target=arm.matrix_world@arm.pose.bones[names[2]].head;target.z+=floor-low;solve(side,target,source)
            key_bones(arm,names,frame,previous);bpy.context.view_layer.update();low=min(p.z for _,_,p in foot_points(selections,side))/h;minimum=min(minimum,low);record['minimum_z_H']=low;row['feet'][side]=record
        if protected:max_protected=max(max_protected,float(np.max(np.abs(bone_worlds(arm,protected)-state['protected']))))
        rows.append(row)
    linear_curves(arm.animation_data.action,changed)
    # Re-evaluate saved-key semantics, not just temporary property assignments.
    for frame,state in enumerate(states,1):
        scene.frame_set(frame);bpy.context.view_layer.update()
        if protected:max_protected=max(max_protected,float(np.max(np.abs(bone_worlds(arm,protected)-state['protected']))))
        for side in ('left','right'):
            record=rows[frame-1]['feet'][side];minimum=min(minimum,min(p.z for _,_,p in foot_points(selections,side))/h)
            if record['mode']=='material-pivot-contact':max_pivot=max(max_pivot,(vertex(side,tuple(record['vertex']))-Vector(record['anchor_world'])).length/h)
    if max_protected>1e-5 or max_pivot>.0001 or minimum<floor/h-.00003 or geometry_identity(scene,arm)!=geometry:raise ValueError('Material stance/protected original-body verification failed')
    scene['body_material_iteration_stop_tolerance_H']=.00003;scene['body_material_acceptance_tolerance_H']=.0001;scene.frame_set(1)
    return {'status':'material-stance-baked-await-stop-and-complete-visuals','frames':count,'fps':plan['fps'],'geometry_identity':geometry,'speed_world_units_per_second':travel_report['speed_world_units_per_second'],'maximum_protected_bone_world_error':max_protected,'maximum_material_pivot_error_H':max_pivot,'minimum_sole_z_H':minimum,'allowed_leg_dependency_bones':sorted(allowed),'rows':rows,'rights':travel_report['rights'],'source_input_sha256':travel_report['source_input_sha256'],'scope':'Actual selected skinned material vertices anchored during explicit stance intervals, allowing documented rolling pivot switches and bounded residual release. Original upper body/world root/rest/mesh/weights retained. No subframe, full-volume/physics/friction, natural stance timing or continuous visual acceptance.'}

def main(arguments=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('blend','travel-report','character','plan','output','report'):parser.add_argument('--'+key,required=True,type=Path)
    a=parser.parse_args(arguments if arguments is not None else sys.argv[sys.argv.index('--')+1:]);paths={key:getattr(a,key).resolve() for key in ('blend','travel_report','character','plan','output','report')}
    if len(set(paths.values()))!=6 or paths['output'].suffix.lower()!='.blend' or paths['report'].suffix.lower()!='.json' or paths['output'].exists() or paths['report'].exists():raise ValueError('Distinct inputs and new blend/report outputs required')
    plan,files=load_plan(paths['plan']);record=load_json(paths['travel_report']);character=load_json(paths['character']);hashes={p:sha(p) for p in [paths['blend'],paths['travel_report'],paths['character'],paths['plan'],*files.values()]}
    if record.get('status')!='measured-travel-and-signed-grounding-await-material-contacts' or record.get('output_scene_sha256')!=hashes[paths['blend']] or record.get('character_sha256')!=hashes[paths['character']] or record.get('plan_sha256')!=hashes[paths['plan']] or record.get('writer_sha256')!=sha(Path(__file__).with_name('travel_body_motion.py')):raise ValueError('Stale travel scene/producer evidence')
    require_current_producer(record)
    bpy.ops.wm.open_mainfile(filepath=str(paths['blend']),load_ui=False,use_scripts=False)
    try:result=plant(bpy.context.scene,character,plan,record)
    except ValueError as exc:
        linked_inputs_unchanged(hashes);paths['report'].parent.mkdir(parents=True,exist_ok=True);paths['report'].write_text(json.dumps({'status':'rejected-before-save','reason':str(exc),'input_scene_sha256':hashes[paths['blend']],'plan_sha256':hashes[paths['plan']],'source_unchanged':True},indent=2),'utf-8');raise
    linked_inputs_unchanged(hashes);paths['output'].parent.mkdir(parents=True,exist_ok=True);paths['report'].parent.mkdir(parents=True,exist_ok=True);bpy.ops.wm.save_as_mainfile(filepath=str(paths['output']))
    result.update(schema=1,producer_sha256=producer_hashes(),input_scene_sha256=hashes[paths['blend']],travel_report_sha256=hashes[paths['travel_report']],output_scene_sha256=sha(paths['output']),character_sha256=hashes[paths['character']],plan_sha256=hashes[paths['plan']],writer_sha256=sha(Path(__file__)),runtime_sha256=sha(Path(__file__).with_name('body_motion_runtime.py')),validator_sha256=sha(Path(__file__).with_name('body_motion_plan.py')))
    paths['report'].write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),'utf-8');print('BODY_MATERIAL_STANCE',result['maximum_material_pivot_error_H'],result['minimum_sole_z_H'],flush=True)

if __name__=='__main__':main()
