"""Remix a reviewed fitted body action with retiming, a two-step stop and acting."""
from pathlib import Path
import argparse,json,sys,math,datetime
sys.dont_write_bytecode=True;sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy,numpy as np
from mathutils import Matrix,Vector,Quaternion,Euler
from body_motion_plan import load_plan,sha
from body_motion_runtime import character_rig,geometry_identity,select_feet,foot_points,orient_world,key_bones,linear_curves,bone_worlds,require_current_producer
from body_approach_pose import blend_basis,smooth,mesh_point,solve_ankle,constraint_signature
from acting_clip_plan import compile_plan,values
from build_performance import two_bone,look_at,principled
from gaze_control import aim_existing_control

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for k in ['blend','source-report','body-plan','neutral','mapping','acting-plan','output','report']:p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);paths=[getattr(a,k).resolve() for k in ['blend','source_report','body_plan','neutral','mapping','acting_plan','output','report']]
    if len(set(paths))!=8 or a.output.exists() or a.report.exists() or a.output.suffix!='.blend':raise ValueError('Distinct new outputs and preserved inputs required')
    load=lambda p:json.loads(p.read_text('utf-8'));source=load(a.source_report);body,files=load_plan(a.body_plan);cfg=load(a.mapping);document=load(a.acting_plan);plan=compile_plan(document);settings=document['remix'];first,last=plan['frames'];h=cfg['height'];ground=cfg['ground'];end_source=settings['source_end'];left_land=settings['left_land'];stop_end=settings['stop_end'];recover_start=settings['recover_start'];recover_end=settings['recover_end'];ref=settings['reference_side'];other='left' if ref=='right' else 'right'
    if first!=1 or last>240 or any(type(f) is not int for f in [end_source,left_land,stop_end,recover_start,recover_end]) or not 1<end_source<left_land<stop_end<recover_start<recover_end<last or ref!='right':raise ValueError('Bounded run/left-land/right-land/recovery phases required')
    if source.get('status')!='material-stance-baked-await-stop-and-complete-visuals' or source['output_scene_sha256']!=sha(a.blend):raise ValueError('A reviewed planted source action is required')
    require_current_producer(source);original_hash=sha(a.blend);controls=list(source.get('controls',[])) or [r['bone'] for r in body['body']]+[n for row in body['limbs'].values() for n in row['bones']];legs={side:body['limbs'][side+'_leg']['bones'][:3] for side in ['left','right']};foot_roots=body['feet'];neutral_hash=sha(a.neutral)
    bpy.ops.wm.open_mainfile(filepath=str(a.neutral.resolve()),load_ui=False,use_scripts=False);scene=bpy.context.scene;scene.frame_set(cfg.get('neutral_frame',1));arm,actor=character_rig(scene);identity=geometry_identity(scene,arm);neutral={n:arm.pose.bones[n].matrix_basis.copy() for n in controls};neutral_feet={side:{'ankle':arm.matrix_world@arm.pose.bones[legs[side][2]].head-actor.matrix_world.translation,'q':(arm.matrix_world@arm.pose.bones[legs[side][2]].matrix).to_quaternion()} for side in ['left','right']}
    bpy.ops.wm.open_mainfile(filepath=str(a.blend.resolve()),load_ui=False,use_scripts=False);scene=bpy.context.scene;arm,actor=character_rig(scene)
    if geometry_identity(scene,arm)!=identity or scene.frame_end!=source['frames'] or scene.render.fps/scene.render.fps_base!=plan['fps'] or last*len(arm.pose.bones)>500000:raise ValueError('Neutral/source identity, timeline or rig work mismatch')
    signature=constraint_signature(arm);selections=select_feet(scene,arm,body);states=[]
    for f in range(first,last+1):
        t=values(plan,f)['source_time'][0]
        if not 1<=t<=source['frames']:raise ValueError('Source time outside reviewed action')
        scene.frame_set(int(t),subframe=t-int(t));bpy.context.view_layer.update();states.append({'frame':f,'source_time':t,'basis':{n:arm.pose.bones[n].matrix_basis.copy() for n in controls},'root':actor.location.copy(),'feet':{side:{'ankle':arm.matrix_world@arm.pose.bones[legs[side][2]].head,'q':(arm.matrix_world@arm.pose.bones[legs[side][2]].matrix).to_quaternion(),'pole':arm.matrix_world@arm.pose.bones[legs[side][1]].head} for side in ['left','right']}})
    # Measured exit velocity determines an explicit deceleration distance.
    source_rate=(states[end_source-1]['source_time']-states[0]['source_time'])/(end_source-1);speed=source['speed_world_units_per_second']*source_rate;duration=(stop_end-end_source)/plan['fps'];distance=speed*duration/2;direction=Vector(body['travel']['direction']);end_root=states[end_source-1]['root'];final_root=end_root+direction*distance;left_goal=final_root+neutral_feet[other]['ankle'];right_goal=final_root+neutral_feet[ref]['ankle']-direction*(settings['stagger_H']*h)
    if not 0<distance<h*.5 or not 0<=settings['stagger_H']<=.2:raise ValueError('Stop distance/stagger outside bounded support route')
    old_ref=source['rows'][-1]['feet'][ref]
    if old_ref['mode']!='material-pivot-contact':raise ValueError('Source must finish in declared reference-foot stance')
    contacts={ref:{'vertex':old_ref['vertex'],'anchor':Vector(old_ref['anchor_world'])}};foot_rot={side:states[end_source-1]['feet'][side]['q'] for side in ['left','right']};floor=ground+body['travel']['sole_height']*h;tol=.0005*h;maximum_pivot=0.;minimum_gap=1e9;landing_starts={};previous={};rows=[];last_ankles={};last_q={};source_first=states[0]
    for obj in [arm,actor]:
        obj.animation_data_create();obj.animation_data.action=bpy.data.actions.new('External body remix / '+obj.name)
    scene.frame_start=first;scene.frame_end=last;scene.render.fps=plan['fps'];scene.render.fps_base=1
    for o in scene.objects:
        if o.type=='MESH' and o.data.shape_keys:o.data.shape_keys.animation_data_clear()
    bones={k:arm.pose.bones[v] for k,v in cfg['bones'].items()};gaze=cfg.get('gaze');eye=arm.pose.bones[gaze['control']] if gaze else None
    if eye and eye.name not in controls:controls.append(eye.name)
    # Add an owned story prop after source capture; no source appearance is used.
    owned_collection=bpy.data.collections.new('Owned story props');scene.collection.children.link(owned_collection)
    def own_prop(obj):
        for collection in list(obj.users_collection):collection.objects.unlink(obj)
        owned_collection.objects.link(obj);obj.hide_render=False;obj.hide_set(False);obj['owned_story_prop']=True
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24,ring_count=12,radius=cfg['prop']['radius_H']*h);orb=bpy.context.object;orb.name=cfg['prop']['name'];orb.data.materials.append(principled('Owned comic orb',cfg['prop']['color'],.7,0,1));own_prop(orb)
    radius=cfg['prop']['radius_H']*h
    for sign in [-1,1]:
        bpy.ops.mesh.primitive_uv_sphere_add(segments=12,ring_count=6,radius=radius*.12,location=(radius*.3*sign,-radius*.96,radius*.12));o=bpy.context.object;o.name='Owned orb eye';o.parent=orb;o.data.materials.append(principled('Owned orb eye',(.012,.02,.025),1));own_prop(o)
    transport=cfg.get('transport_arm_frames',False)
    if type(transport) is not bool:raise ValueError('Explicit boolean arm-frame transport required')
    arm_history={};maximum_transport_endpoint_error=0.
    def arm_frame(side):
        names=[cfg['bones'][side+s] for s in ['_arm','_elbow','_wrist']];joints=[arm.pose.bones[n] for n in names];world=[arm.matrix_world@b.matrix for b in joints];points=[m.translation for m in world]
        return {'q':[m.to_quaternion() for m in world[:2]],'directions':[(points[i+1]-points[i]).normalized() for i in range(2)]}
    def set_time(f):scene.frame_set(f);bpy.context.view_layer.update()
    def pole(side):
        raw=cfg['leg_poles'][side];return actor.matrix_world.translation+Vector((raw[0]*h,raw[1]*h,ground+raw[2]*h))
    def ankle_solve(side,target,q):
        solve_ankle(arm,legs[side],target,q,two_bone,h,pole(side))
    def lowest(side):return min(foot_points(selections,side),key=lambda row:row[2].z)
    def new_contact(side):
        name,index,point=lowest(side);contacts[side]={'vertex':[name,index],'anchor':Vector((point.x,point.y,floor))}
    def plant(side,q):
        nonlocal maximum_pivot
        contact=contacts[side];target=arm.matrix_world@arm.pose.bones[legs[side][2]].head;switches=0
        for _ in range(12):
            error=contact['anchor']-mesh_point(scene,contact['vertex'])
            if error.length>tol:target+=error;ankle_solve(side,target,q);continue
            name,index,point=lowest(side)
            if point.z<floor-tol:contact.update(vertex=[name,index],anchor=Vector((point.x,point.y,floor)));switches+=1;continue
            break
        gap=(mesh_point(scene,contact['vertex'])-contact['anchor']).length
        if gap>h*.003:raise ValueError('Stop contact did not converge at frame '+str(scene.frame_current)+' '+side+' '+str(gap))
        maximum_pivot=max(maximum_pivot,gap);return {'mode':'material-contact','vertex':contact['vertex'],'anchor':list(contact['anchor']),'error_m':gap,'pivot_switches':switches}
    def swing(side,start,end,u,q,arc):
        target=start.lerp(end,smooth(u));target.z+=arc*h*math.sin(math.pi*min(1,max(0,u)));ankle_solve(side,target,q);name,index,point=lowest(side)
        if point.z<floor or u>=1-1e-9:
            target.z+=floor-point.z;ankle_solve(side,target,q)
        return {'mode':'authored-swing','u':u,'target_ankle':list(target)}
    for f,state in enumerate(states,1):
        set_time(f);v=values(plan,f);w=v['source_weight'][0]
        for n in controls:
            if n in neutral:arm.pose.bones[n].matrix_basis=blend_basis(neutral[n],state['basis'][n],w)
        if f<=end_source:actor.location=state['root']
        else:
            u=min(1,(f-end_source)/(stop_end-end_source));actor.location=end_root+direction*distance*(2*u-u*u)
        bpy.context.view_layer.update()
        hips=arm.pose.bones[body['hips']];desired=hips.matrix.copy();desired.translation+=arm.matrix_world.to_3x3().inverted()@Vector((0,0,-v['crouch'][0]*h));hips.matrix_basis=hips.bone.convert_local_to_pose(desired,hips.bone.matrix_local,parent_matrix=hips.parent.matrix,parent_matrix_local=hips.parent.bone.matrix_local,invert=True)
        if f<=end_source and v['crouch'][0]==0 and (hips.location-state['basis'][body['hips']].to_translation()).length>1e-5:raise ValueError('Source center bob changed before authored crouch')
        for semantic,channel in cfg['overlay_channels'].items():
            b=bones[semantic];b.rotation_mode='QUATERNION';b.rotation_quaternion=b.matrix_basis.to_quaternion()@Euler(tuple(math.radians(x) for x in v[channel]),'XYZ').to_quaternion()
        bpy.context.view_layer.update();root_world=actor.matrix_world.translation;upper=v['upper_weight'][0]
        for side in ['left','right']:
            if upper>1e-6:
                arm_names=[cfg['bones'][side+s] for s in ['_arm','_elbow','_wrist']];saved={n:arm.pose.bones[n].matrix_basis.copy() for n in arm_names};hand=root_world+Vector((v[side+'_target'][0]*h,v[side+'_target'][1]*h,ground+v[side+'_target'][2]*h));elbow=root_world+Vector((cfg['arm_poles'][side][0]*h,cfg['arm_poles'][side][1]*h,ground+cfg['arm_poles'][side][2]*h));inv=arm.matrix_world.inverted();answer=two_bone(*[arm.pose.bones[n] for n in arm_names],inv@hand,inv@elbow,1)
                if answer['clamped']:raise ValueError('Authored arm target unreachable '+str(f)+' '+side+' '+json.dumps(answer))
                if transport:
                    desired=arm_frame(side);prior=arm_history.get(side,desired)
                    for index,name in enumerate(arm_names[:2]):
                        if prior['directions'][index].dot(desired['directions'][index])<-.99999:raise ValueError('Antipodal temporal arm step requires an authored intermediate pose')
                        q=prior['directions'][index].rotation_difference(desired['directions'][index])@prior['q'][index];orient_world(arm,arm.pose.bones[name],q)
                    error=(arm.matrix_world@arm.pose.bones[arm_names[2]].head-hand).length;maximum_transport_endpoint_error=max(maximum_transport_endpoint_error,error)
                    if error>h*.0001:raise ValueError('Transported arm frame changed required endpoint '+str(f)+' '+side+' '+str(error))
                for n in arm_names:arm.pose.bones[n].matrix_basis=blend_basis(saved[n],arm.pose.bones[n].matrix_basis,upper)
                bpy.context.view_layer.update()
                if 'hand_frame_from_wrist' in cfg:
                    finger=Vector(v[side+'_finger']).normalized();normal=Vector(v[side+'_normal']);normal-=finger*normal.dot(finger)
                    if normal.length<1e-6:raise ValueError('Hand finger/normal frame collapsed')
                    normal.normalize();x=finger.cross(normal).normalized();hand=Matrix((x,finger,normal)).transposed();desired_q=(hand@Matrix(cfg['hand_frame_from_wrist'][side]).to_3x3()).to_quaternion();wrist=bones[side+'_wrist'];current=(arm.matrix_world@wrist.matrix).to_quaternion();orient_world(arm,wrist,current.slerp(desired_q,upper))
        footrows={}
        if f>end_source:
            if f<=left_land:
                footrows[ref]=plant(ref,foot_rot[ref]);q=states[end_source-1]['feet'][other]['q'].slerp(neutral_feet[other]['q'],smooth((f-end_source)/(left_land-end_source)));footrows[other]=swing(other,states[end_source-1]['feet'][other]['ankle'],left_goal,(f-end_source)/(left_land-end_source),q,settings['landing_lift_H'])
                if f==left_land:new_contact(other);foot_rot[other]=q.copy();footrows[other]=plant(other,q);landing_starts[ref]=arm.matrix_world@arm.pose.bones[legs[ref][2]].head
            elif f<=stop_end:
                footrows[other]=plant(other,foot_rot[other]);q=foot_rot[ref].slerp(neutral_feet[ref]['q'],smooth((f-left_land)/(stop_end-left_land)));footrows[ref]=swing(ref,landing_starts[ref],right_goal,(f-left_land)/(stop_end-left_land),q,settings['landing_lift_H'])
                if f==stop_end:new_contact(ref);foot_rot[ref]=q.copy();footrows[ref]=plant(ref,q)
            elif f<recover_start:
                for side in ['left','right']:footrows[side]=plant(side,foot_rot[side])
            elif f<=recover_end:
                footrows[other]=plant(other,foot_rot[other])
                if f==recover_start:landing_starts['recover']=last_ankles[ref].copy()
                target=final_root+neutral_feet[ref]['ankle'];footrows[ref]=swing(ref,landing_starts['recover'],target,(f-recover_start)/(recover_end-recover_start),neutral_feet[ref]['q'],settings['recovery_lift_H'])
                if f==recover_end:new_contact(ref);foot_rot[ref]=neutral_feet[ref]['q'].copy();footrows[ref]=plant(ref,foot_rot[ref])
            else:
                for side in ['left','right']:footrows[side]=plant(side,foot_rot[side])
        else:
            for side in ['left','right']:footrows[side]={'mode':'retimed-source','source_time':state['source_time']}
        root_world=actor.matrix_world.translation;target=root_world+Vector((v['look'][0]*h,v['look'][1]*h,ground+v['look'][2]*h));head=bones['head'];saved=head.matrix_basis.copy();look_at(head,arm.matrix_world.inverted()@target,cfg['head_forward'],cfg['head_limit_degrees']);head.matrix_basis=blend_basis(saved,head.matrix_basis,v['look_weight'][0]);bpy.context.view_layer.update()
        if gaze:aim_existing_control(arm,gaze,arm.matrix_world.inverted()@target)
        for mesh in [o for o in scene.objects if o.type=='MESH' and o.data.shape_keys]:
            for channel,name in cfg['shapes'].items():
                block=mesh.data.shape_keys.key_blocks[name];block.value=v[channel][0];block.keyframe_insert('value',frame=f)
        orb.location=root_world+Vector((v['orb'][0]*h,v['orb'][1]*h,ground+v['orb'][2]*h));orb.scale=v['orb_scale'];orb.keyframe_insert('location',frame=f);orb.keyframe_insert('scale',frame=f);key_bones(arm,controls,f,previous);actor.keyframe_insert('location',frame=f);bpy.context.view_layer.update();bone_worlds(arm,arm.pose.bones.keys())
        for side in ['left','right']:
            gap=lowest(side)[2].z-floor;minimum_gap=min(minimum_gap,gap);footrows[side]['minimum_sole_gap_m']=gap;last_ankles[side]=arm.matrix_world@arm.pose.bones[legs[side][2]].head
        if transport:
            for side in ['left','right']:arm_history[side]=arm_frame(side)
        rows.append({'frame':f,'source_time':state['source_time'],'source_weight':w,'root':list(actor.location),'crouch_H':v['crouch'][0],'feet':footrows})
        if f%12==0:print('BODY_REMIX_FRAME',f,flush=True)
    scene['arm_frame_transport']=json.dumps({'enabled':transport,'maximum_endpoint_error_m':maximum_transport_endpoint_error})
    for obj in [arm,actor,orb]:linear_curves(obj.animation_data.action)
    if geometry_identity(scene,arm)!=identity or constraint_signature(arm)!=signature or sha(a.blend)!=original_hash or sha(a.neutral)!=neutral_hash:raise ValueError('Original rig/source data changed')
    for marker in list(scene.timeline_markers):scene.timeline_markers.remove(marker)
    for beat in document.get('beats',[]):scene.timeline_markers.new(beat['label'],frame=beat['frame'])
    scene['body_remix_plan']=json.dumps({'title':document.get('title'),'remix':settings,'beats':document.get('beats',[])},ensure_ascii=False);set_time(1);a.output.parent.mkdir(parents=True,exist_ok=True);bpy.ops.wm.save_as_mainfile(filepath=str(a.output.resolve()));report={'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'full-body-source-remix-saved-await-reopen-and-visuals','source_sha256':original_hash,'source_report_sha256':sha(a.source_report),'neutral_sha256':neutral_hash,'mapping_sha256':sha(a.mapping),'acting_plan_sha256':sha(a.acting_plan),'body_plan_sha256':sha(a.body_plan),'writer_sha256':sha(Path(__file__)),'dependencies':{name:sha(Path(__file__).with_name(name)) for name in ['acting_clip_plan.py','body_motion_runtime.py','body_approach_pose.py','build_performance.py','gaze_control.py']},'output_sha256':sha(a.output),'geometry_identity':identity,'frames':last,'fps':plan['fps'],'source_exit_speed_m_per_s':speed,'stop_distance_m':distance,'maximum_stop_contact_error_m':maximum_pivot,'minimum_sole_gap_m':minimum_gap,'source_rights':source['rights'],'rows':rows,'scope':'Starts already running. Source pose/time retimed and upper body overlaid, then two-step stop and planted reaction/recovery. Original rest/weights/morph geometry and source constraints retained. No continuous naturalness, dynamic balance or whole-body collision certification.'};a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8');print('BODY_REMIX_SAVED',str(a.output),flush=True)

if __name__=='__main__':main()
