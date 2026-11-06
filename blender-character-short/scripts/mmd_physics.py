"""Documented original-data MMD Tools assembly/bake on isolated scene copies.

Requires enabled official addon/version, caller-reviewed instructions, original
PMX physics data and explicit input hashes. No installation, parameter tuning,
MMR generation, network or modification of source scenes is performed.
"""
from pathlib import Path
import argparse,datetime,importlib,json,math,sys
sys.dont_write_bytecode=True;sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy,numpy as np
from body_motion_runtime import character_rig,geometry_identity
from action_sequence_plan import sha

def finite_matrix(value, label):
    result=np.asarray(value,dtype=np.float64)
    if result.shape!=(4,4) or not np.isfinite(result).all():
        raise ValueError('Finite 4x4 matrix required: '+label)
    return result.copy()

def pose_error(actual,expected,label):
    # Check operands before max(): Python max(0, NaN) can silently retain zero.
    a=finite_matrix(actual,label+' actual');b=finite_matrix(expected,label+' expected')
    error=float(np.max(np.abs(a-b)))
    if not math.isfinite(error):raise ValueError('Nonfinite pose comparison: '+label)
    return error

def load_config(path,mode):
    if path.stat().st_size>65536:raise ValueError('Physics plan exceeds64KB')
    def unique(pairs):
        out={}
        for k,v in pairs:
            if k in out:raise ValueError('Duplicate physics plan key')
            out[k]=v
        return out
    cfg=json.loads(path.read_text(encoding='utf-8'),object_pairs_hook=unique)
    common={'schema','module','addon_version','instructions_url'}
    fields=common|({'model_sha256','motion_sha256','pre_roll_frames','mute_ik','probe_frames','pack_resources'} if mode=='prepare' else {'source_sha256','frames','probe_frames'})
    if not isinstance(cfg,dict) or set(cfg)!=fields or type(cfg['schema']) is not int or cfg['schema']!=1:raise ValueError('Explicit physics plan schema1 required')
    if cfg['instructions_url']!='https://mmd-blender.fandom.com/wiki/MMD_Tools/Manual':raise ValueError('Matching reviewed original-data manual required')
    module=cfg['module']
    if not isinstance(module,str) or not (module=='mmd_tools' or module.startswith('bl_ext.') and module.endswith('.mmd_tools')):raise ValueError('Explicit MMD Tools module required')
    if not bpy.context.preferences.addons.get(module):raise ValueError('Requested installed MMD Tools addon is not enabled')
    addon=importlib.import_module(module)
    if cfg['addon_version']!='4.5.14' or getattr(addon,'MMD_TOOLS_VERSION',None)!=cfg['addon_version']:raise ValueError('Only the actually reviewed MMD Tools4.5.14 interface is supported by this route')
    for key in (['model_sha256','motion_sha256'] if mode=='prepare' else ['source_sha256']):
        v=cfg[key]
        if not isinstance(v,str) or len(v)!=64 or any(c not in '0123456789abcdef' for c in v):raise ValueError('Reviewed lowercase input SHA256 required')
    probes=cfg['probe_frames']
    if not isinstance(probes,list) or not 2<=len(probes)<=12 or any(type(x) is not int or x<1 for x in probes) or probes!=sorted(set(probes)):raise ValueError('Explicit sorted unique physics probe frames required')
    if mode=='prepare':
        if type(cfg['pre_roll_frames']) is not int or not 0<=cfg['pre_roll_frames']<=120 or type(cfg['pack_resources']) is not bool:raise ValueError('Explicit bounded settling pre-roll and packing choice required')
        if not isinstance(cfg['mute_ik'],list) or len(cfg['mute_ik'])>16 or any(not isinstance(r,dict) or set(r)!={'bone','constraint'} or any(not isinstance(v,str) or not v for v in r.values()) for r in cfg['mute_ik']):raise ValueError('Explicit original IK entries required')
    else:
        f=cfg['frames']
        if not isinstance(f,list) or len(f)!=2 or any(type(v) is not int for v in f) or not 1<=f[0]<f[1] or f[1]-f[0]+1>480:raise ValueError('Bounded integer physics cache range required')
        if probes[0]<f[0] or probes[-1]>f[1]:raise ValueError('Physics probes exceed cache range')
    return cfg

def open_copy(path):bpy.ops.wm.open_mainfile(filepath=str(path.resolve()),load_ui=False,use_scripts=False)

def select_root():
    roots=[o for o in bpy.data.objects if getattr(o,'mmd_type',None)=='ROOT']
    if len(roots)!=1:raise ValueError('One original MMD model root required')
    bpy.ops.object.select_all(action='DESELECT');roots[0].select_set(True);bpy.context.view_layer.objects.active=roots[0]
    if bpy.context.object.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
    return roots[0]

