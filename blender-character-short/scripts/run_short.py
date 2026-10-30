"""Rebuild a configured PMX short from raw asset in an independent directory.

Technical completion is distinct from rendering, reference/performance and reuse
acceptance. One sequential Blender process at a time; no UI/MCP session touched.
"""
import argparse,json,hashlib,subprocess,sys,time
from pathlib import Path

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def encoding_inputs(frames, count, fps, encoder):
    """Bind an ordered PNG sequence and the actual encoder contract, without I/O writes."""
    frames=Path(frames)
    if count<1 or fps<=0:raise ValueError('Encoding count and fps must be positive')
    return {'schema':1,'encoder_script_sha256':sha(encoder),
            'parameters':{'pattern':'frame_%04d.png','start':1,'count':int(count),'fps':float(fps),
                          'codec':'libx264','preset':'medium','crf':18,'pixel_format':'yuv420p',
                          'movflags':'+faststart','audio':'silent'},
            'frames':[{'frame':frame,'file':f'frame_{frame:04d}.png',
                       'sha256':sha(frames/f'frame_{frame:04d}.png')} for frame in range(1,count+1)]}

def require_current_video(video, sidecar, expected_inputs):
    """Read-only acceptance guard. Missing or stale evidence never authorizes overwrite."""
    video=Path(video);sidecar=Path(sidecar)
    try:record=json.loads(sidecar.read_text('utf-8'))
    except (OSError,ValueError) as exc:
        raise ValueError('Existing video has no readable frame signature; preserve it and choose a new version: '+str(video)) from exc
    if not isinstance(record,dict) or record.get('schema')!=1 or record.get('inputs')!=expected_inputs:
        raise ValueError('Existing video frame order/content or encoding signature changed; preserve it and choose a new version: '+str(video))
    if not video.is_file() or record.get('video_sha256')!=sha(video):
        raise ValueError('Existing video bytes differ from their frame signature: '+str(video))
    return record

