"""Proportional FK fitting of reviewed node motion to an unanimated original rig."""
from pathlib import Path
import argparse,sys,json,math
sys.dont_write_bytecode=True;sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy,numpy as np
from mathutils import Matrix,Vector
from body_motion_plan import load_json,load_plan,prepare_source,sha,finite
from body_motion_runtime import character_rig,meshes_for,geometry_identity,select_feet,foot_points,orient_world,key_bones,linear_curves,bone_worlds,linked_inputs_unchanged,producer_hashes,require_current_producer
from build_performance import aim_bone

def fit(scene,character,plan,data):
    arm,actor=character_rig(scene);count=len(data['times']);h=finite(character['height'],'height',True)
    if count*len(arm.pose.bones)>500000:raise ValueError('Target bone-frame budget exceeded')
    matrix=np.asarray(arm.matrix_world.to_3x3())
    if not np.allclose(matrix@matrix.T,np.eye(3),atol=1e-6) or abs(np.linalg.det(matrix)-1)>1e-6:raise ValueError('Unit-scale proper armature world transform required')
    mappings=plan['body'];limbs=plan['limbs'];controls=[row['bone'] for row in mappings]+[n for row in limbs.values() for n in row['bones']];required=set(controls)|set(plan['scale_reference']['bones'])
    if any(n not in arm.pose.bones for n in required):raise ValueError('Mapped original bone missing')
    for item in limbs.values():
        chain=[arm.pose.bones[n] for n in item['bones']]
        if any(a not in b.parent_recursive for a,b in zip(chain,chain[1:])):raise ValueError('Limb mapping must follow original ancestor chains')
    before=geometry_identity(scene,arm);drivers=0
    for obj in scene.objects:
        ids=[obj]
        if obj.type=='MESH' and obj.data.shape_keys:ids.append(obj.data.shape_keys)
        for owner in ids:
            ad=owner.animation_data
            if ad:
                drivers+=len(ad.drivers)
                if len(ad.nla_tracks) or ad.action and any(len(c.keyframe_points) or len(c.sampled_points) for c in ad.action.fcurves):raise ValueError('Fresh unanimated import baseline required; existing animation is not discarded')
        if obj.type=='MESH' and obj.data.shape_keys:
            for key in obj.data.shape_keys.key_blocks:key.value=0
    muted=[]
    for side in ('left','right'):
        for name in limbs[side+'_leg']['bones'][1:3]:
            for constraint in arm.pose.bones[name].constraints:
                if constraint.type=='IK':muted.append({'bone':name,'constraint':constraint.name,'previous_mute':constraint.mute});constraint.mute=True
    if any(not c.mute and c.influence>0 and c.type=='IK' for side in ('left','right') for n in limbs[side+'_arm']['bones'] for c in arm.pose.bones[n].constraints):raise ValueError('Active arm IK is outside proportional FK route')
    for bone in arm.pose.bones:bone.rotation_mode='QUATERNION';bone.matrix_basis=Matrix.Identity(4)
    bpy.context.view_layer.update();rest={b.name:b.matrix.copy() for b in arm.pose.bones};ref=plan['scale_reference'];joints=[arm.matrix_world@arm.pose.bones[n].head for n in ref['bones']];source=data['reference'];nodes=ref['source']
    target_length=sum((b-a).length for a,b in zip(joints,joints[1:]));source_length=sum(np.linalg.norm(source[b,:3,3]-source[a,:3,3]) for a,b in zip(nodes,nodes[1:]))
    if not math.isfinite(source_length) or min(target_length,source_length)<1e-6:raise ValueError('Degenerate scale reference')
    scale=target_length/source_length
    if not 1e-6<=scale<=1e6:raise ValueError('Source/target scale ratio out of supported bounds')
    basis=np.asarray(plan['basis'],float);arm_rotation=arm.matrix_world.to_quaternion();previous={};rows=[];errors=[];selection=select_feet(scene,arm,plan)
    scene.frame_start=1;scene.frame_end=count;scene.render.fps=plan['fps'];scene.render.fps_base=1
    def rotation(index,name,world):
        delta=basis@world[index,:3,:3]@np.linalg.inv(source[index,:3,:3])@basis.T
        return Matrix(delta.tolist()).to_quaternion()@(arm_rotation@arm.pose.bones[name].bone.matrix_local.to_quaternion())
    for frame,world in enumerate(data['worlds'],1):
        scene.frame_set(frame)
        for bone in arm.pose.bones:bone.matrix_basis=Matrix.Identity(4)
        bpy.context.view_layer.update()
        for row in mappings:orient_world(arm,arm.pose.bones[row['bone']],rotation(row['source'],row['bone'],world))
        hips=arm.pose.bones[plan['hips']];index=next(row['source'] for row in mappings if row['bone']==hips.name);offset=arm.matrix_world.to_3x3().inverted()@Vector((basis@(world[index,:3,3]-source[index,:3,3])*scale).tolist())
        desired=hips.matrix.copy();desired.translation=rest[hips.name].translation+offset
        hips.matrix_basis=hips.bone.convert_local_to_pose(desired,hips.bone.matrix_local,parent_matrix=hips.parent.matrix if hips.parent else Matrix.Identity(4),parent_matrix_local=hips.parent.bone.matrix_local if hips.parent else Matrix.Identity(4),invert=True);bpy.context.view_layer.update()
        for item in limbs.values():
            names=item['bones'];indexes=item['source'];a,b,c=[arm.pose.bones[n] for n in names[:3]]
            for bone,child,start,end in ((a,b,indexes[0],indexes[1]),(b,c,indexes[1],indexes[2])):
                direction=arm.matrix_world.to_3x3().inverted()@Vector((basis@(world[end,:3,3]-world[start,:3,3])).tolist())
                if direction.length<1e-8:raise ValueError('Source limb segment collapsed')
                aim_bone(bone,direction,child.head-bone.head);bone.location=(0,0,0);bone.scale=(1,1,1);bpy.context.view_layer.update();errors.append(math.degrees((child.head-bone.head).angle(direction)))
            if len(names)==4:
                for name,index in zip(names[2:],indexes[2:]):orient_world(arm,arm.pose.bones[name],rotation(index,name,world))
        key_bones(arm,controls,frame,previous);bpy.context.view_layer.update();bone_worlds(arm,arm.pose.bones.keys())
        row={'frame':frame,'source_time':data['times'][frame-1],'feet':{}}
        for side,item in plan['feet'].items():
            ankle=limbs[side+'_leg']['bones'][2];row['feet'][side]={'minimum_z_H':min(p.z for _,_,p in foot_points(selection,side))/h,'ankle_world':list(arm.matrix_world@arm.pose.bones[ankle].head)}
        rows.append(row)
    if max(errors)>1:raise ValueError('Original constraints prevent source joint-direction fitting')
    linear_curves(arm.animation_data.action,controls)
    if geometry_identity(scene,arm)!=before:raise ValueError('Original rest/geometry/weights/morph data changed')
    scene.frame_set(1)
    return {'status':'proportional-body-FK-fitted-await-travel-contact-and-visuals','frames':count,'fps':plan['fps'],'geometry_identity':before,'controls':controls,'muted_leg_IK_in_new_scene':muted,'original_driver_count_retained':drivers,'target_scale_length':target_length,'source_scale_length':float(source_length),'world_scale_ratio':float(scale),'maximum_limb_direction_error_degrees':max(errors),'rows':rows,'rights':data['rights'],'source_input_sha256':data['source_hashes'],'scope':'Explicit torso rotations/root bob and proportional limb joint directions; source ankle/toe orientation, original wrist-relative orientation. No source mesh, skin, texture or logo. Original rest/weights/morph geometry retained. Declared leg IK constraints muted, drivers retained; no travel/footplant/stop/naturalness/cross-rig acceptance.'}

