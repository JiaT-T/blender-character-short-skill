"""Existing-rig FK hand state, binding and evaluated original-skin helpers."""
from pathlib import Path
import hashlib,json,math
import bpy,numpy as np
from mathutils import Quaternion
from mathutils.bvhtree import BVHTree

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def arrays(data,field,count):
    result=np.empty(count,dtype=np.float32);data.foreach_get(field,result)
    if not np.isfinite(result).all():raise ValueError('Nonfinite original hand/shape data')
    return result
def set_frame(scene,time):scene.frame_set(int(math.floor(time)),subframe=time-math.floor(time));bpy.context.view_layer.update()
def rigs(scene):
    arms=[o for o in scene.objects if o.type=='ARMATURE']
    if len(arms)!=1 or len(arms[0].pose.bones)>2048:raise ValueError('One armature with at most2048 bones required')
    arm=arms[0];meshes=[o for o in scene.objects if o.type=='MESH' and any(m.type=='ARMATURE' and m.object==arm for m in o.modifiers)]
    if not meshes or sum(len(o.data.vertices) for o in meshes)>500000:raise ValueError('Bounded original skinned meshes required')
    return arm,meshes
def geometry_signature(arm,meshes):
    digest=hashlib.sha256();bones=[(b.name,b.parent.name if b.parent else None,b.use_deform,[[round(float(x),8) for x in row] for row in b.matrix_local]) for b in arm.data.bones];digest.update(json.dumps(bones,ensure_ascii=False,separators=(',',':')).encode())
    for obj in sorted(meshes,key=lambda x:x.name):
        digest.update(obj.name.encode());digest.update(arrays(obj.data.vertices,'co',len(obj.data.vertices)*3).tobytes());digest.update(json.dumps([list(p.vertices) for p in obj.data.polygons],separators=(',',':')).encode());names={g.index:g.name for g in obj.vertex_groups};weights=[[(names[g.group],float(g.weight)) for g in v.groups] for v in obj.data.vertices];digest.update(json.dumps(weights,ensure_ascii=False,separators=(',',':')).encode())
        if obj.data.shape_keys:
            for key in obj.data.shape_keys.key_blocks:digest.update(key.name.encode());digest.update(arrays(key.data,'co',len(key.data)*3).tobytes())
    return digest.hexdigest()
