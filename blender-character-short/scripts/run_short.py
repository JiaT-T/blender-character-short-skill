"""Rebuild a configured PMX short from raw asset in an independent directory.

Technical completion is distinct from rendering, reference/performance and reuse
acceptance. One sequential Blender process at a time; no UI/MCP session touched.
"""
import argparse,json,hashlib,math,subprocess,sys,time
from pathlib import Path
from blueprint_fingerprint import collect_blueprint_inputs
from scene_asset_inputs import collect_scene_asset_inputs
from scene_tempo_plan import load_json as load_tempo_json,validate_plan as validate_tempo_plan
from body_motion_plan import load_plan as load_body_plan,BODY_PRODUCER_NAMES
from scene_feedback_plan import load_json as load_feedback_json,validate_plan as validate_feedback_plan

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
    p=argparse.ArgumentParser();p.add_argument('--blender',required=True);p.add_argument('--asset',required=True);p.add_argument('--mmd-source',required=True);p.add_argument('--dependencies',required=True);p.add_argument('--character',required=True);p.add_argument('--story',required=True);p.add_argument('--post-config',required=True);p.add_argument('--lut',required=True);p.add_argument('--output',required=True);p.add_argument('--variant',default='A');p.add_argument('--duration',type=float);p.add_argument('--width',type=int,default=640);p.add_argument('--height',type=int,default=360);p.add_argument('--samples',type=int,default=16);p.add_argument('--max-render-seconds',type=float);p.add_argument('--max-post-seconds',type=float,help='Budget newly composited frames; cache validation time is extra');p.add_argument('--smaa-area');p.add_argument('--smaa-search');p.add_argument('--hand-retime-plan',help='Optional bounded post-contact arm recovery time map; requires final protection and visual audits');p.add_argument('--gaze-plan',help='Optional explicit integer-frame real-object gaze bake, applied after build and before rendering');p.add_argument('--elbow-pole-plan',help='Optional wrist-preserving elbow pose correction; requires final sleeve/contact and visual checks');p.add_argument('--scene-tempo-plan',help='Optional whole-scene time map, after acting/gaze layers; requires final motion and visual checks');p.add_argument('--body-approach-plan',help='Optional reviewed full-body proportional approach/stance/stop before authored acting; requires stationary FK support and final visual checks')
    p.add_argument('--additional-elbow-pole-plan',action='append',default=[],help='Append an ordered wrist-preserving elbow stage after the primary plan; up to7 additional plans, all separately hashed and verified')
    p.add_argument('--scene-feedback-plan',help='Optional one-shot stable-placement material response on an external scene indicator; source-frame conditions, before scene tempo')
    a=p.parse_args();here=Path(__file__).resolve().parent
    if a.max_post_seconds is not None and (not math.isfinite(a.max_post_seconds) or a.max_post_seconds<=0):p.error('--max-post-seconds must be finite and positive')
    for key in ['blender','asset','character','story','post_config','lut']:
        path=Path(getattr(a,key))
        if not path.is_file():raise FileNotFoundError(key+' file does not exist: '+str(path))
    if a.hand_retime_plan and not Path(a.hand_retime_plan).is_file():raise FileNotFoundError('Hand retime plan missing: '+a.hand_retime_plan)
    if a.elbow_pole_plan and not Path(a.elbow_pole_plan).is_file():raise FileNotFoundError('Elbow pole plan missing: '+a.elbow_pole_plan)
    if a.additional_elbow_pole_plan and not a.elbow_pole_plan:raise ValueError('Additional elbow plans require a primary --elbow-pole-plan')
    if len(a.additional_elbow_pole_plan)>7:raise ValueError('At most8 total elbow stages are supported')
    elbow_plans=([a.elbow_pole_plan]+a.additional_elbow_pole_plan) if a.elbow_pole_plan else []
    if len({Path(path).resolve() for path in elbow_plans})!=len(elbow_plans):raise ValueError('Ordered elbow stages must use distinct plan paths')
    for path in a.additional_elbow_pole_plan:
        if not Path(path).is_file():raise FileNotFoundError('Additional elbow plan missing: '+path)
    if a.gaze_plan and not Path(a.gaze_plan).is_file():raise FileNotFoundError('Gaze plan missing: '+a.gaze_plan)
    if a.scene_tempo_plan and not Path(a.scene_tempo_plan).is_file():raise FileNotFoundError('Scene tempo plan missing: '+a.scene_tempo_plan)
    if a.body_approach_plan and not Path(a.body_approach_plan).is_file():raise FileNotFoundError('Body approach plan missing: '+a.body_approach_plan)
    if a.scene_feedback_plan and not Path(a.scene_feedback_plan).is_file():raise FileNotFoundError('Scene feedback plan missing: '+a.scene_feedback_plan)
    if bool(a.smaa_area)!=bool(a.smaa_search):raise ValueError('--smaa-area and --smaa-search must be supplied together')
    if a.smaa_area:
        for key in ['smaa_area','smaa_search']:
            if not Path(getattr(a,key)).is_file():raise FileNotFoundError(key+' file does not exist: '+str(getattr(a,key)))
        if not (here/'smaa_cpu.py').is_file():raise FileNotFoundError('SMAA module must be packaged beside run_short.py: '+str(here/'smaa_cpu.py'))
    if not (Path(a.mmd_source)/'mmd_tools/__init__.py').is_file():raise FileNotFoundError('mmd_tools source is missing its package: '+a.mmd_source)
    import numpy,PIL,imageio_ffmpeg
    if a.width%2 or a.height%2:raise ValueError('H.264 yuv420p delivery dimensions must be even')
    story=json.loads(Path(a.story).read_text('utf-8'));duration=a.duration or story['duration'];fps=story.get('fps',24);count=round(duration*fps);source_count=count
    if a.scene_tempo_plan:count=validate_tempo_plan(load_tempo_json(a.scene_tempo_plan),1,source_count)['output_last']
    if a.scene_feedback_plan:validate_feedback_plan(load_feedback_json(a.scene_feedback_plan),1,source_count)
    if a.variant not in story['camera_variants']:raise ValueError('Camera variant missing from story: '+a.variant)
    identity={'inputs':{k:sha(getattr(a,k)) for k in ['asset','character','story','post_config','lut']},'scripts':{x.name:sha(x) for x in here.glob('*.py')},'duration':duration,'fps':fps,'frames':count,'width':a.width,'height':a.height,'samples':a.samples,'variant':a.variant,'blender':str(Path(a.blender).resolve())};out=Path(a.output).resolve();manifest=out/'pipeline-inputs.json'
    if a.gaze_plan:identity['inputs']['gaze_plan']=sha(a.gaze_plan)
    if a.scene_feedback_plan:identity['inputs']['scene_feedback_plan']=sha(a.scene_feedback_plan)
    if a.body_approach_plan:
        body_plan,body_files=load_body_plan(a.body_approach_plan)
        if type(story.get('body_interaction_frame')) is not int or not 1<=story['body_interaction_frame']<=source_count:raise ValueError('Body route needs an explicit source-story body_interaction_frame')
        identity['inputs']['body_approach_plan']=sha(a.body_approach_plan)
        identity['body_motion_inputs']={key:{'path':str(path),'sha256':sha(path)} for key,path in body_files.items()}
    if a.scene_tempo_plan:
        identity['inputs']['scene_tempo_plan']=sha(a.scene_tempo_plan);identity['source_frames_before_tempo']=source_count
    if a.elbow_pole_plan:identity['inputs']['elbow_pole_plan']=sha(a.elbow_pole_plan)
    for index,path in enumerate(a.additional_elbow_pole_plan,1):identity['inputs']['additional_elbow_pole_plan_'+str(index)]=sha(path)
    if a.hand_retime_plan:identity['inputs']['hand_retime_plan']=sha(a.hand_retime_plan)
    if a.smaa_area:identity['inputs'].update({k:sha(getattr(a,k)) for k in ['smaa_area','smaa_search']})
    if story.get('source_motion_layers'):
        identity['source_motion_inputs']=[{key:{'path':str(Path(layer[key]).resolve()),'sha256':sha(layer[key])} for key in ('clip','skeleton')} for layer in story['source_motion_layers']]
    blueprint_inputs=collect_blueprint_inputs(a.character)
    if blueprint_inputs is not None:identity['blueprint_inputs']=blueprint_inputs
    scene_asset_inputs=collect_scene_asset_inputs(a.story)
    if scene_asset_inputs:identity['scene_asset_inputs']=scene_asset_inputs
    if manifest.exists() and json.loads(manifest.read_text('utf-8'))!=identity:raise ValueError('Output inputs or scripts changed. Preserve this version and choose a clean output directory.')
    out.mkdir(parents=True,exist_ok=True);manifest.write_text(json.dumps(identity,indent=2),encoding='utf-8');logdir=out/'logs';logdir.mkdir(exist_ok=True);events=[];start=time.monotonic()
    previous_progress=out/'pipeline-progress.json'
    if previous_progress.exists():
        attempt=1
        while (logdir/('progress-before-resume-%03d.json'%attempt)).exists():attempt+=1
        with (logdir/('progress-before-resume-%03d.json'%attempt)).open('xb') as copy:copy.write(previous_progress.read_bytes())
    def run(stage,cmd):
        print('PIPELINE_START',stage,flush=True);t=time.monotonic()
        path=logdir/(stage+'.log');attempt=2
        while path.exists():path=logdir/('%s.attempt%03d.log'%(stage,attempt));attempt+=1
        event={'stage':stage,'status':'starting','command':list(map(str,cmd)),'log':str(path),'started_unix_seconds':time.time()};events.append(event)
        with path.open('x',encoding='utf-8') as log:
            child=subprocess.Popen(list(map(str,cmd)),stdout=log,stderr=subprocess.STDOUT);event.update(status='running',pid=child.pid);(out/'pipeline-progress.json').write_text(json.dumps({'status':'running','events':events},indent=2),encoding='utf-8');code=child.wait()
        event.update(status='complete' if code==0 else 'failed',returncode=code,seconds=time.monotonic()-t);(out/'pipeline-progress.json').write_text(json.dumps({'status':'running','events':events},indent=2),encoding='utf-8')
        if code:raise RuntimeError(stage+' failed; inspect '+str(path))
        print('PIPELINE_DONE',stage,round(time.monotonic()-t,2),flush=True)
    def blend(script,args):return [a.blender,'--background','--factory-startup','--disable-autoexec','--python-exit-code','1','--python',here/script,'--',*args]
    baseline=out/'import-baseline.blend';scene=out/'scene/scene.blend'
    try:
        if not baseline.exists():run('import',blend('import_pmx.py',['--asset',a.asset,'--addon-source',a.mmd_source,'--dependency-dir',a.dependencies,'--output',baseline,'--report',out/'import-report.json']))
        if not (out/'calibration.json').exists():run('inspect',blend('inspect_character.py',['--blend',baseline,'--output',out/'calibration.json']))
        if not scene.exists():run('build',blend('build_performance.py',['--baseline',baseline,'--character',a.character,'--story',a.story,'--output',out/'scene','--variant',a.variant,'--duration',str(duration),'--width',str(a.width),'--height',str(a.height),'--samples',str(a.samples)]))
        if a.body_approach_plan:
            def require_body(path,status,expected):
                record=json.loads(path.read_text('utf-8'))
                producer={name:sha(here/name) for name in BODY_PRODUCER_NAMES}
                if record.get('schema')!=1 or record.get('status')!=status or record.get('producer_sha256')!=producer or any(record.get(key)!=value for key,value in expected.items()):raise ValueError('Body stage evidence stale/incomplete; preserve output and use a new version: '+str(path))
                return record
            shared={'character_sha256':sha(a.character),'plan_sha256':sha(a.body_approach_plan),'runtime_sha256':sha(here/'body_motion_runtime.py'),'validator_sha256':sha(here/'body_motion_plan.py')}
            fit=out/'body-fit/scene.blend';fit_report=out/'body-fit/fit-report.json'
            if not fit.exists():run('body-fit',blend('fit_body_motion.py',['--baseline',baseline,'--character',a.character,'--plan',a.body_approach_plan,'--output',fit,'--report',fit_report]))
            require_body(fit_report,'proportional-body-FK-fitted-await-travel-contact-and-visuals',{**shared,'input_scene_sha256':sha(baseline),'output_scene_sha256':sha(fit),'writer_sha256':sha(here/'fit_body_motion.py')})
            travel=out/'body-travel/scene.blend';travel_report=out/'body-travel/travel-report.json'
            if not travel.exists():run('body-travel',blend('travel_body_motion.py',['--blend',fit,'--fit-report',fit_report,'--character',a.character,'--plan',a.body_approach_plan,'--output',travel,'--report',travel_report]))
            require_body(travel_report,'measured-travel-and-signed-grounding-await-material-contacts',{**shared,'input_scene_sha256':sha(fit),'fit_report_sha256':sha(fit_report),'output_scene_sha256':sha(travel),'writer_sha256':sha(here/'travel_body_motion.py')})
            planted=out/'body-plant/scene.blend';plant_report=out/'body-plant/plant-report.json'
            if not planted.exists():run('body-plant',blend('plant_body_motion.py',['--blend',travel,'--travel-report',travel_report,'--character',a.character,'--plan',a.body_approach_plan,'--output',planted,'--report',plant_report]))
            require_body(plant_report,'material-stance-baked-await-stop-and-complete-visuals',{**shared,'input_scene_sha256':sha(travel),'travel_report_sha256':sha(travel_report),'output_scene_sha256':sha(planted),'writer_sha256':sha(here/'plant_body_motion.py')})
            built=scene;scene=out/'body-compose/scene.blend';compose_report=out/'body-compose/compose-report.json'
            if not scene.exists():run('body-compose',blend('compose_body_approach.py',['--blend',built,'--gait',planted,'--plant-report',plant_report,'--character',a.character,'--story',a.story,'--plan',a.body_approach_plan,'--output',scene,'--report',compose_report]))
            require_body(compose_report,'body-approach-composed-await-final-gaze-clearance-and-visuals',{**shared,'input_scene_sha256':sha(built),'gait_scene_sha256':sha(planted),'plant_report_sha256':sha(plant_report),'story_sha256':sha(a.story),'output_scene_sha256':sha(scene),'writer_sha256':sha(here/'compose_body_approach.py'),'pose_helper_sha256':sha(here/'body_approach_pose.py')})
        if a.hand_retime_plan:
            built=scene;scene=out/'hand-retime/scene.blend';retime_report=out/'hand-retime/bake-report.json'
            if not scene.exists():run('hand-retime',blend('bake_hand_retime.py',['--blend',built,'--character',a.character,'--build-report',out/'scene/build-report.json','--plan',a.hand_retime_plan,'--output',scene,'--report',retime_report]))
            saved=json.loads(retime_report.read_text('utf-8'))
            expected={'input_scene_sha256':sha(built),'output_scene_sha256':sha(scene),'character_sha256':sha(a.character),'plan_sha256':sha(a.hand_retime_plan),'writer_sha256':sha(here/'bake_hand_retime.py'),'base_solver_sha256':sha(here/'build_performance.py'),'plan_validator_sha256':sha(here/'hand_retime_plan.py'),'build_report_sha256':sha(out/'scene/build-report.json')}
            if saved.get('schema')!=1 or saved.get('status')!='new-scene-saved-retimed-arm-await-protection-and-visual-audits' or any(saved.get(k)!=v for k,v in expected.items()):raise ValueError('Hand retime evidence stale or incomplete; preserve output and use a new version')
        for index,elbow_plan in enumerate(elbow_plans):
            stage='elbow-pole' if index==0 else 'elbow-pole-'+str(index+1)
            built=scene;scene=out/stage/'scene.blend';elbow_report=out/stage/'bake-report.json'
            if not scene.exists():run(stage,blend('bake_elbow_poles.py',['--blend',built,'--character',a.character,'--plan',elbow_plan,'--output',scene,'--report',elbow_report]))
            saved=json.loads(elbow_report.read_text('utf-8'))
            expected={'input_scene_sha256':sha(built),'output_scene_sha256':sha(scene),'character_sha256':sha(a.character),'plan_sha256':sha(elbow_plan),'writer_sha256':sha(here/'bake_elbow_poles.py'),'base_solver_sha256':sha(here/'build_performance.py'),'plan_validator_sha256':sha(here/'elbow_pole_plan.py')}
            if saved.get('schema')!=1 or saved.get('status')!='new-scene-saved-wrist-preserved-await-clearance-and-visual-audits' or any(saved.get(k)!=v for k,v in expected.items()):raise ValueError('Elbow pole evidence stale or incomplete; preserve output and use a new version')
        if a.gaze_plan:
            built=scene;scene=out/'gaze/scene.blend';gaze_report=out/'gaze/bake-report.json'
            if not scene.exists():run('gaze',blend('bake_gaze_targets.py',['--blend',built,'--character',a.character,'--plan',a.gaze_plan,'--output',scene,'--report',gaze_report]))
            saved=json.loads(gaze_report.read_text('utf-8'))
            expected={'input_scene_sha256':sha(built),'output_scene_sha256':sha(scene),'character_sha256':sha(a.character),'plan_sha256':sha(a.gaze_plan),'writer_sha256':sha(here/'bake_gaze_targets.py'),'plan_validator_sha256':sha(here/'gaze_plan.py')}
            if saved.get('schema')!=1 or saved.get('status')!='new-scene-saved-control-only-await-final-audit' or any(saved.get(k)!=v for k,v in expected.items()):raise ValueError('Gaze bake evidence stale or incomplete; preserve output and use a new version')
        if a.scene_feedback_plan:
            built=scene;scene=out/'scene-feedback/scene.blend';feedback_report=out/'scene-feedback/bake-report.json'
            if not scene.exists():run('scene-feedback',blend('bake_scene_feedback.py',['--blend',built,'--character',a.character,'--plan',a.scene_feedback_plan,'--output',scene,'--report',feedback_report]))
            saved=json.loads(feedback_report.read_text('utf-8'));expected={'input_scene_sha256':sha(built),'output_scene_sha256':sha(scene),'character_sha256':sha(a.character),'plan_sha256':sha(a.scene_feedback_plan),'writer_sha256':sha(here/'bake_scene_feedback.py')}
            dependencies={name:sha(here/name) for name in ('scene_feedback_plan.py','bake_scene_tempo.py','scene_tempo_plan.py','body_motion_runtime.py','elbow_pole_plan.py')}
            if saved.get('schema')!=1 or saved.get('status')!='placement-response-baked-await-output-and-visual-checks' or saved.get('dependency_sha256')!=dependencies or any(saved.get(k)!=v for k,v in expected.items()):raise ValueError('Scene feedback evidence stale or incomplete; preserve output and use a new version')
        if a.scene_tempo_plan:
            built=scene;scene=out/'scene-tempo/scene.blend';tempo_report=out/'scene-tempo/bake-report.json'
            if not scene.exists():run('scene-tempo',blend('bake_scene_tempo.py',['--blend',built,'--plan',a.scene_tempo_plan,'--output',scene,'--report',tempo_report]))
            saved=json.loads(tempo_report.read_text('utf-8'))
            expected={'input_scene_sha256':sha(built),'output_scene_sha256':sha(scene),'plan_sha256':sha(a.scene_tempo_plan),'writer_sha256':sha(here/'bake_scene_tempo.py'),'plan_validator_sha256':sha(here/'scene_tempo_plan.py'),'json_validator_sha256':sha(here/'elbow_pole_plan.py')}
            if saved.get('schema')!=1 or saved.get('status')!='new-scene-saved-mapped-states-verified-await-motion-and-visual-audits' or saved.get('plan',{}).get('output_last')!=count or any(saved.get(k)!=v for k,v in expected.items()):raise ValueError('Scene tempo evidence stale or incomplete; preserve output and use a new version')
        render_args=['--blend',scene,'--output',out/'raw','--width',str(a.width),'--height',str(a.height),'--samples',str(a.samples)]
        if a.max_render_seconds:render_args+=['--max-seconds',str(a.max_render_seconds)]
        run('render',blend('render_performance.py',render_args));state=json.loads((out/'raw/progress.json').read_text('utf-8'))
        if state['status']!='complete':
            (out/'pipeline-progress.json').write_text(json.dumps({'status':'paused','events':events,'resume':'Repeat the same command without --max-render-seconds. Existing validated raw frames are retained.'},indent=2),encoding='utf-8');print('PIPELINE_PAUSED',state['last_frame'],flush=True);return
        post_args=[sys.executable,here/'post_sequence.py','--raw',out/'raw','--output',out/'frames','--config',a.post_config,'--lut',a.lut,'--end',str(count)]
        if a.smaa_area:post_args+=['--smaa-area',a.smaa_area,'--smaa-search',a.smaa_search]
        if a.max_post_seconds is not None:post_args+=['--max-new-seconds',str(a.max_post_seconds)]
        run('composite',post_args)
        post_state=json.loads((out/'frames/post-progress.json').read_text('utf-8'))
        if post_state['status']=='budget-paused':
            (out/'pipeline-progress.json').write_text(json.dumps({'status':'paused','paused_stage':'composite','events':events,'last_validated_post_frame':post_state['last_frame'],'resume':'Repeat with the same inputs and producer. The post execution budget may change; no encode is accepted before complete checkpoint validation.'},indent=2),'utf-8')
            print('PIPELINE_PAUSED_POST',post_state['last_frame'],flush=True);return
        if post_state['status']!='complete':raise ValueError('Post sequence did not complete; no encoding authorized')
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
