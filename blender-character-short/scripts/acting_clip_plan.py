"""Compose external semantic acting clips with explicit retiming and holds."""
import math

def number(x):
    if type(x) not in (int,float) or not math.isfinite(x):raise ValueError('Finite numeric value required')
    return float(x)

def vector(v,width):
    if not isinstance(v,list) or len(v)!=width:raise ValueError('Channel width mismatch')
    return [number(x) for x in v]

def sample(keys,time,curve='quintic'):
    if time<=keys[0][0]:return list(keys[0][1])
    for (a,x),(b,y) in zip(keys,keys[1:]):
        if time<=b:
            u=(time-a)/(b-a)
            if curve=='quintic':u=u*u*u*(10+u*(-15+6*u))
            return [p+(q-p)*u for p,q in zip(x,y)]
    return list(keys[-1][1])

def compile_plan(data):
    if not isinstance(data,dict) or type(data.get('schema')) is not int or data['schema']!=1:raise ValueError('Acting schema 1 required')
    frames=data.get('frames');fps=data.get('fps')
    if not isinstance(frames,list) or len(frames)!=2 or any(type(x) is not int for x in frames) or not 1<=frames[0]<frames[1] or frames[1]-frames[0]+1>480 or type(fps) is not int or not 1<=fps<=60:raise ValueError('Bounded integer timeline/fps required')
    channels=data.get('channels');clips=data.get('clips');instances=data.get('instances')
    if not isinstance(channels,dict) or not 1<=len(channels)<=192 or not isinstance(clips,dict) or not 1<=len(clips)<=128 or not isinstance(instances,list) or not 1<=len(instances)<=256:raise ValueError('Bounded channels, clips and instances required')
    result={};prepared={};total=0
    for name,c in channels.items():
        if not isinstance(name,str) or not name:raise ValueError('Nonempty channel id required')
        width=c.get('width');bounds=c.get('range')
        if type(width) is not int or not 1<=width<=4:raise ValueError('Channel width 1..4 required')
        base=vector(c.get('base'),width)
        if not isinstance(bounds,list) or len(bounds)!=2:raise ValueError('Explicit channel range required')
        lo,hi=map(number,bounds)
        if lo>=hi or any(not lo<=x<=hi for x in base):raise ValueError('Invalid channel range/base')
        result[name]={'base':base,'range':[lo,hi],'segments':[]}
    for name,clip in clips.items():
        tracks=clip.get('tracks');curve=clip.get('curve','quintic')
        if not isinstance(tracks,dict) or not tracks or curve not in ['quintic','linear']:raise ValueError('Clip tracks and supported curve required')
        prepared[name]={}
        for channel,keys in tracks.items():
            if channel not in result or not isinstance(keys,list) or not 2<=len(keys)<=128:raise ValueError('Known channel and bounded key list required')
            clean=[];previous=-1
            for key in keys:
                if not isinstance(key,list) or len(key)!=2:raise ValueError('Keys are [phase,value-vector]')
                t=number(key[0]);v=vector(key[1],len(result[channel]['base']))
                if not previous<t<=1 or t<0:raise ValueError('Strictly ordered normalized phases required')
                previous=t;clean.append([t,v])
            if clean[0][0]!=0 or clean[-1][0]!=1:raise ValueError('Every clip track includes phases 0 and 1')
            total+=len(clean)
            if total>16384:raise ValueError('Key work limit exceeded')
            prepared[name][channel]={'keys':clean,'curve':curve}
    ids=set()
    for inst in instances:
        identity=inst.get('id');name=inst.get('clip');start=inst.get('start');end=inst.get('end');amp=number(inst.get('amplitude',1))
        if not isinstance(identity,str) or not identity or identity in ids or name not in prepared or any(type(t) is not int for t in [start,end]) or not frames[0]<=start<end<=frames[1] or not 0<=amp<=2:raise ValueError('Unique instance, known clip, bounded placement/amplitude required')
        ids.add(identity)
        for channel,track in prepared[name].items():
            cfg=result[channel];base=cfg['base'];lo,hi=cfg['range'];keys=[[t,[b+(x-b)*amp for b,x in zip(base,v)]] for t,v in track['keys']]
            if any(not lo<=x<=hi for _,v in keys for x in v):raise ValueError('Placed clip exceeds channel range')
            cfg['segments'].append({'id':identity,'clip':name,'start':start,'end':end,'keys':keys,'curve':track['curve']})
    for cfg in result.values():
        cfg['segments'].sort(key=lambda row:row['start']);previous_end=frames[0];previous_value=cfg['base']
        for seg in cfg['segments']:
            if seg['start']<previous_end:raise ValueError('Overlapping writers on the same channel')
            if max(abs(a-b) for a,b in zip(seg['keys'][0][1],previous_value))>1e-6:raise ValueError('Clip entry jumps from preceding held value')
            previous_end=seg['end'];previous_value=seg['keys'][-1][1]
    if (frames[1]-frames[0]+1)*sum(len(c['base']) for c in result.values())>200000:raise ValueError('Sampling work limit exceeded')
    return {'frames':list(frames),'fps':fps,'channels':result,'instances':len(instances)}

def values(plan,frame):
    frame=number(frame)
    if not plan['frames'][0]<=frame<=plan['frames'][1]:raise ValueError('Frame outside compiled timeline')
    out={}
    for name,cfg in plan['channels'].items():
        value=list(cfg['base'])
        for seg in cfg['segments']:
            if frame<seg['start']:break
            value=sample(seg['keys'],min(1,(frame-seg['start'])/(seg['end']-seg['start'])),seg['curve'])
            if frame<=seg['end']:break
        out[name]=value
    return out
