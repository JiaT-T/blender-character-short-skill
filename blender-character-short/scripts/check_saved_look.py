"""Bounded real-camera/shape/head checks of a saved look; no UI or source save."""
from pathlib import Path
import argparse,sys,json,hashlib,math,datetime
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy,numpy as np
from mathutils import Vector,Quaternion
from production_contract import declared_file,sha,write_json
from render_device_policy import prepare_render,render_with_policy

def geometry(ob,attribute=None):
    evaluated=ob.evaluated_get(bpy.context.evaluated_depsgraph_get());m=evaluated.to_mesh()
    try:
        a=np.empty(len(m.vertices)*3,np.float32);m.vertices.foreach_get('co',a);d={'vertices':len(m.vertices),'positions_sha256':hashlib.sha256(a.tobytes()).hexdigest(),'finite':bool(np.isfinite(a).all())}
        if attribute:
            mask=np.empty(len(m.vertices),np.float32);m.attributes[attribute].data.foreach_get('value',mask);d.update(mask_sha256=hashlib.sha256(mask.tobytes()).hexdigest(),mask_positive=int((mask>.5).sum()),mask_finite=bool(np.isfinite(mask).all()))
        return d
    finally:evaluated.to_mesh_clear()
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);file=Path(a.plan).resolve();plan=json.loads(file.read_text('utf-8'));base=file.parent;source=declared_file(plan['source'],base);pf=declared_file(plan['profile'],base);profile=json.loads(Path(pf['path']).read_text('utf-8'));out=(base/plan['output']).resolve();out.mkdir(parents=True,exist_ok=False)
    bpy.ops.wm.open_mainfile(filepath=source['path'],load_ui=False,use_scripts=False);scene=bpy.context.scene
    if scene.render.engine!='BLENDER_EEVEE_NEXT':raise ValueError('Eevee saved look required')
    rig=bpy.data.objects[profile['controller']];arm=bpy.data.objects[profile['model']];mesh=bpy.data.objects[profile['mesh']];head=rig.pose.bones[profile['head_control']];blink=mesh.data.shape_keys.key_blocks[profile['blink_shape']];display=bpy.data.objects[profile['display_helper']];shadow=bpy.data.objects[profile['shadow_helper']]
    head_state={k:(getattr(head,k).copy() if hasattr(getattr(head,k),'copy') else tuple(getattr(head,k)) if k=='rotation_axis_angle' else getattr(head,k)) for k in ['rotation_mode','rotation_euler','rotation_quaternion','rotation_axis_angle','location','scale']};q=head.matrix_basis.to_quaternion();old_blink=blink.value;old_cam=scene.camera;old_frame=scene.frame_current
    inverse=(rig.matrix_world@head.matrix).to_3x3().inverted();axes=[(inverse@Vector(v)).normalized() for v in [(0,0,1),(1,0,0),(0,-1,0)]]
    body_response=None
    if not plan.get('reference') and 'baseline_profile' in plan:
        from mmd_baseline import controls_report
        bp=declared_file(plan['baseline_profile'],base);body_response=controls_report(json.loads(Path(bp['path']).read_text('utf-8')))
        if not body_response['all_passed']:raise ValueError('Actual controller response regressed after look transfer')
    face=next(m for m in mesh.data.materials if m.get('hx_original_slot')==profile['face_slot']);device=prepare_render(scene);scene.render.resolution_x=profile['size'][0];scene.render.resolution_y=profile['size'][1];scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGBA';scene.render.image_settings.color_depth='8';scene.render.film_transparent=True;scene.eevee.taa_render_samples=profile['samples'];scene.eevee.shadow_pool_size=str(profile['shadow_pool_mib']);rows=[]
    try:
        for case in profile['cases']:
            scene.frame_set(old_frame);scene.camera=bpy.data.objects[case['camera']];head.rotation_mode='QUATERNION';head.rotation_quaternion=q@Quaternion(axes[0],math.radians(case.get('yaw',0)))@Quaternion(axes[1],math.radians(case.get('pitch',0)))@Quaternion(axes[2],math.radians(case.get('roll',0)));blink.value=case.get('blink',0)
            rig.update_tag();arm.update_tag();mesh.update_tag(refresh={'DATA'});bpy.context.view_layer.update();display_state=geometry(display,profile['receiver_attribute']);shadow_state=geometry(shadow)
            ev=arm.evaluated_get(bpy.context.evaluated_depsgraph_get());bone=ev.pose.bones[profile['head_model_bone']];rot=(ev.matrix_world.to_3x3()@bone.matrix.to_3x3()@bone.bone.matrix_local.to_3x3().inverted()).to_quaternion();errors=[]
            for node,axis in profile['face_axes'].items():
                actual=Vector([face.node_tree.nodes[node].inputs[j].default_value for j in range(3)]);expected=(rot@Vector(axis)).normalized();errors.append(max(abs(actual[j]-expected[j]) for j in range(3)))
            if max(errors)>=2e-5 or not display_state['finite'] or not display_state['mask_finite'] or not shadow_state['finite']:raise ValueError('Look driver/helper geometry failed: '+case['id'])
            target=out/(case['id']+'.png');scene.render.filepath=str(target);render_with_policy(write_still=True);rows.append({'id':case['id'],'camera':scene.camera.name,'case':case,'file':str(target),'sha256':sha(target),'display':display_state,'shadow':shadow_state,'face_axis_error':max(errors)});write_json(out/'progress.json',{'complete':False,'cases':rows})
    finally:
        for key,value in head_state.items():setattr(head,key,value)
        blink.value=old_blink;scene.camera=old_cam;scene.frame_set(old_frame);rig.update_tag();arm.update_tag();mesh.update_tag(refresh={'DATA'});bpy.context.view_layer.update()
    by={r['id']:r for r in rows};checks={'active_camera_changes_receiver':by['front']['display']['mask_sha256']!=by['side']['display']['mask_sha256'],'front_restore_receiver_exact':by['front']['display']['mask_sha256']==by['front-return']['display']['mask_sha256'],'blink_changes_receiver':by['front']['display']['mask_sha256']!=by['closed']['display']['mask_sha256'],'head_turn_moves_helper':by['front']['display']['positions_sha256']!=by['turn']['display']['positions_sha256'],'source_unchanged':sha(source['path'])==source['sha256']}
    result={'accepted_technical':all(checks.values()),'checks':checks,'source':source,'profile':pf,'cases':rows,'device':device,'body_response_after_look':body_response,'normal_speed_visual_acceptance':False,'source_website_pixel_parity':False,'requires_actual_image_review':True,'ui_used':False,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat()};write_json(out/'checks.json',result)
    if not result['accepted_technical']:raise ValueError('Saved look behavior checks failed')
    print('SAVED_LOOK_CASES_COMPLETE',len(rows),str(out))
if __name__=='__main__':main()
