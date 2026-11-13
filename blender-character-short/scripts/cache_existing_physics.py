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
import re
import sys
# Blender --python does not guarantee that sibling modules are importable.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bpy


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def validate_plan(cfg):
    required = {'schema', 'source_sha256', 'module', 'addon_version', 'instructions_url',
                'controller_object', 'model_armature', 'controller_bones', 'rigid_bodies', 'frames'}
    optional = {'mmd_root', 'physics_population'}
    if (not isinstance(cfg, dict) or not required <= set(cfg) or set(cfg) - required - optional
            or type(cfg['schema']) is not int or cfg['schema'] != 1):
        raise ValueError('Exact existing-physics schema1 required')
    if not isinstance(cfg['source_sha256'], str) or not re.fullmatch('[0-9a-f]{64}', cfg['source_sha256']):
        raise ValueError('Explicit source SHA256 required')
    if cfg['instructions_url'] != 'https://mmd-blender.fandom.com/wiki/MMD_Tools/Manual' or cfg['addon_version'] != '4.5.14':
        raise ValueError('Matching reviewed MMD Tools4.5.14 instructions required')
    module = cfg['module']
    if not isinstance(module, str) or not re.fullmatch(r'(?:mmd_tools|bl_ext\.[A-Za-z_]\w*\.mmd_tools)', module):
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
    for field in ('controller_object', 'model_armature', 'mmd_root'):
        if field in cfg and (not isinstance(cfg[field], str) or not cfg[field] or len(cfg[field]) > 256):
            raise ValueError('Explicit bounded object names required')
    if cfg['controller_object'] == cfg['model_armature']:
        raise ValueError('Controller and original model must be different armatures')
    population = cfg.get('physics_population')
    if 'physics_population' in cfg:
        fields = {'joints', 'world_bodies', 'world_constraints', 'passive_bodies'}
        if not isinstance(population, dict) or set(population) != fields:
            raise ValueError('Exact reviewed physics_population required')
        for key, minimum, maximum in [('joints', 0, 4096), ('world_bodies', 1, 1040), ('world_constraints', 0, 50000)]:
            if type(population[key]) is not int or not minimum <= population[key] <= maximum:
                raise ValueError('Bounded exact physics_population required')
        names = population['passive_bodies']
        if (not isinstance(names, list) or len(names) > 16
                or any(not isinstance(n, str) or not n or len(n) > 256 for n in names)
                or len(set(names)) != len(names)):
            raise ValueError('Explicit unique passive body names required')
        if population['world_bodies'] != cfg['rigid_bodies'] + len(names) or count * population['world_bodies'] > 500000:
            raise ValueError('Reviewed world population/work budget differs')
    return cfg


def root_ancestors(obj):
    roots, seen = [], set()
    while obj is not None:
        if id(obj) in seen:
            raise ValueError('Cyclic object ancestry')
        seen.add(id(obj))
        if getattr(obj, 'mmd_type', None) == 'ROOT':
            roots.append(obj)
        obj = obj.parent
    return roots


def select_actor_root(scene, cfg, rig, arm, model):
    """Resolve from the declared native armature, never from scene ROOT order."""
    candidates = root_ancestors(arm)
    if len(candidates) != 1 or scene.objects.get(candidates[0].name) != candidates[0]:
        raise ValueError('Original model must identify exactly one scene MMD ROOT')
    root = candidates[0]
    if 'mmd_root' in cfg and scene.objects.get(cfg['mmd_root']) != root:
        raise ValueError('Explicit MMD ROOT is not the declared original model ROOT')
    if model.find_root_object(arm) != root or model.find_armature_object(root) != arm:
        raise ValueError('MMD ROOT/native armature association is ambiguous')
    controller_roots = root_ancestors(rig)
    if controller_roots and controller_roots != [root]:
        raise ValueError('Controller belongs to a different or ambiguous MMD ROOT')
    links = 0
    for bone in arm.pose.bones:
        for con in bone.constraints:
            target, subtarget = getattr(con, 'target', None), getattr(con, 'subtarget', '')
            if con.name.startswith(('MMR', 'SkillBind')) and hasattr(con, 'target') and (target != rig or not rig.pose.bones.get(subtarget)):
                raise ValueError('Existing MMR binding does not target the declared controller')
            if target == rig and subtarget and rig.pose.bones.get(subtarget):
                links += 1
    if not links or not root.mmd_root.is_built:
        raise ValueError('Built actor ROOT and actual native/controller bindings required')
    return root


