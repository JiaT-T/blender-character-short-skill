"""Fresh-process, read-only check of serialized smoothed-curve coordinates.

Compare the candidate against its exact original project. Verify native spline
length, original endpoint channels and actual control displacement at all saved
knots, required times and interval quarter/mid/three-quarter probes. This does
not establish physical contacts, arbitrary-time correctness or visual approval.
"""
import argparse
import json
from pathlib import Path
import re
import sys
import numpy as np
from curve_smoothing import arc_length
from smooth_curve import inspect, sha, validate_plan
from curve_verification import verification_times
from curve_native_metrics import native_length_witness


def read_candidate(cord):
    if (not cord or cord.type!='CURVE' or len(cord.data.splines)!=1
            or cord.data.splines[0].type!='NURBS'):
        raise ValueError('One saved NURBS spline required')
    if (cord.parent or cord.constraints or cord.modifiers or cord.rigid_body or cord.library
            or cord.data.library or cord.data.users!=1 or cord.data.shape_keys
            or cord.data.dimensions!='3D'):
        raise ValueError('Independent unique local curve data required')
    if cord.animation_data and (cord.animation_data.action or cord.animation_data.drivers or cord.animation_data.nla_tracks):
        raise ValueError('Unreviewed object animation in candidate')
    ad=cord.data.animation_data
    if not ad or not ad.action or ad.drivers or ad.nla_tracks:
        raise ValueError('Plain coordinate Action without driver/NLA overrides required')
    if ad.action.library or ad.action.users!=1+bool(ad.action.use_fake_user):
        raise ValueError('Unique local candidate Action required')
    spline=cord.data.splines[0];action=cord.data.animation_data.action
    if (not 4<=len(spline.points)<=128 or spline.order_u!=4 or not spline.use_endpoint_u or spline.use_cyclic_u or spline.use_bezier_u
            or any(abs(p.co[3]-1)>1e-7 for p in spline.points)):
        raise ValueError('Open clamped unit-weight cubic required')
    channels={};times=set()
    for c in action.fcurves:
        match=re.fullmatch(r'splines\[0\]\.points\[(\d+)\]\.co',c.data_path)
        key=(int(match[1]),c.array_index) if match else None
        if (key is None or not 0<=key[0]<len(spline.points) or not 0<=key[1]<4 or key in channels
                or c.mute or c.modifiers or c.sampled_points or not c.keyframe_points
                or c.extrapolation!='CONSTANT' or any(k.interpolation!='LINEAR' for k in c.keyframe_points)):
            raise ValueError('Unsupported serialized coordinate channel')
        if key[1]==3 and any(abs(k.co.y-1)>1e-7 for k in c.keyframe_points):
            raise ValueError('Serialized rational weights are not unit weights')
        channels[key]=c;times.update(float(k.co.x) for k in c.keyframe_points)
    if not all((i,axis) in channels for i in range(len(spline.points)) for axis in range(3)):
        raise ValueError('Missing XYZ coordinate channels')
    return spline,channels,sorted(times)


def endpoint_signature(channels,count):
    return {str((i,axis)):[(tuple(k.co),tuple(k.handle_left),tuple(k.handle_right),k.interpolation,
                            k.handle_left_type,k.handle_right_type) for k in channels[i,axis].keyframe_points]
            for i,axis in channels if i in (0,count-1) or axis==3}