def prepare(args,cfg):
    if args.model is None or args.motion is None or sha(args.model)!=cfg['model_sha256'] or sha(args.motion)!=cfg['motion_sha256']:raise ValueError('Original-physics/model motion input identity mismatch')
    open_copy(args.motion);scene=bpy.context.scene;source_arm,source_actor=character_rig(scene)
    if scene.frame_start!=1 or scene.rigidbody_world or not source_arm.animation_data or not source_arm.animation_data.action or source_arm.animation_data.nla_tracks:raise ValueError('Fresh baked original-rig motion before physics is required')
    count=scene.frame_end;fps=scene.render.fps/scene.render.fps_base
    if not float(fps).is_integer() or not 2<=count<=480 or (count+cfg['pre_roll_frames'])*len(source_arm.pose.bones)>500000 or count+cfg['pre_roll_frames']>480:raise ValueError('Bounded source motion/pre-roll required')
    if cfg['probe_frames'][-1]>count:raise ValueError('Motion probe exceeds source range')
    mapping={b.path_from_id(k):b.name for b in source_arm.pose.bones for k in ['rotation_quaternion','location','scale']}
    if any(c.data_path not in mapping for c in source_arm.animation_data.action.fcurves):raise ValueError('Only explicit original-bone motion channels are supported')
    names=sorted({mapping[c.data_path] for c in source_arm.animation_data.action.fcurves})
    if any(source_arm.pose.bones[n].rotation_mode!='QUATERNION' for n in names):raise ValueError('Source quaternion action required')
    for r in cfg['mute_ik']:
        c=source_arm.pose.bones[r['bone']].constraints.get(r['constraint'])
        if c is None or c.type!='IK' or not c.mute:raise ValueError('Declared source IK state differs')
    geometry=geometry_identity(scene,source_arm);action_name=source_arm.animation_data.action.name;root_matrix=finite_matrix(source_actor.matrix_world,'source actor')
    if any(c.extrapolation!='CONSTANT' for c in source_arm.animation_data.action.fcurves):raise ValueError('Settling pre-roll requires explicit constant endpoint extrapolation')
    samples={}
    for f in cfg['probe_frames']:
        scene.frame_set(f);bpy.context.view_layer.update();samples[f]={n:finite_matrix(source_arm.pose.bones[n].matrix,'source pose '+n) for n in names}
    open_copy(args.model);scene=bpy.context.scene;arm,actor=character_rig(scene);root=select_root()
    if root.mmd_root.is_built or arm.animation_data and arm.animation_data.action:raise ValueError('Use a preserved unassembled original-physics model copy')
    rigids=[o for o in scene.objects if getattr(o,'mmd_type',None)=='RIGID_BODY'];joints=[o for o in scene.objects if getattr(o,'mmd_type',None)=='JOINT']
    if not 1<=len(rigids)<=1024 or not 1<=len(joints)<=4096:raise ValueError('Original author rigid body/joint data missing or beyond lightweight bounds')
    if geometry_identity(scene,arm)!=geometry or not np.array_equal(finite_matrix(actor.matrix_world,'target actor'),root_matrix):raise ValueError('Original physics reimport differs from motion rest/skin/root identity')
    with bpy.data.libraries.load(str(args.motion.resolve()),link=False) as (available,loaded):loaded.actions=[action_name]
    action=loaded.actions[0]
    if action is None:raise ValueError('Recorded action did not load')
    arm.animation_data_create();arm.animation_data.action=action
    for name in names:arm.pose.bones[name].rotation_mode='QUATERNION'
    muted=[]
    for r in cfg['mute_ik']:
        c=arm.pose.bones[r['bone']].constraints.get(r['constraint'])
        if c is None or c.type!='IK':raise ValueError('Original target IK differs')
        muted.append({**r,'previous_mute':c.mute});c.mute=True
    error=0.
    for f,expected in samples.items():
        scene.frame_set(f);bpy.context.view_layer.update()
        for name,value in expected.items():error=max(error,pose_error(arm.pose.bones[name].matrix,value,'transferred '+name+' / '+str(f)))
    if not math.isfinite(error) or error>1e-5:raise ValueError('Transferred action differs before physics: '+str(error))
    for curve in action.fcurves:
        for key in curve.keyframe_points:key.co.x+=cfg['pre_roll_frames'];key.handle_left.x+=cfg['pre_roll_frames'];key.handle_right.x+=cfg['pre_roll_frames']
    scene.frame_start=1;scene.frame_end=count+cfg['pre_roll_frames'];scene.render.fps=int(fps);scene.render.fps_base=1;scene.frame_set(1)
    if cfg['pack_resources']:bpy.ops.file.pack_all()
    select_root();bpy.ops.wm.save_as_mainfile(filepath=str(args.output.resolve()),check_existing=False)
    if 'FINISHED' not in bpy.ops.mmd_tools.rigid_body_world_update() or 'FINISHED' not in bpy.ops.mmd_tools.build_rig() or not root.mmd_root.is_built:raise RuntimeError('Documented MMD world/assembly step failed')
    world=scene.rigidbody_world;world.point_cache.frame_start=1;world.point_cache.frame_end=scene.frame_end
    if len(world.constraints.objects)>50000:raise ValueError('Assembled constraint budget exceeded')
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output.resolve()),check_existing=False)
    if sha(args.model)!=cfg['model_sha256'] or sha(args.motion)!=cfg['motion_sha256']:raise ValueError('A source scene changed')
    return {'status':'original-mmd-physics-assembled-await-bake-and-visuals','motion_frames':count,'cache_frames':[1,scene.frame_end],
            'displayed_motion_frames':[1+cfg['pre_roll_frames'],scene.frame_end],'fps':int(fps),'rigid_bodies':len(rigids),'original_joints':len(joints),
            'world_constraints':len(world.constraints.objects),'substeps':world.substeps_per_frame,'solver_iterations':world.solver_iterations,
            'geometry_identity':geometry,'transferred_pose_max_component_error':error,'pose_probe_frames':cfg['probe_frames'],
            'declared_transfer_component_tolerance':1e-5,'muted_original_IK':muted,'packed_resources':cfg['pack_resources'],'baked':world.point_cache.is_baked}

