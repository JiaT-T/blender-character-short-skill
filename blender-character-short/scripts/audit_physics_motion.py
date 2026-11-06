"""Read-only source-keyed bone preservation across original-data physics bake."""
from pathlib import Path
import argparse,datetime,json,math,sys
sys.dont_write_bytecode=True;sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy,numpy as np
from action_sequence_plan import sha
from body_motion_runtime import character_rig,geometry_identity,bone_worlds

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for k in ['motion','baked','plan','report']:p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    if not bpy.app.background or a.report.exists() or a.report.suffix.lower()!='.json':raise ValueError('Isolated read-only audit and new report required')
    if a.plan.stat().st_size>65536:raise ValueError('Motion preservation plan exceeds64KB')
    def unique(pairs):
        result={}
        for k,v in pairs:
            if k in result:raise ValueError('Duplicate motion audit key')
            result[k]=v
        return result
    cfg=json.loads(a.plan.read_text(encoding='utf-8'),object_pairs_hook=unique)
    if not isinstance(cfg,dict) or set(cfg)!={'schema','motion_sha256','baked_sha256','pre_roll_frames'} or type(cfg['schema']) is not int or cfg['schema']!=1 or type(cfg['pre_roll_frames']) is not int or not 0<=cfg['pre_roll_frames']<=120:raise ValueError('Explicit source/baked identity and integer pre-roll schema1 required')
    if sha(a.motion)!=cfg['motion_sha256'] or sha(a.baked)!=cfg['baked_sha256']:raise ValueError('Reviewed source/baked scene identities differ')
    bpy.ops.wm.open_mainfile(filepath=str(a.motion.resolve()),load_ui=False,use_scripts=False);scene=bpy.context.scene;arm,_=character_rig(scene);first,last=scene.frame_start,scene.frame_end;fps=scene.render.fps/scene.render.fps_base
    if scene.rigidbody_world or not arm.animation_data or not arm.animation_data.action or arm.animation_data.nla_tracks:raise ValueError('Original pre-physics baked armature action required')
    paths={b.path_from_id(k):b.name for b in arm.pose.bones for k in ['location','rotation_quaternion','scale']}
    curves=arm.animation_data.action.fcurves
    if not curves or any(c.data_path not in paths for c in curves):raise ValueError('Explicit original-bone transform channels required')
    names=sorted({paths[c.data_path] for c in curves});count=last-first+1
    if not 2<=count<=480 or count*len(names)>500000:raise ValueError('Bounded keyed-bone frame audit required')
    identity=geometry_identity(scene,arm);expected=[]
    for f in range(first,last+1):
        scene.frame_set(f);bpy.context.view_layer.update();expected.append(bone_worlds(arm,names).copy())
    bpy.ops.wm.open_mainfile(filepath=str(a.baked.resolve()),load_ui=False,use_scripts=False);scene=bpy.context.scene;arm,_=character_rig(scene);world=scene.rigidbody_world;offset=cfg['pre_roll_frames']
    if world is None or not world.point_cache.is_baked or world.point_cache.frame_start>first+offset or world.point_cache.frame_end<last+offset or scene.frame_start>first+offset or scene.frame_end<last+offset or scene.render.fps/scene.render.fps_base!=fps or geometry_identity(scene,arm)!=identity:raise ValueError('Reopened baked cache/timeline/original geometry differs')
    maxima=np.zeros(len(names));rows=[]
    for i,f in enumerate(range(first,last+1)):
        scene.frame_set(f+offset);bpy.context.view_layer.update();errors=np.max(np.abs(bone_worlds(arm,names)-expected[i]),axis=(1,2))
        if not np.isfinite(errors).all():raise ValueError('Nonfinite source-controlled pose comparison')
        maxima=np.maximum(maxima,errors);rows.append({'source_frame':f,'baked_frame':f+offset,'maximum_component_error':float(errors.max())})
    if sha(a.motion)!=cfg['motion_sha256'] or sha(a.baked)!=cfg['baked_sha256']:raise ValueError('A read-only audit input changed')
    maximum=float(maxima.max());passed=math.isfinite(maximum) and maximum<=1e-5
    result={'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'controlled-original-motion-preserved-across-physics' if passed else 'controlled-motion-preservation-failed',
            'motion_sha256':cfg['motion_sha256'],'baked_sha256':cfg['baked_sha256'],'plan_sha256':sha(a.plan),'writer_sha256':sha(Path(__file__)),'frames':[first,last],'pre_roll_frames':offset,'fps':fps,'keyed_bones':names,'integer_samples':count,'maximum_component_error':maximum,
            'worst_bones':sorted([{'bone':n,'maximum_component_error':float(v)} for n,v in zip(names,maxima)],key=lambda r:r['maximum_component_error'],reverse=True)[:12],
            'rows':rows,'inputs_unchanged':True,'pass':passed,'normal_speed_continuous_viewing':False,
            'scope':'All original transform-keyed bones compared in world space at every shifted integer frame before/after saved physics. Unkeyed cloth/hair motion, morph values, subframes, collision/force quality and naturalness are separate.'}
    a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8');print(json.dumps({k:v for k,v in result.items() if k not in ['rows','keyed_bones','worst_bones']},ensure_ascii=True))
    if not passed:raise ValueError('Original recorded control motion changed during physics')

if __name__=='__main__':main()