def check_population(scene, world, root, cfg):
    if not world or not world.collection or not world.constraints or not world.enabled:
        raise ValueError('Enabled assembled world and both collections required')
    bodies, constraints = list(world.collection.all_objects), list(world.constraints.all_objects)
    if any(scene.objects.get(o.name) != o or not o.rigid_body for o in bodies):
        raise ValueError('World collection contains an invalid rigid body')
    actor_bodies = [o for o in root.children_recursive if getattr(o, 'mmd_type', None) == 'RIGID_BODY']
    joints = [o for o in root.children_recursive if getattr(o, 'mmd_type', None) == 'JOINT']
    if len(actor_bodies) != cfg['rigid_bodies'] or len(joints) > 4096 or len(constraints) > 50000:
        raise ValueError('Actual actor physics population/budget differs')
    actor_names = {o.name for o in actor_bodies}
    if any(scene.objects.get(o.name) != o or root_ancestors(o) != [root] or not o.rigid_body for o in actor_bodies):
        raise ValueError('Original rigid bodies must belong to the declared actor ROOT')
    for joint in joints:
        con = joint.rigid_body_constraint
        if (scene.objects.get(joint.name) != joint or joint not in constraints
                or root_ancestors(joint) != [root] or not con or not con.object1 or not con.object2
                or con.object1.name not in actor_names or con.object2.name not in actor_names):
            raise ValueError('Original joint endpoints must refer to declared actor bodies')
    population = cfg.get('physics_population')
    passive_names = population['passive_bodies'] if population is not None else []
    if {o.name for o in bodies} != actor_names | set(passive_names):
        raise ValueError('World bodies differ; additional passive bodies require an explicit reviewed population')
    for name in passive_names:
        obj = scene.objects.get(name)
        if (not obj or obj.type != 'MESH' or obj.parent is not None or root_ancestors(obj)
                or getattr(obj, 'mmd_type', None) in {'RIGID_BODY', 'JOINT'}
                or not obj.rigid_body or obj.rigid_body.type != 'PASSIVE'):
            raise ValueError('Declared extra world body must be an independent passive mesh')
    if population is not None and (len(joints) != population['joints'] or len(bodies) != population['world_bodies']
                                   or len(constraints) != population['world_constraints']):
        raise ValueError('Actual exact reviewed physics_population differs')
    count = cfg['frames'][1] - cfg['frames'][0] + 1
    if count * len(bodies) > 500000:
        raise ValueError('Actual world body-frame budget exceeded')
    return bodies, {'actor_root': root.name, 'actor_rigid_bodies': len(actor_bodies),
                    'original_joints': len(joints), 'world_bodies': len(bodies),
                    'world_constraints': len(constraints), 'passive_bodies': sorted(passive_names),
                    'scene_mmd_roots': sorted(o.name for o in scene.objects if getattr(o, 'mmd_type', None) == 'ROOT')}


def cache_state(cache):
    return {key: bool(getattr(cache, key)) for key in
            ('is_baked', 'is_baking', 'use_disk_cache', 'use_external', 'is_outdated', 'is_frame_skip')}


def check_cache(cache, frames, *, baked):
    if [cache.frame_start, cache.frame_end] != frames:
        raise ValueError('Actual cache range differs')
    if cache.is_baking or cache.use_disk_cache or cache.use_external:
        raise ValueError('Completed embedded cache required; disk/external caches are unsupported')
    if cache.is_frame_skip:
        raise ValueError('Rigid-body cache reports skipped frames')
    if baked and not cache.is_baked:
        raise ValueError('Actual baked cache required')
    # is_outdated is a runtime-world diagnostic, not evidence of corruption alone.