def run(args,guard=None):
    import bpy
    source,candidate,plan_file,report=[getattr(args,n).resolve() for n in ('source','candidate','plan','report')]
    if (not bpy.app.background or len(set((source,candidate,plan_file,report)))!=4 or report.exists()
            or sha(source)!=args.source_sha256 or sha(candidate)!=args.candidate_sha256):
        raise ValueError('Background execution and separate identity-bound inputs/report required')
    plan_sha256=sha(plan_file)
    plan=validate_plan(json.loads(plan_file.read_text('utf-8')))
    bpy.ops.wm.open_mainfile(filepath=str(candidate),load_ui=False,use_scripts=False)
    cord=bpy.context.scene.objects.get(plan['object'])
    spline,channels,key_times=read_candidate(cord);count=len(spline.points)
    candidate_endpoints=endpoint_signature(channels,count)
    candidate_matrix=[list(r) for r in cord.matrix_world]
    # Read original knots before choosing verification times. A damaged candidate
    # can omit a short source peak; candidate-only sampling could miss it.
    bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False)
    original=bpy.context.scene.objects.get(plan['object'])
    original_spline,original_channels,original_knots=inspect(original)
    if len(original_spline.points)!=count:raise ValueError('Control count changed')
    original_endpoints=endpoint_signature(original_channels,count)
    original_matrix=[list(r) for r in original.matrix_world]
    if any(not plan['frames'][0]<=t<=plan['frames'][1] for t in key_times+original_knots):
        raise ValueError('Plan must cover every original and candidate knot')
    times=verification_times(original_knots,key_times,plan['sample_times'],count)
    original_points=np.array([[[original_channels[i,axis].evaluate(t) for axis in range(3)]
                              for i in range(count)] for t in times])
    if not np.isfinite(original_points).all():raise ValueError('Non-finite original curve coordinates')
    bpy.ops.wm.open_mainfile(filepath=str(candidate),load_ui=False,use_scripts=False)
    cord=bpy.context.scene.objects.get(plan['object']);spline,channels,_=read_candidate(cord)
    points=np.array([[[channels[i,axis].evaluate(t) for axis in range(3)] for i in range(count)] for t in times])
    if not np.isfinite(points).all():raise ValueError('Non-finite serialized curve coordinates')
    probe=bpy.data.curves.new('TEMP_UNLINKED_SERIALIZED_CURVE_WITNESS','CURVE');probe.dimensions='3D'
    native=probe.splines.new('NURBS');native.points.add(count-1);native.order_u=4;native.use_endpoint_u=True
    maximum_error=maximum_numerical_error=maximum_agreement=maximum_resolution_delta=0.
    selected_resolutions=set()
    try:
        for index,pose in enumerate(points):
            if guard is not None and index%100==0:guard()
            metric=native_length_witness(native,pose,plan['target_length'],plan['length_tolerance'])
            maximum_error=max(maximum_error,metric['native_target_error'])
            maximum_numerical_error=max(maximum_numerical_error,metric['numerical_target_error'])
            maximum_agreement=max(maximum_agreement,metric['native_quadrature_error'])
            maximum_resolution_delta=max(maximum_resolution_delta,metric['native_pair_delta'])
            selected_resolutions.update(metric['selected_resolutions'])
    finally:bpy.data.curves.remove(probe)
    maximum_shift=float(np.linalg.norm(points-original_points,axis=2).max())
    endpoint_error=float(np.linalg.norm(points[:,[0,-1]]-original_points[:,[0,-1]],axis=2).max())
    checks=dict(native_length=maximum_error<=plan['length_tolerance'],
                integrated_length=maximum_numerical_error<=plan['length_tolerance'],
                independent_quadrature=maximum_agreement<=plan['length_tolerance']*.25,
                native_pair_agrees=maximum_resolution_delta<=plan['length_tolerance']*.5,
                displacement=maximum_shift<=plan['max_displacement']+1e-9,
                evaluated_endpoints_identical=endpoint_error==0,
                endpoint_channels_identical=candidate_endpoints==original_endpoints,
                world_matrix_identical=candidate_matrix==original_matrix,
                source_preserved=sha(source)==args.source_sha256,
                candidate_preserved=sha(candidate)==args.candidate_sha256,
                plan_preserved=sha(plan_file)==plan_sha256)
    result=dict(schema=1,checks=checks,passed=all(checks.values()),source_sha256=args.source_sha256,
                candidate_sha256=args.candidate_sha256,plan_sha256=plan_sha256,sample_count=len(times),
                required_times=len(plan['sample_times']),saved_knots=len(key_times),original_knots=len(original_knots),
                maximum_native_length_error=maximum_error,maximum_native_quadrature_error=maximum_agreement,
                maximum_integrated_length_error=maximum_numerical_error,native_resolutions_used=sorted(selected_resolutions),
                maximum_native_resolution_delta=maximum_resolution_delta,maximum_control_shift=maximum_shift,
                maximum_endpoint_error=endpoint_error,project_saved=False,continuous_time_proof=False,
                physical_contact_verified=False,normal_speed_visual_acceptance=False)
    with report.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2,allow_nan=False)
    if not result['passed']:raise ValueError('Serialized curve verification failed: '+repr(checks))
    return result


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('source','candidate','plan','report'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--source-sha256',required=True);p.add_argument('--candidate-sha256',required=True)
    run(p.parse_args(argv))


if __name__=='__main__':main(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else None)
