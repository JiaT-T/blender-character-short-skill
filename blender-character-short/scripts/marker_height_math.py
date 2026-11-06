"""Relative recorded ankle/toe-joint heights, not toe-tip geometry or contacts."""
import math

def number(value,label,low,high):
    if type(value) not in [int,float] or not math.isfinite(value) or not low<=value<=high:raise ValueError('Finite bounded '+label+' required')
    return float(value)

def marker(value):
    if not isinstance(value,dict) or set(value)!={'ankle_y_m','toe_joint_y_m'}:raise ValueError('Two explicitly recorded joint heights required')
    return {k:number(v,k,-1e5,1e5) for k,v in value.items()}

def derive(samples,calibration,scale,ground,height):
    scale=number(scale,'scale',1e-6,1e6);ground=number(ground,'ground',-1000,1000);height=number(height,'height',.01,100)
    if not isinstance(samples,list) or not 2<=len(samples)<=240 or not isinstance(calibration,dict) or set(calibration)!={'left','right'}:raise ValueError('Bounded motion and both declared calibration references required')
    calibration={s:marker(p) for s,p in calibration.items()};rows=[];details=[];previous=0
    for frame,row in enumerate(samples,1):
        if not isinstance(row,dict) or set(row)!={'frame','source_frame','feet'} or type(row['frame']) is not int or row['frame']!=frame or type(row['source_frame']) is not int or not previous<row['source_frame']<=20000 or not isinstance(row['feet'],dict) or set(row['feet'])!={'left','right'}:raise ValueError('Consecutive target and ordered original source frames required')
        previous=row['source_frame'];goals={};measurements={}
        for side in ['left','right']:
            point=marker(row['feet'][side]);relative={k:point[k]-calibration[side][k] for k in point};minimum=min(relative.values());target=ground+scale*max(0.,minimum)
            if not math.isfinite(target) or not ground<=target<=ground+2*height:raise ValueError('Marker-derived goal exceeds bounded stage height')
            goals[side]={'target_lowest_sole_z_m':target};measurements[side]={'recorded_joint_heights_m':point,'relative_to_declared_reference_m':relative,'minimum_relative_joint_height_m':minimum,'negative_offset_clamped':minimum<0,'target_lowest_sole_z_m':target}
        rows.append({'frame':frame,'source_frame':row['source_frame'],'feet':goals});details.append({'frame':frame,'source_frame':row['source_frame'],'feet':measurements})
    return rows,details
