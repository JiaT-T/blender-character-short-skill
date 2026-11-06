"""External hand mappings and bounded, smooth, per-axis motion channels."""
import math

def number(value,label):
    if type(value) not in (int,float) or not math.isfinite(value):raise ValueError(label+' must be finite numeric')
    return float(value)

def text(value,label):
    if not isinstance(value,str) or not value or len(value)>160 or any(ord(c)<32 for c in value):raise ValueError(label+' must be a nonempty bounded string')
    return value

def profile(document):
    if not isinstance(document,dict):raise ValueError('Hand profile must be an object')
    if type(document.get('schema')) is not int or document['schema']!=1:raise ValueError('Hand profile schema1 required')
    hands=document.get('hands');joints=document.get('joints')
    if not isinstance(hands,dict) or not hands or set(hands)-{'left','right'}:raise ValueError('Explicit left/right wrist mappings required')
    hands={side:text(name,'wrist') for side,name in hands.items()}
    if len(set(hands.values()))!=len(hands):raise ValueError('Wrist mappings must be distinct')
    if not isinstance(joints,list) or not 1<=len(joints)<=64:raise ValueError('1..64 explicit hand joints required')
    result=[];ids=set();bones=set()
    for row in joints:
        ident=text(row.get('id'),'joint id');bone=text(row.get('bone'),'bone');side=row.get('side');digit=text(row.get('digit'),'digit')
        if ident in ids or bone in bones or side not in hands or digit=='palm' or '.' in digit:raise ValueError('Unique joint/bone, nonreserved digit and configured side required')
        ids.add(ident);bones.add(bone);axes=row.get('axes');total=number(row.get('max_total_degrees'),'max_total_degrees')
        if not 0<total<=135 or not isinstance(axes,list) or not 1<=len(axes)<=3:raise ValueError('Bounded total angle and1..3 ordered axes required')
        converted=[];axis_ids=set()
        for axis in axes:
            name=text(axis.get('id'),'axis id');v=axis.get('axis_local');limit=number(axis.get('limit_degrees'),'axis limit')
            if name in axis_ids or not isinstance(v,list) or len(v)!=3 or not 0<limit<=90:raise ValueError('Unique bounded axis required')
            axis_ids.add(name);v=[number(x,'axis coordinate') for x in v];length=math.sqrt(sum(x*x for x in v))
            if abs(length-1)>1e-4:raise ValueError('axis_local must be calibrated unit vector')
            converted.append({'id':name,'axis_local':[x/length for x in v],'limit_degrees':limit})
        result.append({'id':ident,'bone':bone,'side':side,'digit':digit,'axes':converted,'max_total_degrees':total})
    binding=document.get('binding_sha256')
    if binding is not None and (not isinstance(binding,str) or len(binding)!=64 or any(c not in '0123456789abcdef' for c in binding)):raise ValueError('binding_sha256 must be lowercase SHA256')
    return {'schema':1,'id':text(document.get('id'),'profile id'),'hands':hands,'joints':result,'binding_sha256':binding}

def motion(document,mapping):
    if not isinstance(document,dict):raise ValueError('Hand motion must be an object')
    if type(document.get('schema')) is not int or document['schema']!=1:raise ValueError('Hand motion schema1 required')
    frames=document.get('frames')
    if not isinstance(frames,list) or len(frames)!=2 or any(type(x) is not int for x in frames) or not 1<=frames[0]<frames[1] or frames[1]-frames[0]+1>240:raise ValueError('Explicit2..240 positive integer-frame window required')
    channels=document.get('channels');known={(j['id'],a['id']) for j in mapping['joints'] for a in j['axes']};seen=set();result=[]
    if not isinstance(channels,list) or not 1<=len(channels)<=192:raise ValueError('1..192 motion channels required')
    for row in channels:
        key=(row.get('joint'),row.get('axis'))
        if key not in known or key in seen:raise ValueError('Unknown or repeated motion channel')
        seen.add(key);keys=row.get('keys')
        if not isinstance(keys,list) or not 2<=len(keys)<=256:raise ValueError('2..256 explicit channel keys required')
        clean=[]
        for pair in keys:
            if not isinstance(pair,list) or len(pair)!=2 or type(pair[0]) is not int:raise ValueError('Channel keys must be[integer frame, normalized fraction]')
            f,value=pair[0],number(pair[1],'motion fraction')
            if not frames[0]<=f<=frames[1] or not 0<=value<=1 or (clean and f<=clean[-1][0]):raise ValueError('Ordered keys/fractions must stay in declared bounds')
            clean.append([f,value])
        if clean[0][0]!=frames[0] or clean[-1][0]!=frames[1]:raise ValueError('Every channel must include both clip boundaries')
        result.append({'joint':key[0],'axis':key[1],'keys':clean})
    fps=document.get('fps',24)
    if type(fps) is not int or not 1<=fps<=60:raise ValueError('Explicit fps must be integer1..60')
    return {'schema':1,'frames':frames,'fps':fps,'channels':result,'interpolation':'quintic target, densely sampled; actual saved interpolation requires separate audit'}

def value_at(keys,frame):
    if frame<=keys[0][0]:return keys[0][1]
    if frame>=keys[-1][0]:return keys[-1][1]
    for (a,x),(b,y) in zip(keys,keys[1:]):
        if a<=frame<=b:
            u=(frame-a)/(b-a);w=u*u*u*(u*(u*6-15)+10);return x+(y-x)*w
    raise ValueError('Frame not covered by channel')
