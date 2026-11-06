"""Bounded two-action timeline and explicit external source/rights identities."""
from pathlib import Path
import hashlib,json

def validate(value):
    if not isinstance(value,dict) or set(value)!={'schema','fps','transition_frames','clips'} or type(value['schema']) is not int or value['schema']!=1:raise ValueError('Action sequence requires exact schema1 fields')
    if type(value['fps']) is not int or not 1<=value['fps']<=120:raise ValueError('Explicit integer fps required')
    overlap=value['transition_frames'];clips=value['clips']
    if type(overlap) is not int or not 2<=overlap<=48 or not isinstance(clips,list) or len(clips)!=2:raise ValueError('Exactly two clips and2..48transition frames required')
    counts=[]
    fields={'scene','sha256','frames','source','credit','license','modifications','restrictions'}
    for clip in clips:
        if not isinstance(clip,dict) or set(clip)!=fields:raise ValueError('Clip scene, identity, frame cut and full rights declaration required')
        if any(not isinstance(clip[k],str) or not clip[k].strip() for k in fields-{'frames'}):raise ValueError('Clip string fields must be nonempty')
        if len(clip['sha256'])!=64 or any(c not in '0123456789abcdef' for c in clip['sha256']):raise ValueError('Reviewed lowercase scene SHA256 required')
        if clip['scene'].startswith(('\\\\','//')) or Path(clip['scene']).suffix.lower()!='.blend':raise ValueError('Local scene path required')
        frames=clip['frames']
        if not isinstance(frames,list) or len(frames)!=2 or any(type(x) is not int for x in frames) or not 1<=frames[0]<frames[1]<=20000:raise ValueError('Clip cut needs integer first/last frames')
        count=frames[1]-frames[0]+1
        if not 2<=count<=240 or overlap>count//2:raise ValueError('Clip or overlap budget exceeded')
        counts.append(count)
    if sum(counts)-overlap>480:raise ValueError('Combined output exceeds480frames')
    return value

def load(path):
    path=Path(path)
    if path.stat().st_size>65536:raise ValueError('Action sequence plan exceeds64KB')
    def unique(pairs):
        out={}
        for k,v in pairs:
            if k in out:raise ValueError('Duplicate action sequence key')
            out[k]=v
        return out
    value=validate(json.loads(path.read_text(encoding='utf-8'),object_pairs_hook=unique))
    for clip in value['clips']:
        source=Path(clip['scene'])
        if not source.is_absolute():source=path.resolve().parent/source
        if not source.is_file() or source.stat().st_size>512*1024*1024:raise ValueError('Bounded existing source scene required')
        if sha(source)!=clip['sha256']:raise ValueError('Reviewed action scene changed')
        clip['scene']=str(source.resolve())
    return value

def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def timeline(plan):
    validate(plan)
    a,b=plan['clips'];na=a['frames'][1]-a['frames'][0]+1;nb=b['frames'][1]-b['frames'][0]+1;n=plan['transition_frames'];start=na-n+1
    result=[]
    for frame in range(1,na+nb-n+1):
        if frame<start:result.append({'frame':frame,'a':a['frames'][0]+frame-1,'b':None,'weight':0.})
        elif frame<=na:
            t=(frame-start)/(n-1);weight=t*t*t*(10+t*(-15+6*t))
            result.append({'frame':frame,'a':a['frames'][0]+frame-1,'b':b['frames'][0]+frame-start,'weight':weight})
        else:result.append({'frame':frame,'a':None,'b':b['frames'][0]+frame-start,'weight':1.})
    return result