def protected_state(scene, rig, arm, bodies):
    """Hash stored assets and rig data, excluding simulated rigid transforms."""
    from scene_integrity import _action, _animation, _armature, _mesh, _rna
    physical_names = {o.name for o in bodies}
    def digest(value):
        return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
            separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()
    meshes = [o for o in scene.objects if o.type == 'MESH' and o.name not in physical_names]
    return {
        'meshes_weights_uv_shape_keys': digest([(o.name, _mesh(o.data),
            [(g.name, g.index, g.lock_weight) for g in o.vertex_groups],
            [_rna(m) for m in o.modifiers]) for o in sorted(meshes, key=lambda o: o.name)]),
        'armature_rest': digest([(o.name, _armature(o.data)) for o in scene.objects if o.type == 'ARMATURE']),
        'actions': digest([_action(a) for a in sorted(bpy.data.actions, key=lambda a: a.name)]),
        'controller_and_native_bindings': digest([(o.name, o.parent.name if o.parent else None,
            _animation(o), [_rna(c) for c in o.constraints],
            [(b.name, [_rna(c) for c in b.constraints]) for b in o.pose.bones]) for o in (rig, arm)]),
        'physics_settings': digest({'bodies': [(o.name, o.parent.name if o.parent else None, _rna(o.rigid_body)) for o in bodies],
            'original_joints': [(o.name, _rna(o.rigid_body_constraint)) for o in scene.objects
                                if getattr(o, 'mmd_type', None) == 'JOINT']}),
    }


