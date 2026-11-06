"""Validate an explicit, licensed BVH sampling plan without Blender or network."""
import hashlib, json, math
from pathlib import Path

def load_plan(path, source):
    def unique(pairs):
        out={}
        for k,v in pairs:
            if k in out:raise ValueError('Duplicate BVH plan key: '+k)
            out[k]=v
        return out
    raw=Path(path).read_bytes()
    if len(raw)>65536:raise ValueError('BVH plan exceeds64KB')
    plan=json.loads(raw.decode('utf-8'),object_pairs_hook=unique,
                    parse_constant=lambda x:(_ for _ in ()).throw(ValueError('Nonfinite plan number')))
    required={'schema','source_sha256','frames','fps','scale','axes','reference','rights'}
    if not isinstance(plan,dict) or set(plan)!=required or type(plan['schema']) is not int or plan['schema']!=1:raise ValueError('BVH sampling plan requires exact schema1 fields')
    digest=plan['source_sha256']
    if not isinstance(digest,str) or len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest):raise ValueError('Reviewed lowercase source SHA256 required')
    source=Path(source)
    if source.stat().st_size>16*1024*1024:raise ValueError('BVH source exceeds16MB')
    if hashlib.sha256(source.read_bytes()).hexdigest()!=digest:raise ValueError('BVH source changed after review')
    frames=plan['frames']
    if not isinstance(frames,list) or len(frames)!=3 or any(type(x) is not int for x in frames):raise ValueError('Frames require integer first,last,step')
    a,b,step=frames
    if not 1<=a<=b<=20000 or not 1<=step<=8 or not 2<=len(range(a,b+1,step))<=240:raise ValueError('BVH sample frame budget exceeded')
    if type(plan['fps']) is not int or not 1<=plan['fps']<=120:raise ValueError('FPS requires integer1..120')
    scale=plan['scale']
    if type(scale) not in [int,float] or not math.isfinite(scale) or not .0001<=scale<=1000:raise ValueError('Explicit bounded finite BVH scale required')
    axes=plan['axes']
    if not isinstance(axes,dict) or set(axes)!={'forward','up'} or any(v not in ['X','Y','Z','-X','-Y','-Z'] for v in axes.values()) or axes['forward'][-1]==axes['up'][-1]:raise ValueError('BVH forward/up axes must be distinct signed axes')
    reference=plan['reference']
    if not isinstance(reference,dict) or reference.get('mode') not in ['bind-rebased','first-frame','captured-horizontal']:raise ValueError('Explicit supported source calibration mode required')
    fields={'mode','pelvis','frame'} if reference['mode']=='captured-horizontal' else {'mode','pelvis'}
    if set(reference)!=fields or not isinstance(reference['pelvis'],str) or not 1<=len(reference['pelvis'])<=128:raise ValueError('Exact source calibration fields and pelvis bone required')
    if reference['mode']=='captured-horizontal' and (type(reference['frame']) is not int or not 1<=reference['frame']<=20000):raise ValueError('Reviewed integer captured calibration frame required')
    rights=plan['rights'];required_rights={'source','credit','license','modifications','restrictions'}
    if not isinstance(rights,dict) or set(rights)!=required_rights or any(not isinstance(v,str) or not v.strip() for v in rights.values()):raise ValueError('Reviewed source, attribution, license, changes and restrictions required')
    return plan

def probe_bvh(source, plan):
    """Bound importer work and reject malformed/nonfinite text before native use."""
    raw=Path(source).read_text(encoding='ascii');lines=raw.splitlines()
    try:marker=lines.index('MOTION')
    except ValueError as e:raise ValueError('BVH lacks MOTION section') from e
    if not lines or lines[0].strip()!='HIERARCHY':raise ValueError('Expected BVH hierarchy')
    if sum(l.strip().startswith('ROOT ') for l in lines[:marker])!=1:raise ValueError('Exactly one BVH root required')
    bones=sum(l.strip().startswith(('ROOT ','JOINT ')) for l in lines[:marker])
    channels=sum(int(l.split()[1]) for l in lines[:marker] if l.strip().startswith('CHANNELS '))
    try:
        count=int(lines[marker+1].split(':')[1]);dt=float(lines[marker+2].split(':')[1])
    except (ValueError,IndexError) as e:raise ValueError('Malformed BVH timing header') from e
    if not 2<=bones<=128 or not 1<=count<=20000 or count*bones>500000 or not 1<=channels<=1024 or count*channels>1000000:raise ValueError('BVH import work budget exceeded')
    if not math.isfinite(dt) or dt<=0 or abs(dt*plan['frames'][2]-1/plan['fps'])>1e-6:raise ValueError('Requested sample cadence would change source tempo')
    rows=[l for l in lines[marker+3:] if l.strip()]
    if len(rows)!=count or plan['frames'][1]>count:raise ValueError('BVH declared/sample frame count mismatch')
    if plan['reference']['mode']=='captured-horizontal' and plan['reference']['frame']>count:raise ValueError('Captured calibration frame exceeds source file')
    for line in rows:
        values=[float(x) for x in line.split()]
        if len(values)!=channels or not all(math.isfinite(v) and abs(v)<1e8 for v in values):raise ValueError('Invalid or unbounded BVH channel value')
    return {'raw_frames':count,'bones':bones,'channels':channels,'frame_time':dt}
