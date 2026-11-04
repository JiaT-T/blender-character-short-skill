"""Configured pose/prop operations for a bounded approach-to-authored transition."""
import math
import bpy
from mathutils import Matrix,Vector,Quaternion
from body_motion_runtime import orient_world

def smooth(value):
    value=max(0.,min(1.,value));return value*value*(3-2*value)

def blend_basis(a,b,weight):
    pa,qa,sa=a.decompose();pb,qb,sb=b.decompose()
    return Matrix.LocRotScale(pa.lerp(pb,weight),qa.slerp(qb,weight),sa.lerp(sb,weight))

def keyed_bones(arm):
    if not arm.animation_data or not arm.animation_data.action:return set()
    prefixes={bone.name:bone.path_from_id()+'.' for bone in arm.pose.bones}
    result=set()
    for curve in arm.animation_data.action.fcurves:
        names=[name for name,prefix in prefixes.items() if curve.data_path.startswith(prefix)]
        if len(names)!=1:raise ValueError('Approach input action may contain only existing bone channels')
        suffix=curve.data_path[len(prefixes[names[0]]):]
        if suffix not in ('location','rotation_quaternion'):raise ValueError('Only keyed bone quaternion/location channels are supported; other authored channels are not discarded')
        result.add(names[0])
    return result

def constraint_signature(arm):
    result=[]
    for bone in arm.pose.bones:
        for constraint in bone.constraints:
            values={'bone':bone.name,'name':constraint.name,'type':constraint.type}
            for prop in constraint.bl_rna.properties:
                key=prop.identifier
                if prop.is_readonly or key in ('name','type','show_expanded','active'):continue
                value=getattr(constraint,key)
                if prop.type=='COLLECTION':
                    if len(value):raise ValueError('Multi-target constraint collections are unsupported')
                    continue
                if prop.type=='POINTER':
                    if value is not None and not isinstance(value,bpy.types.ID):raise ValueError('Unsupported constraint configuration pointer')
                    values[key]=value.name if value is not None else None
                elif getattr(prop,'is_array',False):
                    import numpy as np
                    array=np.asarray(value)
                    if not np.isfinite(array).all():raise ValueError('Nonfinite original constraint configuration')
                    values[key]=array.tolist()
                elif prop.type in ('BOOLEAN','INT','FLOAT','STRING','ENUM'):
                    if prop.type=='FLOAT' and not math.isfinite(value):raise ValueError('Nonfinite original constraint configuration')
                    values[key]=value
            result.append(values)
    return result

def mesh_point(scene,key):
    obj=scene.objects[key[0]];ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh()
    try:return ev.matrix_world@mesh.vertices[key[1]].co
    finally:ev.to_mesh_clear()

def solve_ankle(arm,names,target,rotation,solver,height,pole):
    a,b,c=[arm.pose.bones[n] for n in names];inverse=arm.matrix_world.inverted();answer=solver(a,b,c,inverse@target,inverse@pole,reach_fraction=1)
    if answer['clamped']:raise ValueError('Transition ankle unreachable at frame'+str(bpy.context.scene.frame_current)+': '+str(answer))
    orient_world(arm,c,rotation)
    return arm.matrix_world@c.head

def aim_head(arm,character,target,authored_rotation,restore):
    head=arm.pose.bones[character['bones']['head']];control=arm.pose.bones[character['gaze']['control']];control.matrix_basis=Matrix.Identity(4);forward=Vector(character['gaze']['forward']).normalized();limit=math.radians(character['head_angle_limit'])
    for iteration in range(6):
        bpy.context.view_layer.update();eyes=[arm.pose.bones[character['gaze'][side]] for side in ('left','right')];origin=arm.matrix_world@((eyes[0].head+eyes[1].head)*.5);delta_world=target-origin
        if delta_world.length<1e-8:raise ValueError('Head target coincides with actual eye pivot')
        direction=(arm.matrix_world.to_3x3().inverted()@delta_world).normalized();delta=forward.rotation_difference(direction)
        if delta.angle>limit:delta=Quaternion().slerp(delta,limit/delta.angle)
        desired=(delta@head.bone.matrix_local.to_quaternion()).slerp(authored_rotation,restore);orient_world(arm,head,arm.matrix_world.to_quaternion()@desired)

def restore_prop(prop,story,height,ground,fps,end):
    if prop.animation_data and (len(prop.animation_data.drivers) or len(prop.animation_data.nla_tracks)):raise ValueError('Driven/NLA props are unsupported')
    if prop.animation_data:prop.animation_data.action=None
    for key in story['prop']['keys']:
        frame=max(1,min(end,round(key['t']*fps)+1));p=key['p'];prop.location=(p[0]*height,p[1]*height,ground+p[2]*height);prop.rotation_euler=tuple(math.radians(v) for v in key.get('rotation',[0,0,0]));prop.keyframe_insert('location',frame=frame);prop.keyframe_insert('rotation_euler',frame=frame)
    for curve in prop.animation_data.action.fcurves:
        for key in curve.keyframe_points:key.interpolation='BEZIER';key.handle_left_type='AUTO_CLAMPED';key.handle_right_type='AUTO_CLAMPED'