def save_video_signature(video, sidecar, inputs):
    """Commit only after successful encoding and unchanged input revalidation."""
    sidecar=Path(sidecar);temporary=sidecar.with_name(sidecar.name+'.partial')
    record={'schema':1,'inputs':inputs,'video_sha256':sha(video)}
    temporary.write_text(json.dumps(record,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    temporary.replace(sidecar)
    return record

def main():
    p=argparse.ArgumentParser();p.add_argument('--blender',required=True);p.add_argument('--asset',required=True);p.add_argument('--mmd-source',required=True);p.add_argument('--dependencies',required=True);p.add_argument('--character',required=True);p.add_argument('--story',required=True);p.add_argument('--post-config',required=True);p.add_argument('--lut',required=True);p.add_argument('--output',required=True);p.add_argument('--variant',default='A');p.add_argument('--duration',type=float);p.add_argument('--width',type=int,default=640);p.add_argument('--height',type=int,default=360);p.add_argument('--samples',type=int,default=16);p.add_argument('--max-render-seconds',type=float);p.add_argument('--smaa-area');p.add_argument('--smaa-search');a=p.parse_args();here=Path(__file__).resolve().parent
    for key in ['blender','asset','character','story','post_config','lut']:
        path=Path(getattr(a,key))
        if not path.is_file():raise FileNotFoundError(key+' file does not exist: '+str(path))
    if bool(a.smaa_area)!=bool(a.smaa_search):raise ValueError('--smaa-area and --smaa-search must be supplied together')
    if a.smaa_area:
        for key in ['smaa_area','smaa_search']:
            if not Path(getattr(a,key)).is_file():raise FileNotFoundError(key+' file does not exist: '+str(getattr(a,key)))
        if not (here/'smaa_cpu.py').is_file():raise FileNotFoundError('SMAA module must be packaged beside run_short.py: '+str(here/'smaa_cpu.py'))
    if not (Path(a.mmd_source)/'mmd_tools/__init__.py').is_file():raise FileNotFoundError('mmd_tools source is missing its package: '+a.mmd_source)
    import numpy,PIL,imageio_ffmpeg
    if a.width%2 or a.height%2:raise ValueError('H.264 yuv420p delivery dimensions must be even')
    story=json.loads(Path(a.story).read_text('utf-8'));duration=a.duration or story['duration'];fps=story.get('fps',24);count=round(duration*fps)
    if a.variant not in story['camera_variants']:raise ValueError('Camera variant missing from story: '+a.variant)
    identity={'inputs':{k:sha(getattr(a,k)) for k in ['asset','character','story','post_config','lut']},'scripts':{x.name:sha(x) for x in here.glob('*.py')},'duration':duration,'fps':fps,'frames':count,'width':a.width,'height':a.height,'samples':a.samples,'variant':a.variant,'blender':str(Path(a.blender).resolve())};out=Path(a.output).resolve();manifest=out/'pipeline-inputs.json'
    if a.smaa_area:identity['inputs'].update({k:sha(getattr(a,k)) for k in ['smaa_area','smaa_search']})
    if manifest.exists() and json.loads(manifest.read_text('utf-8'))!=identity:raise ValueError('Output inputs or scripts changed. Preserve this version and choose a clean output directory.')
    out.mkdir(parents=True,exist_ok=True);manifest.write_text(json.dumps(identity,indent=2),encoding='utf-8');logdir=out/'logs';logdir.mkdir(exist_ok=True);events=[];start=time.monotonic()
    def run(stage,cmd):
        print('PIPELINE_START',stage,flush=True);t=time.monotonic()
        with (logdir/(stage+'.log')).open('w',encoding='utf-8') as log:r=subprocess.run(list(map(str,cmd)),stdout=log,stderr=subprocess.STDOUT)
        events.append({'stage':stage,'returncode':r.returncode,'seconds':time.monotonic()-t,'command':list(map(str,cmd))});(out/'pipeline-progress.json').write_text(json.dumps({'status':'running','events':events},indent=2),encoding='utf-8')
        if r.returncode:raise RuntimeError(stage+' failed; inspect '+str(logdir/(stage+'.log')))
        print('PIPELINE_DONE',stage,round(time.monotonic()-t,2),flush=True)
    def blend(script,args):return [a.blender,'--background','--factory-startup','--python-exit-code','1','--python',here/script,'--',*args]
    baseline=out/'import-baseline.blend';scene=out/'scene/scene.blend'
    try:
        if not baseline.exists():run('import',blend('import_pmx.py',['--asset',a.asset,'--addon-source',a.mmd_source,'--dependency-dir',a.dependencies,'--output',baseline,'--report',out/'import-report.json']))
        if not (out/'calibration.json').exists():run('inspect',blend('inspect_character.py',['--blend',baseline,'--output',out/'calibration.json']))
        if not scene.exists():run('build',blend('build_performance.py',['--baseline',baseline,'--character',a.character,'--story',a.story,'--output',out/'scene','--variant',a.variant,'--duration',str(duration),'--width',str(a.width),'--height',str(a.height),'--samples',str(a.samples)]))
        render_args=['--blend',scene,'--output',out/'raw','--width',str(a.width),'--height',str(a.height),'--samples',str(a.samples)]
        if a.max_render_seconds:render_args+=['--max-seconds',str(a.max_render_seconds)]
        run('render',blend('render_performance.py',render_args));state=json.loads((out/'raw/progress.json').read_text('utf-8'))
        if state['status']!='complete':
            (out/'pipeline-progress.json').write_text(json.dumps({'status':'paused','events':events,'resume':'Repeat the same command without --max-render-seconds. Existing validated raw frames are retained.'},indent=2),encoding='utf-8');print('PIPELINE_PAUSED',state['last_frame'],flush=True);return
        post_args=[sys.executable,here/'post_sequence.py','--raw',out/'raw','--output',out/'frames','--config',a.post_config,'--lut',a.lut,'--end',str(count)]
        if a.smaa_area:post_args+=['--smaa-area',a.smaa_area,'--smaa-search',a.smaa_search]
        run('composite',post_args)
        video=out/'preview.mp4';video_sidecar=out/'preview-frame-signature.json';encoder=here/'encode_video.py'
        video_inputs=encoding_inputs(out/'frames',count,fps,encoder)
        if video.exists():require_current_video(video,video_sidecar,video_inputs)
        else:
            run('encode',[sys.executable,encoder,'--frames',out/'frames','--pattern','frame_%04d.png','--output',video,'--count',str(count),'--fps',str(fps)])
            if encoding_inputs(out/'frames',count,fps,encoder)!=video_inputs:
                raise ValueError('PNG sequence or encoder changed during encoding; video is unbound and cannot be accepted')
            save_video_signature(video,video_sidecar,video_inputs)
        run('qa',[sys.executable,here/'video_qa.py',out/'preview.mp4','--output-dir',out/'qa','--expected-fps',str(fps),'--expected-frames',str(count),'--expected-duration',str(count/fps)])
        (out/'pipeline-progress.json').write_text(json.dumps({'status':'technical-complete','events':events,'elapsed':time.monotonic()-start,'visual_acceptance':'pending actual viewing','strict_render_acceptance':'not implied; inspect source implementation gaps','audio':'silent'},indent=2),encoding='utf-8');print('PIPELINE_COMPLETE',out/'preview.mp4',flush=True)
    except Exception as exc:
        (out/'pipeline-progress.json').write_text(json.dumps({'status':'failed','events':events,'error':str(exc)},indent=2),encoding='utf-8');raise

if __name__=='__main__':main()
