"""Smooth a reviewed animated POLY cord in a new saved Blender project.

Run in isolated background Blender with required addons already initialized and
the shared execution lock held. Paths, object identity and numeric bounds come
from the invocation/plan, never from character-specific defaults.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import numpy as np
from curve_smoothing import arc_length, prepare_samples
from curve_verification import verification_times
from curve_native_metrics import native_length_witness


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def validate_plan(plan):
    expected = {'schema', 'object', 'frames', 'sample_times', 'target_length',
                'max_displacement', 'length_tolerance', 'maximum_key_step'}
    if not isinstance(plan, dict) or set(plan) != expected or type(plan['schema']) is not int or plan['schema'] != 1:
        raise ValueError('Exact smoothing plan schema1 required')
    if not isinstance(plan['object'], str) or not plan['object'].strip():
        raise ValueError('Explicit existing curve object required')
    bounds = plan['frames']
    if (not isinstance(bounds, list) or len(bounds) != 2 or any(type(t) is not int for t in bounds)
            or not 0 <= bounds[1] - bounds[0] <= 10000):
        raise ValueError('Bounded ordered inclusive integer frame range required')
    times = plan['sample_times']
    if (not isinstance(times, list) or not 2 <= len(times) <= 10000
            or any(type(t) not in (int, float) or not np.isfinite(t)
                   or not bounds[0] <= t <= bounds[1] for t in times)):
        raise ValueError('Explicit finite in-range verification times required')
    for key in ('target_length','max_displacement','length_tolerance','maximum_key_step'):
        if type(plan[key]) not in (int, float) or not np.isfinite(plan[key]) or plan[key] <= 0:
            raise ValueError('Finite positive numeric bounds required')
    if not .01 <= plan['maximum_key_step'] <= 1:
        raise ValueError('Maximum key step must be .01..1 frames')
    return plan


def inspect(cord):
    if cord is None or cord.type != 'CURVE' or cord.parent or cord.constraints or cord.modifiers or cord.rigid_body:
        raise ValueError('Independent unconstrained existing curve object required')
    if cord.data.users != 1 or cord.data.library or cord.library or cord.data.shape_keys:
        raise ValueError('Unique local curve data without shape keys required')
    if not np.allclose(np.asarray(cord.matrix_world)[:3,:3].T @ np.asarray(cord.matrix_world)[:3,:3], np.eye(3), atol=1e-7, rtol=0):
        raise ValueError('Unit-scale rigid world transform required')
    if cord.animation_data and (cord.animation_data.action or cord.animation_data.drivers or cord.animation_data.nla_tracks):
        raise ValueError('Object animation requires a separate reviewed route')
    data = cord.data; ad = data.animation_data
    if len(data.splines) != 1 or data.dimensions != '3D':
        raise ValueError('One 3D spline required')
    spline = data.splines[0]
    if (spline.type != 'POLY' or not 4 <= len(spline.points) <= 128 or spline.use_cyclic_u
            or any(abs(p.co[3]-1) > 1e-7 for p in spline.points)):
        raise ValueError('Open 4..128-point unit-weight POLY spline required')
    if not ad or not ad.action or ad.drivers or ad.nla_tracks:
        raise ValueError('One plain coordinate Action required')
    action = ad.action
    if action.library or action.users != 1 + bool(action.use_fake_user):
        raise ValueError('Unique local action required')
    channels = {}; times = set()
    for curve in action.fcurves:
        match = re.fullmatch(r'splines\[0\]\.points\[(\d+)\]\.co', curve.data_path)
        key = (int(match[1]), curve.array_index) if match else None
        if key is None or not 0 <= key[0] < len(spline.points) or not 0 <= key[1] < 4 or key in channels:
            raise ValueError('Only unique XYZW coordinate channels are supported')
        if (curve.mute or curve.modifiers or curve.sampled_points or not curve.keyframe_points
                or curve.extrapolation != 'CONSTANT' or any(k.interpolation != 'LINEAR' for k in curve.keyframe_points)):
            raise ValueError('Unmodified unmuted LINEAR keys with constant extrapolation required')
        if key[1] == 3 and any(abs(k.co.y-1)>1e-7 for k in curve.keyframe_points):
            raise ValueError('Animated rational weights must remain identically one')
        channels[key] = curve; times.update(float(k.co.x) for k in curve.keyframe_points)
    if not all((i,axis) in channels for i in range(len(spline.points)) for axis in range(3)):
        raise ValueError('All XYZ channels required')
    return spline, channels, sorted(times)


def smooth_data(cord, plan, guard=None):
    """Fail before mutation if planning/native unlinked checks cannot pass."""
    import bpy
    plan = validate_plan(plan)
    spline, channels, knots = inspect(cord)
    count = len(spline.points)
    start, end = plan['frames']
    if min(knots) < start or max(knots) > end:
        raise ValueError('Plan must include every original coordinate knot')
    def sample(t):
        return np.array([[channels[i, axis].evaluate(t) for axis in range(3)] for i in range(count)])
    # Blender FCurve time and value storage are float32. Merge equivalent times
    # before planning, then reject any new adaptive knot collision before edits.
    grid_count = int(np.ceil((end-start) / plan['maximum_key_step']))
    grid = np.linspace(start, end, grid_count + 1).tolist()
    times = sorted(set(float(np.float32(t)) for t in knots + plan['sample_times'] + grid))
    proposal = prepare_samples(sample, times, target_length=plan['target_length'],
                               max_displacement=plan['max_displacement'], tolerance=plan['length_tolerance'], guard=guard)
    stored_times = proposal['times'].astype(np.float32)
    if len(np.unique(stored_times)) != len(stored_times):
        raise ValueError('Adaptive key times collide at Blender storage precision')
    verification=verification_times(knots,stored_times.tolist(),plan['sample_times'],count)
    # Independent Blender spline evaluation of every proposed pose before edits.
    probe = bpy.data.curves.new('TEMP_UNLINKED_SMOOTH_CURVE_WITNESS', 'CURVE')
    probe.dimensions = '3D'; native = probe.splines.new('NURBS'); native.points.add(count-1)
    native.order_u = 4; native.use_endpoint_u = True
    worst_native=worst_agreement=worst_numerical=0.
    selected_resolutions=set()
    try:
        for index, points in enumerate(proposal['points']):
            if guard is not None and index % 100 == 0: guard()
            metric=native_length_witness(native,points,plan['target_length'],plan['length_tolerance'])
            worst_native=max(worst_native,metric['native_target_error'])
            worst_agreement=max(worst_agreement,metric['native_quadrature_error'])
            worst_numerical=max(worst_numerical,metric['numerical_target_error'])
            selected_resolutions.update(metric['selected_resolutions'])
        if worst_native > plan['length_tolerance'] or worst_numerical > plan['length_tolerance']:
            raise ValueError(f'Native/integrated length bound failed before mutation: native={worst_native}, integrated={worst_numerical}')
    finally:
        bpy.data.curves.remove(probe)
    if guard is not None: guard()
    endpoint_signatures = {str((i,axis)): [(tuple(k.co),k.interpolation) for k in channels[i,axis].keyframe_points]
                           for i in (0,count-1) for axis in range(3)}
    weights_before={str(key):[(tuple(k.co),k.interpolation) for k in curve.keyframe_points]
                    for key,curve in channels.items() if key[1]==3}
    spline.type = 'NURBS'; spline.order_u = 4; spline.use_endpoint_u = True
    spline.use_cyclic_u = False; spline.use_bezier_u = False; spline.resolution_u = 64
    for i in range(1,count-1):
        for axis in range(3):
            curve=channels[i,axis];curve.keyframe_points.clear();curve.keyframe_points.add(len(stored_times))
            curve.keyframe_points.foreach_set('co', np.column_stack((stored_times,proposal['points'][:,i,axis])).ravel())
            for key in curve.keyframe_points:key.interpolation='LINEAR'
            curve.update()
    after = {str((i,axis)): [(tuple(k.co),k.interpolation) for k in channels[i,axis].keyframe_points]
             for i in (0,count-1) for axis in range(3)}
    if after != endpoint_signatures:
        raise ValueError('Endpoint channels changed')
    if weights_before!={str(key):[(tuple(k.co),k.interpolation) for k in curve.keyframe_points]
                       for key,curve in channels.items() if key[1]==3}:
        raise ValueError('Unit-weight animation changed')
    return dict(**proposal['summary'], native_proposed_pose_length_error=worst_native,
                integrated_proposed_pose_length_error=worst_numerical,
                native_vs_quadrature_error=worst_agreement,native_resolutions_used=sorted(selected_resolutions),
                planned_verification_times=len(verification),endpoint_channels_unchanged=True,
                weight_channels_unchanged=True,control_count=count, output_type='NURBS', required_fresh_reopen=True,
                serialized_curve_verified=False, physical_contact_verified=False)


def main(argv=None):
    import bpy
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source','plan','output','report'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--source-sha256',required=True)
    args=parser.parse_args(argv)
    source, plan_file, output, report = [getattr(args,n).resolve() for n in ('source','plan','output','report')]
    if (not bpy.app.background or not re.fullmatch('[0-9a-f]{64}',args.source_sha256)
            or source.suffix.lower()!='.blend' or output.suffix.lower()!='.blend'
            or len(set((source,plan_file,output,report)))!=4 or output.exists() or report.exists()
            or sha(source)!=args.source_sha256):
        raise ValueError('Background execution, reviewed source and new separate outputs required')
    plan=validate_plan(json.loads(plan_file.read_text('utf-8')))
    bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False)
    result=smooth_data(bpy.context.scene.objects.get(plan['object']),plan)
    if sha(source)!=args.source_sha256:raise ValueError('Source identity changed')
    bpy.ops.wm.save_as_mainfile(filepath=str(output),check_existing=False,relative_remap=False)
    result.update(source_sha256=args.source_sha256,plan_sha256=sha(plan_file),output_sha256=sha(output),
                  source_preserved=sha(source)==args.source_sha256)
    with report.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2,allow_nan=False)
    print('SMOOTH_CURVE_SAVED_REOPEN_REQUIRED',flush=True)


if __name__=='__main__':
    main(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else None)
