"""Prepare/independently verify an unanimated MMD + reviewed MMR baseline."""
from pathlib import Path
import argparse,json,sys,math,datetime
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy,numpy as np
from mathutils import Matrix,Vector
import scene_integrity as integrity
from production_contract import sha,digest,declared_file,write_json,baseline_identity,require_baseline_binding
def producer():return {n:sha(Path(__file__).with_name(n)) for n in ['mmd_baseline.py','scene_integrity.py','production_contract.py']}

def arrays(mesh):
    ob=mesh.evaluated_get(bpy.context.evaluated_depsgraph_get());data=ob.to_mesh()
    try:
        a=np.empty(len(data.vertices)*3,np.float32);data.vertices.foreach_get('co',a);return a.reshape(-1,3).copy()
    finally:ob.to_mesh_clear()
def mesh_hash(mesh):return digest(integrity._mesh(mesh.data))
def unanimated(objects):
    for o in objects:
        a=o.animation_data
        if a and (a.action or a.nla_tracks):raise ValueError('Unanimated baseline required: '+o.name)
        k=getattr(o.data,'shape_keys',None)
        if k and k.animation_data and (k.animation_data.action or k.animation_data.nla_tracks):raise ValueError('Baseline has animated shapes')
def controls_report(profile):
    model=bpy.data.objects[profile['model']];rig=bpy.data.objects[profile['controller']];mesh=bpy.data.objects[profile['mesh']]
    rows=[]
    for spec in profile['probes']:
        if spec['kind'] not in ('rotate','translate'):raise ValueError('Unknown probe kind')
        amount=spec['amount'];axis=spec['axis']
        if axis not in 'XYZ' or not math.isfinite(amount) or abs(amount)>(.25 if spec['kind']=='rotate' else .02):raise ValueError('Probe exceeds small bounded response test')
        p=rig.pose.bones[spec['control']];original=model.pose.bones[spec['model_bone']];saved=[]
        for switch in spec.get('switches',[]):
            owner=rig.pose.bones[switch['bone']];key=switch['property'];saved.append((owner,key,owner[key]));owner[key]=switch['value']
        rig.update_tag();model.update_tag();bpy.context.view_layer.update()
        base=arrays(mesh);matrix=p.matrix_basis.copy();p0=p.matrix.copy();m0=original.matrix.copy()
        ids={original.name}|{b.name for b in model.data.bones[original.name].children_recursive};groups={g.index for g in mesh.vertex_groups if g.name in ids};selected=np.array([v.index for v in mesh.data.vertices if any(w.group in groups and w.weight>.02 for w in v.groups)],np.int32)
        try:
            if spec['kind']=='rotate':p.matrix_basis=matrix@Matrix.Rotation(amount,4,axis)
            else:
                change=matrix.copy();change.translation+=Vector(tuple(amount if i=='XYZ'.index(axis) else 0 for i in range(3)));p.matrix_basis=change
            rig.update_tag();model.update_tag();bpy.context.view_layer.update();changed=arrays(mesh);dist=np.linalg.norm(changed-base,axis=1)
            row={'id':spec['id'],'control':spec['control'],'model_bone':spec['model_bone'],'weighted_vertices':len(selected),'skin_max_delta_m':float(dist[selected].max()) if len(selected) else 0.,'control_delta':max(abs(p.matrix[i][j]-p0[i][j]) for i in range(4) for j in range(4)),'original_bone_delta':max(abs(original.matrix[i][j]-m0[i][j]) for i in range(4) for j in range(4)),'finite':bool(np.isfinite(changed).all())}
        finally:
            p.matrix_basis=matrix;rig.update_tag();model.update_tag();bpy.context.view_layer.update();restored=arrays(mesh)
            for owner,key,value in saved:owner[key]=value
            rig.update_tag();model.update_tag();bpy.context.view_layer.update()
        row['restoration_error_m']=float(np.linalg.norm(restored-base,axis=1).max());row['passed']=row['finite'] and row['skin_max_delta_m']>1e-5 and row['original_bone_delta']>1e-5 and row['control_delta']>1e-5 and row['restoration_error_m']<1e-6;rows.append(row)
    return {'probes':rows,'all_passed':bool(rows) and all(r['passed'] for r in rows),'normal_speed_acceptance':False}
