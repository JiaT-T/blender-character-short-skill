"""Sample prop-surface clearance along a calibrated palm normal.

This is a directional, sampled diagnostic, not a general collision detector.
It complements the single anchor ray and never changes the saved scene.
"""
import argparse,json,sys
from pathlib import Path
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def hand_surfaces(scene,arm,anchor,min_weight):
    start=arm.pose.bones[anchor['start_bone']]
    allowed={start.name,*[b.name for b in start.children_recursive]}
    dg=bpy.context.evaluated_depsgraph_get();result=[]
    for obj in scene.objects:
        if obj.type!='MESH' or not any(m.type=='ARMATURE' and m.object==arm for m in obj.modifiers):continue
        groups={g.index for g in obj.vertex_groups if g.name in allowed}
        selected={v.index for v in obj.data.vertices if sum(g.weight for g in v.groups if g.group in groups)>min_weight}
        ev=obj.evaluated_get(dg);mesh=ev.to_mesh()
        try:
            if len(mesh.vertices)!=len(obj.data.vertices):raise ValueError('Footprint audit does not support topology-changing hand modifiers')
            faces=[p for p in mesh.polygons if all(i in selected for i in p.vertices)]
            if not faces:continue
            vertices=[obj.matrix_world@v.co for v in mesh.vertices]
            bvh=BVHTree.FromPolygons(vertices,[tuple(p.vertices) for p in faces])
            result.append((obj.name,bvh,[obj.data.materials[p.material_index].name for p in faces]))
        finally:ev.to_mesh_clear()
    if not result:raise ValueError('No weighted hand surface found')
    return result


def prop_samples(prop):
    ev=prop.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh()
    try:
        mesh.calc_loop_triangles();world=[prop.matrix_world@v.co for v in mesh.vertices]
        samples=[('vertex:'+str(i),v) for i,v in enumerate(world)]
        edges=set()
        for ti,tri in enumerate(mesh.loop_triangles):
            ids=list(tri.vertices);samples.append(('triangle-center:'+str(ti),sum((world[i] for i in ids),Vector())/3))
            for a,b in zip(ids,ids[1:]+ids[:1]):edges.add(tuple(sorted((a,b))))
        samples.extend(('edge-mid:'+str(a)+':'+str(b),(world[a]+world[b])*.5) for a,b in sorted(edges))
        return samples
    finally:ev.to_mesh_clear()


def measure(scene,arm,prop,anchor,height,ray_length=.1,min_weight=.35,min_normal_dot=.25):
    if any(abs(v-1)>1e-6 for v in arm.scale):raise ValueError('Footprint audit requires unit-scale armature object')
    start=arm.pose.bones[anchor['start_bone']]
    normal=(arm.matrix_world.to_3x3()@start.matrix.to_3x3()@Vector(anchor['normal_local'])).normalized()
    surfaces=hand_surfaces(scene,arm,anchor,min_weight);samples=prop_samples(prop);hits=[];misses=[];grazing=[]
    for label,point in samples:
        candidates=[]
        for name,bvh,materials in surfaces:
            hit,n,index,distance=bvh.ray_cast(point+normal*height*ray_length,-normal,height*ray_length*2)
            if hit is None:continue
            candidates.append({'mesh':name,'point':list(hit),'normal':list(n),'normal_dot':n.dot(normal),'material':materials[index],'clearance_height':(point-hit).dot(normal)/height})
        if not candidates:misses.append(label);continue
        nearest=min(candidates,key=lambda x:x['clearance_height'])
        record={'sample':label,'prop_world':list(point),**nearest}
        if nearest['normal_dot']<min_normal_dot:grazing.append(record)
        else:hits.append(record)
    minimum=min((x['clearance_height'] for x in hits),default=None)
    return {'palm_normal_world':list(normal),'sample_count':len(samples),'valid_hits':len(hits),'miss_count':len(misses),'grazing_count':len(grazing),'minimum_clearance_height':minimum,'required_normal_translation_for_zero_height':max(0,-minimum) if minimum is not None else None,'lowest_samples':sorted(hits,key=lambda x:x['clearance_height'])[:12],'all_hits':hits,'missed_samples':misses,'grazing_hits':grazing}


def main():
    p=argparse.ArgumentParser();p.add_argument('--blend',required=True);p.add_argument('--character',required=True);p.add_argument('--anchor',required=True);p.add_argument('--prop',default='Story prop');p.add_argument('--frames',required=True);p.add_argument('--output',required=True);p.add_argument('--ray-length',type=float,default=.1);p.add_argument('--min-weight',type=float,default=.35);a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    if a.ray_length<=0:raise ValueError('Ray length must be positive')
    cfg=json.loads(Path(a.character).read_text('utf-8'));anchor=cfg['contact_anchors'][a.anchor]
    bpy.ops.wm.open_mainfile(filepath=str(Path(a.blend).resolve()));scene=bpy.context.scene;arms=[o for o in scene.objects if o.type=='ARMATURE']
    if len(arms)!=1:raise ValueError('Expected one character armature')
    prop=scene.objects.get(a.prop)
    if prop is None or prop.type!='MESH':raise ValueError('Configured prop mesh is absent: '+a.prop)
    records=[]
    for frame in map(int,a.frames.split(',')):
        scene.frame_set(frame);bpy.context.view_layer.update();record=measure(scene,arms[0],prop,anchor,cfg['height'],a.ray_length,a.min_weight);record['frame']=frame;records.append(record)
    report={'blend':str(Path(a.blend).resolve()),'anchor':a.anchor,'prop':prop.name,'records':records,'scope':'Vertices, triangle centers and edge midpoints sampled against weighted hand faces along configured palm normal. Misses/grazing hits are not passes. Negative clearance is a directional overlap warning; not a complete 3D collision result. No automatic scene modification or collision acceptance.'}
    target=Path(a.output);target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
    print('FOOTPRINT_AUDIT',json.dumps([{k:r[k] for k in ['frame','minimum_clearance_height','valid_hits','miss_count','grazing_count']} for r in records]))


if __name__=='__main__':main()
