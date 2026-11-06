"""Explicit bounded adaptation of a stationary recorded-action join."""
import json,math
from pathlib import Path

def load(path):
    raw=Path(path).read_bytes()
    if len(raw)>65536:raise ValueError('Recorded stance plan exceeds64KB')
    def unique(pairs):
        out={}
        for k,v in pairs:
            if k in out:raise ValueError('Duplicate stance plan key')
            out[k]=v
        return out
    return validate(json.loads(raw,object_pairs_hook=unique))

def validate(p):
    fields={'schema','mode','source_sha256','frames','fps','height','reference_frame','match_frames','limbs','align_ankle_orientation','maximum_shift_H','maximum_ankle_orientation_degrees','maximum_leg_rotation_degrees','endpoint_tolerance_H'}
    if not isinstance(p,dict) or set(p)!=fields or type(p['schema']) is not int or p['schema']!=1 or p['mode']!='declared-stationary-transition':raise ValueError('Explicit stationary transition schema1 required')
    digest=p['source_sha256']
    if not isinstance(digest,str) or len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest):raise ValueError('Reviewed input SHA256 required')
    f=p['frames'];m=p['match_frames'];r=p['reference_frame']
    if not isinstance(f,list) or len(f)!=2 or any(type(x) is not int for x in f) or not 1<=f[0]<f[1]<=20000 or f[1]-f[0]+1>480:raise ValueError('Bounded complete source interval required')
    if not isinstance(m,list) or len(m)!=2 or any(type(x) is not int for x in m) or not f[0]<=m[0]<m[1]<=f[1] or not 2<=m[1]-m[0]+1<=48:raise ValueError('Explicit short adaptation interval required')
    if type(r) is not int or not f[0]<=r<=m[0] or type(p['fps']) is not int or not 1<=p['fps']<=120 or type(p['align_ankle_orientation']) is not bool:raise ValueError('Explicit reference/fps/orientation mode required')
    for k,lo,hi in [('height',.1,10),('maximum_shift_H',.0001,.05),('maximum_ankle_orientation_degrees',.01,15),('maximum_leg_rotation_degrees',.01,35),('endpoint_tolerance_H',.000001,.0002)]:
        v=p[k]
        if type(v) not in [int,float] or not math.isfinite(v) or not lo<=v<=hi:raise ValueError('Finite bounded stance parameter required: '+k)
    if not isinstance(p['limbs'],dict) or set(p['limbs'])!={'left','right'}:raise ValueError('Two explicitly mapped legs required')
    all_bones=[]
    for item in p['limbs'].values():
        if not isinstance(item,dict) or set(item)!={'bones','axis_local','bend_sign'}:raise ValueError('Explicit calibrated hinge mapping required')
        b=item['bones'];axis=item['axis_local']
        if not isinstance(b,list) or len(b)!=3 or any(not isinstance(n,str) or not n for n in b):raise ValueError('Three original leg joints required')
        if not isinstance(axis,list) or len(axis)!=3 or any(type(v) not in [int,float] or not math.isfinite(v) for v in axis) or abs(sum(v*v for v in axis)-1)>1e-6:raise ValueError('Unit finite hinge axis required')
        if type(item['bend_sign']) is not int or item['bend_sign'] not in [-1,1]:raise ValueError('Explicit hinge bend sign required')
        all_bones+=b
    if len(set(all_bones))!=6:raise ValueError('Leg mappings must be distinct')
    return p

def weight(frame,match):
    t=min(1.,max(0.,(frame-match[0])/(match[1]-match[0])))
    return t*t*t*(10+t*(-15+6*t))
