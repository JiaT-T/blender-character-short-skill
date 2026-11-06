"""Reviewed geometric shoe-height trajectory, not inferred physical contacts."""
from pathlib import Path
import json,math

def number(value,label,low,high):
    if type(value) not in [int,float] or not math.isfinite(value) or not low<=value<=high:raise ValueError('Finite bounded '+label+' required')
    return float(value)

def name(value):
    if not isinstance(value,str) or not value.strip() or len(value)>256 or any(ord(c)<32 for c in value):raise ValueError('Explicit original bone/constraint name required')
    return value

def digest(value):
    if not isinstance(value,str) or len(value)!=64 or any(c not in '0123456789abcdef' for c in value):raise ValueError('Reviewed lowercase SHA256 required')

def validate(cfg):
    required={'schema','blend_sha256','root_bone','height','ground','frames','fps','legs','feet','weight_threshold','existing_IK','ankle_pitch_bias_degrees','desired_initial_toe_direction_pitch_degrees','maximum_ankle_pitch_bias_degrees','ankle_pitch_axis_local','stride_scale','maximum_root_lowering_H','reach_fraction','reach_margin_H','maximum_height_error_H','maximum_horizontal_error_H','maximum_segment_length_error_H','iterations_per_frame','rows'}
    optional={'at_utc','scope','source_heel_calibration_frames','source_initial_ankle_to_tip_pitch_degrees','source_native_witness_sha256','source_toe_tail_sha256','shared_calibration_witness_sha256','shoe_bias_reused_from_same_source_and_model','height_proxy'}
    if not isinstance(cfg,dict) or set(cfg)-required-optional or required-set(cfg) or type(cfg['schema']) is not int or cfg['schema'] not in [1,2]:raise ValueError('Explicit shoe adaptation schema1 or2 required')
    if cfg['schema']==2:
        proxy=cfg.get('height_proxy')
        if not isinstance(proxy,dict) or set(proxy)!={'kind','derivation_report_sha256'} or proxy['kind']!='recorded-joint-offsets':raise ValueError('Schema2 needs explicitly reviewed recorded-joint-offset goals')
        digest(proxy['derivation_report_sha256'])
    elif 'height_proxy' in cfg:raise ValueError('Typed marker goals require schema2')
    digest(cfg['blend_sha256']);name(cfg['root_bone']);number(cfg['height'],'height',.01,100);number(cfg['ground'],'ground',-1000,1000)
    frames=cfg['frames']
    if not isinstance(frames,list) or len(frames)!=2 or any(type(x) is not int for x in frames) or not 1<=frames[0]<frames[1]<=20000 or frames[1]-frames[0]+1>240:raise ValueError('At most240 original motion frames required')
    if type(cfg['fps']) is not int or not 1<=cfg['fps']<=120 or type(cfg['iterations_per_frame']) is not int or not 1<=cfg['iterations_per_frame']<=12:raise ValueError('Bounded integer fps/solve iterations required')
    for field in ['legs','feet','ankle_pitch_bias_degrees']:
        if not isinstance(cfg[field],dict) or set(cfg[field])!={'left','right'}:raise ValueError('Exactly two explicitly mapped feet required')
    bones=[]
    for side in ['left','right']:
        chain=cfg['legs'][side]
        if not isinstance(chain,list) or len(chain)!=4:raise ValueError('Four original leg/ankle/toe bones required')
        bones.extend(name(n) for n in chain)
        if not isinstance(cfg['feet'][side],dict) or set(cfg['feet'][side])!={'deform_root'}:raise ValueError('Explicit weighted shoe root required')
        name(cfg['feet'][side]['deform_root'])
    if len(set(bones))!=8 or cfg['root_bone'] in bones:raise ValueError('Distinct original legs and separate body root required')
    bounds={'weight_threshold':(.01,1),'maximum_ankle_pitch_bias_degrees':(0,30),'stride_scale':(.8,1),'maximum_root_lowering_H':(0,.06),'reach_fraction':(.95,.9999),'reach_margin_H':(0,.002),'maximum_height_error_H':(.000001,.001),'maximum_horizontal_error_H':(.000001,.001),'maximum_segment_length_error_H':(.000001,.0001)}
    for k,(lo,hi) in bounds.items():number(cfg[k],k,lo,hi)
    axis=cfg['ankle_pitch_axis_local']
    if not isinstance(axis,list) or len(axis)!=3 or abs(sum(number(x,'pitch axis',-1,1)**2 for x in axis)-1)>1e-6:raise ValueError('Unit original local pitch axis required')
    directions=cfg['desired_initial_toe_direction_pitch_degrees']
    if not isinstance(directions,dict) or set(directions)-{'left','right'}:raise ValueError('Explicit optional toe direction targets required')
    for side,value in directions.items():number(value,'toe pitch',0,90)
    for side,value in cfg['ankle_pitch_bias_degrees'].items():
        if value is None:
            if side not in directions:raise ValueError('Uncalibrated shoe pitch requires a reviewed target direction')
        else:number(value,'pitch bias',-cfg['maximum_ankle_pitch_bias_degrees'],cfg['maximum_ankle_pitch_bias_degrees'])
    ik=cfg['existing_IK']
    if not isinstance(ik,list) or len(ik)!=4:raise ValueError('Exactly four existing original leg/toe IK constraints required')
    seen=set();targets=set()
    for row in ik:
        if not isinstance(row,dict) or set(row)!={'side','bone','constraint','target_bone','chain_count'} or row['side'] not in ['left','right'] or type(row['chain_count']) is not int or row['chain_count'] not in [1,2]:raise ValueError('Reviewed original IK identity required')
        side=row['side'];count=row['chain_count'];token=(side,count)
        if token in seen or row['bone']!=cfg['legs'][side][1 if count==2 else 2]:raise ValueError('Each original knee/ankle IK must occur once')
        seen.add(token);name(row['constraint']);name(row['target_bone']);targets.add(row['target_bone'])
    if len(targets)!=4:raise ValueError('Distinct existing original IK targets required')
    rows=cfg['rows']
    if not isinstance(rows,list) or len(rows)!=frames[1]-frames[0]+1:raise ValueError('One reviewed source-height row per original integer frame required')
    for frame,row in zip(range(frames[0],frames[1]+1),rows):
        if not isinstance(row,dict) or set(row)!={'frame','source_frame','feet'} or type(row['frame']) is not int or row['frame']!=frame or type(row['source_frame']) is not int or not 1<=row['source_frame']<=20000 or not isinstance(row['feet'],dict) or set(row['feet'])!={'left','right'}:raise ValueError('Consecutive target and explicit original source frames required')
        for point in row['feet'].values():
            fields={'target_lowest_sole_z_m'} if cfg['schema']==2 else {'source_heel_y_m','source_toe_tip_y_m','unclamped_source_proxy_y_m','target_lowest_sole_z_m'}
            if not isinstance(point,dict) or set(point)!=fields:raise ValueError('Explicit schema-specific proxy/target shoe height required')
            for k,v in point.items():number(v,k,-1000,1000)
            if not cfg['ground']-1e-8<=point['target_lowest_sole_z_m']<=cfg['ground']+cfg['height']*2:raise ValueError('Target proxy height must remain within bounded stage range')
    for key in optional:
        if key.endswith('sha256') and key in cfg:digest(cfg[key])
    return cfg

def load(path):
    path=Path(path)
    if path.stat().st_size>1024*1024:raise ValueError('Shoe plan exceeds1MB')
    def unique(pairs):
        result={}
        for k,v in pairs:
            if k in result:raise ValueError('Duplicate shoe plan key')
            result[k]=v
        return result
    def invalid(value):raise ValueError('Nonfinite shoe plan constant: '+value)
    return validate(json.loads(path.read_text('utf-8'),object_pairs_hook=unique,parse_constant=invalid))
