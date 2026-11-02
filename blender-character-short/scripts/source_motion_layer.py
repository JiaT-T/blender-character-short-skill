"""Bake explicitly mapped, rotation-only source variation over authored acting."""
import hashlib,json,math
from pathlib import Path
import bpy,numpy as np
from mathutils import Matrix,Quaternion
from source_motion import decode_clip,node_worlds


def smooth(value):
    value=max(0.,min(1.,value));return value*value*(3-2*value)


def bake_source_layers(scene,arm,character,layers,fps,time_scale):
    if not layers:return {'status':'not-requested'}
    prepared=[];targets={}
    for layer in layers:
        clip_path=Path(layer['clip']).resolve();skeleton_path=Path(layer['skeleton']).resolve()
        clip_raw=clip_path.read_bytes();skeleton_raw=skeleton_path.read_bytes()
        clip=json.loads(clip_raw);skeleton=json.loads(skeleton_raw);tracks=decode_clip(clip)
        basis=np.asarray(layer['basis'],dtype=float)
        if basis.shape!=(3,3) or not np.isfinite(basis).all() or not np.allclose(basis@basis.T,np.eye(3),atol=1e-6) or np.linalg.det(basis)<.999:
            raise ValueError('Source motion basis must be a proper rotation')
        mapping={semantic:int(index) for semantic,index in layer['mapping'].items()}
        for semantic,index in mapping.items():
            if semantic not in character['bones'] or not 0<=index<len(skeleton['nodes']):
                raise ValueError('Invalid explicit source-motion mapping')
            targets[semantic]=arm.pose.bones[character['bones'][semantic]]
        start=float(layer['start'])*time_scale;end=float(layer['end'])*time_scale
        blend_in=float(layer.get('blend_in',0))*time_scale
        blend_out=float(layer.get('blend_out',0))*time_scale
        strength=float(layer.get('strength',1));speed=float(layer.get('speed',1))
        duration=float(layer['duration']);reference=float(layer.get('reference_time',0));phase=float(layer.get('phase',0))
        if not mapping:raise ValueError('Source-motion mapping must be nonempty')
        if not all(math.isfinite(v) for v in (start,end,blend_in,blend_out,strength,speed,duration,reference,phase)) or end<=start or min(blend_in,blend_out,strength)<0 or speed<=0 or duration<=0 or not 0<=reference<=duration:
            raise ValueError('Invalid source-motion interval or weight')
        if blend_in+blend_out>end-start:raise ValueError('Source fades overlap')
        reference_world=node_worlds(skeleton,tracks,reference)
        prepared.append(dict(source=layer,clip=clip,skeleton=skeleton,tracks=tracks,
                             basis=basis,mapping=mapping,start=start,end=end,
                             blend_in=blend_in,blend_out=blend_out,strength=strength,
                             speed=speed,duration=duration,reference=reference_world,
                             clip_sha256=hashlib.sha256(clip_raw).hexdigest(),
                             skeleton_sha256=hashlib.sha256(skeleton_raw).hexdigest()))
    # Snapshot all source-independent authored states before adding dense keys.
    # Otherwise earlier new keys can change later interpolated base samples.
    base={}
    for frame in range(scene.frame_start,scene.frame_end+1):
        scene.frame_set(frame);bpy.context.view_layer.update()
        base[frame]={semantic:{'matrix':bone.matrix.copy(),'location':bone.location.copy(),'scale':bone.scale.copy()}
                     for semantic,bone in targets.items()}
    arm_rotation=arm.matrix_world.to_quaternion().normalized()
    previous={};maximum={semantic:0. for semantic in targets};active_frames=0
    ordered=sorted(targets,key=lambda name:len(targets[name].parent_recursive))
    for frame in range(scene.frame_start,scene.frame_end+1):
        scene.frame_set(frame);t=(frame-1)/fps
        deltas={semantic:Quaternion() for semantic in targets}
        any_active=False
        for layer in prepared:
            if t<layer['start'] or t>layer['end']:continue
            weight=layer['strength']
            if layer['blend_in']:weight*=smooth((t-layer['start'])/layer['blend_in'])
            if layer['blend_out']:weight*=smooth((layer['end']-t)/layer['blend_out'])
            if weight<=0:continue
            any_active=True
            source_time=(t-layer['start'])*layer['speed']+float(layer['source'].get('phase',0))
            source_time=source_time%layer['duration'] if layer['source'].get('loop',True) else min(layer['duration'],max(0.,source_time))
            world=node_worlds(layer['skeleton'],layer['tracks'],source_time)
            for semantic,index in layer['mapping'].items():
                rotation=world[index,:3,:3]@np.linalg.inv(layer['reference'][index,:3,:3])
                rotation=layer['basis']@rotation@layer['basis'].T
                q=Matrix(rotation.tolist()).to_quaternion().normalized()
                if q.w<0:q.negate()
                weighted=Quaternion().slerp(q,weight)
                delta=arm_rotation.inverted()@weighted@arm_rotation
                deltas[semantic]=delta@deltas[semantic]
        if any_active:active_frames+=1
        for semantic in ordered:
            bone=targets[semantic];original=base[frame][semantic]
            q=deltas[semantic]@original['matrix'].to_quaternion()
            desired=Matrix.Translation(bone.matrix.translation)@q.to_matrix().to_4x4()
            local=bone.bone.convert_local_to_pose(
                desired,bone.bone.matrix_local,parent_matrix=bone.parent.matrix if bone.parent else Matrix.Identity(4),
                parent_matrix_local=bone.parent.bone.matrix_local if bone.parent else Matrix.Identity(4),invert=True)
            # The requested world rotation must not pin a mapped child's head
            # to its old world position after its parent turns. Keep authored
            # local translation/scale so the target rig's joint chain follows.
            bone.rotation_mode='QUATERNION';q=local.to_quaternion().normalized()
            if semantic in previous and q.dot(previous[semantic])<0:q.negate()
            bone.location=original['location'];bone.scale=original['scale']
            bone.rotation_quaternion=q;previous[semantic]=q.copy()
            bone.keyframe_insert('rotation_quaternion',frame=frame)
            bone.keyframe_insert('location',frame=frame)
            maximum[semantic]=max(maximum[semantic],math.degrees(deltas[semantic].angle))
            bpy.context.view_layer.update()
    for semantic,bone in targets.items():
        for property_ in ('rotation_quaternion','location'):
            path=bone.path_from_id(property_)
            for curve in arm.animation_data.action.fcurves:
                if curve.data_path==path:
                    for key in curve.keyframe_points:key.interpolation='LINEAR'
    return {'status':'baked-rotation-variation','active_frames':active_frames,
            'maximum_applied_angle_degrees':maximum,
            'layers':[{'clip_sha256':layer['clip_sha256'],'skeleton_sha256':layer['skeleton_sha256'],
                       'mapping':layer['mapping'],'start':layer['start'],'end':layer['end']}
                      for layer in prepared],
            'scope':'Explicit world-basis rotation variation relative to one source sample; authored target local joint offsets and scales retained. No locomotion, root-position transfer, face events, morph retargeting or automatic rig matching.'}