def main(arguments=None):
    p = argparse.ArgumentParser()
    p.add_argument('--mode', choices=['bake', 'verify'], required=True)
    for field in ('source', 'plan', 'report'):
        p.add_argument('--' + field, type=Path, required=True)
    p.add_argument('--output', type=Path)
    args = p.parse_args(arguments if arguments is not None else sys.argv[sys.argv.index('--') + 1:])
    for field in ('source', 'plan', 'report', 'output'):
        if getattr(args, field) is not None:
            setattr(args, field, getattr(args, field).resolve())
    if not bpy.app.background:
        raise ValueError('Isolated background process required')
    paths = [args.source, args.plan, args.report] + ([args.output] if args.output else [])
    if len(set(paths)) != len(paths) or not args.source.is_file() or args.source.suffix.lower() != '.blend':
        raise ValueError('Distinct existing .blend source, plan and new output/report paths required')
    if args.report.suffix.lower() != '.json' or args.output is not None and args.output.suffix.lower() != '.blend':
        raise ValueError('Explicit .blend output and JSON report required')
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
    validate_plan(cfg)
    module, frames = cfg['module'], cfg['frames']
    source_sha = sha(args.source)
    if source_sha != cfg['source_sha256']:
        raise ValueError('Reviewed source differs')
    addon = importlib.import_module(module)
    if getattr(addon, 'MMD_TOOLS_VERSION', None) != cfg['addon_version']:
        raise ValueError('Matching installed addon version required before runtime activation')
    runtime_activation = not bool(bpy.context.preferences.addons.get(module))
    if runtime_activation and 'FINISHED' not in bpy.ops.preferences.addon_enable(module=module):
        raise ValueError('Runtime-only MMD Tools activation did not finish')
    if not bpy.context.preferences.addons.get(module) or getattr(addon, 'MMD_TOOLS_VERSION', None) != cfg['addon_version']:
        raise ValueError('Matching installed addon must be enabled in this process')
    model = importlib.import_module(module + '.core.model').FnModel
    bpy.ops.wm.open_mainfile(filepath=str(args.source.resolve()), load_ui=False, use_scripts=False)
    scene = bpy.context.scene
    rig, arm = (scene.objects.get(cfg[k]) for k in ('controller_object', 'model_armature'))
    world = scene.rigidbody_world
    if not rig or not arm or rig == arm or rig.type != 'ARMATURE' or arm.type != 'ARMATURE' or len(rig.data.bones) != cfg['controller_bones']:
        raise ValueError('Actual existing controller/model differs')
    count = frames[1] - frames[0] + 1
    if not 1 <= len(arm.data.bones) <= 2048 or count * (len(rig.data.bones) + len(arm.data.bones)) > 1000000:
        raise ValueError('Actual controller/native bone-frame budget exceeded')
    root = select_actor_root(scene, cfg, rig, arm, model)
    bodies, population = check_population(scene, world, root, cfg)
    check_cache(world.point_cache, frames, baked=args.mode == 'verify')
    if args.mode == 'bake' and world.point_cache.is_baked:
        raise ValueError('Already baked; preserve it or explicitly prepare a new unbaked project')
    if any(not math.isfinite(getattr(world, k)) for k in ('time_scale', 'substeps_per_frame', 'solver_iterations')) or not 0 < world.time_scale <= 2 or not 1 <= world.substeps_per_frame <= 120 or not 1 <= world.solver_iterations <= 100:
        raise ValueError('Require finite bounded existing solver settings')
    def bindings():
        return [(b.name, [(c.name, c.type, c.target.name if getattr(c, 'target', None) else None,
                          getattr(c, 'subtarget', None), c.influence, c.mute) for c in b.constraints]) for b in arm.pose.bones]
    settings = {k: getattr(world, k) for k in ('time_scale', 'substeps_per_frame', 'solver_iterations')}
    display = [scene.frame_start, scene.frame_end, scene.render.fps, scene.render.fps_base]
    initial_frame = scene.frame_current
    scene.frame_set(initial_frame)
    bpy.context.view_layer.update()
    before_bindings = bindings()
    protected_before = protected_state(scene, rig, arm, bodies)
    initial_cache = cache_state(world.point_cache)
    if args.mode == 'bake':
        bpy.ops.object.select_all(action='DESELECT')
        root.select_set(True)
        bpy.context.view_layer.objects.active = root
        scene.frame_set(frames[0])
        args.output.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(args.output.resolve()))
        if 'FINISHED' not in bpy.ops.mmd_tools.ptcache_rigid_body_bake():
            raise ValueError('Documented cache bake did not finish')
    check_cache(world.point_cache, frames, baked=True)
    diagnostic_flags = {'outdated_frames': [], 'frame_skip_frames': []}
    for frame in range(frames[0], frames[1] + 1):
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        if world.point_cache.is_outdated:
            diagnostic_flags['outdated_frames'].append(frame)
        if world.point_cache.is_frame_skip:
            diagnostic_flags['frame_skip_frames'].append(frame)
        check_cache(world.point_cache, frames, baked=True)
        matrices = [o.matrix_world for o in bodies]
        matrices.extend(b.matrix for b in rig.pose.bones)
        matrices.extend(b.matrix for b in arm.pose.bones)
        if any(not math.isfinite(v) for matrix in matrices for row in matrix for v in row):
            raise ValueError('Nonfinite integer cached/controller transform at ' + str(frame))
        if frame % 60 == frames[0] % 60:
            print('EXISTING_CACHE_CHECK', frame, frames[1], flush=True)
    scene.frame_set(initial_frame)
    bpy.context.view_layer.update()
    check_cache(world.point_cache, frames, baked=True)
    if select_actor_root(scene, cfg, rig, arm, model) != root or check_population(scene, world, root, cfg)[1] != population:
        raise ValueError('Existing actor ROOT or physics population changed')
    if protected_state(scene, rig, arm, bodies) != protected_before:
        raise ValueError('Stored mesh assets, armature rest, actions, bindings or physics settings changed')
    if [scene.frame_start, scene.frame_end, scene.render.fps, scene.render.fps_base] != display:
        raise ValueError('Existing display range or frame rate changed')
    if bindings() != before_bindings or settings != {k: getattr(world, k) for k in settings}:
        raise ValueError('Existing controller constraints or solver settings changed')
    if args.mode == 'bake':
        bpy.ops.wm.save_as_mainfile(filepath=str(args.output.resolve()))
    if sha(args.source) != source_sha:
        raise ValueError('Read-only source changed')
    result = {'at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'mode': args.mode,
              'source_sha256': source_sha, 'plan_sha256': sha(args.plan), 'writer_sha256': sha(Path(__file__)),
              'cache_frames': frames, 'rigid_bodies': cfg['rigid_bodies'], 'controller_bones': cfg['controller_bones'],
              'cache_baked': True, 'all_integer_cached_and_controller_matrices_finite': True,
              'all_integer_native_matrices_finite': True, 'physics_population': population,
              'initial_cache': initial_cache, 'final_cache': cache_state(world.point_cache),
              'diagnostic_cache_flags': diagnostic_flags,
              'cache_flag_note': 'is_outdated is diagnostic only; is_frame_skip fails verification.',
              'protected_assets_sha256': protected_before, 'stored_assets_actions_and_rig_unchanged': True,
              'original_model_constraint_rows_unchanged': True, 'world_settings': settings,
              'runtime_only_activation': runtime_activation, 'preferences_saved': False,
              'fresh_process_reopen_verified': args.mode == 'verify', 'normal_speed_continuous_viewing': False,
              'scope': 'Existing assembled MMD cache only. No action correction, cache clearing, controller generation, volume collision or naturalness acceptance.'}
    if args.output:
        result.update(output=str(args.output.resolve()), output_sha256=sha(args.output))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + '\n')
    print('EXISTING_PHYSICS_CHECKPOINT', args.mode, flush=True)


if __name__ == '__main__':
    main()
