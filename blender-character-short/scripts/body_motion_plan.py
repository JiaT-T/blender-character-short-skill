"""External proportional-body mappings and exact local conversion provenance."""
from pathlib import Path
import hashlib,math
import numpy as np
from elbow_pole_plan import load_json,finite
from convert_glb_motion import read_bounded,parse_provenance,convert,skeleton_only,finite_worlds
from source_motion import decode_clip

SOURCE_KEYS={'clip','skeleton','conversion_report','source_glb','provenance'}
BODY_PRODUCER_NAMES=('body_motion_plan.py','body_motion_runtime.py','body_approach_pose.py','body_launch_pose.py',
                    'fit_body_motion.py','travel_body_motion.py','plant_body_motion.py',
                    'compose_body_approach.py','source_motion.py','convert_glb_motion.py',
                    'elbow_pole_plan.py','bake_elbow_poles.py','build_performance.py','contact_motion.py','limb_frame.py','foot_reference.py')

def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def integer(value,label,low,high):
    if type(value) is not int or not low<=value<=high:raise ValueError(label+' outside integer bounds')
    return value

def bone_name(value):
    if not isinstance(value,str) or not 1<=len(value)<=128:raise ValueError('Explicit existing bone name required')
    return value

def numeric_vector(value,count,label):
    if not isinstance(value,list) or len(value)!=count:raise ValueError(label+' must contain'+str(count)+' numeric values')
    return np.asarray([finite(v,label) for v in value],dtype=float)

