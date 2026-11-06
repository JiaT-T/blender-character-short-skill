"""Shared evaluated-rig operations for the explicitly configured body route."""
import hashlib,json,math
from pathlib import Path
import bpy,numpy as np
from mathutils import Matrix,Vector

def character_rig(scene):
    arms=[o for o in scene.objects if o.type=='ARMATURE']
    if len(arms)!=1 or len(arms[0].pose.bones)>2048:raise ValueError('One character armature with at most2048 bones required')
    arm=arms[0];actor=arm
    while actor.parent is not None:actor=actor.parent
    if actor==arm or actor.type!='EMPTY' or len(actor.constraints) or not np.allclose(np.asarray(actor.matrix_world.to_3x3()),np.eye(3),atol=1e-6):raise ValueError('An unconstrained unit-axis actor root is required')
    return arm,actor

def meshes_for(scene,arm):return [o for o in scene.objects if o.type=='MESH' and any(m.type=='ARMATURE' and m.object==arm for m in o.modifiers)]

def geometry_identity(scene,arm):
    digest=hashlib.sha256()
    rest=[(b.name,b.parent.name if b.parent else None,list(map(list,b.matrix_local))) for b in arm.data.bones]
    digest.update(json.dumps(rest,ensure_ascii=False).encode())
    for obj in sorted(meshes_for(scene,arm),key=lambda o:o.name):
        digest.update(obj.name.encode());digest.update(np.asarray([v.co[:] for v in obj.data.vertices],dtype=np.float32).tobytes())
        digest.update(json.dumps([[(g.group,g.weight) for g in v.groups] for v in obj.data.vertices]).encode())
        digest.update(json.dumps([(g.name,g.index) for g in obj.vertex_groups]).encode())
        digest.update(json.dumps([list(p.vertices) for p in obj.data.polygons]).encode())
        if obj.data.shape_keys:
            for key in obj.data.shape_keys.key_blocks:
                digest.update(key.name.encode());digest.update(np.asarray([v.co[:] for v in key.data],dtype=np.float32).tobytes())
    return digest.hexdigest()

def select_feet(scene,arm,plan):
    result={}
    for side,item in plan['feet'].items():
        name=item['deform_root']
        if name not in arm.pose.bones:raise ValueError('Missing actual foot deform root: '+name)
        bone=arm.pose.bones[name];names={name,*[b.name for b in bone.children_recursive]};entries=[]
        for obj in meshes_for(scene,arm):
            groups={g.index for g in obj.vertex_groups if g.name in names}
            indices=[v.index for v in obj.data.vertices if sum(g.weight for g in v.groups if g.group in groups)>=plan['weight_threshold']]
            if indices:entries.append((obj,indices))
        if not entries:raise ValueError('No selected weighted foot vertices: '+side)
        result[side]=entries
    return result

def foot_points(selections,side):
    result=[];dg=bpy.context.evaluated_depsgraph_get()
    for obj,indices in selections[side]:
        ev=obj.evaluated_get(dg);mesh=ev.to_mesh()
        try:
            if len(mesh.vertices)!=len(obj.data.vertices):raise ValueError('Foot material-point operations require unchanged vertex topology')
            result.extend((obj.name,index,ev.matrix_world@mesh.vertices[index].co) for index in indices)
        finally:ev.to_mesh_clear()
    if not all(math.isfinite(v) for _,_,p in result for v in p):raise ValueError('Nonfinite evaluated foot vertex')
    return result

def orient_world(arm,bone,world_rotation):
    quaternion=arm.matrix_world.to_quaternion().inverted()@world_rotation
    desired=Matrix.Translation(bone.head)@quaternion.to_matrix().to_4x4()
    bone.matrix_basis=bone.bone.convert_local_to_pose(desired,bone.bone.matrix_local,parent_matrix=bone.parent.matrix if bone.parent else Matrix.Identity(4),parent_matrix_local=bone.parent.bone.matrix_local if bone.parent else Matrix.Identity(4),invert=True)
    bpy.context.view_layer.update()

def key_bones(arm,names,frame,previous):
    for name in names:
        bone=arm.pose.bones[name];bone.rotation_mode='QUATERNION';q=bone.rotation_quaternion.copy()
        if name in previous and q.dot(previous[name])<0:q.negate()
        if not all(math.isfinite(v) for v in [*q,*bone.location,*bone.scale]):raise ValueError('Nonfinite target bone transform')
        bone.rotation_quaternion=q;previous[name]=q.copy();bone.keyframe_insert('rotation_quaternion',frame=frame);bone.keyframe_insert('location',frame=frame)

def linear_curves(action,names=None):
    for curve in action.fcurves:
        if names is None or any(curve.data_path.startswith('pose.bones["'+n+'"]') for n in names):
            for key in curve.keyframe_points:key.interpolation='LINEAR'

def bone_worlds(arm,names):
    value=np.asarray([list(map(list,arm.matrix_world@arm.pose.bones[name].matrix)) for name in names])
    if not np.isfinite(value).all():raise ValueError('Nonfinite evaluated target bone world matrix')
    return value

def linked_inputs_unchanged(hashes):
    from body_motion_plan import sha
    if any(sha(path)!=value for path,value in hashes.items()):raise ValueError('An input changed during body adaptation')

def producer_hashes():
    from body_motion_plan import sha,BODY_PRODUCER_NAMES
    return {name:sha(Path(__file__).with_name(name)) for name in BODY_PRODUCER_NAMES}

def require_current_producer(record):
    if record.get('producer_sha256')!=producer_hashes():raise ValueError('Body stage producer/dependency bytes changed; preserve this version and rebuild in a clean directory')
