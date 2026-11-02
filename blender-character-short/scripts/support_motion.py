"""Opt-in stationary foot support on existing deform bones, baked each frame.

This FK route explicitly mutes the configured knees/ankles' original IK in
the new production scene. It is not locomotion or a claim of original-IK parity.
The source asset, weights and baseline remain unchanged.
"""
import math
import bpy
from mathutils import Vector, Matrix


def bake_support(scene, arm, configuration, solve_two_bone, height, ground):
    if not configuration:
        return {'status': 'not-requested'}
    legs=[]
    inv=arm.matrix_world.inverted()
    def position(value):
        if len(value)!=3 or not all(math.isfinite(float(v)) for v in value):
            raise ValueError('Support target/pole requires three finite values')
        return inv@Vector((value[0]*height,value[1]*height,ground+value[2]*height))
    disabled=[]
    for side,item in configuration.items():
        chain=[arm.pose.bones.get(item[k]) for k in ('upper','knee','ankle')]
        if any(bone is None for bone in chain):
            raise ValueError('Invalid support bone mapping for '+side)
        upper,knee,ankle=chain
        if knee.parent!=upper or ankle.parent!=knee:
            raise ValueError('Support requires a direct upper/knee/ankle chain')
        for bone in (knee,ankle):
            for constraint in bone.constraints:
                if constraint.type=='IK':
                    disabled.append({'bone':bone.name,'constraint':constraint.name,
                                     'previous_mute':constraint.mute})
                    constraint.mute=True
        legs.append((side,chain,position(item['target']),position(item['pole']),
                     ankle.bone.matrix_local.to_quaternion()))
    previous={}
    records=[]
    for frame in range(scene.frame_start,scene.frame_end+1):
        scene.frame_set(frame)
        for side,chain,target,pole,rest_rotation in legs:
            upper,knee,ankle=chain
            for bone in chain:bone.matrix_basis=Matrix.Identity(4)
            bpy.context.view_layer.update()
            result=solve_two_bone(upper,knee,ankle,target,pole,reach_fraction=1)
            desired=Matrix.Translation(ankle.head)@rest_rotation.to_matrix().to_4x4()
            ankle.matrix_basis=ankle.bone.convert_local_to_pose(
                desired,ankle.bone.matrix_local,parent_matrix=knee.matrix,
                parent_matrix_local=knee.bone.matrix_local,invert=True)
            bpy.context.view_layer.update()
            # Use only the linear part for a direction/error vector.
            error=(arm.matrix_world.to_3x3()@(ankle.head-target)).length/height
            if error>.0001 or result['clamped']:
                raise ValueError(f'Unreachable planted foot {side} at {frame}: {error:.7f}H')
            for bone in chain:
                bone.rotation_mode='QUATERNION'
                q=bone.rotation_quaternion.copy()
                if bone.name in previous and q.dot(previous[bone.name])<0:q.negate()
                bone.rotation_quaternion=q
                previous[bone.name]=q.copy()
                bone.keyframe_insert('rotation_quaternion',frame=frame)
                bone.keyframe_insert('location',frame=frame)
            records.append({'frame':frame,'side':side,'target_error_height':error})
    # Per-frame support keys must not overshoot between integer frames.
    supported={bone.name for _,chain,*_ in legs for bone in chain}
    for curve in arm.animation_data.action.fcurves:
        if any(curve.data_path.startswith('pose.bones["'+name+'"]') for name in supported):
            for key in curve.keyframe_points:key.interpolation='LINEAR'
    return {'status':'baked-stationary-FK','frames':scene.frame_end-scene.frame_start+1,
            'original_ik_muted':disabled,
            'maximum_target_error_height':max(r['target_error_height'] for r in records),
            'scope':'Configured stationary ankle heads and rest ankle orientation, integer frames only; inspect visible soles, knees and costume separately.'}
