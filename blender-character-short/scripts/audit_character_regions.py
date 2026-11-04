"""Inspect configured weighted character-region triangle surface pairs.

Exit0 means inspection completed. Read no_nonadjacent_surface_pairs_in_selected_scope and
the warning rows; this is not full-volume or naturalness acceptance.
"""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import argparse,hashlib,json,math,datetime
import bpy,numpy as np
from mathutils.bvhtree import BVHTree
from region_surface_plan import load_json,validate_plan,check_work,CHUNK_TRIANGLES,MAX_PAIRS_PER_FRAME

def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def selected_geometry(scene,arm,plan):
    objects=[o for o in scene.objects if o.type=='MESH' and not o.hide_render and any(m.type=='ARMATURE' and m.object==arm for m in o.modifiers)]
    regions={};triangles={};meshes={o.name:o for o in objects}
    for obj in objects:
        if len(obj.data.vertices)>1000000 or len(obj.data.polygons)>1000000:raise ValueError('Original character mesh exceeds geometry budget')
        obj.data.calc_loop_triangles();triangles[obj.name]=[tuple(t.vertices) for t in obj.data.loop_triangles]
    counts={};chunks={}
    for name,row in plan['regions'].items():
        bone=arm.pose.bones.get(row['root_bone'])
        if bone is None:raise ValueError('Configured region bone missing: '+row['root_bone'])
        allowed={bone.name,*[b.name for b in bone.children_recursive]};entries=[];count=0
        for obj in objects:
            groups={g.index for g in obj.vertex_groups if g.name in allowed};indices=set()
            for vertex in obj.data.vertices:
                weights=[g.weight for g in vertex.groups if g.group in groups]
                if not all(math.isfinite(w) and 0<=w<=1 for w in weights):raise ValueError('Invalid original region skin weights')
                if sum(weights)>=row['weight_threshold']:indices.add(vertex.index)
            ids=[i for i,tri in enumerate(triangles[obj.name]) if all(v in indices for v in tri)]
            count+=len(ids)
            for start in range(0,len(ids),CHUNK_TRIANGLES):entries.append((obj.name,ids[start:start+CHUNK_TRIANGLES]))
        if not count:raise ValueError('No complete weighted triangles for region '+name)
        regions[name]=entries;counts[name]=count;chunks[name]=len(entries)
    work=check_work(plan,counts,chunks)
    return meshes,triangles,regions,counts,work

def evaluated_points(scene,meshes,triangles):
    result={};dg=bpy.context.evaluated_depsgraph_get()
    for name,obj in meshes.items():
        ev=obj.evaluated_get(dg);mesh=ev.to_mesh()
        try:
            mesh.calc_loop_triangles()
            if len(mesh.vertices)!=len(obj.data.vertices) or [tuple(t.vertices) for t in mesh.loop_triangles]!=triangles[name]:raise ValueError('Region audit requires unchanged original vertex and triangle topology')
            points=[ev.matrix_world@v.co for v in mesh.vertices]
            if not np.isfinite(np.asarray(points,dtype=np.float64)).all():raise ValueError('Nonfinite evaluated region geometry')
            result[name]=points
        finally:ev.to_mesh_clear()
    return result

def build_chunks(regions,triangles,points):
    result={}
    for region,entries in regions.items():
        chunks=[]
        for name,ids in entries:
            original=[triangles[name][i] for i in ids];indices=sorted({v for tri in original for v in tri});remap={v:i for i,v in enumerate(indices)};vertices=[points[name][i] for i in indices]
            coords=np.asarray(vertices);bounds=(np.min(coords,axis=0),np.max(coords,axis=0))
            tree=BVHTree.FromPolygons(vertices,[tuple(remap[v] for v in tri) for tri in original],all_triangles=True)
            chunks.append((name,ids,original,tree,bounds))
        result[region]=chunks
    return result

