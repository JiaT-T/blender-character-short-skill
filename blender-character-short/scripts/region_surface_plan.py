"""Bounded external weighted-region pair plans; no character data embedded."""
from elbow_pole_plan import load_json,finite

MAX_FRAMES=1200
MAX_TRIANGLE_FRAMES=50000000
MAX_CHUNK_PAIR_FRAMES=1000000
CHUNK_TRIANGLES=512
MAX_PAIRS_PER_FRAME=200000

def validate_plan(value,first,last):
    try:return _validate(value,first,last)
    except (TypeError,KeyError,IndexError,OverflowError) as exc:raise ValueError('Malformed region surface plan: '+str(exc)) from exc

def _validate(value,first,last):
    if type(first) is not int or type(last) is not int or not 1<=first<=last<=MAX_FRAMES:raise ValueError('Scene must fit integer frames1..1200')
    if not isinstance(value,dict) or set(value)!={'schema','regions','pairs','ranges'} or type(value['schema']) is not int or value['schema']!=1:raise ValueError('Region plan requires schema1,regions,pairs,ranges')
    regions=value['regions']
    if not isinstance(regions,dict) or not 2<=len(regions)<=8:raise ValueError('Require2..8 explicitly weighted regions')
    roots=set()
    for name,row in regions.items():
        if not isinstance(name,str) or not 1<=len(name)<=64 or not isinstance(row,dict) or set(row)!={'root_bone','weight_threshold'}:raise ValueError('Each named region needs root_bone and weight_threshold')
        if not isinstance(row['root_bone'],str) or not 1<=len(row['root_bone'])<=128:raise ValueError('Explicit existing region root bone required')
        if row['root_bone'] in roots:raise ValueError('Region root bones must be distinct')
        roots.add(row['root_bone'])
        if not 0<finite(row['weight_threshold'],'Region weight threshold')<=1:raise ValueError('Region weight threshold must be in(0,1]')
    pairs=value['pairs'];seen=set()
    if not isinstance(pairs,list) or not 1<=len(pairs)<=16:raise ValueError('Require1..16 explicit region pairs')
    for pair in pairs:
        if not isinstance(pair,list) or len(pair)!=2 or any(not isinstance(n,str) or n not in regions for n in pair) or pair[0]==pair[1]:raise ValueError('Each surface pair names two different configured regions')
        key=tuple(sorted(pair))
        if key in seen:raise ValueError('Duplicate or reversed region pair')
        seen.add(key)
    ranges=value['ranges'];previous=first-1;frames=[]
    if not isinstance(ranges,list) or not 1<=len(ranges)<=64:raise ValueError('Require1..64 ordered frame ranges')
    for row in ranges:
        if not isinstance(row,list) or len(row)!=2 or any(type(f) is not int for f in row) or not first<=row[0]<=row[1]<=last or row[0]<=previous:raise ValueError('Frame ranges must be integer, ordered, nonoverlapping and inside the scene')
        frames.extend(range(row[0],row[1]+1));previous=row[1]
    if len(frames)>MAX_FRAMES:raise ValueError('Frame sample budget exceeded')
    return {'schema':1,'regions':regions,'pairs':pairs,'ranges':ranges,'frames':frames}

def check_work(plan,triangle_counts,chunk_counts):
    triangles=sum(triangle_counts.values());chunks=0
    for a,b in plan['pairs']:chunks+=chunk_counts[a]*chunk_counts[b]
    work={'sample_frames':len(plan['frames']),'selected_triangle_frames':triangles*len(plan['frames']),'maximum_chunk_pair_frames':chunks*len(plan['frames'])}
    if not triangles or work['selected_triangle_frames']>MAX_TRIANGLE_FRAMES or work['maximum_chunk_pair_frames']>MAX_CHUNK_PAIR_FRAMES:raise ValueError('Selected-region work exceeds triangle/chunk-pair budget')
    return work