def bind(scene,mapping,require_bound=True):
    arm,meshes=rigs(scene);bone_names={j['bone'] for j in mapping['joints']};wrists=set(mapping['hands'].values())
    if any(n not in arm.data.bones for n in wrists):raise ValueError('Missing mapped wrist')
    if any(arm.data.bones[a] in arm.data.bones[b].parent_recursive for a in wrists for b in wrists if a!=b):raise ValueError('Mapped wrists cannot be nested')
    for j in mapping['joints']:
        bone=arm.data.bones.get(j['bone']);wrist=arm.data.bones.get(mapping['hands'][j['side']])
        if bone is None or wrist is None or wrist not in bone.parent_recursive:raise ValueError('Each configured joint must be an existing descendant of its wrist')
        if any(c.influence>1e-8 and not c.mute for c in arm.pose.bones[bone.name].constraints):raise ValueError('Constrained finger controls require a separately validated indirect route')
        paths={arm.pose.bones[bone.name].path_from_id(key) for key in ['rotation_quaternion','rotation_euler','rotation_axis_angle']}
        if arm.animation_data and any(fc.data_path in paths for fc in arm.animation_data.drivers):raise ValueError('Driven finger rotations require separate validation')
    for name in list(bone_names):bone_names.update(b.name for b in arm.data.bones[name].children_recursive)
    rest_names=bone_names|wrists
    for name in list(rest_names):rest_names.update(b.name for b in arm.data.bones[name].parent_recursive)
    selections={};finger_regions={};palm_regions={};digest=hashlib.sha256();digest.update(json.dumps([(name,arm.data.bones[name].parent.name if arm.data.bones[name].parent else None,[[round(float(x),7) for x in row] for row in arm.data.bones[name].matrix_local]) for name in sorted(rest_names)],ensure_ascii=False,separators=(',',':')).encode())
    for obj in sorted(meshes,key=lambda x:x.name):
        names={g.index:g.name for g in obj.vertex_groups};rows={v.index:{names[g.group]:g.weight for g in v.groups} for v in obj.data.vertices}
        if any(not math.isfinite(w) or not 0<=w<=1.000001 for row in rows.values() for w in row.values()):raise ValueError('Invalid skin weights')
        ids={i for i,w in rows.items() if any(w.get(n,0)>1e-8 for n in bone_names|wrists)}
        if not ids:continue
        obj.data.calc_loop_triangles();tris=[tuple(t.vertices) for t in obj.data.loop_triangles];selections[obj.name]={'indices':sorted(ids),'triangles':[t for t in tris if all(i in ids for i in t)],'vertex_count':len(obj.data.vertices),'all_triangles':tris}
        digest.update(obj.name.encode());digest.update(json.dumps([[[round(float(x),7) for x in row] for row in arm.matrix_world.inverted()@obj.matrix_world],[(i,[round(float(x),7) for x in obj.data.vertices[i].co],sorted((n,round(float(w),7)) for n,w in rows[i].items())) for i in sorted(ids)],selections[obj.name]['triangles']],ensure_ascii=False,separators=(',',':')).encode())
        for side,wrist in mapping['hands'].items():
            palm_regions.setdefault(side+'.palm',{})[obj.name]={i for i,w in rows.items() if w.get(wrist,0)>=.35}
            digits={j['digit'] for j in mapping['joints'] if j['side']==side}
            for digit in digits:
                selected={j['bone'] for j in mapping['joints'] if j['side']==side and j['digit']==digit}
                for name in list(selected):selected.update(b.name for b in arm.data.bones[name].children_recursive)
                finger_regions.setdefault(side+'.'+digit,{})[obj.name]={i for i,w in rows.items() if sum(w.get(n,0) for n in selected)>=.35}
    signature=digest.hexdigest()
    if require_bound and mapping.get('binding_sha256')!=signature:raise ValueError('Hand rest/skin binding is absent or stale; calibrate this exact rig first')
    return arm,meshes,selections,{**palm_regions,**finger_regions},signature
def protection(arm,scene,active):
    allowed=set(active)
    for name in active:allowed.update(p.name for p in arm.pose.bones[name].children_recursive)
    attached={o for o in scene.objects if o.parent==arm and o.parent_type=='BONE' and o.parent_bone in allowed}
    for o in list(attached):attached.update(o.children_recursive)
    protected=sorted(set(arm.pose.bones.keys())-allowed);objects=[o for o in scene.objects if o not in attached]
    return allowed,protected,objects,sorted(o.name for o in attached)
def worlds(arm,names):
    values=np.asarray([list(map(list,arm.matrix_world@arm.pose.bones[n].matrix)) for n in names],dtype=np.float64)
    if not np.isfinite(values).all():raise ValueError('Nonfinite evaluated bone world matrix')
    return values
def object_worlds(objects):
    values=np.asarray([list(map(list,o.matrix_world)) for o in objects],dtype=np.float64)
    if not np.isfinite(values).all():raise ValueError('Nonfinite object world matrix')
    return values
def morphology(meshes):
    values={(o.name,k.name):float(k.value) for o in meshes if o.data.shape_keys for k in o.data.shape_keys.key_blocks}
    if not all(math.isfinite(v) for v in values.values()):raise ValueError('Nonfinite morph value')
    return values
