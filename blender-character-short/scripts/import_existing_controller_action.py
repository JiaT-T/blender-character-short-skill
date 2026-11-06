"""Transfer reviewed finite world-pose targets to mapped existing FK controls.

Character mappings and captured/edited target data are external. This does not
convert, license or fit arbitrary motion; validate those earlier stages first.
"""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import math
import sys
import zipfile
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bpy
import numpy as np
from mathutils import Matrix
from body_motion_runtime import geometry_identity
from existing_controller_plan import shortest_quaternion_angle_degrees


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main(arguments=None):
    p = argparse.ArgumentParser()
    for field in ('source', 'plan', 'goals', 'output', 'report'):
        p.add_argument('--' + field, type=Path, required=True)
    args = p.parse_args(arguments if arguments is not None else sys.argv[sys.argv.index('--') + 1:])
    if args.output.exists() or args.report.exists() or args.plan.stat().st_size > 65536:
        raise ValueError('New outputs and bounded reviewed plan required')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate action plan key')
            result[key] = value
        return result
    cfg = json.loads(args.plan.read_text('utf-8'), object_pairs_hook=unique)
    fields = {'schema', 'source_sha256', 'goals_sha256', 'controller_object', 'model_armature',
              'mapping', 'fk_switches', 'fps', 'frames', 'maximum_position_difference_m',
              'maximum_orientation_difference_degrees'}
    if not isinstance(cfg, dict) or set(cfg) != fields or type(cfg['schema']) is not int or cfg['schema'] != 1:
        raise ValueError('Exact existing action schema1 required')
    for field, low, high in [('fps', 1, 60), ('frames', 2, 480)]:
        if type(cfg[field]) is not int or not low <= cfg[field] <= high:
            raise ValueError('Bounded integer FPS/frame count required')
    for field, maximum in [('maximum_position_difference_m', .05), ('maximum_orientation_difference_degrees', 8)]:
        value = cfg[field]
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= maximum:
            raise ValueError('Finite bounded acceptance thresholds required')
    pairs = cfg['mapping']
    if not isinstance(pairs, list) or not 1 <= len(pairs) <= 128 or cfg['frames'] * len(pairs) > 61440:
        raise ValueError('Bounded explicit mapping required')
    for row in pairs:
        if not isinstance(row, dict) or set(row) != {'model_bone', 'controller_bone', 'control', 'helper', 'preserve_local_translation_scale'}:
            raise ValueError('Exact per-bone action mapping fields required')
        if type(row['preserve_local_translation_scale']) is not bool or any(not isinstance(row[k], str) or not row[k] or len(row[k].encode('utf-8')) > 63 for k in row if k != 'preserve_local_translation_scale'):
            raise ValueError('Exact bounded bone names and explicit preservation flag required')
    for field in ('model_bone', 'control'):
        if len({row[field] for row in pairs}) != len(pairs):
            raise ValueError('Model targets and keyed controls must be unique')
    switches = cfg['fk_switches']
    if not isinstance(switches, list) or len(switches) > 16:
        raise ValueError('Bounded explicit FK switches required')
    for row in switches:
        if not isinstance(row, dict) or set(row) != {'bone', 'property', 'value'} or type(row['value']) not in (int, float) or not math.isfinite(row['value']) or not 0 <= row['value'] <= 1 or any(not isinstance(row[k], str) or not row[k] for k in ('bone', 'property')):
            raise ValueError('Explicit finite FK switch required')
    source_sha, goals_sha = sha(args.source), sha(args.goals)
    if source_sha != cfg['source_sha256'] or goals_sha != cfg['goals_sha256']:
        raise ValueError('Reviewed source/target identity differs')
    with zipfile.ZipFile(args.goals) as archive:
        members = archive.infolist()
        if len(members) != 3 or {m.filename for m in members} != {'frames.npy', 'names.npy', 'worlds.npy'} or sum(m.file_size for m in members) > 16000000:
            raise ValueError('Require bounded three-array non-object target NPZ')
    names = [row['model_bone'] for row in pairs]
    with np.load(args.goals, allow_pickle=False) as loaded:
        if loaded['names'].tolist() != names or loaded['frames'].tolist() != list(range(1, cfg['frames'] + 1)):
            raise ValueError('Target frame/name order differs')
        sequence = loaded['worlds'].copy()
    if sequence.shape != (cfg['frames'], len(names), 4, 4) or not np.issubdtype(sequence.dtype, np.floating) or not np.isfinite(sequence).all():
        raise ValueError('Finite reviewed world matrix targets required')
    if np.max(np.abs(sequence)) > 1e6 or not np.allclose(sequence[..., 3, :], [0, 0, 0, 1], rtol=0, atol=1e-7):
        raise ValueError('Bounded affine target transforms required')
    determinants = np.linalg.det(sequence[..., :3, :3])
    if not np.isfinite(determinants).all() or np.any(np.abs(determinants) < 1e-12):
        raise ValueError('Nonsingular bounded target transforms required')
    bpy.ops.wm.open_mainfile(filepath=str(args.source.resolve()), load_ui=False, use_scripts=False)
    scene = bpy.context.scene
    rig, arm = (scene.objects.get(cfg[k]) for k in ('controller_object', 'model_armature'))
    if not rig or not arm or rig == arm or rig.type != 'ARMATURE' or arm.type != 'ARMATURE' or scene.rigidbody_world:
        raise ValueError('Reviewed unassembled existing rigs required')
    for owner in (rig, arm):
        if owner.animation_data and (owner.animation_data.action or owner.animation_data.nla_tracks):
            raise ValueError('Preserve existing controller/model actions; use a reviewed unanimated copy')
    weighted_skin = False
    for obj in scene.objects:
        if obj.type != 'MESH' or not any(m.type == 'ARMATURE' and m.object == arm for m in obj.modifiers):
            continue
        groups = {g.index for g in obj.vertex_groups if g.name in arm.data.bones}
        if any(g.weight > 0 and g.group in groups for vertex in obj.data.vertices for g in vertex.groups):
            weighted_skin = True
            break
    if not weighted_skin:
        raise ValueError('Original model requires actual positive-weight skin linked to its armature')
    if len(rig.data.bones) > 2048 or len(arm.data.bones) > 2048:
        raise ValueError('Rig population budget exceeded')
    geometry = geometry_identity(scene, arm)
    rest = {o.name: [(b.name, [list(r) for r in b.matrix_local]) for b in o.data.bones] for o in (rig, arm)}
    for row in switches:
        pb = rig.pose.bones.get(row['bone'])
        if not pb or row['property'] not in pb:
            raise ValueError('Observed FK property missing')
        pb[row['property']] = row['value']
        pb.keyframe_insert(data_path='[' + json.dumps(row['property']) + ']', frame=1)
    rig.update_tag(refresh={'OBJECT'})
    bpy.context.view_layer.update()
    offsets, controls, local = {}, {}, {}
    for row in pairs:
        if row['model_bone'] not in arm.pose.bones or any(row[k] not in rig.pose.bones for k in ('controller_bone', 'control', 'helper')):
            raise ValueError('Reviewed target/control/helper mapping missing')
        org, helper, control = (rig.matrix_world @ rig.pose.bones[row[k]].matrix for k in ('controller_bone', 'helper', 'control'))
        offsets[row['model_bone']] = org.inverted() @ helper
        controls[row['model_bone']] = control.inverted() @ org
        pb = rig.pose.bones[row['control']]
        local[pb.name] = (pb.location.copy(), pb.scale.copy())
    order = sorted(range(len(pairs)), key=lambda i: len(rig.pose.bones[pairs[i]['control']].parent_recursive))
    previous, rows = {}, []
    maxima = {'component': 0., 'position_m': 0., 'orientation_degrees': 0.}
    scene.frame_start = 1
    scene.frame_end = cfg['frames']
    scene.render.fps = cfg['fps']
    scene.render.fps_base = 1
    for frame, expected in enumerate(sequence, 1):
        scene.frame_set(frame)
        for i in order:
            row = pairs[i]
            pb = rig.pose.bones[row['control']]
            goal = Matrix(expected[i].tolist()) @ offsets[row['model_bone']].inverted() @ controls[row['model_bone']].inverted()
            pb.rotation_mode = 'QUATERNION'
            pb.matrix = rig.matrix_world.inverted() @ goal
            if row['preserve_local_translation_scale']:
                pb.location, pb.scale = local[pb.name]
            rig.update_tag(refresh={'OBJECT'})
            bpy.context.view_layer.update()
        measured = {'component': 0., 'position_m': 0., 'orientation_degrees': 0.}
        for i, row in enumerate(pairs):
            actual = arm.matrix_world @ arm.pose.bones[row['model_bone']].matrix
            if not np.isfinite(np.asarray(actual)).all():
                raise ValueError('Nonfinite evaluated target pose')
            desired = Matrix(expected[i].tolist())
            values = {'component': float(np.max(np.abs(np.asarray(actual) - expected[i]))),
                      'position_m': (actual.translation - desired.translation).length,
                      'orientation_degrees': shortest_quaternion_angle_degrees(tuple(actual.to_quaternion()), tuple(desired.to_quaternion()))}
            for key, value in values.items():
                if not math.isfinite(value):
                    raise ValueError('Nonfinite comparison')
                measured[key] = max(measured[key], value)
                maxima[key] = max(maxima[key], value)
            pb = rig.pose.bones[row['control']]
            if pb.name in previous and pb.rotation_quaternion.dot(previous[pb.name]) < 0:
                pb.rotation_quaternion.negate()
            previous[pb.name] = pb.rotation_quaternion.copy()
            for channel in ('location', 'rotation_quaternion', 'scale'):
                pb.keyframe_insert(data_path=channel, frame=frame, group=pb.name)
        if measured['position_m'] > cfg['maximum_position_difference_m'] or measured['orientation_degrees'] > cfg['maximum_orientation_difference_degrees']:
            raise ValueError('Actual original-model transfer exceeds reviewed tolerance at ' + str(frame))
        rows.append({'frame': frame, **measured})
        if frame % 30 == 1:
            print('EXISTING_ACTION_IMPORT', frame, cfg['frames'], flush=True)
    for curve in rig.animation_data.action.fcurves:
        curve.extrapolation = 'CONSTANT'
        for key in curve.keyframe_points:
            key.interpolation = 'LINEAR'
    if geometry_identity(scene, arm) != geometry or rest != {o.name: [(b.name, [list(r) for r in b.matrix_local]) for b in o.data.bones] for o in (rig, arm)}:
        raise ValueError('Original rest/model geometry changed')
    bpy.ops.file.pack_all()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output.resolve()))
    if sha(args.source) != source_sha or sha(args.goals) != goals_sha:
        raise ValueError('Reviewed source/targets changed')
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps({'at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'source_sha256': source_sha, 'goals_sha256': goals_sha, 'plan_sha256': sha(args.plan), 'writer_sha256': sha(Path(__file__)),
        'output': str(args.output.resolve()), 'output_sha256': sha(args.output), 'frames': cfg['frames'], 'fps': cfg['fps'],
        'controls': len(pairs), 'maximum_differences': maxima, 'rows': rows, 'original_rest_and_geometry_preserved': True,
        'controller_regenerated': False, 'saved_reopen_verified': False, 'normal_speed_continuous_viewing': False,
        'scope': 'Imported reviewed integer-frame target poses onto existing FK controls. Source fitting/licensing, saved action reopen, subframe clearance and visual naturalness require separate evidence.'}, ensure_ascii=False, indent=2, allow_nan=False), 'utf-8')
    print('EXISTING_ACTION_SAVED', maxima, flush=True)


if __name__ == '__main__':
    main()
