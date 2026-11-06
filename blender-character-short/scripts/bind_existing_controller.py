"""Add reviewed missing rotation bindings to a copy of an existing controller rig.

This never generates controllers, changes weights, or replaces existing bindings.
Run a separate process for motion-response and saved-file acceptance.
"""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bpy
import numpy as np
from body_motion_runtime import geometry_identity
from existing_controller_plan import validate_plan


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main(arguments=None):
    parser = argparse.ArgumentParser()
    for field in ('source', 'plan', 'output', 'report'):
        parser.add_argument('--' + field, type=Path, required=True)
    args = parser.parse_args(arguments if arguments is not None else sys.argv[sys.argv.index('--') + 1:])
    source, plan_path, output, report = (getattr(args, n).resolve() for n in ('source', 'plan', 'output', 'report'))
    if len({source, plan_path, output, report}) != 4 or output.exists() or report.exists():
        raise ValueError('Separate new output/report paths required; preserve earlier versions')
    if plan_path.stat().st_size > 65536:
        raise ValueError('Reviewed binding plan exceeds64KB')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate binding plan key')
            result[key] = value
        return result
    plan = validate_plan(json.loads(plan_path.read_text('utf-8'), object_pairs_hook=unique))
    if sha(source) != plan['source_sha256']:
        raise ValueError('Reviewed source differs')
    bpy.ops.wm.open_mainfile(filepath=str(source), load_ui=False, use_scripts=False)
    scene = bpy.context.scene
    rig = scene.objects.get(plan['controller_object'])
    arm = scene.objects.get(plan['model_armature'])
    mesh = scene.objects.get(plan['mesh_object'])
    if not rig or not arm or rig.type != 'ARMATURE' or arm.type != 'ARMATURE' or not mesh or mesh.type != 'MESH':
        raise ValueError('Explicit original rig, controller and weighted mesh required')
    if scene.rigidbody_world or len(rig.data.bones) != plan['existing_controller_bones']:
        raise ValueError('Require reviewed unassembled existing controller scene')
    if len(mesh.data.vertices) > 250000 or not any(m.type == 'ARMATURE' and m.object == arm for m in mesh.modifiers):
        raise ValueError('Bounded mesh must be deformed by the original model armature')
    if any(image.source == 'FILE' and not image.packed_file for image in bpy.data.images):
        raise ValueError('Pack reviewed file images before relocating the project')

    def rest(obj, names):
        return [(n, obj.data.bones[n].parent.name if obj.data.bones[n].parent else None,
                 [list(row) for row in obj.data.bones[n].matrix_local], obj.data.bones[n].use_deform)
                for n in names]

    def constraints():
        return [(b.name, [(c.name, c.type, c.influence, c.mute,
                          c.target.name if getattr(c, 'target', None) else None,
                          getattr(c, 'subtarget', None)) for c in b.constraints]) for b in arm.pose.bones]

    def skin():
        bpy.context.view_layer.update()
        evaluated = mesh.evaluated_get(bpy.context.evaluated_depsgraph_get())
        evaluated_mesh = evaluated.to_mesh()
        try:
            result = np.asarray([list(evaluated.matrix_world @ v.co) for v in evaluated_mesh.vertices])
        finally:
            evaluated.to_mesh_clear()
        if not np.isfinite(result).all():
            raise ValueError('Nonfinite baseline/evaluated skin')
        return result

    rig_names, model_names = list(rig.data.bones.keys()), list(arm.data.bones.keys())
    rig_rest, model_rest = rest(rig, rig_names), rest(arm, model_names)
    geometry = geometry_identity(scene, arm)
    original_constraints = constraints()
    baseline = skin()
    offsets = {}
    for row in plan['pairs']:
        target = 'SkillBind-' + row['model_bone']
        pb = arm.pose.bones.get(row['model_bone'])
        parent = rig.pose.bones.get(row['controller_bone'])
        if not pb or not parent or rig.data.bones.get(target) or any(c.name.startswith(('MMR', 'SkillBind')) for c in pb.constraints):
            raise ValueError('Missing target or existing binding; never replace user controls/constraints')
        desired = rig.matrix_world.inverted() @ arm.matrix_world @ pb.matrix
        offsets[target] = parent.bone.matrix_local @ parent.matrix.inverted() @ desired

    bpy.ops.object.select_all(action='DESELECT')
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='EDIT')
    collection = rig.data.collections.new('Skill missing-binding helpers')
    collection.is_visible = False
    for row in plan['pairs']:
        name = 'SkillBind-' + row['model_bone']
        bone = rig.data.edit_bones.new(name)
        # A zero-length edit bone can discard the matrix orientation: set length first.
        bone.length = max(.005, arm.data.bones[row['model_bone']].length)
        bone.matrix = offsets[name]
        bone.parent = rig.data.edit_bones[row['controller_bone']]
        bone.use_connect = False
        bone.use_deform = False
        collection.assign(bone)
    bpy.ops.object.mode_set(mode='OBJECT')
    for row in plan['pairs']:
        constraint = arm.pose.bones[row['model_bone']].constraints.new('COPY_ROTATION')
        constraint.name = 'SkillBind existing controller rotation'
        constraint.target = rig
        constraint.subtarget = 'SkillBind-' + row['model_bone']
        constraint.owner_space = constraint.target_space = 'WORLD'
        constraint.mix_mode = 'REPLACE'
    error = float(np.max(np.linalg.norm(skin() - baseline, axis=1)))
    if error > plan['maximum_baseline_skin_difference_m'] or rest(rig, rig_names) != rig_rest or rest(arm, model_names) != model_rest or geometry_identity(scene, arm) != geometry:
        raise ValueError('Original rest/skin/geometry changed; no output accepted')
    after = constraints()
    for (name, before), (after_name, rows) in zip(original_constraints, after):
        if name != after_name or rows[:len(before)] != before:
            raise ValueError('Original constraints changed')
    output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output))
    if sha(source) != plan['source_sha256']:
        raise ValueError('Read-only source changed')
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps({'at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'source_sha256': plan['source_sha256'], 'plan_sha256': sha(plan_path), 'writer_sha256': sha(Path(__file__)),
        'output': str(output), 'output_sha256': sha(output),
        'bindings_added': len(plan['pairs']), 'original_controller_bones_preserved': len(rig_names),
        'original_model_bones': len(model_names), 'maximum_baseline_skin_difference_m': error,
        'original_constraints_rest_and_geometry_preserved': True, 'rig_regenerated': False,
        'saved_reopen_verified': False, 'normal_speed_continuous_viewing': False,
        'scope': 'Rotation-only missing bindings on an existing rig. Separate fresh-process reopen, dynamic skin response, action transfer and visual acceptance are required.'}, ensure_ascii=False, indent=2, allow_nan=False), 'utf-8')
    print('EXISTING_CONTROLLER_BINDINGS_SAVED', len(plan['pairs']), error, flush=True)


if __name__ == '__main__':
    main()