def evaluated(scene,meshes,selections):
    result={};deps=scene.depsgraph if hasattr(scene,'depsgraph') else bpy.context.evaluated_depsgraph_get()
    for obj in meshes:
        if obj.name not in selections:continue
        ev=obj.evaluated_get(deps);mesh=ev.to_mesh()
        try:
            mesh.calc_loop_triangles();selection=selections[obj.name]
            if len(mesh.vertices)!=selection['vertex_count'] or [tuple(t.vertices) for t in mesh.loop_triangles]!=selection['all_triangles']:raise ValueError('Original evaluated hand topology changed; vertex-index evidence unsupported')
            values=[ev.matrix_world@v.co for v in mesh.vertices]
            if not np.isfinite(np.asarray(values)).all():raise ValueError('Nonfinite evaluated skin vertex')
            result[obj.name]=values
        finally:ev.to_mesh_clear()
    return result
def surface_pairs(points,selections,regions):
    trees={}
    for region,entries in regions.items():
        chunks=[]
        for name,ids in entries.items():
            tris=[t for t in selections[name]['all_triangles'] if all(i in ids for i in t)]
            if tris:
                used=sorted({i for t in tris for i in t});remap={v:i for i,v in enumerate(used)};vertices=[points[name][i] for i in used];chunks.append((name,tris,BVHTree.FromPolygons(vertices,[tuple(remap[i] for i in t) for t in tris],all_triangles=True)))
        trees[region]=chunks
    rows=[];names=sorted(trees)
    for a,left in enumerate(names):
        for right in names[a+1:]:
            if left.split('.')[0]!=right.split('.')[0]:continue
            count=0
            for na,ta,tree_a in trees[left]:
                for nb,tb,tree_b in trees[right]:
                    count+=sum(not (na==nb and set(ta[x])&set(tb[y])) for x,y in tree_a.overlap(tree_b))
            rows.append({'regions':[left,right],'triangle_surface_pairs':count})
    return rows
def quat_degrees(q):
    if not all(math.isfinite(float(v)) for v in q) or q.magnitude<1e-8:raise ValueError('Invalid quaternion')
    return math.degrees(2*math.acos(min(1.,abs(q.normalized().w))))

def active_joints(mapping,plan):
    names={c['joint'] for c in plan['channels']};return [j for j in mapping['joints'] if j['id'] in names]
def rotation_delta(joint,channels,time):
    from hand_control_plan import value_at
    q=Quaternion()
    for axis in joint['axes']:
        keys=channels.get((joint['id'],axis['id']));fraction=value_at(keys,time) if keys is not None else 0.;q=q@Quaternion(axis['axis_local'],math.radians(axis['limit_degrees']*fraction))
    if quat_degrees(q)>joint['max_total_degrees']+.001:raise ValueError('Combined axis rotation exceeds joint total limit: '+joint['id'])
    return q
def check_work(arm,meshes,scene,times):
    if len(times)*len(arm.pose.bones)>300000 or len(times)*len(scene.objects)>300000 or len(times)*sum(len(o.data.vertices) for o in meshes)>20000000:raise ValueError('Hand clip exceeds bone/object/vertex inspection budget')
def topology(mesh):
    mesh.calc_loop_triangles();values=np.empty(len(mesh.loop_triangles)*3,dtype=np.int32);mesh.loop_triangles.foreach_get('vertices',values);return values
def evaluated_arrays(scene,meshes,topologies):
    result={};deps=bpy.context.evaluated_depsgraph_get()
    for obj in meshes:
        ev=obj.evaluated_get(deps);mesh=ev.to_mesh()
        try:
            if len(mesh.vertices)!=len(obj.data.vertices) or not np.array_equal(topology(mesh),topologies[obj.name]):raise ValueError('Evaluated skin topology changed')
            co=arrays(mesh.vertices,'co',len(mesh.vertices)*3).reshape(-1,3);matrix=np.asarray(ev.matrix_world,dtype=np.float64);values=co@matrix[:3,:3].T+matrix[:3,3]
            if not np.isfinite(values).all():raise ValueError('Nonfinite deformed skin')
            result[obj.name]=values
        finally:ev.to_mesh_clear()
    return result
def linear_new_keys(arm,paths,first,last):
    for layer in arm.animation_data.action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for curve in bag.fcurves:
                    if curve.data_path in paths:
                        for point in curve.keyframe_points:
                            if first<=point.co.x<=last:point.interpolation='LINEAR'