def _validate_plan(value):
    fields={'schema','source','fps','basis','body','limbs','hips','scale_reference','feet','travel','release_frames','compose','weight_threshold'}
    if not isinstance(value,dict) or type(value.get('schema')) is not int or value['schema'] not in (1,2):raise ValueError('Unsupported body motion plan schema')
    if value['schema']==2:fields.add('launch')
    if 'wrist_rotation' in value:
        fields.add('wrist_rotation')
        if value['wrist_rotation'] not in ['original-relative','source-first-fitted']:raise ValueError('Unknown recorded wrist calibration mode')
    if 'arm_rotation' in value:
        fields.add('arm_rotation')
        if value['arm_rotation'] not in ['direction-fit','source-first-fitted']:raise ValueError('Unknown recorded arm calibration mode')
        if value['arm_rotation']=='source-first-fitted' and value.get('wrist_rotation')!='source-first-fitted':raise ValueError('Captured arm rotations require explicitly captured wrist calibration')
    if 'root_motion' in value:
        fields.add('root_motion')
        if value['root_motion'] not in ['legacy-measured-travel','recorded']:raise ValueError('Unknown source root-motion route')
    if 'foot_orientation_references' in value:fields.add('foot_orientation_references')
    if 'limb_hinges' in value:
        fields.add('limb_hinges');hinges=value['limb_hinges']
        if not isinstance(hinges,dict) or not hinges or set(hinges)-{'left_leg','right_leg'}:raise ValueError('Explicit leg hinge mappings required')
        for row in hinges.values():
            if not isinstance(row,dict) or set(row) not in ({'axis_local','bend_sign'},{'axis_local','bend_sign','minimum_bend_degrees'}) or type(row['bend_sign']) is not int or row['bend_sign'] not in [-1,1]:raise ValueError('Calibrated knee-local axis and bend sign required')
            if abs(np.linalg.norm(numeric_vector(row['axis_local'],3,'hinge axis'))-1)>1e-6:raise ValueError('Unit knee-local hinge axis required')
            if not 0<=finite(row.get('minimum_bend_degrees',0),'minimum bend')<=30:raise ValueError('Minimum knee bend outside0..30degrees')
    if set(value)!=fields:raise ValueError('Incomplete body motion plan')
    source=value['source']
    if not isinstance(source,dict) or set(source)!={'files','sha256'} or not isinstance(source['files'],dict) or not isinstance(source['sha256'],dict) or set(source['files'])!=SOURCE_KEYS or set(source['sha256'])!=SOURCE_KEYS:raise ValueError('All five source files and reviewed SHA256 identities are required')
    for name in SOURCE_KEYS:
        if not isinstance(source['files'][name],str) or not source['files'][name].strip() or source['files'][name].startswith(('\\\\','//')):raise ValueError('A local source path is required')
        digest=source['sha256'][name]
        if not isinstance(digest,str) or len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest):raise ValueError('Lowercase SHA256 identity required')
    fps=integer(value['fps'],'fps',1,120);bone_name(value['hips']);integer(value['release_frames'],'release_frames',1,12)
    if not 0<finite(value['weight_threshold'],'weight threshold')<=1:raise ValueError('Weight threshold must be in(0,1]')
    if not isinstance(value['basis'],list) or len(value['basis'])!=3:raise ValueError('Basis requires three numeric rows')
    basis=np.asarray([numeric_vector(row,3,'Basis row') for row in value['basis']])
    if basis.shape!=(3,3) or not np.isfinite(basis).all() or not np.allclose(basis@basis.T,np.eye(3),atol=1e-6) or abs(np.linalg.det(basis)-1)>1e-6:raise ValueError('Basis must be a proper orthonormal3x3 rotation')
    if 'foot_orientation_references' in value:
        from foot_reference import validate as validate_feet
        validate_feet(value['foot_orientation_references'],source['sha256']['source_glb'],basis)
    if not isinstance(value['body'],list) or not 1<=len(value['body'])<=32:raise ValueError('Explicit bounded body mapping required')
    mapped=[]
    for row in value['body']:
        if not isinstance(row,dict) or set(row)!={'bone','source'}:raise ValueError('Body mapping requires bone/source')
        mapped.append(bone_name(row['bone']));integer(row['source'],'source node',0,255)
    limbs=value['limbs']
    if not isinstance(limbs,dict) or set(limbs)!={'left_leg','right_leg','left_arm','right_arm'}:raise ValueError('Four explicitly mapped limbs required')
    for side,row in limbs.items():
        count=4 if side.endswith('_leg') else 3
        if not isinstance(row,dict) or set(row)!={'bones','source'} or not isinstance(row['bones'],list) or not isinstance(row['source'],list) or len(row['bones'])!=count or len(row['source'])!=count:raise ValueError('Invalid limb mapping')
        mapped.extend(bone_name(n) for n in row['bones'])
        for n in row['source']:integer(n,'limb source node',0,255)
    if len(set(mapped))!=len(mapped) or value['hips'] not in {row['bone'] for row in value['body']}:raise ValueError('Body/limb controls must be distinct and body mapping must contain hips')
    reference=value['scale_reference']
    if not isinstance(reference,dict) or set(reference)!={'bones','source'} or not isinstance(reference['bones'],list) or not isinstance(reference['source'],list) or len(reference['bones'])!=3 or len(reference['source'])!=3:raise ValueError('Three-joint scale reference required')
    for n in reference['bones']:bone_name(n)
    for n in reference['source']:integer(n,'scale source node',0,255)
    if not any(reference['bones']==limbs[side+'_leg']['bones'][:3] and reference['source']==limbs[side+'_leg']['source'][:3] for side in ('left','right')):raise ValueError('Scale reference must follow one explicitly mapped anatomical leg')
    if not isinstance(value['feet'],dict) or set(value['feet'])!={'left','right'}:raise ValueError('Two foot selections required')
    for side,row in value['feet'].items():
        if not isinstance(row,dict) or set(row)!={'deform_root','contacts'}:raise ValueError('Foot needs deform_root/contact intervals')
        bone_name(row['deform_root'])
        minimum_contacts=0 if value.get('root_motion')=='recorded' else 1
        if not isinstance(row['contacts'],list) or not minimum_contacts<=len(row['contacts'])<=16:raise ValueError('Bounded stance intervals required; empty means undeclared contacts only for recorded-root fitting')
        previous=0
        for interval in row['contacts']:
            if not isinstance(interval,list) or len(interval)!=2:raise ValueError('A stance is a start/end frame pair')
            start,end=interval;integer(start,'stance start',1,240);integer(end,'stance end',start,240)
            if start<=previous:raise ValueError('Foot stance/release intervals overlap')
            previous=end+value['release_frames']
    travel=value['travel']
    if not isinstance(travel,dict) or set(travel)!={'direction','sole_height','maximum_vertical_change_H','fit_threshold_H','speed_range_H_per_second','grounding_mode'}:raise ValueError('Explicit bounded travel settings required')
    if travel['grounding_mode'] not in ('raise-only','lowest-sole'):raise ValueError('Unknown grounding mode')
    direction=numeric_vector(travel['direction'],3,'Travel direction')
    if direction.shape!=(3,) or not np.isfinite(direction).all() or abs(direction[2])>1e-8 or abs(np.linalg.norm(direction)-1)>1e-6:raise ValueError('Travel direction must be a horizontal unit vector')
    for key,low,high in (('sole_height',0,.01),('maximum_vertical_change_H',0,.25),('fit_threshold_H',0,.1)):
        number=finite(travel[key],key)
        if not low<=number<=high or key!='sole_height' and number==0:raise ValueError('Travel setting outside supported bounds')
    speeds=travel['speed_range_H_per_second']
    if not isinstance(speeds,list) or len(speeds)!=2 or not 0<finite(speeds[0],'minimum speed')<finite(speeds[1],'maximum speed')<=10:raise ValueError('Invalid speed range')
    compose=value['compose']
    if not isinstance(compose,dict) or set(compose)!={'gait_start','minimum_stop_frames','maximum_stop_frames','reference_side','landing_lift_H','target_object'}:raise ValueError('Explicit composition settings required')
    integer(compose['gait_start'],'gait_start',1,1200);integer(compose['minimum_stop_frames'],'minimum stop',2,120);integer(compose['maximum_stop_frames'],'maximum stop',compose['minimum_stop_frames'],120)
    if compose['reference_side'] not in ('left','right') or not isinstance(compose['target_object'],str) or not compose['target_object']:raise ValueError('Reference side and target object required')
    if not 0<=finite(compose['landing_lift_H'],'landing lift')<=.1:raise ValueError('Landing lift out of bounds')
    if value['schema']==2:
        launch=value['launch']
        if not isinstance(launch,dict) or set(launch)!={'hold_frames','ramp_frames','reference_side','crouch_H','free_lift_H'}:raise ValueError('Launch requires explicit hold/ramp/reference/crouch/lift settings')
        hold=integer(launch['hold_frames'],'launch hold',1,120);ramp=integer(launch['ramp_frames'],'launch ramp intermediate frames',3,48)
        if launch['reference_side']!=compose['reference_side'] or launch['reference_side'] not in ('left','right'):raise ValueError('Launch reference must match the configured stop reference side')
        if compose['gait_start']!=hold+ramp+1:raise ValueError('Launch gait_start must equal hold_frames+ramp_frames+1')
        if value['feet'][launch['reference_side']]['contacts'][0][0]!=1:raise ValueError('Launch needs an explicit reference stance beginning at source1')
        if not 0<=finite(launch['crouch_H'],'launch crouch')<=.08 or not 0<=finite(launch['free_lift_H'],'launch free lift')<=.08:raise ValueError('Launch crouch/lift outside[0,.08]')
    return value

