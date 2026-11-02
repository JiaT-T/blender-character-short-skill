"""Exercise real SMAA history across graceful post pauses using supplied raw frames."""
import argparse,hashlib,json,pathlib,shutil,subprocess,sys
import numpy as np

def main():
    p=argparse.ArgumentParser();p.add_argument('--raw-source',required=True,type=pathlib.Path);p.add_argument('--source-frames',default='126,169,301');p.add_argument('--config',required=True,type=pathlib.Path);p.add_argument('--lut',required=True,type=pathlib.Path);p.add_argument('--smaa-area',required=True,type=pathlib.Path);p.add_argument('--smaa-search',required=True,type=pathlib.Path);p.add_argument('--reference-post',required=True,type=pathlib.Path);p.add_argument('--output',required=True,type=pathlib.Path);a=p.parse_args()
    out=a.output.resolve();out.mkdir(exist_ok=False);frames=list(map(int,a.source_frames.split(',')))
    if len(frames)<3 or min(frames)<1:raise ValueError('Supply at least3real positive source frame numbers')
    raw=out/'derived-raw-test-sequence';raw.mkdir();sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest();sources=[]
    for index,frame in enumerate(frames,1):
        source=a.raw_source/f'frame_{frame:04d}.npz';dest=raw/f'frame_{index:04d}.npz';shutil.copy2(source,dest);sources.append({'test_frame':index,'source_frame':frame,'source_npz_sha256':sha(source)})
    (raw/'render-job.json').write_text(json.dumps({'mode':'derived-test-sequence-not-a-new-render','original_render_job_sha256':sha(a.raw_source/'render-job.json'),'sources':sources},indent=2),'utf-8')
    script=pathlib.Path(__file__).resolve().with_name('post_sequence.py');count=len(frames)
    def run(label,target,producer,budget=None,expected=0):
        cmd=[sys.executable,str(producer),'--raw',str(raw),'--output',str(target),'--start','1','--end',str(count),'--config',str(a.config),'--lut',str(a.lut),'--smaa-area',str(a.smaa_area),'--smaa-search',str(a.smaa_search)]
        if budget is not None:cmd+=['--max-new-seconds',str(budget)]
        with (out/(label+'.log')).open('w',encoding='utf-8') as log:code=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT).returncode
        assert code==expected,(label,code,expected)
        return json.loads((target/'post-progress.json').read_text('utf-8')) if expected==0 else None
    reference=out/'reference';default=out/'new-default';bounded=out/'bounded';switched=out/'budget-then-default'
    run('reference',reference,a.reference_post);run('new-default',default,script)
    states=[];previous={};identity=None
    for attempt in range(count):
        state=run('bounded-'+str(attempt+1),bounded,script,.000001)
        assert all(sha(bounded/name)==value for name,value in previous.items()),'Previously committed PNG changed'
        new=[r['frame'] for r in state['records'] if r['status']=='composited'];assert new==[attempt+1],new
        if identity is not None:assert state['job_sha256']==identity
        identity=state['job_sha256'];status=state['status'];states.append({'status':status,'new_frames':new,'validated_prefix':sum(r['status']=='existing-validated' for r in state['records'])})
        assert status==('complete' if attempt==count-1 else 'budget-paused')
        previous={f.name:sha(f) for f in bounded.glob('frame_*.png')}
    first=run('switch-paused',switched,script,.000001);assert first['status']=='budget-paused';first_png=sha(switched/'frame_0001.png')
    last=run('switch-complete',switched,script);assert last['status']=='complete' and last['job_sha256']==first['job_sha256'] and sha(switched/'frame_0001.png')==first_png
    for frame in range(1,count+1):
        name=f'frame_{frame:04d}.png';expected=sha(reference/name)
        for folder in [default,bounded,switched]:
            assert sha(folder/name)==expected,'Pixel bytes differ: '+str(folder/name)
            with np.load(reference/'edges'/f'frame_{frame:04d}.npz') as x,np.load(folder/'edges'/f'frame_{frame:04d}.npz') as y:assert np.array_equal(x['edges'],y['edges']),'SMAA history differs'
    invalid=out/'invalid-nan';run('invalid-nan',invalid,script,'nan',2);assert not invalid.exists(),'Invalid budget wrote output'
    result={'status':'pass','source_frames':sources,'frame_count':count,'bounded_calls':states,'default_png_bytes_match_reference':True,'bounded_png_bytes_match_reference':True,'budget_omission_resume_png_bytes_match_reference':True,'SMAA_edge_arrays_exact_all_cases':True,
            'budget_not_part_of_image_job_identity':True,'cached_validation_does_not_starve_new_work':True,'nan_rejected_before_output':True,'reference_post_sha256':sha(a.reference_post),'new_post_sha256':sha(script),
            'scope':'Actual CPU sourcepost/SMAA PNG and edge history on a derived changing-pose/camera raw sequence. Controlled graceful budget pauses, not forced process death, GPU website equivalence or continuous viewing.'}
    (out/'result.json').write_text(json.dumps(result,indent=2),'utf-8');print('POST_BUDGET_IMAGE_AND_HISTORY_VERIFIED',count,'frames',flush=True)

if __name__=='__main__':main()
