"""Reopen a sphere grasp: actual skin contact, sliding, body preservation and cord."""
from pathlib import Path
import sys,json,argparse,datetime,math,itertools
sys.dont_write_bytecode=True;sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy,numpy as np
from mathutils import Matrix,Vector,Quaternion
from mathutils.bvhtree import BVHTree
from hand_control_plan import profile,motion,value_at
from hand_control_runtime import *

def tree(points,triangles):
    used=sorted({i for t in triangles for i in t});indices={v:i for i,v in enumerate(used)}
    return BVHTree.FromPolygons([points[i] for i in used],[tuple(indices[i] for i in t) for t in triangles],all_triangles=True)

def object_geometry(obj,deps):
    evaluated=obj.evaluated_get(deps);mesh=evaluated.to_mesh()
    try:
        pts=arrays(mesh.vertices,'co',len(mesh.vertices)*3).reshape(-1,3);matrix=np.asarray(evaluated.matrix_world);pts=pts@matrix[:3,:3].T+matrix[:3,3];tris=topology(mesh).reshape(-1,3).copy()
        if not np.isfinite(pts).all():raise ValueError('Nonfinite evaluated prop geometry')
        return pts,[tuple(map(int,t)) for t in tris]
    finally:evaluated.to_mesh_clear()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ['blend','source','profile','motion','spec','fit','plan','body-report','bake-report','report','snapshots']:parser.add_argument('--'+key,required=True,type=Path)
    a=parser.parse_args(sys.argv[sys.argv.index('--')+1:]);assert not a.report.exists() and not a.snapshots.exists() and not a.snapshots.with_name(a.snapshots.name+'.json').exists();mapping=profile(json.loads(a.profile.read_text('utf-8')));plan=json.loads(a.plan.read_text('utf-8'));fit=json.loads(a.fit.read_text('utf-8'));spec=json.loads(a.spec.read_text('utf-8'));bake=json.loads(a.bake_report.read_text('utf-8'));body=json.loads(a.body_report.read_text('utf-8'));gesture=motion(json.loads(a.motion.read_text('utf-8')),mapping);source_hash=sha(a.source);candidate_hash=sha(a.blend)
    progress=a.report.with_suffix('.progress.jsonl')
    if progress.exists():raise ValueError('Choose a new audit/progress path; retain previous partial evidence')
    a.report.parent.mkdir(parents=True,exist_ok=True)
    expected=(source_hash,candidate_hash,sha(a.profile),sha(a.motion),sha(Path(__file__).with_name('hand_control_runtime.py')),sha(Path(__file__).with_name('hand_control_plan.py')))
    if tuple(bake[k] for k in ['source_sha256','output_sha256','profile_sha256','motion_sha256','runtime_sha256','plan_module_sha256'])!=expected or body['output_sha256']!=source_hash or body['fit_sha256']!=sha(a.fit) or body['plan_sha256']!=sha(a.plan) or fit['spec_sha256']!=sha(a.spec) or not fit['static_candidate_pass']:raise ValueError('Stale source, profile, plan, fit or producer evidence')
    first,last=gesture['frames'];times=[first+i/2 for i in range((last-first)*2+1)];held=plan['held_frames'];radius=body['radius_m'];contacts=spec['contacts'];joints=active_joints(mapping,gesture);active=[j['bone'] for j in joints];channels={(c['joint'],c['axis']):c['keys'] for c in gesture['channels']};side=plan['side'];wrist_name=mapping['hands'][side]
    bpy.ops.wm.open_mainfile(filepath=str(a.source.resolve()),load_ui=False,use_scripts=False);scene=bpy.context.scene;set_frame(scene,first);arm,meshes,_,_,binding=bind(scene,mapping);check_work(arm,meshes,scene,times);allowed,protected,objects,attached=protection(arm,scene,active);object_names=[o.name for o in objects];identity=geometry_signature(arm,meshes);tops={o.name:topology(o.data) for o in meshes};nonfinger={};regions={};export={};finger_names={j['bone'] for j in mapping['joints'] if j['side']==side};elbow=plan['arm_bones']['elbow'];forearm={elbow,*[b.name for b in arm.data.bones[elbow].children_recursive]}
    digit_groups={}
    for joint in mapping['joints']:
        if joint['side']==side:digit_groups.setdefault(joint['digit'],set()).add(joint['bone'])
    region_defs={name:(set(row['bones']),row['min_weight']) for name,row in contacts.items()};region_defs.update({'digit.'+digit:(bones,.35) for digit,bones in digit_groups.items()});region_defs['digit.palm']=({wrist_name},.35)
    for obj in meshes:
        names={g.index:g.name for g in obj.vertex_groups};weights={v.index:{names[g.group]:g.weight for g in v.groups} for v in obj.data.vertices};triangles=[tuple(map(int,t)) for t in tops[obj.name].reshape(-1,3)];nonfinger[obj.name]=[i for i,w in weights.items() if not any(w.get(n,0)>1e-8 for n in allowed)]
        ids=sorted(i for i,w in weights.items() if any(w.get(n,0)>1e-8 for n in forearm));chosen=set(ids)
        if ids:export[obj.name]={'indices':ids,'triangles':[t for t in triangles if all(i in chosen for i in t)]}
        for region,(bones,threshold) in region_defs.items():
            ids={i for i,w in weights.items() if sum(w.get(n,0) for n in bones)>=threshold};tris=[t for t in triangles if all(i in ids for i in t)]
            if tris:regions.setdefault(region,[]).append((obj.name,tris))
    if any(name not in regions for name in contacts):raise ValueError('Missing original weighted pad triangles')
    states=[]
    for i,t in enumerate(times):
        set_frame(scene,t);worlds(arm,active);points=evaluated_arrays(scene,meshes,tops);states.append({'worlds':worlds(arm,protected),'objects':object_worlds(objects),'morphs':morphology(meshes),'basis':{n:arm.pose.bones[n].matrix_basis.copy() for n in active},'nonfinger':{n:points[n][ids].astype(np.float32) for n,ids in nonfinger.items()}})
        if i%48==0:print('GRASP_AUDIT_SOURCE',i+1,'of',len(times),flush=True)
    bpy.ops.wm.open_mainfile(filepath=str(a.blend.resolve()),load_ui=False,use_scripts=False);scene=bpy.context.scene;set_frame(scene,first);arm,meshes,_,_,binding2=bind(scene,mapping);allowed2,protected2,objects2,attached2=protection(arm,scene,active)
    if binding2!=binding or geometry_signature(arm,meshes)!=identity or protected2!=protected or [o.name for o in objects2]!=object_names or attached2!=attached:raise ValueError('Saved rig/dependency identity mismatch')
    sphere=scene.objects[body['sphere_name']];cord=scene.objects[body['cord_name']];radii=[v.co.length for v in sphere.data.vertices]
    if max(abs(r-radius) for r in radii)>1e-6 or scene.frame_start!=first or scene.frame_end!=last or scene.render.fps!=gesture['fps'] or abs(scene.render.fps_base-1)>1e-8:raise ValueError('Actual primitive radius/timeline mismatch')
    G=Matrix(body['sphere_in_wrist']);M0=Matrix(body['rest_sphere_world']);W0=M0@G.inverted();H0=W0@Matrix(plan['hand_frame_from_wrist']).inverted();approach=H0.to_3x3()@Vector(plan['approach_offset_hand_m']);lift=Vector(plan['lift_world_m']);anchor=Vector(body['cord_top_world']);attach=Vector(body['cord_attach_sphere_local']);errors={k:0. for k in ['protected_bone_world','protected_object_world','morph_values','nonfinger_skin_world','finger_local_translation','finger_local_scale','finger_integer_rotation_matrix','finger_subframe_target_degrees','wrist_target_m','wrist_rotation_degrees','held_relative_prop_translation_m','held_relative_prop_rotation_degrees','material_contact_drift_m','cord_length_error_m','cord_anchor_error_m','cord_attachment_error_m']};anchors={};rows=[];captured={n:[] for n in export};sphere_matrices=[];cord_vertices=[];cord_topology=None;previous_position=None;maximum_step=0.;sphere_positions=[]
    def region_trees(points):return {region:[(name,triangles,tree(points[name],triangles)) for name,triangles in chunks] for region,chunks in regions.items()}
    def closest(chunks,center):
        best=None
        for name,tris,bvh in chunks:
            p,n,index,d=bvh.find_nearest(center)
            if best is None or d<best['distance']:best={'mesh':name,'tri':tris[index],'point':p,'normal':n,'distance':d}
        return best
    for i,(t,state) in enumerate(zip(times,states)):
        set_frame(scene,t);worlds(arm,active);points=evaluated_arrays(scene,meshes,tops);errors['protected_bone_world']=max(errors['protected_bone_world'],float(np.max(np.abs(worlds(arm,protected)-state['worlds']))));errors['protected_object_world']=max(errors['protected_object_world'],float(np.max(np.abs(object_worlds(objects2)-state['objects']))));morphs=morphology(meshes);errors['morph_values']=max(errors['morph_values'],max((abs(morphs[k]-v) for k,v in state['morphs'].items()),default=0.))
        for n,ids in nonfinger.items():
            if ids:errors['nonfinger_skin_world']=max(errors['nonfinger_skin_world'],float(np.max(np.abs(points[n][ids]-state['nonfinger'][n]))))
        for j in joints:
            b=arm.pose.bones[j['bone']];base=state['basis'][b.name];target=base.to_quaternion()@rotation_delta(j,channels,t);actual=b.matrix_basis.to_quaternion();errors['finger_local_translation']=max(errors['finger_local_translation'],(b.location-base.to_translation()).length);errors['finger_local_scale']=max(errors['finger_local_scale'],(b.scale-base.to_scale()).length)
            if t==round(t):errors['finger_integer_rotation_matrix']=max(errors['finger_integer_rotation_matrix'],float(np.max(np.abs(np.asarray(actual.to_matrix())-np.asarray(target.to_matrix())))))
            else:errors['finger_subframe_target_degrees']=max(errors['finger_subframe_target_degrees'],quat_degrees(actual.rotation_difference(target)))
        W=arm.matrix_world@arm.pose.bones[wrist_name].matrix;u=value_at(plan['approach_keys'],t);v=value_at(plan['lift_keys'],t);wtarget=W0.translation+approach*u+lift*v;werror=(W.translation-wtarget).length;errors['wrist_target_m']=max(errors['wrist_target_m'],werror)
        if t==round(t):errors['wrist_integer_target_m']=max(errors.get('wrist_integer_target_m',0.),werror)
        q=Quaternion(plan['inspection_axis_world'],math.radians(plan['inspection_degrees'])*v)@W0.to_quaternion();errors['wrist_rotation_degrees']=max(errors['wrist_rotation_degrees'],quat_degrees(q.rotation_difference(W.to_quaternion())))
        M=sphere.matrix_world.copy();center=M.translation;sphere_positions.append(list(center));held_now=held[0]<=t<=held[1]
        if max(abs(s-1) for s in M.to_scale())>1e-5:raise ValueError('Sphere world scale changed')
        if not held_now:errors['unheld_prop_rest_m']=max(errors.get('unheld_prop_rest_m',0.),(M.translation-M0.translation).length)
        if previous_position is not None:maximum_step=max(maximum_step,(center-previous_position).length)
        previous_position=center.copy();deps=bpy.context.evaluated_depsgraph_get();spoints,stris=object_geometry(sphere,deps);cpoints,ctris=object_geometry(cord,deps);sphere_tree=tree(spoints,stris);cord_tree=tree(cpoints,ctris);body_trees={o.name:tree(points[o.name],[tuple(map(int,q)) for q in tops[o.name].reshape(-1,3)]) for o in meshes};minimum_gap=min(b.find_nearest(center)[3]-radius for b in body_trees.values());sphere_pairs=sum(len(b.overlap(sphere_tree)) for b in body_trees.values());cord_pairs=sum(len(b.overlap(cord_tree)) for b in body_trees.values());rt=region_trees(points);digit_names=sorted(n for n in rt if n.startswith('digit.'));self_pairs=0
        for left,right in itertools.combinations(digit_names,2):
            for na,ta,ba in rt[left]:
                for nb,tb,bb in rt[right]:self_pairs+=sum(not(na==nb and set(ta[x])&set(tb[y])) for x,y in ba.overlap(bb))
        contact_rows={};opposition=[];maximum_contact_gap=0.;facing=True
        for name in contacts:
            r=closest(rt[name],center);distance=r['distance'];radial=(r['point']-center).normalized();contact_rows[name]={'gap_m':distance-radius,'point_world':list(r['point']),'external_facing_cos':r['normal'].dot(center-r['point'])/max(distance,1e-12),'radial':list(radial)}
            if held_now:
                maximum_contact_gap=max(maximum_contact_gap,abs(distance-radius));facing=facing and contact_rows[name]['external_facing_cos']>=.1
                if name not in anchors:
                    vertices=np.asarray(points[r['mesh']])[list(r['tri'])];a0=vertices[0];A=np.stack((vertices[1]-a0,vertices[2]-a0),axis=1);vw=np.linalg.lstsq(A,np.asarray(r['point'])-a0,rcond=None)[0];weights=np.asarray([1-vw.sum(),*vw]);material=weights@vertices;local=np.asarray(M.inverted()@Vector(material));anchors[name]={'mesh':r['mesh'],'triangle':list(r['tri']),'barycentric':weights.tolist(),'prop_local_point':local.tolist()}
                ref=anchors[name];material=np.asarray(ref['barycentric'])@points[ref['mesh']][ref['triangle']];local=M.inverted()@Vector(material);errors['material_contact_drift_m']=max(errors['material_contact_drift_m'],(local-Vector(ref['prop_local_point'])).length)
        if held_now:
            relative=W.inverted()@M;errors['held_relative_prop_translation_m']=max(errors['held_relative_prop_translation_m'],(relative.translation-G.translation).length);errors['held_relative_prop_rotation_degrees']=max(errors['held_relative_prop_rotation_degrees'],quat_degrees(relative.to_quaternion().rotation_difference(G.to_quaternion())))
            for l,r in spec['opposition_pairs']:opposition.append(Vector(contact_rows[l]['radial']).dot(Vector(contact_rows[r]['radial'])))
        evaluated_cord=cord.evaluated_get(deps);line=[evaluated_cord.matrix_world@Vector(p.co[:3]) for p in evaluated_cord.data.splines[0].points];length=sum((b-a).length for a,b in zip(line,line[1:]));errors['cord_length_error_m']=max(errors['cord_length_error_m'],abs(length-plan['cord_length_m']));errors['cord_anchor_error_m']=max(errors['cord_anchor_error_m'],(line[0]-anchor).length);errors['cord_attachment_error_m']=max(errors['cord_attachment_error_m'],(line[-1]-M@attach).length)
        rows.append({'frame':t,'held':held_now,'minimum_original_skin_sphere_gap_m':minimum_gap,'actual_sphere_skin_triangle_pairs':sphere_pairs,'actual_cord_skin_triangle_pairs':cord_pairs,'same_hand_region_surface_pairs':self_pairs,'contacts':contact_rows,'held_max_contact_gap_m':maximum_contact_gap if held_now else None,'held_contacts_exterior_facing':facing if held_now else None,'opposing_radial_dots':opposition,'cord_length_m':length})
        for n,selection in export.items():captured[n].append(points[n][selection['indices']].astype(np.float32))
        sphere_matrices.append(np.asarray(M,dtype=float));cord_vertices.append(cpoints.astype(np.float32))
        if cord_topology is None:cord_topology=[]
        cord_topology.append(ctris)
        progress=a.report.with_suffix('.progress.jsonl')
        with progress.open('a',encoding='utf-8') as stream:stream.write(json.dumps(rows[-1])+'\n')
        if i%24==0:print('GRASP_AUDIT_SAVED',i+1,'of',len(times),'gap',minimum_gap,'pairs',sphere_pairs,cord_pairs,self_pairs,flush=True)
    fixed=[k for k in errors if k not in ['wrist_target_m','finger_subframe_target_degrees','wrist_rotation_degrees','held_relative_prop_rotation_degrees','material_contact_drift_m','cord_length_error_m','cord_anchor_error_m','cord_attachment_error_m','held_relative_prop_translation_m']];checks={k:errors[k]<=1e-5 for k in fixed};checks.update({'wrist_subframe_path_within_declared_tolerance':errors['wrist_target_m']<=plan.get('wrist_path_tolerance_m',.00025),'finger_subframe_target_degrees':errors['finger_subframe_target_degrees']<=.25,'wrist_rotation_degrees':errors['wrist_rotation_degrees']<=.15,'held_relative_prop_rotation_degrees':errors['held_relative_prop_rotation_degrees']<=.15,'held_relative_prop_translation_m':errors['held_relative_prop_translation_m']<=plan['stability_tolerance_m'],'material_contact_drift_m':errors['material_contact_drift_m']<=plan['stability_tolerance_m'],'cord_length_error_m':errors['cord_length_error_m']<=plan['cord_length_tolerance_m'],'cord_anchor_error_m':errors['cord_anchor_error_m']<=1e-5,'cord_attachment_error_m':errors['cord_attachment_error_m']<=1e-5,'all_frames_skin_sphere_clearance':all(r['minimum_original_skin_sphere_gap_m']>=-plan['penetration_tolerance_m'] for r in rows),'actual_sphere_skin_surfaces_disjoint':all(r['actual_sphere_skin_triangle_pairs']==0 for r in rows),'actual_cord_skin_surfaces_disjoint':all(r['actual_cord_skin_triangle_pairs']==0 for r in rows),'same_hand_region_surfaces_disjoint':all(r['same_hand_region_surface_pairs']==0 for r in rows),'all_held_declared_pad_contacts':all(r['held_max_contact_gap_m']<=plan['contact_gap_limit_m'] and r['held_contacts_exterior_facing'] for r in rows if r['held']),'all_held_declared_opposition':all(all(v<=spec['max_radial_dot'] for v in r['opposing_radial_dots']) for r in rows if r['held']),'actual_lift_present':max(p[2] for p in sphere_positions)-sphere_positions[int((held[0]-first)*2)][2]>=plan.get('minimum_lift_m',.02),'source_and_saved_bytes_unchanged':sha(a.source)==source_hash and sha(a.blend)==candidate_hash})
    payload={'frames':np.asarray(times),'sphere_world':np.stack(sphere_matrices)};entries={};cord_frames=[]
    for i,(vertices,triangles) in enumerate(zip(cord_vertices,cord_topology)):
        key='cord_vertices_'+str(i);payload[key]=vertices;cord_frames.append({'positions_key':key,'triangles':triangles})
    for i,(name,values) in enumerate(captured.items()):key='positions_'+str(i);payload[key]=np.stack(values);entries[key]={'mesh':name,'original_vertex_indices':export[name]['indices'],'original_triangles':export[name]['triangles']}
    a.snapshots.parent.mkdir(parents=True,exist_ok=True);np.savez_compressed(a.snapshots,**payload);sphere.data.calc_loop_triangles();metadata={'source_scene_sha256':candidate_hash,'snapshots_sha256':sha(a.snapshots),'entries':entries,'sphere_local_vertices':[list(v.co) for v in sphere.data.vertices],'sphere_triangles':[list(t.vertices) for t in sphere.data.loop_triangles],'sphere_triangle_materials':[sphere.data.polygons[t.polygon_index].material_index for t in sphere.data.loop_triangles],'cord_frames':cord_frames,'cord_anchor_world':list(anchor),'scope':'Actual saved source-model forearm/hand skin and native sphere/cord evaluated at declared half frames; cord topology stored independently per frame. Local-only derived geometry, not continuous watching.'};a.snapshots.with_name(a.snapshots.name+'.json').write_text(json.dumps(metadata,ensure_ascii=False),'utf-8');result={'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'saved-sphere-grasp-inspection-complete','checks':checks,'technical_scope_pass':all(checks.values()),'errors':errors,'source_sha256':source_hash,'candidate_sha256':candidate_hash,'writer_sha256':sha(Path(__file__)),'runtime_sha256':sha(Path(__file__).with_name('hand_control_runtime.py')),'profile_sha256':sha(a.profile),'motion_sha256':sha(a.motion),'plan_sha256':sha(a.plan),'fit_sha256':sha(a.fit),'sample_count':len(times),'held_samples':sum(r['held'] for r in rows),'protected_bone_count':len(protected),'radius_m':radius,'maximum_half_frame_sphere_step_m':maximum_step,'material_contact_anchors':anchors,'snapshots_sha256':sha(a.snapshots),'rows':rows,'normal_speed_continuous_viewing':False,'tolerances':{'wrist_integer_target_m':1e-5,'wrist_subframe_target_m':plan.get('wrist_path_tolerance_m',.00025),'finger_subframe_target_degrees':.25,'wrist_rotation_degrees':.15,'contact_gap_m':plan['contact_gap_limit_m'],'penetration_m':plan['penetration_tolerance_m'],'stability_m':plan['stability_tolerance_m']},'scope':'Actual native saved geometry/pose and conservative ideal-sphere distance, contact-pad opposition, material anchors, body preservation and supported cord. Only declared discrete times, selected same-hand region pairs; no full self-volume, general whole-character self-collision, dynamics/friction/force-closure or continuous naturalness certification. Exit0 means inspection completed: read all checks.'};a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf-8');print('GRASP_AUDIT_DONE',json.dumps({'pass':result['technical_scope_pass'],'checks':checks,'errors':errors}),flush=True)
if __name__=='__main__':main()