def validate_plan(value):
    try:return _validate_plan(value)
    except (TypeError,KeyError,IndexError,OverflowError) as exc:raise ValueError('Malformed body motion plan: '+str(exc)) from exc

def load_plan(path):
    path=Path(path).resolve();value=validate_plan(load_json(path));files={key:(path.parent/filename).resolve() for key,filename in value['source']['files'].items()}
    for key,p in files.items():
        maximum=64*1024*1024 if key=='source_glb' else 4*1024*1024
        if not p.is_file() or p.stat().st_size>maximum or sha(p)!=value['source']['sha256'][key]:raise ValueError('Source missing, oversized or changed: '+key)
    return value,files

def prepare_source(plan,files):
    raw=read_bounded(files['source_glb'],'source_bytes');rights_raw=read_bounded(files['provenance'],'provenance_bytes');rights=parse_provenance(rights_raw,sha(files['source_glb']));report=load_json(files['conversion_report'])
    if report.get('status')!='CPU-conversion-numerically-verified' or report.get('source_sha256')!=sha(files['source_glb']) or report.get('provenance_sha256')!=sha(files['provenance']):raise ValueError('Conversion/source/provenance identity mismatch')
    skeleton=load_json(files['skeleton']);clip=load_json(files['clip'])
    if not isinstance(skeleton,dict) or set(skeleton)!={'nodes'} or not 1<=len(skeleton['nodes'])<=256:raise ValueError('Body hierarchy exceeds256nodes')
    checked=skeleton_only(skeleton)
    if checked!=skeleton:raise ValueError('Skeleton contains unreviewed non-transform data')
    original_skeleton,original_clip,_=convert(raw,integer(report.get('animation_index'),'animation index',0,1024))
    if original_skeleton!=skeleton or original_clip!=clip:raise ValueError('External motion bytes do not match recomputed permitted conversion')
    tracks=decode_clip(clip);times=clip.get('packing',{}).get('times')
    if not isinstance(times,list) or not 2<=len(times)<=240 or len(tracks)>768 or len(times)*len(skeleton['nodes'])>50000:raise ValueError('Body clip exceeds bounded source work')
    if not np.allclose(np.diff(times),1/plan['fps'],atol=1e-6,rtol=0):raise ValueError('Body clip must have a uniform frame grid at declaredfps')
    for track in tracks:
        if track['property'] not in ('position','quaternion','scale') or not np.isfinite(track['values']).all():raise ValueError('Unsupported or nonfinite body channel')
    reference=finite_worlds(skeleton);worlds=[finite_worlds(skeleton,tracks,time) for time in times]
    for world in [reference,*worlds]:
        rotation=world[:,:3,:3]
        if not np.allclose(rotation@np.swapaxes(rotation,1,2),np.eye(3),atol=1e-4) or not np.allclose(np.linalg.det(rotation),1,atol=1e-4):raise ValueError('Source nonrigid scale/shear/reflection is unsupported')
    indexes=[row['source'] for row in plan['body']]+[i for row in plan['limbs'].values() for i in row['source']]+plan['scale_reference']['source']
    if max(indexes)>=len(skeleton['nodes']) or any(end>len(times) for foot in plan['feet'].values() for start,end in foot['contacts']):raise ValueError('Mapping or stance interval exceeds source')
    return {'skeleton':skeleton,'clip':clip,'tracks':tracks,'reference':reference,'worlds':worlds,'times':times,'rights':rights,'source_hashes':{key:sha(p) for key,p in files.items()}}

FRAMING_FEATURES={'head','left_hand','right_hand','left_foot','right_foot','prop'}

def parse_framing_plan(value,last):
    integer(last,'framing source last',1,1200)
    if not isinstance(value,dict) or set(value)!={'schema','ranges'} or type(value['schema']) is not int or value['schema']!=1:raise ValueError('Framing plan requires schema1 and ranges')
    ranges=value['ranges']
    if not isinstance(ranges,list) or not 1<=len(ranges)<=64:raise ValueError('Framing plan requires1..64 ranges')
    previous=0
    for row in ranges:
        if not isinstance(row,dict) or set(row)!={'start','end','features','margin'}:raise ValueError('Framing range requires start/end/features/margin')
        start=integer(row['start'],'framing start',1,last);end=integer(row['end'],'framing end',start,last)
        if start<=previous:raise ValueError('Framing ranges must be ordered without overlap')
        features=row['features']
        if not isinstance(features,list) or not features or any(not isinstance(f,str) or f not in FRAMING_FEATURES for f in features) or len(set(features))!=len(features):raise ValueError('Unknown/duplicate framing feature')
        if not 0<=finite(row['margin'],'framing margin')<=.25:raise ValueError('Framing margin outside[0,.25]')
        previous=end
    return ranges
