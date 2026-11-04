"""Bounded whole-scene time maps, with no embedded character or motion assets."""
from bisect import bisect_left
from fractions import Fraction
from elbow_pole_plan import load_json

MAX_FRAMES=1200
MAX_MATRIX_FRAMES=500000
MAX_KEY_SAMPLES=2000000

def validate_plan(value,first,last):
    if type(first) is not int or type(last) is not int or first!=1 or not 2<=last<=MAX_FRAMES:
        raise ValueError('Tempo input must start at1 and contain2..1200 frames')
    if not isinstance(value,dict) or set(value)!={'schema','knots'}:
        raise ValueError('Tempo plan requires exactly schema and knots')
    if type(value['schema']) is not int or value['schema']!=1:
        raise ValueError('Unsupported scene tempo schema')
    knots=value['knots']
    if not isinstance(knots,list) or not 2<=len(knots)<=MAX_FRAMES:
        raise ValueError('Tempo plan requires2..1200 ordered knots')
    previous=None
    for knot in knots:
        if not isinstance(knot,dict) or set(knot)!={'output','source'}:
            raise ValueError('Each tempo knot requires exactly output and source')
        if any(type(knot[k]) is not int for k in ('output','source')):
            raise ValueError('Tempo knot frames must be integers, not booleans')
        if not 1<=knot['output']<=MAX_FRAMES or not first<=knot['source']<=last:
            raise ValueError('Tempo knot frame outside supported scene range')
        if previous and (knot['output']<=previous['output'] or knot['source']<previous['source']):
            raise ValueError('Output knots must increase; source time must not reverse')
        previous=knot
    if knots[0]!={'output':1,'source':first} or knots[-1]['source']!=last:
        raise ValueError('Tempo knots must cover the complete input scene, starting at output1')
    times=[];segment=0
    for frame in range(1,knots[-1]['output']+1):
        while segment+1<len(knots)-1 and frame>knots[segment+1]['output']:segment+=1
        a,b=knots[segment:segment+2]
        time=Fraction(a['source'])+Fraction(frame-a['output'],b['output']-a['output'])*(b['source']-a['source'])
        times.append(float(time))
    return {'schema':1,'knots':[dict(k) for k in knots],'source_first':first,'source_last':last,
            'output_first':1,'output_last':knots[-1]['output'],'source_times':times}

def map_marker(frame,plan):
    if type(frame) is not int or not plan['source_first']<=frame<=plan['source_last']:
        raise ValueError('Timeline markers must be inside the complete source interval')
    return 1+bisect_left(plan['source_times'],frame)

def check_work(plan,matrix_count,curve_count):
    for number in (matrix_count,curve_count):
        if type(number) is not int or number<0:raise ValueError('Work counts must be nonnegative integers')
    count=plan['output_last']
    if count*matrix_count>MAX_MATRIX_FRAMES or count*curve_count>MAX_KEY_SAMPLES:
        raise ValueError('Tempo work exceeds500000 matrix-frames or2000000 curve samples')
    return {'output_frames':count,'matrix_frames':count*matrix_count,'curve_samples':count*curve_count}
