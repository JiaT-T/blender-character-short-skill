"""Bake or freshly verify an already assembled existing-controller MMD project.

Run bake and verify in distinct Blender processes. No controller regeneration,
MMR operations, world tuning, assembly changes or implicit cache clearing.
"""
from pathlib import Path
import argparse
import datetime
import hashlib
import importlib
import json
import math
import sys
import bpy


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main(arguments=None):
    p = argparse.ArgumentParser()
    p.add_argument('--mode', choices=['bake', 'verify'], required=True)
    for field in ('source', 'plan', 'report'):
        p.add_argument('--' + field, type=Path, required=True)
    p.add_argument('--output', type=Path)
    args = p.parse_args(arguments if arguments is not None else sys.argv[sys.argv.index('--') + 1:])
    if not bpy.app.background:
        raise ValueError('Isolated background process required')
    if args.report.exists() or args.mode == 'bake' and (args.output is None or args.output.exists()):
        raise ValueError('New report and bake output required')
    if args.mode == 'verify' and args.output is not None:
        raise ValueError('Verification is read-only; omit output')
    if args.plan.stat().st_size > 65536:
        raise ValueError('Bounded reviewed plan required')
    def unique(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise ValueError('Duplicate plan key')
            out[key] = value
        return out
    cfg = json.loads(args.plan.read_text('utf-8'), object_pairs_hook=unique)
    required = {'schema', 'source_sha256', 'module', 'addon_version', 'instructions_url',
                'controller_object', 'model_armature', 'controller_bones', 'rigid_bodies', 'frames'}
    if not isinstance(cfg, dict) or set(cfg) != required or type(cfg['schema']) is not int or cfg['schema'] != 1:
        raise ValueError('Exact existing-physics schema1 required')
    if cfg['instructions_url'] != 'https://mmd-blender.fandom.com/wiki/MMD_Tools/Manual' or cfg['addon_version'] != '4.5.14':
        raise ValueError('Matching reviewed MMD Tools4.5.14 instructions required')
    module = cfg['module']
    if not isinstance(module, str) or not (module == 'mmd_tools' or module.startswith('bl_ext.') and module.endswith('.mmd_tools')):
        raise ValueError('Explicit MMD Tools module required')
    frames = cfg['frames']
    if not isinstance(frames, list) or len(frames) != 2 or any(type(v) is not int for v in frames) or not 1 <= frames[0] < frames[1] <= 10000 or frames[1] - frames[0] + 1 > 480:
        raise ValueError('Require bounded explicit cache frames')
    for field, maximum in [('controller_bones', 2048), ('rigid_bodies', 1024)]:
        if type(cfg[field]) is not int or not 1 <= cfg[field] <= maximum:
            raise ValueError('Bounded exact populations required')
    count = frames[1] - frames[0] + 1
    if count * cfg['rigid_bodies'] > 500000 or count * cfg['controller_bones'] > 1000000:
        raise ValueError('Cache/check work budget exceeded')
    for field in ('controller_object', 'model_armature'):
        if not isinstance(cfg[field], str) or not cfg[field] or len(cfg[field]) > 256:
            raise ValueError('Explicit bounded armature names required')
    source_sha = sha(args.source)
    if source_sha != cfg['source_sha256']:
        raise ValueError('Reviewed source differs')
    addon = importlib.import_module(module)
    if not bpy.context.preferences.addons.get(module) or getattr(addon, 'MMD_TOOLS_VERSION', None) != cfg['addon_version']:
        raise ValueError('Matching installed addon must already be enabled')
    bpy.ops.wm.open_mainfile(filepath=str(args.source.resolve()), load_ui=False, use_scripts=False)
    scene = bpy.context.scene
    rig, arm = (scene.objects.get(cfg[k]) for k in ('controller_object', 'model_armature'))
    roots = [o for o in scene.objects if getattr(o, 'mmd_type', None) == 'ROOT']
    world = scene.rigidbody_world
    if not rig or not arm or rig.type != 'ARMATURE' or arm.type != 'ARMATURE' or len(rig.data.bones) != cfg['controller_bones']:
        raise ValueError('Actual existing controller/model differs')
    if len(roots) != 1 or not roots[0].mmd_root.is_built or not world or not world.collection or len(world.collection.objects) != cfg['rigid_bodies']:
        raise ValueError('Actual assembled original physics population differs')
    if [world.point_cache.frame_start, world.point_cache.frame_end] != frames or len(world.constraints.objects) > 50000:
        raise ValueError('Actual cache range/constraint budget differs')
    if any(not math.isfinite(getattr(world, k)) for k in ('time_scale', 'substeps_per_frame', 'solver_iterations')) or not 0 < world.time_scale <= 2 or not 1 <= world.substeps_per_frame <= 120 or not 1 <= world.solver_iterations <= 100:
        raise ValueError('Require finite bounded existing solver settings')
    def bindings():
        return [(b.name, [(c.name, c.type, c.target.name if getattr(c, 'target', None) else None,
                          getattr(c, 'subtarget', None), c.influence, c.mute) for c in b.constraints]) for b in arm.pose.bones]
    before_bindings = bindings()
    settings = {k: getattr(world, k) for k in ('time_scale', 'substeps_per_frame', 'solver_iterations')}
    if args.mode == 'bake':
        if world.point_cache.is_baked:
            raise ValueError('Already baked; preserve it or explicitly prepare a new unbaked project')
        bpy.ops.object.select_all(action='DESELECT')
        roots[0].select_set(True)
        bpy.context.view_layer.objects.active = roots[0]
        scene.frame_set(frames[0])
        args.output.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(args.output.resolve()))
        if 'FINISHED' not in bpy.ops.mmd_tools.ptcache_rigid_body_bake():
            raise ValueError('Documented cache bake did not finish')
    if not world.point_cache.is_baked:
        raise ValueError('Actual baked cache required')
    for frame in range(frames[0], frames[1] + 1):
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        matrices = [o.matrix_world for o in world.collection.objects]
        matrices.extend(b.matrix for b in rig.pose.bones)
        if any(not math.isfinite(v) for matrix in matrices for row in matrix for v in row):
            raise ValueError('Nonfinite integer cached/controller transform at ' + str(frame))
        if frame % 60 == frames[0] % 60:
            print('EXISTING_CACHE_CHECK', frame, frames[1], flush=True)
    if bindings() != before_bindings or settings != {k: getattr(world, k) for k in settings}:
        raise ValueError('Existing controller constraints or solver settings changed')
    if args.mode == 'bake':
        scene.frame_set(frames[0])
        bpy.ops.wm.save_as_mainfile(filepath=str(args.output.resolve()))
    if sha(args.source) != source_sha:
        raise ValueError('Read-only source changed')
    result = {'at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'mode': args.mode,
              'source_sha256': source_sha, 'plan_sha256': sha(args.plan), 'writer_sha256': sha(Path(__file__)),
              'cache_frames': frames, 'rigid_bodies': cfg['rigid_bodies'], 'controller_bones': cfg['controller_bones'],
              'cache_baked': True, 'all_integer_cached_and_controller_matrices_finite': True,
              'original_model_constraint_rows_unchanged': True, 'world_settings': settings,
              'fresh_process_reopen_verified': args.mode == 'verify', 'normal_speed_continuous_viewing': False,
              'scope': 'Existing assembled MMD cache only. No action correction, cache clearing, controller generation, volume collision or naturalness acceptance.'}
    if args.output:
        result.update(output=str(args.output.resolve()), output_sha256=sha(args.output))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False), 'utf-8')
    print('EXISTING_PHYSICS_CHECKPOINT', args.mode, flush=True)


if __name__ == '__main__':
    main()