def inspect_pairs(trees,pairs):
    results=[];total=0
    for left,right in pairs:
        count=0;adjacent=0;first=[];tested=0
        for na,idsa,ta,a,ba in trees[left]:
            for nb,idsb,tb,b,bb in trees[right]:
                if np.any(ba[1]<bb[0]) or np.any(bb[1]<ba[0]):continue
                tested+=1
                for ia,ib in a.overlap(b):
                    if na==nb and set(ta[ia])&set(tb[ib]):adjacent+=1;continue
                    count+=1;total+=1
                    if total>MAX_PAIRS_PER_FRAME:raise ValueError('Region surface pairs exceed200000 per-frame reporting budget')
                    if len(first)<16:first.append({'left_mesh':na,'left_original_triangle':idsa[ia],'right_mesh':nb,'right_original_triangle':idsb[ib]})
        results.append({'regions':[left,right],'triangle_surface_pair_count':count,'shared_vertex_pairs_excluded':adjacent,'tested_chunk_pairs':tested,'first_pairs':first})
    return results

def audit(scene,plan):
    arms=[o for o in scene.objects if o.type=='ARMATURE']
    if len(arms)!=1 or len(arms[0].pose.bones)>512:raise ValueError('One bounded character armature required')
    meshes,triangles,regions,counts,work=selected_geometry(scene,arms[0],plan);rows=[]
    for frame in plan['frames']:
        scene.frame_set(frame);bpy.context.view_layer.update();points=evaluated_points(scene,meshes,triangles);trees=build_chunks(regions,triangles,points);pairs=inspect_pairs(trees,plan['pairs'])
        rows.append({'frame':frame,'pairs':pairs,'triangle_surface_pair_count':sum(p['triangle_surface_pair_count'] for p in pairs)})
        if len(rows)%48==0:print('CHARACTER_REGION_AUDIT',len(rows),'of',len(plan['frames']),flush=True)
    return {'status':'selected-region-surface-inspection-complete','no_nonadjacent_surface_pairs_in_selected_scope':not any(r['triangle_surface_pair_count'] for r in rows),'frames_checked':len(rows),'unrequested_scene_integer_frames':scene.frame_end-scene.frame_start+1-len(rows),'frames_with_surface_pairs':sum(bool(r['triangle_surface_pair_count']) for r in rows),'region_triangle_counts':counts,'work':work,'rows':rows,'scope':'Only configured complete weighted triangles on meshes with an armature modifier and object-level hide_render false, at requested saved integer frames. Shared-original-vertex pairs excluded; all alpha geometry included. Reports triangle-surface pairs, not penetration depth or closed-volume containment. No unselected regions, cloth simulation, transparency-aware visibility, subframe safety, full self-collision, normal-speed continuous viewing or naturalness acceptance. Exit0 means inspection completed, not disjointness.'}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('blend','plan','report'):parser.add_argument('--'+name,required=True,type=Path)
    a=parser.parse_args(sys.argv[sys.argv.index('--')+1:]);source=a.blend.resolve();plan_path=a.plan.resolve();report=a.report.resolve()
    if len({source,plan_path,report})!=3 or source.suffix.lower()!='.blend' or report.suffix.lower()!='.json' or report.exists():raise ValueError('Distinct source blend/plan and a new JSON report required')
    identities={str(p):sha(p) for p in (source,plan_path)};document=load_json(plan_path)
    bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False);scene=bpy.context.scene;plan=validate_plan(document,scene.frame_start,scene.frame_end);result=audit(scene,plan)
    if any(sha(Path(path))!=digest for path,digest in identities.items()):raise ValueError('An input changed during region audit')
    result.update(schema=1,at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),input_sha256=identities,writer_sha256=sha(Path(__file__)),plan_validator_sha256=sha(Path(__file__).with_name('region_surface_plan.py')),plan=plan,blender_version=bpy.app.version_string,source_inputs_unchanged=True)
    report.parent.mkdir(parents=True,exist_ok=True);report.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),'utf-8');print('CHARACTER_REGION_AUDIT_DONE',json.dumps({k:result[k] for k in ('no_nonadjacent_surface_pairs_in_selected_scope','frames_checked','frames_with_surface_pairs')}),flush=True)

if __name__=='__main__':main()
