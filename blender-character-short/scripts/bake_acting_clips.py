"""Bake externally composed acting onto an existing original rig, in a new scene."""
from pathlib import Path
import argparse,datetime,json,math,sys
sys.dont_write_bytecode=True;sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy,numpy as np
from mathutils import Matrix,Vector,Quaternion,Euler
from acting_clip_plan import compile_plan,values
from build_performance import two_bone,look_at,principled
from gaze_control import aim_existing_control
from hand_control_plan import profile
from hand_control_runtime import rigs,bind,sha,set_frame,geometry_signature,check_work

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for k in ['blend','mapping','hand-profile','plan','output','hand-motion','report']:p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);paths=[getattr(a,k).resolve() for k in ['blend','mapping','hand_profile','plan','output','hand_motion','report']]
    if len(set(paths))!=7 or any(p.exists() for p in [a.output,a.hand_motion,a.report]) or a.output.suffix!='.blend':raise ValueError('Preserve inputs and choose distinct new outputs')
    document=json.loads(a.plan.read_text('utf-8'));plan=compile_plan(document);cfg=json.loads(a.mapping.read_text('utf-8'));hp=profile(json.loads(a.hand_profile.read_text('utf-8')));h=float(cfg['height']);ground=float(cfg['ground'])
    if not math.isfinite(h) or not .1<h<10 or not math.isfinite(ground) or type(cfg['reference_frame']) is not int:raise ValueError('Finite source scale and integer reference required')
    first,last=plan['frames']
    if last-first+1>240:raise ValueError('This finger-export route supports at most240 frames')
    for name,width in {**{k:3 for k in ['left_target','left_pole','right_target','right_pole','look','eye_look','head_tilt','orb','orb_scale','orb_rotation']},'left_roll':1,'right_roll':1}.items():
        if name not in plan['channels'] or len(plan['channels'][name]['base'])!=width:raise ValueError('Missing or wrong-width acting channel: '+name)
    members=set();known={(j['id'],axis['id']) for j in hp['joints'] for axis in j['axes']}
    for group in cfg['finger_groups']:
        channel=plan['channels'].get(group['channel'])
        if channel is None or len(channel['base'])!=1 or channel['range'][0]<0 or channel['range'][1]>1:raise ValueError('Finger fractions require explicit0..1 scalar channels')
        for member in group['members']:
            key=tuple(member)
            if key not in known or key in members:raise ValueError('Unknown or multiply written finger channel')
            members.add(key)
    for channel in cfg.get('shapes',{}):
        if channel not in plan['channels'] or len(plan['channels'][channel]['base'])!=1 or plan['channels'][channel]['range'][0]<0 or plan['channels'][channel]['range'][1]>1:raise ValueError('Expression fractions require explicit0..1 scalar channels')
    source_sha=sha(a.blend);bpy.ops.wm.open_mainfile(filepath=str(a.blend.resolve()),load_ui=False,use_scripts=False);scene=bpy.context.scene;arm,meshes=rigs(scene);check_work(arm,meshes,scene,range(first,last+1));set_frame(scene,cfg['reference_frame']);bind(scene,hp)
    if arm.animation_data and any(not n.mute and n.strips for n in arm.animation_data.nla_tracks):raise ValueError('Active NLA requires another composition route')
    bones={k:arm.pose.bones[v] for k,v in cfg['bones'].items()};active=[bones[k] for k in ['spine','head','left_arm','left_elbow','left_wrist','right_arm','right_elbow','right_wrist']];gaze=cfg.get('gaze');eye=arm.pose.bones[gaze['control']] if gaze else None
    if any(not c.mute and c.influence>1e-8 for b in active for c in b.constraints):raise ValueError('Indirect active body controls need their own validated route')
    identity=geometry_signature(arm,meshes);bases={b.name:b.matrix_basis.copy() for b in arm.pose.bones};wrist_q={side:(arm.matrix_world@bones[side+'_wrist'].matrix).to_quaternion() for side in ['left','right']};inv=arm.matrix_world.inverted();arm_q=arm.matrix_world.to_quaternion();pos=lambda v:Vector((v[0]*h,v[1]*h,ground+v[2]*h))
    if arm.animation_data:arm.animation_data.action=None
    for b in arm.pose.bones:b.matrix_basis=bases[b.name]
    for semantic,angles in cfg.get('neutral_overrides',{}).items():
        b=bones[semantic];b.rotation_mode='QUATERNION';b.rotation_quaternion=Euler(tuple(math.radians(x) for x in angles)).to_quaternion();bases[b.name]=b.matrix_basis.copy()
    shape_maps={};shape_reference={}
    for mesh in meshes:
        if mesh.data.shape_keys:
            mesh.data.shape_keys.animation_data_clear()
            for block in mesh.data.shape_keys.key_blocks:shape_reference[mesh.name+'/'+block.name]=float(block.value)
            for channel,name in cfg.get('shapes',{}).items():
                if name not in mesh.data.shape_keys.key_blocks:raise ValueError('Mapped expression is missing: '+name)
                shape_maps[channel]=mesh.data.shape_keys.key_blocks[name]
    for o in list(scene.objects):
        if o.type in ['CAMERA','LIGHT'] or (o.type in ['MESH','CURVE'] and o not in meshes):o.hide_render=True;o.hide_set(True)
    radius=h*float(cfg['prop']['radius_H'])
    if not 0<radius<h*.1:raise ValueError('Small prop radius required')
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24,ring_count=12,radius=radius);prop=bpy.context.object;prop.name=cfg['prop']['name'];mat=principled('Owned comic orb',cfg['prop']['color'],.4,0,1.0);prop.data.materials.append(mat)
    for face in prop.data.polygons:face.use_smooth=True
    for side in [-1,1]:
        bpy.ops.mesh.primitive_uv_sphere_add(segments=12,ring_count=6,radius=radius*.12,location=(radius*.3*side,-radius*.96,radius*.12));o=bpy.context.object;o.name='Owned orb eye';o.parent=prop;o.data.materials.append(principled('Owned orb eye',(.012,.02,.025),1))
    scene.frame_start=first;scene.frame_end=last;scene.render.fps=plan['fps'];scene.render.fps_base=1;previous={};rows=[];paths=set()
    for f in range(first,last+1):
        set_frame(scene,f);v=values(plan,f)
        for b in active:b.matrix_basis=bases[b.name]
        for semantic,channel in cfg.get('rotation_channels',{}).items():
            b=bones[semantic];b.rotation_mode='QUATERNION';b.rotation_quaternion=bases[b.name].to_quaternion()@Euler(tuple(math.radians(x) for x in v[channel]),'XYZ').to_quaternion()
        bpy.context.view_layer.update();rec={'frame':f,'hands':{}}
        for side in ['left','right']:
            target=pos(v[side+'_target']);pole=pos(v[side+'_pole']);answer=two_bone(bones[side+'_arm'],bones[side+'_elbow'],bones[side+'_wrist'],inv@target,inv@pole,1)
            rec['hands'][side]=answer
            if answer['clamped'] or answer['endpoint_error']>h*.002:raise ValueError('Unreachable required acting target at frame '+str(f)+' '+side)
            b=bones[side+'_wrist'];q=Quaternion(cfg['wrist_roll_axes_world'][side],math.radians(v[side+'_roll'][0]))@wrist_q[side];desired=Matrix.Translation(b.head)@(arm_q.inverted()@q).to_matrix().to_4x4();b.matrix_basis=b.bone.convert_local_to_pose(desired,b.bone.matrix_local,parent_matrix=b.parent.matrix,parent_matrix_local=b.parent.bone.matrix_local,invert=True);bpy.context.view_layer.update()
        look_at(bones['head'],inv@pos(v['look']),cfg['head_forward'],cfg['head_limit_degrees']);b=bones['head'];b.rotation_quaternion=b.matrix_basis.to_quaternion()@Euler(tuple(math.radians(x) for x in v['head_tilt']),'XYZ').to_quaternion();bpy.context.view_layer.update()
        if gaze:rec['gaze']=aim_existing_control(arm,gaze,inv@pos(v['eye_look']))
        for b in active+([eye] if eye else []):
            b.rotation_mode='QUATERNION';q=b.rotation_quaternion.copy()
            if b.name in previous and q.dot(previous[b.name])<0:q.negate()
            b.rotation_quaternion=q;previous[b.name]=q.copy();b.keyframe_insert('rotation_quaternion',frame=f);paths.add(b.path_from_id('rotation_quaternion'))
        prop.location=pos(v['orb']);prop.scale=v['orb_scale'];prop.rotation_euler=tuple(math.radians(x) for x in v['orb_rotation'])
        for field in ['location','scale','rotation_euler']:prop.keyframe_insert(field,frame=f)
        for channel,block in shape_maps.items():block.value=v[channel][0];block.keyframe_insert('value',frame=f)
        rec.update(head_world=list(arm.matrix_world@bones['head'].head),left_world=list(arm.matrix_world@bones['left_wrist'].head),right_world=list(arm.matrix_world@bones['right_wrist'].head),orb=list(prop.location),eyes_world={side:list((arm.matrix_world@arm.pose.bones[gaze[side]].matrix).to_quaternion()) for side in ['left','right']} if gaze else {});rows.append(rec)
        if (f-first)%48==0:print('ACTING_BAKE',f,flush=True)
    def linear(data):
        if data.animation_data and data.animation_data.action:
            for layer in data.animation_data.action.layers:
                for strip in layer.strips:
                    for bag in strip.channelbags:
                        for fc in bag.fcurves:
                            for k in fc.keyframe_points:k.interpolation='LINEAR'
    for data in [arm,prop]+[o.data.shape_keys for o in meshes if o.data.shape_keys]:linear(data)
    for marker in list(scene.timeline_markers):scene.timeline_markers.remove(marker)
    for beat in document.get('beats',[]):scene.timeline_markers.new(beat['label'],frame=beat['frame'])
    camera=bpy.data.objects.new('Acting inspection camera',bpy.data.cameras.new('Acting inspection camera'));scene.collection.objects.link(camera);camera.location=pos(cfg['camera']['location']);camera.rotation_euler=(pos(cfg['camera']['target'])-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.type='ORTHO';camera.data.ortho_scale=h*cfg['camera']['scale_H'];scene.camera=camera;scene['acting_plan']=json.dumps({'title':document.get('title'),'beats':document.get('beats',[]),'instances':document['instances']},ensure_ascii=False)
    channels=[];known={(j['id'],axis['id']) for j in hp['joints'] for axis in j['axes']}
    for group in cfg['finger_groups']:
        for joint,axis in group['members']:
            if (joint,axis) not in known:raise ValueError('Unknown external finger group member')
            channels.append({'joint':joint,'axis':axis,'keys':[[f,values(plan,f)[group['channel']][0]] for f in range(first,last+1)]})
    hand_motion={'schema':1,'frames':[first,last],'fps':plan['fps'],'channels':channels}
    if geometry_signature(arm,meshes)!=identity or sha(a.blend)!=source_sha:raise ValueError('Original geometry/source changed')
    set_frame(scene,first);a.output.parent.mkdir(parents=True,exist_ok=True);bpy.ops.wm.save_as_mainfile(filepath=str(a.output.resolve()));a.hand_motion.write_text(json.dumps(hand_motion,ensure_ascii=False,indent=2),'utf-8')
    report={'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'new-body-prop-acting-saved-await-finger-layer-and-reopen','source_sha256':source_sha,'output_sha256':sha(a.output),'mapping_sha256':sha(a.mapping),'plan_sha256':sha(a.plan),'hand_profile_sha256':sha(a.hand_profile),'hand_motion_sha256':sha(a.hand_motion),'writer_sha256':sha(Path(__file__)),'clip_module_sha256':sha(Path(__file__).with_name('acting_clip_plan.py')),'geometry_signature':identity,'frames':[first,last],'fps':plan['fps'],'active_body_bones':[b.name for b in active]+([eye.name] if eye else []),'rest_pose_source_frame':cfg['reference_frame'],'source_unchanged':True,'rows':rows,'scope':'External retimed clip values baked to original FK, existing binocular control, original morphs and own animated orb. Original rig/skin unchanged; other bones fixed at reference. No library full-body retargeting, dynamics or naturalness claim.'}
    a.report.write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8');print('ACTING_BODY_SAVED',str(a.output),flush=True)

if __name__=='__main__':main()