def bake(args,cfg):
    if args.blend is None or sha(args.blend)!=cfg['source_sha256']:raise ValueError('Prepared physics source identity mismatch')
    open_copy(args.blend);scene=bpy.context.scene;root=select_root();world=scene.rigidbody_world
    if world is None or not root.mmd_root.is_built or [world.point_cache.frame_start,world.point_cache.frame_end]!=cfg['frames'] or [scene.frame_start,scene.frame_end]!=cfg['frames']:raise ValueError('Saved assembled scene/cache range differs')
    rigids=list(world.collection.objects);first,last=cfg['frames']
    if not 1<=len(rigids)<=1024 or len(rigids)*(last-first+1)>500000 or len(world.constraints.objects)>50000:raise ValueError('Bounded original physics world required')
    scene.frame_set(first);bpy.ops.wm.save_as_mainfile(filepath=str(args.output.resolve()),check_existing=False)
    if 'FINISHED' not in bpy.ops.mmd_tools.ptcache_rigid_body_bake() or not world.point_cache.is_baked:raise RuntimeError('Documented bake did not produce a confirmed cache')
    arm,_=character_rig(scene);meshes=[o for o in scene.objects if o.type=='MESH' and any(m.type=='ARMATURE' and m.object==arm for m in o.modifiers)];samples=[]
    for frame in range(first,last+1):
        scene.frame_set(frame);bpy.context.view_layer.update()
        if any(not math.isfinite(v) for ob in rigids for row in ob.matrix_world for v in row):raise ValueError('Nonfinite cached rigid body transform at '+str(frame))
        if frame not in cfg['probe_frames']:continue
        points=[]
        for ob in meshes:
            ev=ob.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh()
            try:points.extend(ev.matrix_world@v.co for v in me.vertices)
            finally:ev.to_mesh_clear()
        if not points or any(not math.isfinite(v) for point in points for v in point):raise ValueError('Nonfinite cached skin at '+str(frame))
        samples.append({'frame':frame,'bounds':[[min(p[i] for p in points) for i in range(3)],[max(p[i] for p in points) for i in range(3)]]})
    scene.frame_set(first);bpy.ops.wm.save_as_mainfile(filepath=str(args.output.resolve()),check_existing=False)
    # Prove the committed cache survives a fresh scene load, not just in-memory state.
    open_copy(args.output);reopened=bpy.context.scene.rigidbody_world
    if reopened is None or not reopened.point_cache.is_baked or [reopened.point_cache.frame_start,reopened.point_cache.frame_end]!=cfg['frames']:raise ValueError('Physics cache did not survive saved-scene reopen')
    if sha(args.blend)!=cfg['source_sha256']:raise ValueError('Prepared source changed')
    return {'status':'original-mmd-physics-baked-reopened-await-visuals','cache_frames':cfg['frames'],'baked':True,'reopened_cache_verified':True,
            'all_integer_rigid_transforms_finite':True,'rigid_body_count':len(rigids),'skin_probe_samples':samples,
            'scope':'Original PMX rigid data, installed plugin defaults, bounded bake; integer rigid-transform finite check and explicit skin probes. No full-volume collision, force accuracy, continuous visual naturalness or exact MMD simulation acceptance.'}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--mode',choices=['prepare','bake'],required=True)
    for key in ['model','motion','blend']:p.add_argument('--'+key,type=Path)
    for key in ['plan','output','report']:p.add_argument('--'+key,type=Path,required=True)
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    if not bpy.app.background:raise ValueError('Use an isolated background Blender process')
    if args.output.exists() or args.report.exists() or args.output.suffix.lower()!='.blend' or args.report.suffix.lower()!='.json':raise ValueError('New blend/report outputs required')
    cfg=load_config(args.plan,args.mode);args.output.parent.mkdir(parents=True,exist_ok=True)
    result=prepare(args,cfg) if args.mode=='prepare' else bake(args,cfg)
    result.update(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),blender=bpy.app.version_string,addon_module=cfg['module'],addon_version=cfg['addon_version'],instructions_url=cfg['instructions_url'],output=str(args.output.resolve()),output_sha256=sha(args.output),plan_sha256=sha(args.plan),writer_sha256=sha(Path(__file__)),normal_speed_continuous_viewing=False)
    args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8');print(json.dumps(result,ensure_ascii=True))

if __name__=='__main__':main()
