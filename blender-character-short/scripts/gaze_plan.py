"""Validate real-object fixation ranges and optional returns to authored gaze."""

def parse_plan(plan, first, last, object_names):
    if not isinstance(plan,dict) or not isinstance(plan.get('ranges'),list):
        raise ValueError('Gaze plan requires a ranges list')
    targets={}
    for row in plan['ranges']:
        if not isinstance(row,dict):raise ValueError('Target range must be an object')
        start=row.get('start');end=row.get('end');name=row.get('object')
        if type(start)!=int or type(end)!=int or not first<=start<=end<=last or not isinstance(name,str) or name not in object_names:
            raise ValueError('Invalid target range')
        for frame in range(start,end+1):
            if frame in targets:raise ValueError('Overlapping target ranges')
            targets[frame]=name
    if not targets:raise ValueError('No target frames')
    returns=plan.get('returns',[])
    if not isinstance(returns,list):raise ValueError('Gaze returns must be a list')
    parsed=[];occupied=set()
    for row in returns:
        if not isinstance(row,dict) or set(row)-{'start','end','easing'}:raise ValueError('Unknown gaze return fields')
        start=row.get('start');end=row.get('end');easing=row.get('easing','smoothstep')
        if type(start)!=int or type(end)!=int or not first<=start<end<=last:raise ValueError('Return requires at least two integer frames inside the scene')
        if start-1 not in targets:raise ValueError('Return must immediately follow a fixation range')
        if easing not in ('linear','smoothstep'):raise ValueError('Unknown gaze return easing')
        frames=set(range(start,end+1))
        if frames.intersection(targets) or frames.intersection(occupied):raise ValueError('Return overlaps a fixation or another return')
        occupied.update(frames);parsed.append({'start':start,'end':end,'source_frame':start-1,'easing':easing})
    return targets,sorted(parsed,key=lambda row:row['start'])


def return_weight(frame, row):
    """Last fixation has weight0; return end has weight1 (the authored control)."""
    if type(frame)!=int or not row['source_frame']<=frame<=row['end']:raise ValueError('Frame outside gaze return')
    value=(frame-row['source_frame'])/(row['end']-row['source_frame'])
    return value if row['easing']=='linear' else value*value*(3-2*value)
