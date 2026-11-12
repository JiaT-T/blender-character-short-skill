"""Canonical local entry: doctor, baseline, look, render, encode for MMD/MMR."""
from pathlib import Path
import argparse,datetime,json,os,subprocess,sys,time,importlib.metadata
from production_contract import sha,digest,write_json,declared_file,producer_identity,require_baseline_binding,require_look_binding
SCRIPTS=Path(__file__).resolve().parent
def run_native(project,base,script,args,stage):
    runtime=project['runtime'];binary=(base/runtime['blender']).resolve()
    if not binary.is_file():raise FileNotFoundError('Reviewed Blender executable missing')
    stamp=str(time.time_ns());reports=(base/project['reports']).resolve();reports.mkdir(parents=True,exist_ok=True);log=reports/(stage+'-'+stamp+'.log');receipt=reports/(stage+'-'+stamp+'.job.json');lock=(base/project['execution_lock']).resolve()
    command=[str(binary),'--background','--disable-autoexec','--offline-mode','--threads',str(runtime.get('threads',1)),'--python-exit-code','1','--python-expr','import sys;sys.dont_write_bytecode=True','--python',str(SCRIPTS/script),'--',*map(str,args)]
    wrapper=[sys.executable,str(SCRIPTS/'execution_lock.py'),'--lock',str(lock),'--',*command];env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONUTF8='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
    data={'command':command,'wrapper':wrapper,'stage':stage,'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'starting','ui_used':False}
    write_json(receipt,data)
    flags=(subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS) if os.name=='nt' else 0
    with log.open('x',encoding='utf-8') as stream:
        child=subprocess.Popen(wrapper,stdout=stream,stderr=subprocess.STDOUT,env=env,creationflags=flags);data.update(status='running',wrapper_pid=child.pid);write_json(receipt,data)
        while True:
            try:code=child.wait(timeout=20);break
            except subprocess.TimeoutExpired:print('PROJECT_STAGE_RUNNING',stage,child.pid,flush=True)
    data.update(status='completed' if code==0 else 'failed_no_automatic_retry',returncode=code,finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat());write_json(receipt,data)
    if code!=0:raise RuntimeError(f'{stage} failed ({code}); inspect {log}; no automatic retry')
    print('PROJECT_STAGE_COMPLETE',stage,str(receipt),flush=True)
def baseline(project,base):
    p=(base/project['baseline_plan']).resolve();plan=json.loads(p.read_text('utf-8'));report=(p.parent/plan['report']).resolve()
    if report.exists():
        prior=json.loads(report.read_text('utf-8'))
        require_baseline_binding(plan,prior,p.parent)
        if not prior.get('accepted') or sha(prior['output'])!=prior['output_sha256'] or any(sha(SCRIPTS/k)!=v for k,v in prior.get('producer',{}).items()) or not prior.get('producer'):raise ValueError('Existing baseline/producer is unaccepted or changed; choose a new plan version')
    else:run_native(project,base,'mmd_baseline.py',['--plan',p,'--mode','prepare'],'baseline-prepare')
    run_native(project,base,'mmd_baseline.py',['--plan',p,'--mode','verify'],'baseline-fresh-verify')
    return report
def look(project,base):
    bpath=(base/project['baseline_plan']).resolve();bp=json.loads(bpath.read_text('utf-8'));b=json.loads((bpath.parent/bp['report']).read_text('utf-8'));verify=json.loads((bpath.parent/bp['verify_report']).read_text('utf-8'))
    require_baseline_binding(bp,b,bpath.parent)
    if verify.get('baseline_output_sha256')!=b['output_sha256'] or verify.get('plan_identity')!=b['plan_identity'] or verify.get('producer')!=b['producer']:raise ValueError('Fresh verification belongs to a different baseline/producer')
    if not verify['accepted'] or sha(b['output'])!=b['output_sha256']:raise ValueError('Verified baseline required')
    plan=dict(project['look']);plan['target']={'path':b['output'],'sha256':b['output_sha256']};p=base/('look-execution-'+project.get('id','production')+'.json')
    if p.exists() and json.loads(p.read_text('utf-8'))!=plan:raise ValueError('Look execution plan changed; use a new project version')
    write_json(p,plan);report=(base/plan['report']).resolve()
    if report.exists():
        r=json.loads(report.read_text('utf-8'))
        require_look_binding(plan,r,base)
        if not r.get('accepted') or sha(r['output'])!=r['output_sha256'] or not r.get('producer') or any(sha(SCRIPTS/k)!=v for k,v in r['producer'].items()):raise ValueError('Existing look artifact/producer changed or unaccepted')
    else:run_native(project,base,'saved_look.py',['--plan',p],'look-transfer')
def render(project,base,complete=False,max_seconds=1800):
    job=dict(project['render']);source=job.pop('source',None)
    if source is None:
        prior=json.loads((base/project['look']['report']).read_text('utf-8'));source={'path':prior['output'],'sha256':prior['output_sha256']}
    actual=declared_file(source,base);job.update(blend=actual['path'],source_sha256=actual['sha256']);path=base/('render-execution-'+project.get('id','production')+'.json');write_json(path,job);started=time.monotonic()
    while True:
        run_native(project,base,'saved_project_render.py',['--job',path],'saved-render')
        state=json.loads((base/job['output']/'progress.json').read_text('utf-8'))
        if state['complete'] or not complete:return state
        if time.monotonic()-started>=max_seconds:raise RuntimeError('Foreground render budget reached; matching frames retained')
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('stage',choices=['version','doctor','baseline','look','build','render','encode','tests','check-look','diagnostic','refine']);p.add_argument('--project',type=Path);p.add_argument('--complete',action='store_true');p.add_argument('--reference',action='store_true');p.add_argument('--max-seconds',type=float,default=1800);a=p.parse_args()
    if a.stage=='version':
        codes=producer_identity(SCRIPTS);print(json.dumps({'skill':str(SCRIPTS.parent),'version':json.loads((SCRIPTS.parent/'version.json').read_text('utf-8')),'script_count':len(codes),'producer_identity_sha256':digest(codes)},indent=2));return
    if a.project is None:p.error('--project required')
    file=a.project.resolve();base=file.parent;project=json.loads(file.read_text('utf-8'))
    if project.get('schema')!=1:raise ValueError('Project schema1 required')
    import re
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,48}',project.get('id','production')):raise ValueError('Project id must be a short filename-safe identifier')
    if a.stage not in ['doctor','build']:
        runtime=json.loads((base/project['reports']/'runtime.json').read_text('utf-8'))
        if not runtime['accepted'] or runtime.get('runtime_spec_sha256')!=digest(project['runtime']) or runtime.get('binary_sha256')!=sha((base/project['runtime']['blender']).resolve()):raise ValueError('Run doctor for this reviewed runtime before production')
    if a.stage in ['doctor','build']:
        report=base/project['reports']/'runtime.json';run_native(project,base,'runtime_probe.py',['--project',file,'--report',report],'runtime')
        import imageio_ffmpeg
        ff=imageio_ffmpeg.get_ffmpeg_exe();flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0;version=subprocess.run([ff,'-version'],capture_output=True,text=True,creationflags=flags,check=True).stdout.splitlines()[0]
        write_json(base/project['reports']/'version-report.json',{'skill':str(SCRIPTS.parent),'version':json.loads((SCRIPTS.parent/'version.json').read_text('utf-8')),'scripts':producer_identity(SCRIPTS),'host_python':sys.version,'dependencies':{k:importlib.metadata.version(k) for k in ['numpy','Pillow','imageio-ffmpeg']},'ffmpeg':{'version':version,'sha256':sha(ff)},'project_sha256':sha(file)})
    if a.stage in ['baseline','build']:baseline(project,base)
    if a.stage in ['look','build']:look(project,base)
    if a.stage=='render':render(project,base,a.complete,a.max_seconds)
    if a.stage=='encode':
        from encode_saved_project import encode
        print(json.dumps(encode(base/project['render']['output'],base/project['movie']),indent=2))
    if a.stage=='refine':
        plan=(base/project['refine_plan']).resolve()
        run_native(project,base,'refine_saved_project.py',['--plan',plan],'refine-saved-project')
    if a.stage=='tests':run_native(project,base,'native_validation.py',['--report',base/project['reports']/'native-tests.json'],'native-tests')
    if a.stage=='check-look':
        cfg=dict(project['look_checks'])
        if a.reference:cfg['source']=project['look']['donor'];cfg['output']=cfg['output']+'-reference'
        else:
            r=json.loads((base/project['look']['report']).read_text('utf-8'));cfg['source']={'path':r['output'],'sha256':r['output_sha256']}
        cfg['reference']=a.reference;p=base/('look-check-'+project.get('id','production')+('-reference' if a.reference else '-target')+'.json');write_json(p,cfg);run_native(project,base,'check_saved_look.py',['--plan',p],'look-cases-reference' if a.reference else 'look-cases-target')
    if a.stage=='diagnostic':
        prior=json.loads((base/project['look']['report']).read_text('utf-8'));checks=json.loads((base/project['look_checks']['output']/'checks.json').read_text('utf-8'))
        if checks.get('source',{}).get('sha256')!=prior['output_sha256'] or checks.get('profile')!=declared_file(project['look_checks']['profile'],base):raise ValueError('Look case checks do not match the current look/profile')
        if not prior['accepted'] or not checks['accepted_technical']:raise ValueError('Transferred look and completed technical case checks required')
        cfg=dict(project['diagnostic']);cfg.update(source={'path':prior['output'],'sha256':prior['output_sha256']},profile=project['look_checks']['profile']);p=base/('diagnostic-'+project.get('id','production')+'.json');write_json(p,cfg);run_native(project,base,'make_look_diagnostic.py',['--plan',p],'look-diagnostic-build')
if __name__=='__main__':main()
