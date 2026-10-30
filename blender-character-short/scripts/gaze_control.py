"""Aim an existing binocular control using an actual two-eye pivot.

The character mapping supplies all bone names and rest-forward/angle limits.
This preserves the rig's existing constraint route; it does not create or replace
eye constraints. Verify actual deformation and rendered iris movement per rig.
"""
import math
import bpy
from mathutils import Vector,Matrix,Quaternion

def aim_existing_control(arm,config,target):
    required=('control','left','right','forward','max_angle')
    if any(key not in config for key in required):raise ValueError('Gaze mapping requires control, left, right, forward and max_angle')
    for key in ('control','left','right'):
        if config[key] not in arm.pose.bones:raise ValueError('Gaze bone missing: '+config[key])
    limit=math.radians(float(config['max_angle']))
    if not 0<limit<=math.pi/4:raise ValueError('Gaze max_angle must be in (0,45] degrees; actual rig needs visual calibration')
    control=arm.pose.bones[config['control']];left=arm.pose.bones[config['left']];right=arm.pose.bones[config['right']]
    control.matrix_basis=Matrix.Identity(4);bpy.context.view_layer.update()
    origin=(left.head+right.head)*.5;direction=Vector(target)-origin
    if direction.length<1e-7:raise ValueError('Gaze target coincides with eye pivot')
    forward=Vector(config['forward'])
    if forward.length<1e-7:raise ValueError('Gaze rest-forward is zero')
    current=(control.matrix.to_3x3()@control.bone.matrix_local.to_3x3().inverted()@forward).normalized()
    desired=direction.normalized();delta=current.rotation_difference(desired);requested=delta.angle
    if delta.angle>limit:delta=Quaternion().slerp(delta,limit/delta.angle)
    q=delta@control.matrix.to_quaternion();matrix=Matrix.Translation(control.head)@q.to_matrix().to_4x4()
    control.matrix_basis=control.bone.convert_local_to_pose(matrix,control.bone.matrix_local,parent_matrix=control.parent.matrix if control.parent else Matrix.Identity(4),parent_matrix_local=control.parent.bone.matrix_local if control.parent else Matrix.Identity(4),invert=True)
    bpy.context.view_layer.update()
    return {'origin':list(origin),'target':list(target),'requested_degrees':math.degrees(requested),'applied_degrees':math.degrees(delta.angle),'clamped':requested>limit,'note':'Control aim; actual eye constraints and iris appearance require per-character visual validation'}