def main(arguments=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('baseline','character','plan','output','report'):parser.add_argument('--'+key,required=True,type=Path)
    a=parser.parse_args(arguments if arguments is not None else sys.argv[sys.argv.index('--')+1:]);paths={key:getattr(a,key).resolve() for key in ('baseline','character','plan','output','report')}
    if len(set(paths.values()))!=5 or paths['output'].suffix.lower()!='.blend' or paths['report'].suffix.lower()!='.json' or paths['output'].exists() or paths['report'].exists():raise ValueError('Distinct inputs and new blend/report outputs required')
    plan,files=load_plan(paths['plan']);data=prepare_source(plan,files);character=load_json(paths['character']);hashes={p:sha(p) for p in [paths['baseline'],paths['character'],paths['plan'],*files.values()]}
    bpy.ops.wm.open_mainfile(filepath=str(paths['baseline']),load_ui=False,use_scripts=False);result=fit(bpy.context.scene,character,plan,data);linked_inputs_unchanged(hashes)
    paths['output'].parent.mkdir(parents=True,exist_ok=True);paths['report'].parent.mkdir(parents=True,exist_ok=True);bpy.ops.wm.save_as_mainfile(filepath=str(paths['output']))
    result.update(schema=1,producer_sha256=producer_hashes(),input_scene_sha256=hashes[paths['baseline']],output_scene_sha256=sha(paths['output']),character_sha256=hashes[paths['character']],plan_sha256=hashes[paths['plan']],writer_sha256=sha(Path(__file__)),runtime_sha256=sha(Path(__file__).with_name('body_motion_runtime.py')),validator_sha256=sha(Path(__file__).with_name('body_motion_plan.py')))
    paths['report'].write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),'utf-8');print('BODY_FK_FIT',result['frames'],result['maximum_limb_direction_error_degrees'],flush=True)

if __name__=='__main__':main()
