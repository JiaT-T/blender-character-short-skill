"""Read-only first-hit checks for external opaque scene blockers.

This is separate from eye aiming: it excludes armature-deformed character
meshes and does not certify iris rays, own-character occlusion or perception.
"""
import argparse,bpy,hashlib,json,math,pathlib,sys
from mathutils import Vector
from mathutils.bvhtree import BVHTree

def opaque(material):
    if material is None:return True
    if material.use_backface_culling:return False
    if not material.use_nodes:return material.diffuse_color[3]>=.999
    nt=material.node_tree;outputs=[n for n in nt.nodes if n.type=='OUTPUT_MATERIAL' and n.is_active_output]
    if len(outputs)!=1:return False
    active=set()
    def socket(value):
        if len(value.links)!=1:return False
        node=value.links[0].from_node
        if node in active:return False
        active.add(node)
        if node.type=='BSDF_PRINCIPLED':
            alpha=node.inputs.get('Alpha');trans=node.inputs.get('Transmission Weight')
            result=bool(alpha and not alpha.is_linked and alpha.default_value>=.999 and (trans is None or (not trans.is_linked and trans.default_value==0)))
        elif node.type in ['EMISSION','BSDF_DIFFUSE']:result=True
        elif node.type=='MIX_SHADER':result=socket(node.inputs[1]) and socket(node.inputs[2])
        elif node.type=='ADD_SHADER':result=socket(node.inputs[0]) and socket(node.inputs[1])
        else:result=False
        active.remove(node);return result
    return socket(outputs[0].inputs['Surface'])

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--blend',required=True,type=pathlib.Path);p.add_argument('--character',required=True,type=pathlib.Path);p.add_argument('--plan',required=True,type=pathlib.Path);p.add_argument('--output',required=True,type=pathlib.Path);a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    a.blend=a.blend.resolve();a.output=a.output.resolve()
    if a.output.exists() or a.output in [a.blend,a.character.resolve(),a.plan.resolve()] or a.output.suffix.lower()!='.json':raise ValueError('Use a new.json report separate from all inputs')
    cfg=json.loads(a.character.read_text('utf-8'));plan=json.loads(a.plan.read_text('utf-8'));h=float(cfg['height'])
    if not math.isfinite(h) or h<=0:raise ValueError('Height must be finite and positive')
    source_hash=hashlib.sha256(a.blend.read_bytes()).hexdigest();bpy.ops.wm.open_mainfile(filepath=str(a.blend));s=bpy.context.scene
    arms=[o for o in s.objects if o.type=='ARMATURE']
    if len(arms)!=1:raise ValueError('Require exactly one configured observer armature')
    arm=arms[0];eyes=[arm.pose.bones[cfg['gaze'][k]] for k in ['left','right']];requests={}
    for row in plan['ranges']:
        start=row['start'];end=row['end'];name=row['object'];triangle=row.get('triangle')
        if type(start)!=int or type(end)!=int or not s.frame_start<=start<=end<=s.frame_end or not isinstance(name,str) or name not in s.objects:raise ValueError('Invalid frame range or object')
        if triangle is not None and (type(triangle)!=int or triangle<0):raise ValueError('Triangle anchor must be a nonnegative integer')
        if s.objects[name].type!='MESH':raise ValueError('Target must be an actual mesh, not an unseen proxy')
        for f in range(start,end+1):
            key=(f,name)
            if key in requests:raise ValueError('Duplicate frame/object request')
            requests[key]=triangle
    if not requests:raise ValueError('No target requests')
    excluded=sorted(o.name for o in s.objects if o.type=='MESH' and any(m.type=='ARMATURE' for m in o.modifiers))
    rows=[];unsupported=[]
    for frame in sorted({f for f,n in requests}):
        s.frame_set(frame);bpy.context.view_layer.update();dg=bpy.context.evaluated_depsgraph_get();colliders={};points={}
        for o in s.objects:
            if o.type!='MESH' or o.hide_render or o.name in excluded:continue
            if any(m.show_render!=m.show_viewport for m in o.modifiers):unsupported.append({'frame':frame,'object':o.name,'reason':'Different viewport/render modifier visibility'});continue
            if any(not opaque(m) for m in o.data.materials):unsupported.append({'frame':frame,'object':o.name,'reason':'Transparency, transmission, culling or unsupported surface graph'});continue
            ev=o.evaluated_get(dg);mesh=ev.to_mesh()
            try:
                mesh.calc_loop_triangles();vertices=[ev.matrix_world@v.co for v in mesh.vertices];triangles=[tuple(t.vertices) for t in mesh.loop_triangles]
                colliders[o.name]=BVHTree.FromPolygons(vertices,triangles,all_triangles=True)
                if (frame,o.name) in requests:
                    index=requests[(frame,o.name)]
                    if index is None:points[o.name]=ev.matrix_world.translation.copy()
                    else:
                        if index>=len(triangles):raise ValueError('Target triangle outside evaluated mesh')
                        ids=triangles[index];points[o.name]=sum((vertices[i] for i in ids),Vector())/3
            finally:ev.to_mesh_clear()
        if unsupported:break
        origin=arm.matrix_world@((eyes[0].head+eyes[1].head)*.5)
        for f,name in requests:
            if f!=frame:continue
            if name not in points:unsupported.append({'frame':frame,'object':name,'reason':'Target absent from eligible render meshes'});continue
            target=points[name];delta=target-origin;distance=delta.length
            if distance<h*1e-7:raise ValueError('Target coincides with eye midpoint')
            hits=[]
            for other,tree in colliders.items():
                point,normal,index,near=tree.ray_cast(origin,delta.normalized(),distance+h*.0001)
                if point is not None:hits.append((near,other))
            first=min(hits) if hits else None;status='target-first' if first and first[1]==name else 'external-blocker' if first else 'no-target-surface-hit'
            rows.append({'frame':frame,'target':name,'triangle':requests[(frame,name)],'status':status,'first_hit':first[1] if first else None,'first_hit_distance_H':first[0]/h if first else None,'target_distance_H':distance/h})
    unchanged=hashlib.sha256(a.blend.read_bytes()).hexdigest()==source_hash
    passed=not unsupported and len(rows)==len(requests) and all(r['status']=='target-first' for r in rows) and unchanged
    report={'scope':'External opaque scene geometry only, evaluated integer frames. All armature-deformed character meshes excluded. Object-center or actual evaluated triangle-center targets. No own-character, iris, transparency, light-facing/emission, subframe or continuous-view acceptance.',
            'status':'unsupported-input' if unsupported else 'external-opaque-clear' if passed else 'external-opaque-unpassed','external_opaque_clear':passed,'scene_bytes_unchanged':unchanged,'source_scene_sha256':source_hash,
            'plan_sha256':hashlib.sha256(a.plan.read_bytes()).hexdigest(),'excluded_character_meshes':excluded,'requested_rays':len(requests),'evaluated_rays':len(rows),
            'external_blocked_rays':sum(r['status']=='external-blocker' for r in rows),'no_target_surface_hit_rays':sum(r['status']=='no-target-surface-hit' for r in rows),'unsupported':unsupported,'records':rows}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),'utf-8')
    print('EXTERNAL_OPAQUE_TARGET_AUDIT',report['status'],len(rows),'rays,blocked',report['external_blocked_rays'],flush=True)
    return 0 if passed else 2 if unsupported else 1

if __name__=='__main__':raise SystemExit(main())
