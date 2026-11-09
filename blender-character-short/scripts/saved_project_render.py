"""Render saved native compositing and actual fps with identity-bound resumes."""
from pathlib import Path
import argparse,datetime,json,math,sys,time
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
from production_contract import SCHEMA,sha,digest,write_json,declared_file,producer_identity,png_receipt,validate_frames,output_lock,fps_value
from render_engine_policy import require_engine,apply_sampling
from render_device_policy import prepare_render,render_with_policy
from production_defaults import saved_render_dimensions
def render_job(job,base):
    base=Path(base);source=declared_file({'path':job['blend'],'sha256':job['source_sha256']},base);path=Path(source['path']);root=(base/job['output']).resolve()
    if root==path or path.is_relative_to(root):raise ValueError('Separate render output required')
    if job.get('post_mode')!='saved-native':raise ValueError('Explicit saved-native compositor route required; no external second grading')
    bpy.ops.wm.open_mainfile(filepath=str(path),load_ui=False,use_scripts=False);scene=bpy.context.scene
    engine=require_engine(scene,job.get('engine'));fps=fps_value(scene.render.fps,scene.render.fps_base)
    if 'fps' in job and not math.isclose(float(job['fps']),fps,rel_tol=0,abs_tol=1e-7):raise ValueError('Requested fps differs from saved scene; retime a new scene separately')
    first,last=job['start'],job['end'];width,height=saved_render_dimensions(job);samples=job['samples']
    if any(type(x) is not int for x in [first,last,width,height,samples]) or not scene.frame_start<=first<=last<=scene.frame_end or not 1<=width<=8192 or not 1<=height<=8192 or not 1<=samples<=4096:raise ValueError('Invalid range, resolution or samples')
    batch=job.get('batch_frames',last-first+1);budget=job.get('budget_seconds',360)
    if type(batch) is not int or batch<1 or isinstance(budget,bool) or not isinstance(budget,(int,float)) or not math.isfinite(budget) or budget<=0:raise ValueError('Finite positive frame/time budgets required')
    if bpy.data.libraries:raise ValueError('Linked libraries require a separately packed local production scene')
    unpacked=[im.name for im in bpy.data.images if im.source=='FILE' and not im.packed_file and not len(im.packed_files)]
    if unpacked:raise ValueError('Pack external images before production: '+repr(unpacked))
    if not scene.camera:raise ValueError('Saved active camera required')
    world=scene.rigidbody_world
    if bpy.data.cache_files or (world and (getattr(world.point_cache,'use_disk_cache',False) or getattr(world.point_cache,'use_external',False))):raise ValueError('External simulation caches must be frozen separately; this route accepts embedded caches only')
    if job.get('require_cache') and (not world or not world.point_cache.is_baked or world.point_cache.frame_start>first or world.point_cache.frame_end<last):raise ValueError('Reviewed baked physics cache must cover display range')
    dependencies=[declared_file(r,base) for r in job.get('dependencies',[])]
    signature={'source':source,'dependencies':dependencies,'producer':producer_identity(Path(__file__).parent),'version_sha256':sha(Path(__file__).parents[1]/'version.json'),'blender_binary_sha256':sha(bpy.app.binary_path),'blender_version':bpy.app.version_string,'engine':engine,'width':width,'height':height,'samples':samples,'fps_numerator':scene.render.fps,'fps_base':scene.render.fps_base,'effective_fps':fps,'range':[first,last],'post_mode':'saved-native','use_compositing':scene.render.use_compositing,'compositor_device':getattr(scene.render,'compositor_device',None),'camera':scene.camera.name,'cuts':[[m.frame,m.camera.name if m.camera else None] for m in scene.timeline_markers],'require_cache':bool(job.get('require_cache'))}
    with output_lock(root):
        done=validate_frames(root,signature,first,last);initial=len(done)
        if initial==last-first+1:
            existing=json.loads((root/'progress.json').read_text('utf-8'));existing.update(complete=True,inputs_verified=True);write_json(root/'progress.json',existing);return existing
        prepare_render(scene);apply_sampling(scene,samples);scene.render.resolution_x=width;scene.render.resolution_y=height;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGB';scene.render.image_settings.color_depth='8';scene.render.use_file_extension=True
        started=time.monotonic();new=0;device=None;verified=False
        def state():return {'schema':SCHEMA,'signature':signature,'signature_sha256':digest(signature),'frames':[done[f] for f in sorted(done)],'complete':len(done)==last-first+1 and verified,'inputs_verified':verified,'fps':fps,'actual_device':device,'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'normal_speed_continuous_viewing':False}
        for frame in range(first,last+1):
            if frame in done:continue
            scene.frame_set(frame);cuts=[m for m in scene.timeline_markers if m.camera and m.frame<=frame]
            if cuts:scene.camera=max(cuts,key=lambda m:m.frame).camera
            target=root/f'{frame:04d}.png';temporary=root/f'{frame:04d}.partial.png'
            if target.exists() or temporary.exists():raise ValueError('Refuse overwrite/adopt unreceipted frame')
            scene.render.filepath=str(temporary);device=prepare_render(scene);render_with_policy(write_still=True);device=dict(device,render_completed=True)
            receipt=png_receipt(temporary,width,height);temporary.replace(target);receipt['file']=target.name;receipt.update(frame=frame,camera=scene.camera.name,device=device['devices']);done[frame]=receipt
            write_json(root/'progress.json',state());new+=1;print('SAVED_PROJECT_FRAME',frame,len(done),last-first+1,flush=True)
            if new>=batch or time.monotonic()-started>=budget:break
        if sha(path)!=source['sha256'] or any(sha(r['path'])!=r['sha256'] for r in dependencies):raise ValueError('Inputs changed during render; result not accepted')
        verified=True;result=state();write_json(root/'progress.json',result);return result
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--job',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);path=Path(a.job).resolve();render_job(json.loads(path.read_text('utf-8')),path.parent)
if __name__=='__main__':main()
