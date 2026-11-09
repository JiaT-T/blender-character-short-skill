"""Identity and frame receipts for the saved-project production route (no bpy)."""
from pathlib import Path
from contextlib import contextmanager
import hashlib,json,math,os,struct
SCHEMA='saved-project-render-v45-1'
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)
def digest(value):return hashlib.sha256(canonical(value).encode()).hexdigest()
def write_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_name(path.name+'.tmp');tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n','utf-8');tmp.replace(path)
def fps_value(numerator,base):
    if type(numerator) is not int or numerator<=0 or isinstance(base,bool) or not isinstance(base,(int,float)) or not math.isfinite(base) or base<=0:raise ValueError('Positive saved fps/fps_base required')
    value=numerator/base
    if not math.isfinite(value):raise ValueError('Nonfinite frame rate')
    return value
def declared_file(row,base):
    p=(Path(base)/row['path']).resolve()
    if not p.is_file() or p.is_symlink():raise ValueError('Missing/linked declared input: '+str(p))
    actual=sha(p)
    if actual!=row['sha256']:raise ValueError('Declared input hash mismatch: '+str(p))
    return {'path':str(p),'sha256':actual,'bytes':p.stat().st_size}
def producer_identity(scripts):return {p.name:sha(p) for p in sorted(Path(scripts).glob('*.py'))}

def baseline_identity(plan,base):
    mode=plan['mode']
    if mode not in ['provided','generate']:raise ValueError('Unknown baseline mode')
    fps=plan.get('fps')
    if fps is not None and (type(fps) is not int or not 1<=fps<=120):raise ValueError('Explicit baseline fps must be an integer from 1 to 120')
    identity={'mode':mode,'source':declared_file(plan['source'],base),'profile':declared_file(plan['profile'],base),'output':str((Path(base)/plan['output']).resolve()),'fps':fps}
    if mode=='generate':identity.update(mapping=declared_file(plan['mapping'],base),generation_guidance_acknowledged=plan.get('generation_guidance_acknowledged'))
    return identity

def require_baseline_binding(plan,prior,base):
    if prior.get('plan_identity')!=baseline_identity(plan,base):raise ValueError('Baseline plan/input identity changed or legacy receipt; choose a new baseline version')

def require_look_binding(plan,prior,base):
    for key,record in [('target','target_input'),('donor','look_donor'),('profile','profile')]:
        if prior.get(record)!=declared_file(plan[key],base):raise ValueError('Saved look input identity changed; choose a new look version')
    if prior.get('output')!=str((Path(base)/plan['output']).resolve()):raise ValueError('Saved look output identity changed')

def require_saved_producer(signature,scripts):
    scripts=Path(scripts)
    if signature['producer']!=producer_identity(scripts):raise ValueError('Producer changed since rendering')
    if sha(scripts.parent/'version.json')!=signature['version_sha256']:raise ValueError('Skill version changed since rendering')
def png_receipt(path,width,height):
    path=Path(path)
    with path.open('rb') as stream:header=stream.read(24)
    if len(header)!=24 or header[:8]!=b'\x89PNG\r\n\x1a\n' or struct.unpack('>II',header[16:24])!=(width,height):raise ValueError('Wrong PNG size/header: '+str(path))
    return {'file':path.name,'bytes':path.stat().st_size,'sha256':sha(path)}
def validate_frames(root,signature,first,last):
    root=Path(root);progress=root/'progress.json';expected=digest(signature)
    if not progress.exists():
        if any(root.glob('*.png')):raise ValueError('Unreceipted PNGs exist; refuse adopting size-only cache')
        return {}
    state=json.loads(progress.read_text('utf-8'))
    if state.get('schema')!=SCHEMA or state.get('signature_sha256')!=expected or state.get('signature')!=signature:raise ValueError('Render identity changed; choose a new output directory')
    done={}
    for row in state['frames']:
        frame=row['frame']
        if type(frame) is not int or not first<=frame<=last or frame in done or row['file']!=f'{frame:04d}.png':raise ValueError('Invalid/duplicate frame receipt')
        actual=png_receipt(root/row['file'],signature['width'],signature['height'])
        if any(actual[k]!=row[k] for k in ['file','bytes','sha256']):raise ValueError('Rendered frame bytes changed: '+row['file'])
        done[frame]=row
    recorded={r['file'] for r in done.values()}
    if {p.name for p in root.glob('*.png')}!=recorded:raise ValueError('Unreceipted frame/partial PNG exists; inspect separately')
    if state.get('complete') and (len(done)!=last-first+1 or state.get('inputs_verified') is not True):raise ValueError('False completion state')
    return done
@contextmanager
def output_lock(root):
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    with (root/'writer.lock').open('a+b') as stream:
        stream.seek(0,2)
        if stream.tell()==0:stream.write(b'0');stream.flush()
        stream.seek(0)
        if os.name=='nt':
            import msvcrt
            try:msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
            except OSError as e:raise RuntimeError('Output already has a writer') from e
        else:
            import fcntl
            fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:yield
        finally:
            stream.seek(0)
            if os.name=='nt':msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)
            else:fcntl.flock(stream,fcntl.LOCK_UN)