def prepare(plan,base):
    identity=baseline_identity(plan,base)
    source=declared_file(plan['source'],base);profile_file=declared_file(plan['profile'],base);profile=json.loads(Path(profile_file['path']).read_text('utf-8'));output=(Path(base)/plan['output']).resolve();report=(Path(base)/plan['report']).resolve()
    if output.exists() or report.exists():raise FileExistsError('Keep prior baseline outputs')
    bpy.ops.wm.open_mainfile(filepath=source['path'],load_ui=False,use_scripts=False);model=bpy.data.objects[profile['model']];mesh=bpy.data.objects[profile['mesh']]
    unanimated([o for o in bpy.context.scene.objects if o.type in ('MESH','ARMATURE')]);before=mesh_hash(mesh);rest={b.name:np.array(b.matrix_local) for b in model.data.bones};neutral=arrays(mesh)
    if plan['mode']=='generate':
        if plan.get('generation_guidance_acknowledged') is not True:raise ValueError('Explicit reviewed generation guidance required')
        if any(o.name==profile['controller'] for o in bpy.data.objects) or model.mmr.Generate_controllers or bpy.data.objects.get('MMR_Rig_relative'):raise ValueError('Refuse generating on existing rig/metarig')
        mapping_file=declared_file(plan['mapping'],base);mapping=json.loads(Path(mapping_file['path']).read_text('utf-8'))
        if not mapping or any(k not in model.data.bones for k in mapping):raise ValueError('Bone mapping must match actual MMD names')
        model.mmr.extras_enabled=True;model.mmr.Finger_options=True;model.mmr.Import_presets=True;model.mmr.json_filepath=mapping_file['path'];model.mmr.Only_meta_bones_are_generated=False
        bpy.ops.object.select_all(action='DESELECT');model.hide_set(False);model.select_set(True);bpy.context.view_layer.objects.active=model
        result=bpy.ops.object.mmr_rig('EXEC_DEFAULT',Towards=profile['towards'])
        if result!={'FINISHED'}:raise RuntimeError('MMR did not finish')
    elif plan['mode']!='provided':raise ValueError('mode must be provided or generate')
    if bpy.context.object and bpy.context.object.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
    rig=bpy.data.objects[profile['controller']];bpy.context.view_layer.update()
    rest_delta=max(float(np.abs(np.array(b.matrix_local)-rest[b.name]).max()) for b in model.data.bones)
    if set(rest)!=set(model.data.bones.keys()) or mesh_hash(mesh)!=before or rest_delta>(1e-4 if plan['mode']=='generate' else 0):raise ValueError('Original geometry/weights/shapes/rest data changed outside reviewed generation tolerance')
    response=controls_report(profile)
    if not response['all_passed']:write_json(report,{'accepted':False,'response':response});raise ValueError('A required actual-skin response failed')
    # Static baselines may deliberately set production fps; existing animation is refused above.
    if 'fps' in plan:bpy.context.scene.render.fps=plan['fps'];bpy.context.scene.render.fps_base=1
    original_poses=digest({o.name:integrity._object(o) for o in [model,rig,mesh]});data_identity=digest({o.name:integrity._armature(o.data) for o in [model,rig]});bpy.ops.file.pack_all();output.parent.mkdir(parents=True,exist_ok=True);bpy.ops.wm.save_as_mainfile(filepath=str(output),check_existing=False)
    result={'accepted':True,'stage':'prepared_requires_fresh_verify','mode':plan['mode'],'source':source,'profile':profile_file,'output':str(output),'output_sha256':sha(output),'protected_mesh':mesh_hash(mesh),'protected_rig_objects':original_poses,'protected_rig_data':data_identity,'original_rest_max_delta':rest_delta,'neutral_skin_max_delta_m':float(np.linalg.norm(arrays(mesh)-neutral,axis=1).max()),'model_bones':len(model.data.bones),'controller_bones':len(rig.data.bones),'response':response,'source_unchanged':sha(source['path'])==source['sha256'],'ui_used':False}
    result.update(producer=producer(),plan_identity=identity);write_json(report,result);return result
def verify(plan,base):
    prior=json.loads((Path(base)/plan['report']).read_text('utf-8'));p=Path(prior['output'])
    require_baseline_binding(plan,prior,base)
    if sha(p)!=prior['output_sha256'] or prior.get('producer')!=producer():raise ValueError('Prepared baseline/producer changed; use a new plan version')
    profile_file=declared_file(plan['profile'],base);profile=json.loads(Path(profile_file['path']).read_text('utf-8'));bpy.ops.wm.open_mainfile(filepath=str(p),load_ui=False,use_scripts=False)
    model=bpy.data.objects[profile['model']];rig=bpy.data.objects[profile['controller']];mesh=bpy.data.objects[profile['mesh']];unanimated([model,rig,mesh]);bpy.context.view_layer.update()
    checks={'mesh':mesh_hash(mesh)==prior['protected_mesh'],'rig_objects':digest({o.name:integrity._object(o) for o in [model,rig,mesh]})==prior['protected_rig_objects'],'rig_data':digest({o.name:integrity._armature(o.data) for o in [model,rig]})==prior['protected_rig_data']}
    if 'fps' in plan and (bpy.context.scene.render.fps!=plan['fps'] or bpy.context.scene.render.fps_base!=1):raise ValueError('Saved baseline fps differs from its bound plan')
    response=controls_report(profile);result={'accepted':all(checks.values()) and response['all_passed'],'baseline_output_sha256':prior['output_sha256'],'plan_identity':prior['plan_identity'],'producer':producer(),'fresh_process_reopen':True,'protected_checks':checks,'response':response,'source_unchanged':sha(p)==prior['output_sha256'],'blender':bpy.app.version_string,'ui_used':False,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat()};write_json(Path(base)/plan['verify_report'],result)
    if not result['accepted']:raise ValueError('Fresh baseline verification failed')
    return result
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',required=True);p.add_argument('--mode',choices=['prepare','verify'],required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);path=Path(a.plan).resolve();plan=json.loads(path.read_text('utf-8'));print(json.dumps((prepare if a.mode=='prepare' else verify)(plan,path.parent),ensure_ascii=True))
if __name__=='__main__':main()
