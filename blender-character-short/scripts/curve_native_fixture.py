"""Two-process, asset-free integration fixture for the generic cord tools.

Run author, then verify in a NEW background Blender process, holding the external
execution lock for each. No native result is established by importing this file.
The output directory must not exist before author. Partial outputs are retained
on failure; the original .blend and its recorded SHA256 are recovery evidence.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys
import uuid

import numpy as np


MODULE_NAMES = (
    'curve_smoothing', 'curve_verification', 'curve_native_metrics',
    'smooth_curve', 'verify_smoothed_curve',
)
OBJECT_NAME = 'CPUPreparedIntegrationCord'
FILES = dict(
    source='fixture-source.blend', plan='fixture-plan.json',
    candidate='fixture-candidate.blend', smoothing_report='smoothing-report.json',
    verification_report='verification-report.json', manifest='fixture-manifest.json',
    source_evidence='source-evidence.json',
)


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write_new_json(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def checked_paths(module_dir, output_root):
    module_dir = Path(module_dir).expanduser().resolve(strict=True)
    output_root = Path(output_root).expanduser().resolve()
    if not module_dir.is_dir():
        raise ValueError('module-dir must be an existing directory')
    for name in MODULE_NAMES:
        if not (module_dir / (name + '.py')).is_file():
            raise ValueError('Missing reviewed module: ' + name)
    if output_root == Path(output_root.anchor):
        raise ValueError('A dedicated output directory is required')
    if (module_dir.is_relative_to(output_root)
            or output_root.is_relative_to(module_dir)):
        raise ValueError('Output directory and reviewed module directory must not overlap')
    paths = {name: output_root / filename for name, filename in FILES.items()}
    return module_dir, output_root, paths


def load_generic_modules(module_dir):
    """Reject stale imports from a different checkout, then import exact modules."""
    module_dir = Path(module_dir).resolve(strict=True)
    for name in MODULE_NAMES:
        old = sys.modules.get(name)
        if old is not None and Path(old.__file__).resolve() != module_dir / (name + '.py'):
            raise RuntimeError('Use a fresh process: module already imported elsewhere: ' + name)
    sys.path.insert(0, str(module_dir))
    loaded = {name: importlib.import_module(name) for name in MODULE_NAMES}
    for name, module in loaded.items():
        if Path(module.__file__).resolve() != module_dir / (name + '.py'):
            raise RuntimeError('Unexpected imported module path: ' + name)
    return loaded


def module_hashes(module_dir):
    return {name + '.py': digest(Path(module_dir) / (name + '.py')) for name in MODULE_NAMES}


def fixture_pose(frame):
    """13 POLY points of length .12, gently moving over frames 1..9."""
    phase = (float(frame) - 1.) / 8.
    parameter = np.linspace(0., 1., 13)
    distance = .115 + .0001 * np.sin(np.pi * phase)
    angle = .02 * np.sin(2. * np.pi * phase)
    origin = np.array([.0002 * np.sin(2. * np.pi * phase),
                       .0001 * np.sin(np.pi * phase), .00015 * phase])
    base = np.column_stack((np.zeros(13), np.zeros(13), distance * parameter))
    direction = np.array([np.cos(angle), np.sin(angle), 0.])
    bow = np.sin(np.pi * parameter)[:, None] * direction
    bow[[0, -1]] = 0.
    low, high = 0., .12
    for _ in range(60):
        middle = (low + high) / 2.
        length = np.linalg.norm(np.diff(base + middle * bow, axis=0), axis=1).sum()
        if length < .12:
            low = middle
        else:
            high = middle
    return origin + base + (low + high) / 2. * bow


def prepare_host_fixture(module_dir):
    """CPU-only preparation/check callable without importing bpy.

    Emulate float32 coordinate-key storage and linear FCurve interpolation.
    Native evaluation and .blend serialization are deliberately absent here.
    """
    modules = load_generic_modules(module_dir)
    smoothing = modules['curve_smoothing']
    times = np.linspace(1., 9., 33).astype(np.float32).astype(float)
    poses = np.stack([fixture_pose(t) for t in times]).astype(np.float32).astype(float)
    plan = dict(schema=1, object=OBJECT_NAME, frames=[1, 9],
                sample_times=np.linspace(1., 9., 17).tolist(), target_length=.12,
                max_displacement=.0005, length_tolerance=1e-6, maximum_key_step=.125)
    modules['smooth_curve'].validate_plan(plan)

    def sample(t):
        return np.array([[np.interp(t, times, poses[:, i, axis]) for axis in range(3)]
                         for i in range(13)])

    proposed = smoothing.prepare_samples(
        sample, np.linspace(1., 9., 65), target_length=plan['target_length'],
        max_displacement=plan['max_displacement'], tolerance=plan['length_tolerance'])
    stored_times = proposed['times'].astype(np.float32).astype(float)
    if len(np.unique(stored_times)) != len(stored_times):
        raise ValueError('Host fixture adaptive times collide at float32 precision')
    verification = modules['curve_verification'].verification_times(
        times.tolist(), stored_times.tolist(), plan['sample_times'], 13)
    stored_proposals = proposed['points'].astype(np.float32).astype(float)
    maximum_length_error = maximum_shift = maximum_endpoint_error = 0.
    for t in verification:
        proposal = np.array([[np.interp(t, stored_times, stored_proposals[:, i, axis])
                              for axis in range(3)] for i in range(13)])
        original = sample(t)
        # Writer leaves the original endpoint channels untouched.
        proposal[[0, -1]] = original[[0, -1]]
        maximum_length_error = max(maximum_length_error, abs(smoothing.arc_length(proposal, 32) - .12))
        maximum_shift = max(maximum_shift, float(np.linalg.norm(proposal - original, axis=1).max()))
        maximum_endpoint_error = max(maximum_endpoint_error,
                                     float(np.linalg.norm(proposal[[0, -1]] - original[[0, -1]], axis=1).max()))
    if maximum_length_error > 1e-6 or maximum_shift > .0005 or maximum_endpoint_error != 0.:
        raise ValueError('CPU fixture preparation does not satisfy the requested sampled bounds')
    summary = dict(source_keys=len(times), control_count=13, coordinate_channels=52,
                   planned_control_keys=len(stored_times), verification_times=len(verification),
                   maximum_sampled_integrated_length_error=maximum_length_error,
                   maximum_sampled_control_shift=maximum_shift,
                   maximum_sampled_endpoint_error=maximum_endpoint_error,
                   constant_weight_value=1., native_verified=False, serialized_verified=False,
                   preparation=proposed['summary'])
    return dict(times=times, poses=poses, plan=plan, summary=summary, modules=modules)


def require_fresh_background(bpy):
    if not bpy.app.background:
        raise ValueError('Run in an isolated background Blender process')
    if bpy.data.filepath:
        raise ValueError('Start with --factory-startup and no input .blend; an existing project is open')


def fingerprints(paths):
    result = {}
    for name in ('source', 'plan', 'candidate', 'smoothing_report', 'verification_report'):
        path = paths[name]
        result[name] = dict(path=str(path), exists=path.is_file(),
                            sha256=digest(path) if path.is_file() else None)
    return result


def provenance(bpy, stage, module_dir, root):
    return dict(schema=1, stage=stage, run_id=str(uuid.uuid4()), pid=os.getpid(),
                started_utc=utc_now(), output_root=str(root), module_dir=str(module_dir),
                module_sha256=module_hashes(module_dir), entry_sha256=digest(__file__),
                blender_version=list(bpy.app.version), blender_version_string=bpy.app.version_string)


def create_source(bpy, prepared, source):
    if source.exists():
        raise FileExistsError(source)
    # Fresh process was checked before this reset. No opened project is touched.
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = 9
    scene.render.fps = 24
    data = bpy.data.curves.new('AssetFreeCordData', 'CURVE')
    data.dimensions = '3D'
    spline = data.splines.new('POLY')
    spline.points.add(12)
    spline.use_cyclic_u = False
    for point, co in zip(spline.points, prepared['poses'][0]):
        point.co = (*co, 1.)
    cord = bpy.data.objects.new(OBJECT_NAME, data)
    scene.collection.objects.link(cord)
    data.animation_data_create()
    action = bpy.data.actions.new('AssetFreeCordXYZW')
    if not hasattr(action, 'fcurves'):
        raise RuntimeError('This generic implementation requires the legacy Action.fcurves API')
    data.animation_data.action = action
    for i in range(13):
        for axis in range(4):
            values = prepared['poses'][:, i, axis] if axis < 3 else np.ones(len(prepared['times']))
            channel = action.fcurves.new(data_path=f'splines[0].points[{i}].co', index=axis)
            channel.extrapolation = 'CONSTANT'
            channel.keyframe_points.add(len(prepared['times']))
            channel.keyframe_points.foreach_set('co', np.column_stack((prepared['times'], values)).ravel())
            for key in channel.keyframe_points:
                key.interpolation = 'LINEAR'
            channel.update()
    scene.frame_set(1)
    prepared['modules']['smooth_curve'].inspect(cord)
    bpy.ops.wm.save_as_mainfile(filepath=str(source), check_existing=False, relative_remap=False)
    if not source.is_file():
        raise RuntimeError('Source save did not create the expected file')


def author(module_dir, root, paths):
    # CPU suitability is established before modifying any Blender scene.
    prepared = prepare_host_fixture(module_dir)
    import bpy
    require_fresh_background(bpy)
    # Exclusive directory creation prevents reusing or overwriting partial runs.
    root.mkdir(parents=True, exist_ok=False)
    intent = provenance(bpy, 'author', module_dir, root)
    intent['host_preparation'] = prepared['summary']
    write_new_json(root / 'author-intent.json', intent)
    expected = {}
    status = dict(schema=1, stage='author', passed=False, pid=os.getpid())
    try:
        write_new_json(paths['plan'], prepared['plan'])
        create_source(bpy, prepared, paths['source'])
        expected = dict(source=digest(paths['source']), plan=digest(paths['plan']))
        write_new_json(paths['source_evidence'], dict(
            schema=1, original_source=str(paths['source']), expected_sha256=expected,
            restore_instruction='Open fixture-source.blend directly after matching its SHA256; retain partial outputs for diagnosis.'))
        writer = prepared['modules']['smooth_curve']
        writer.main(['--source', str(paths['source']), '--plan', str(paths['plan']),
                     '--output', str(paths['candidate']), '--report', str(paths['smoothing_report']),
                     '--source-sha256', expected['source']])
        for name in expected:
            if digest(paths[name]) != expected[name]:
                raise RuntimeError('Original input changed during author: ' + name)
        if module_hashes(module_dir) != intent['module_sha256']:
            raise RuntimeError('Reviewed modules changed during author')
        smoothing_report = json.loads(paths['smoothing_report'].read_text('utf-8'))
        if not smoothing_report.get('source_preserved'):
            raise RuntimeError('Generic smoothing report did not confirm source preservation')
        manifest = dict(intent, complete=True, completed_utc=utc_now(),
                        files=fingerprints(paths), original_sha256=expected,
                        required_next_stage='verify in a new background Blender process',
                        native_fixture_passed=False)
        write_new_json(paths['manifest'], manifest)
        status.update(passed=True, candidate_saved=True, fresh_verification_required=True)
    except BaseException as error:
        status['error'] = dict(type=type(error).__name__, message=str(error))
        raise
    finally:
        status.update(completed_utc=utc_now(), files=fingerprints(paths),
                      original_input_hashes=expected,
                      originals_preserved=bool(expected) and all(
                          paths[name].is_file() and digest(paths[name]) == value for name, value in expected.items()))
        write_new_json(root / 'author-result.json', status)
    print('NATIVE_FIXTURE_AUTHOR_COMPLETE_FRESH_VERIFY_REQUIRED', flush=True)


def verify(module_dir, root, paths):
    import bpy
    require_fresh_background(bpy)
    if not root.is_dir():
        raise FileNotFoundError('Author output directory does not exist')
    # Both files use exclusive creation. An interrupted/failed verify is retained
    # for diagnosis and cannot accidentally be replaced by another invocation.
    for name in ('verify-intent.json', 'verify-result.json', FILES['verification_report']):
        if (root / name).exists():
            raise FileExistsError('Use a new author output root for a new run: ' + str(root / name))
    intent = provenance(bpy, 'verify', module_dir, root)
    write_new_json(root / 'verify-intent.json', intent)
    expected = {}
    status = dict(schema=1, stage='verify', passed=False, pid=os.getpid(), native_fixture_passed=False)
    try:
        manifest = json.loads(paths['manifest'].read_text('utf-8'))
        author_result = json.loads((root / 'author-result.json').read_text('utf-8'))
        if not manifest.get('complete') or author_result.get('passed') is not True:
            raise RuntimeError('Author did not complete successfully')
        if manifest['pid'] == os.getpid():
            raise RuntimeError('Verify must run in a NEW Blender process with a different PID')
        if manifest['output_root'] != str(root) or manifest['module_dir'] != str(module_dir):
            raise RuntimeError('Fixture paths do not match the author manifest')
        if manifest['module_sha256'] != intent['module_sha256'] or manifest['entry_sha256'] != intent['entry_sha256']:
            raise RuntimeError('Reviewed code changed between author and verify')
        for name in ('source', 'plan', 'candidate', 'smoothing_report'):
            entry = manifest['files'][name]
            if entry['path'] != str(paths[name]) or not entry['exists'] or digest(paths[name]) != entry['sha256']:
                raise RuntimeError('Saved artifact identity mismatch: ' + name)
            expected[name] = entry['sha256']
        modules = load_generic_modules(module_dir)
        args = argparse.Namespace(source=paths['source'], candidate=paths['candidate'], plan=paths['plan'],
                                  report=paths['verification_report'], source_sha256=expected['source'],
                                  candidate_sha256=expected['candidate'])
        result = modules['verify_smoothed_curve'].run(args)
        if result.get('passed') is not True or not all(result['checks'].values()):
            raise RuntimeError('Generic fresh verifier did not pass')
        if module_hashes(module_dir) != intent['module_sha256']:
            raise RuntimeError('Reviewed modules changed during verify')
        if not all(digest(paths[name]) == value for name, value in expected.items()):
            raise RuntimeError('Saved artifacts changed during verify')
        status.update(passed=True, native_fixture_passed=True, author_pid=manifest['pid'],
                      fresh_process_confirmed=True, generic_report=str(paths['verification_report']),
                      physical_contact_verified=False, normal_speed_visual_acceptance=False)
    except BaseException as error:
        status['error'] = dict(type=type(error).__name__, message=str(error))
        raise
    finally:
        status.update(completed_utc=utc_now(), files=fingerprints(paths), expected_sha256=expected,
                      artifacts_preserved=bool(expected) and all(
                          paths[name].is_file() and digest(paths[name]) == value for name, value in expected.items()))
        write_new_json(root / 'verify-result.json', status)
    print('NATIVE_FIXTURE_FRESH_VERIFY_PASSED', flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--module-dir', type=Path, required=True)
    parser.add_argument('--output-root', type=Path, required=True)
    parser.add_argument('--stage', choices=('author', 'verify'), required=True)
    args = parser.parse_args(argv)
    module_dir, root, paths = checked_paths(args.module_dir, args.output_root)
    if args.stage == 'author':
        author(module_dir, root, paths)
    else:
        verify(module_dir, root, paths)


if __name__ == '__main__':
    main(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else None)
