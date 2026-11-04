"""Explicit bounded one-shot scene response; no character or asset names embedded."""
import math
from elbow_pole_plan import load_json

FIELDS={'schema','prop','receiver','indicator','search_frames','stable_frames','xy_margin_H','bottom_gap_H','max_prop_height_H','max_step_H','ramp_frames','mix','on_color','emission_strength','bloom_weight'}
def number(value,label,low,high):
    if isinstance(value,bool) or not isinstance(value,(int,float)):raise ValueError(label+' must be numeric')
    try:result=float(value)
    except (OverflowError,ValueError):raise ValueError(label+' is not finite')
    if not math.isfinite(result) or not low<=result<=high:raise ValueError(label+' outside supported finite bounds')
    return result
def integer(value,label,low,high):
    if type(value) is not int or not low<=value<=high:raise ValueError(label+' must be a bounded integer')
    return value
def validate_plan(value,first,last):
    if type(first) is not int or type(last) is not int or first!=1 or not 2<=last<=1200:raise ValueError('Feedback requires a1..1200 bounded existing timeline')
    if not isinstance(value,dict) or set(value)!=FIELDS or type(value['schema']) is not int or value['schema']!=1:raise ValueError('Feedback schema1 requires exactly its documented fields')
    result=dict(value)
    for key in ('prop','receiver','indicator'):
        name=value[key]
        if not isinstance(name,str) or not name.strip() or len(name)>256 or any(c in name for c in ('\0','\n','\r')):raise ValueError('Explicit existing object name required: '+key)
    if len({value[k] for k in ('prop','receiver','indicator')})!=3:raise ValueError('Prop, receiver and indicator must be distinct objects')
    frames=value['search_frames']
    if not isinstance(frames,list) or len(frames)!=2:raise ValueError('search_frames requires a start/end pair')
    a=integer(frames[0],'search start',first,last);b=integer(frames[1],'search end',a,last)
    result['stable_frames']=integer(value['stable_frames'],'stable_frames',2,min(48,b-a+1));result['ramp_frames']=integer(value['ramp_frames'],'ramp_frames',1,120)
    for key,low,high in [('xy_margin_H',0,.1),('max_prop_height_H',1e-6,.2),('max_step_H',1e-6,.1),('emission_strength',0,5),('bloom_weight',0,1),('mix',0,1)]:result[key]=number(value[key],key,low,high)
    gap=value['bottom_gap_H']
    if not isinstance(gap,list) or len(gap)!=2:raise ValueError('bottom_gap_H requires a signed interval')
    result['bottom_gap_H']=[number(v,'bottom gap',-.005,.02) for v in gap]
    if result['bottom_gap_H'][0]>result['bottom_gap_H'][1]:raise ValueError('Signed bottom gap interval is reversed')
    for key in ('on_color',):
        if not isinstance(value[key],list) or len(value[key])!=3:raise ValueError(key+' requires RGB')
        result[key]=[number(v,key,0,1) for v in value[key]]
    return result

def confirmation_frame(rows,required):
    """Rows must cover consecutive source integer frames, with explicit booleans."""
    integer(required,'required stable samples',2,48);run=0;previous=None
    for row in rows:
        frame=row['frame'];integer(frame,'row frame',1,1200)
        if previous is not None and frame!=previous+1:raise ValueError('Feedback sample rows must be consecutive')
        if type(row['qualifies']) is not bool:raise ValueError('Feedback qualification must be explicit boolean')
        run=run+1 if row['qualifies'] else 0
        if run>=required:return frame
        previous=frame
    return None

def response_weight(frame,event,ramp):
    t=max(0.,min(1.,(frame-event)/ramp));return t*t*(3-2*t)
