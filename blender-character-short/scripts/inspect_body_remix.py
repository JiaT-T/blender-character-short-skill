"""Fresh saved-scene readback of body action identity, actual soles and amplitude."""
from pathlib import Path
import argparse,datetime,json,math,sys,hashlib
sys.dont_write_bytecode=True;sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy,numpy as np
from body_motion_plan import load_plan,sha
from body_motion_runtime import character_rig,geometry_identity,select_feet,meshes_for,bone_worlds
from body_approach_pose import constraint_signature

def action_identity(owner,excluded=()):
    ad=owner.animation_data;rows=[]
    if ad and ad.action:
        prefixes=[owner.pose.bones[n].path_from_id()+'.' for n in excluded] if owner.type=='ARMATURE' else []
        for fc in ad.action.fcurves:
            if any(fc.data_path.startswith(p) for p in prefixes):continue
            rows.append([fc.data_path,fc.array_index,fc.extrapolation,[[list(k.co),k.interpolation,k.handle_left_type,k.handle_right_type,list(k.handle_left),list(k.handle_right)] for k in fc.keyframe_points]])
    return hashlib.sha256(json.dumps(sorted(rows),separators=(',',':')).encode()).hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--case',type=Path,required=True);p.add_argument('--report',type=Path,required=True);p.add_argument('--substeps',type=int,choices=[1,2],default=2);p.add_argument('--max-sole-penetration-m',type=float,default=.002);p.add_argument('--max-contact-error-m',type=float,default=.006);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);load=lambda p:json.loads(p.read_text('utf-8'));case=load(a.case);base=a.case.resolve().parent;paths={key:(base/value).resolve() for key,value in case.items() if key!='schema'}
    required={'scene','body','fingers','remix_report','finger_report','stage_report','body_plan','mapping','remix_producer'}
    if case.get('schema')!=1 or set(paths)!=required or a.report.exists() or not all(v.is_file() for v in paths.values()) or not 0<a.max_sole_penetration_m<=.02 or not 0<a.max_contact_error_m<=.02:raise ValueError('Bounded case and distinct new report required')
    identities={key:sha(path) for key,path in paths.items()};r=load(paths['remix_report']);finger=load(paths['finger_report']);stage=load(paths['stage_report']);cfg=load(paths['mapping']);body,_=load_plan(paths['body_plan'])
    if (r['output_sha256'],finger['source_sha256'],finger['output_sha256'],stage['source_sha256'],stage['staged_sha256'],r['writer_sha256'])!=(identities['body'],identities['body'],identities['fingers'],identities['fingers'],identities['scene'],identities['remix_producer']) or r['mapping_sha256']!=identities['mapping'] or r['body_plan_sha256']!=identities['body_plan']:raise ValueError('Scene/producer chain mismatch')
    bpy.ops.wm.open_mainfile(filepath=str(paths['body']),load_ui=False,use_scripts=False);scene=bpy.context.scene;arm,actor=character_rig(scene);geometry=geometry_identity(scene,arm);constraints=constraint_signature(arm);body_action=action_identity(arm);root_action=action_identity(actor);orb_action=action_identity(scene.objects[cfg['prop']['name']]);first,last=scene.frame_start,scene.frame_end
    bpy.ops.wm.open_mainfile(filepath=str(paths['scene']),load_ui=False,use_scripts=False);scene=bpy.context.scene;arm,actor=character_rig(scene);meshes=meshes_for(scene,arm);times=[first+i/a.substeps for i in range((last-first)*a.substeps+1)];total_vertices=sum(len(o.data.vertices) for o in meshes)
    if len(times)*len(arm.pose.bones)>500000 or len(times)*total_vertices>25000000:raise ValueError('Inspection exceeds500000bone or25000000vertex frames')
    selection=select_feet(scene,arm,body);ids={o.name:{side:[v for mesh,vertices in selection[side] if mesh==o for v in vertices] for side in ['left','right']} for o in meshes};floor=cfg['ground']+body['travel']['sole_height']*cfg['height'];plane_z=scene.objects['Owned action floor'].matrix_world.translation.z;orb=scene.objects[cfg['prop']['name']];checks={'original_geometry_preserved':geometry_identity(scene,arm)==geometry,'source_constraints_preserved':constraint_signature(arm)==constraints,'nonfinger_body_action_preserved':action_identity(arm,finger['active_bones'])==body_action,'root_action_preserved':action_identity(actor)==root_action,'prop_action_preserved':action_identity(orb)==orb_action,'prop_render_enabled':not orb.hide_render and any(not c.hide_render for c in orb.users_collection),'timeline_preserved':scene.frame_start==1 and last==r['frames'] and scene.render.fps/scene.render.fps_base==r['fps']};root_positions=[];wrists=[];hips=[];min_sole=1e9;min_skin=1e9;max_contact=0.;rows=[];body_lowest=None;last_root=None;path_length=0.
    for i,t in enumerate(times):
        scene.frame_set(int(t),subframe=t-int(t));bpy.context.view_layer.update();bone_worlds(arm,arm.pose.bones.keys());points={};gaps={};whole_min=1e9
        for obj in meshes:
            ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh()
            try:
                if len(me.vertices)!=len(obj.data.vertices):raise ValueError('Saved skin topology changed')
                v=np.empty(len(me.vertices)*3,dtype=np.float32);me.vertices.foreach_get('co',v);v=v.reshape(-1,3);m=np.asarray(ev.matrix_world);v=v@m[:3,:3].T+m[:3,3]
                if not np.isfinite(v).all():raise ValueError('Nonfinite saved skin')
                points[obj.name]=v;low=int(np.argmin(v[:,2]));z=float(v[low,2])-plane_z;whole_min=min(whole_min,z)
                if z<min_skin:
                    min_skin=z;materials={obj.data.materials[p.material_index].name for p in obj.data.polygons if low in p.vertices};body_lowest={'frame':t,'mesh':obj.name,'vertex':low,'point_world':v[low].tolist(),'materials':sorted(materials)}
                for side in ['left','right']:
                    if ids[obj.name][side]:gaps[side]=min(gaps.get(side,1e9),float(v[ids[obj.name][side],2].min())-floor)
            finally:ev.to_mesh_clear()
        min_sole=min(min_sole,*gaps.values());contact_rows={}
        for side in ['left','right']:
            lo=int(math.floor(t));hi=int(math.ceil(t));left=r['rows'][lo-1]['feet'][side];right=r['rows'][hi-1]['feet'][side]
            if left['mode']==right['mode']=='material-contact' and left['vertex']==right['vertex'] and np.max(np.abs(np.asarray(left['anchor'])-np.asarray(right['anchor'])))<1e-7:
                mesh,index=left['vertex'];error=float(np.linalg.norm(points[mesh][index]-np.asarray(left['anchor'])));max_contact=max(max_contact,error);contact_rows[side]={'error_m':error,'vertex':left['vertex']}
        root=np.asarray(actor.matrix_world.translation);root_positions.append(root.copy());hips.append(np.asarray(arm.matrix_world@arm.pose.bones[body['hips']].head));w=[np.asarray(arm.matrix_world@arm.pose.bones[cfg['bones'][side+'_wrist']].head) for side in ['left','right']];wrists.append(w)
        if last_root is not None:path_length+=float(np.linalg.norm(root-last_root))
        last_root=root;rows.append({'frame':t,'sole_gap_to_declared_floor_m':gaps,'whole_skin_gap_to_actual_plane_m':whole_min,'contacts':contact_rows})
        if i%48==0:print('BODY_REMIX_READBACK',i+1,len(times),flush=True)
    roots=np.stack(root_positions);hands=np.asarray(wrists);hip=np.stack(hips);checks['sole_penetration_within_declared_limit']=min_sole>=-a.max_sole_penetration_m;checks['tracked_contact_within_declared_limit']=max_contact<=a.max_contact_error_m;checks['inputs_unchanged']=all(sha(paths[k])==v for k,v in identities.items());result={'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'saved-body-remix-readback-complete','inputs':{k:{'path':str(paths[k]),'sha256':v} for k,v in identities.items()},'writer_sha256':sha(Path(__file__)),'geometry_identity':geometry,'checks':checks,'technical_scope_pass':all(checks.values()),'frames':last,'samples':len(times),'substeps':a.substeps,'max_sole_penetration_m':a.max_sole_penetration_m,'max_contact_error_m':a.max_contact_error_m,'minimum_sole_gap_to_declared_floor_m':min_sole,'minimum_whole_skin_gap_to_actual_plane_m':min_skin,'lowest_whole_skin_sample':body_lowest,'maximum_tracked_contact_error_m':max_contact,'root_axis_range_m':np.ptp(roots,axis=0).tolist(),'root_path_length_m':path_length,'maximum_wrist_span_m':float(np.linalg.norm(hands[:,0]-hands[:,1],axis=1).max()),'hip_vertical_range_m':float(np.ptp(hip[:,2])),'rows':rows,'normal_speed_continuous_viewing':False,'scope':'Saved action/constraint/rest/skin identity and integer/half-frame actual weighted sole/contact samples. Whole-model floor minimum includes all alpha/hidden-material geometry and is a diagnostic, not visible-penetration or closed-volume certification. No cloth dynamics, general self-collision or artistic naturalness acceptance.'};a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf-8');print('BODY_REMIX_INSPECTED',json.dumps({k:result[k] for k in ['checks','samples','minimum_sole_gap_to_declared_floor_m','minimum_whole_skin_gap_to_actual_plane_m','maximum_wrist_span_m']}),flush=True)

if __name__=='__main__':main()
