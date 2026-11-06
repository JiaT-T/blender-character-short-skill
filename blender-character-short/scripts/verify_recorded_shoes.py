"""Independently reopen an experimental original-IK/FK shoe-height result.

Each integer and half frame is checked. Integer/body results and stricter
half-frame proxy-height limits are separate; no force/contact or naturalness
acceptance. --require-half-height fails if that separate limit is unmet.
"""
from pathlib import Path
import argparse,datetime,hashlib,json,math,sys
import bpy,numpy as np
sys.dont_write_bytecode=True;sys.path.insert(0,str(Path(__file__).resolve().parent))
from body_motion_runtime import character_rig,geometry_identity,bone_worlds,select_feet,foot_points
from bake_elbow_poles import dependency_bones
from recorded_shoe_plan import load

def lowest(selection,side):
    values=np.asarray([p for _,_,p in foot_points(selection,side)],dtype=np.float64)
    if values.ndim!=2 or values.shape[1]!=3 or not len(values) or not np.isfinite(values).all():raise ValueError('Finite actual weighted shoe vertices required')
    return float(values[:,2].min())

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['source','trial','plan','bake-report','report']:p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--require-half-height',action='store_true');a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);source=a.source.resolve();target=a.trial.resolve();out=a.report.resolve()
    if not bpy.app.background or out.exists() or out.suffix.lower()!='.json' or len({source,target,a.plan.resolve(),a.bake_report.resolve(),out})!=5 or any(x.stat().st_size>512*1024*1024 for x in [source,target]) or a.bake_report.stat().st_size>1024*1024:raise ValueError('Bounded isolated source/trial and new read-only report required')
    sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();cfg=load(a.plan);producer=json.loads(a.bake_report.read_text('utf-8'))
    if producer.get('integer_frame_technical_pass') is not True or producer.get('source_sha256')!=sha(source) or cfg['blend_sha256']!=sha(source) or producer.get('output_sha256')!=sha(target):raise ValueError('Original source/trial evidence differs')
    for field,file in [('writer_sha256','calibrate_recorded_shoes.py'),('validator_sha256','recorded_shoe_plan.py'),('runtime_sha256','body_motion_runtime.py'),('dependency_sha256','bake_elbow_poles.py'),('contact_runtime_sha256','contact_motion.py')]:
        if producer.get(field)!=sha(Path(__file__).with_name(file)):raise ValueError('Original producer dependency bytes changed; use frozen matching producer')
    if producer.get('plan_sha256')!=sha(a.plan):raise ValueError('Shoe plan changed after bake')
    value=producer.get('constant_root_lowering_m')
    if type(value) not in [int,float] or not math.isfinite(value) or not 0<=value<=cfg['maximum_root_lowering_H']*cfg['height']:raise ValueError('Finite bounded recorded body-height adjustment required')
    first,last=cfg['frames'];count=last-first+1;out.parent.mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False);scene=bpy.context.scene;arm,_=character_rig(scene);names=list(arm.pose.bones.keys());identity=geometry_identity(scene,arm)
    if count*len(names)>500000 or [scene.frame_start,scene.frame_end]!=[first,last] or scene.render.fps/scene.render.fps_base!=cfg['fps']:raise ValueError('Original integer frame/bone budget or fps differs')
    changed={n for chain in cfg['legs'].values() for n in chain};allowed=dependency_bones(arm,changed);protected=[i for i,n in enumerate(names) if n not in allowed];root_deps=dependency_bones(arm,[cfg['root_bone']]);indices=[i for i,n in enumerate(names) if n in root_deps]
    frames=[first+i*.5 for i in range((count-1)*2+1)];expected={};lengths={};states={}
    for e in cfg['existing_IK']:
     c=arm.pose.bones[e['bone']].constraints[e['constraint']];states[e['bone']+':'+e['constraint']]=(c.mute,c.use_stretch,c.subtarget,c.chain_count)
    for f in frames:
     scene.frame_set(int(f),subframe=f%1);bpy.context.view_layer.update();m=bone_worlds(arm,names);m[indices,2,3]-=producer['constant_root_lowering_m'];expected[f]=m
     lengths[f]={s:[(arm.matrix_world@arm.pose.bones[chain[i+1]].head-arm.matrix_world@arm.pose.bones[chain[i]].head).length for i in range(2)] for s,chain in cfg['legs'].items()}
    bpy.ops.wm.open_mainfile(filepath=str(target),load_ui=False,use_scripts=False);scene=bpy.context.scene;arm,_=character_rig(scene);selection=select_feet(scene,arm,cfg)
    if scene.rigidbody_world or geometry_identity(scene,arm)!=identity:raise ValueError('Trial geometry or pre-physics route differs')
    for e in cfg['existing_IK']:
     c=arm.pose.bones[e['bone']].constraints[e['constraint']]
     if states[e['bone']+':'+e['constraint']]!=(c.mute,c.use_stretch,c.subtarget,c.chain_count):raise ValueError('Existing original constraint state changed')
    rows=[];max_body=0.;max_height=0.;max_length=0.;max_unit=0.
    for f in frames:
     scene.frame_set(int(f),subframe=f%1);bpy.context.view_layer.update();actual=bone_worlds(arm,names);body=float(np.max(np.abs(actual[protected]-expected[f][protected])));max_body=max(max_body,body);feet={}
     for side,chain in cfg['legs'].items():
      lo=int(f)-first;hi=min(lo+1,count-1);fraction=f%1;desired=(1-fraction)*cfg['rows'][lo]['feet'][side]['target_lowest_sole_z_m']+fraction*cfg['rows'][hi]['feet'][side]['target_lowest_sole_z_m'];low=lowest(selection,side);error=abs(low-desired)
      points=[arm.matrix_world@arm.pose.bones[n].head for n in chain[:3]];length=max(abs((points[i+1]-points[i]).length-lengths[f][side][i]) for i in range(2));max_length=max(max_length,length);max_height=max(max_height,error)
      for n in chain:
       singular=np.linalg.svd(actual[names.index(n),:3,:3],compute_uv=False);max_unit=max(max_unit,float(np.max(np.abs(singular-1))))
      feet[side]={'lowest_sole_z_m':low,'proxy_error_m':error,'segment_length_error_m':length}
     rows.append({'frame':f,'protected_component_error':body,'feet':feet})
    integer_height=max(r['feet'][s]['proxy_error_m'] for r in rows if r['frame'].is_integer() for s in ['left','right'])
    passed=max_body<=1e-5 and integer_height<=cfg['maximum_height_error_H']*cfg['height'] and max_length<=cfg['maximum_segment_length_error_H']*cfg['height'] and max_unit<=1e-5
    result={'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_sha256':sha(source),'trial_sha256':sha(target),'writer_sha256':sha(Path(__file__)),'plan_sha256':sha(a.plan),'bake_report_sha256':sha(a.bake_report),'validator_sha256':sha(Path(__file__).with_name('recorded_shoe_plan.py')),'half_frame_height_required':a.require_half_height,'geometry_identity':identity,'original_IK_state_preserved':True,'sample_count':len(frames),'integer_count':count,'half_frame_count':len(frames)-count,'maximum_protected_component_error':max_body,'maximum_integer_proxy_sole_error_m':integer_height,'maximum_including_half_frames_proxy_sole_error_m':max_height,'maximum_anatomic_length_error_m':max_length,'maximum_bone_unit_scale_error':max_unit,'integer_and_body_reopen_checks_pass':passed,'half_frame_proxy_height_limit_pass':max_height<=cfg['maximum_height_error_H']*cfg['height'],'normal_speed_continuous_viewing':False,'scope':'Saved original FK, actual weighted lowest sole, original leg lengths and protected source motion checked at every integer and half frame. Source geometric proxies are not physical contacts; no collision, force, continuous-time or naturalness acceptance.','rows':rows}
    result['declared_height_proxy']=cfg.get('height_proxy',{'kind':'legacy-explicit-height-proxy','source_endpoint_truth_verified':False})
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),'utf-8');print(json.dumps({k:v for k,v in result.items() if k!='rows'},ensure_ascii=True))
    if not passed or (a.require_half_height and max_height>cfg['maximum_height_error_H']*cfg['height']):raise ValueError('Required reopened shoe adaptation checks failed; read separate integer/half booleans')

if __name__=='__main__':main()
