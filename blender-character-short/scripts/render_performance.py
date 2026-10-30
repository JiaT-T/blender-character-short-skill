"""Sequential frozen-scene render with raw AOV checkpoints or diagnostic boards."""
import argparse,hashlib,json,sys,time,traceback
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
import bpy,numpy as np
from render_source_probe import setup_raw

def valid_npz(path,w,h,extra=()):
    try:
        with np.load(path) as d:return d['rgba'].shape==(h,w,4) and d['weight'].shape==(h,w,1) and np.isfinite(d['rgba']).all() and np.isfinite(d['weight']).all() and all(d['aov_'+k].shape==(h,w,4) and np.isfinite(d['aov_'+k]).all() for k in extra)
    except Exception:return False

def main():
    p=argparse.ArgumentParser();p.add_argument('--blend',required=True);p.add_argument('--output',required=True);p.add_argument('--start',type=int,default=1);p.add_argument('--end',type=int);p.add_argument('--width',type=int,default=640);p.add_argument('--height',type=int,default=360);p.add_argument('--samples',type=int,default=16);p.add_argument('--board',action='store_true');p.add_argument('--max-seconds',type=float);p.add_argument('--extra-aov',action='append',default=[]);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);blend=Path(a.blend).resolve();out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True);bpy.ops.wm.open_mainfile(filepath=str(blend));scene=bpy.context.scene;end=a.end or scene.frame_end
    signature={'blend_sha256':hashlib.sha256(blend.read_bytes()).hexdigest(),'renderer_script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'width':a.width,'height':a.height,'samples':a.samples,'mode':'diagnostic-board' if a.board else 'raw-source-AOV','fps':scene.render.fps,'frame_end':scene.frame_end}
    job=out/'render-job.json'
    signature['extra_aovs']=a.extra_aov
    if job.exists() and json.loads(job.read_text('utf-8'))!=signature:raise ValueError('Output belongs to different frozen scene/settings; use a new directory')
    job.write_text(json.dumps(signature,indent=2),encoding='utf-8');scene.render.resolution_x=a.width;scene.render.resolution_y=a.height;scene.render.resolution_percentage=100;scene.eevee.taa_render_samples=a.samples;scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGBA'
    if any(o.get('source_outline_cache') for o in scene.objects):
        from bake_source_outline import entries,verify
        glb=Path(scene['outline_source_glb'])
        if hashlib.sha256(glb.read_bytes()).hexdigest()!=scene['outline_source_sha256']:raise ValueError('Outline source asset changed; rebuild the cache')
        items,_,_=entries(scene,glb,json.loads(scene['outline_global_tint']));checks=verify(scene,items,list(range(a.start,end+1)));(out/'outline-cache-verification.json').write_text(json.dumps(checks,indent=2),'utf-8')
    passes=['Image','HX_BloomWeight',*a.extra_aov]
    if not a.board:setup_raw(scene,out/'raw-exr',passes)
    started=time.monotonic();records=[];skipped=[];status='running';current=None
    try:
        for f in range(a.start,end+1):
            current=f;path=out/(f'frame_{f:04}.png' if a.board else f'frame_{f:04}.npz')
            if path.exists():
                if not a.board and valid_npz(path,a.width,a.height,a.extra_aov):skipped.append(f);continue
                if a.board:
                    try:
                        im=bpy.data.images.load(str(path),check_existing=False);ok=tuple(im.size)==(a.width,a.height);bpy.data.images.remove(im)
                        if ok:skipped.append(f);continue
                    except Exception:pass
            scene.frame_set(f);scene.render.filepath=str(path);t=time.monotonic();bpy.ops.render.render(write_still=a.board)
            if not a.board:
                arrays={}
                for name in passes:
                    ep=out/'raw-exr'/f'{name}_{f:04}.exr';im=bpy.data.images.load(str(ep),check_existing=False);arr=np.empty(len(im.pixels),np.float32);im.pixels.foreach_get(arr);arrays[name]=arr.reshape(im.size[1],im.size[0],4);bpy.data.images.remove(im)
                tmp=path.with_name(path.stem+'.partial.npz');np.savez_compressed(tmp,rgba=arrays['Image'],weight=arrays['HX_BloomWeight'][...,:1],**{'aov_'+k:arrays[k] for k in a.extra_aov});tmp.replace(path)
                if not valid_npz(path,a.width,a.height,a.extra_aov):raise RuntimeError('Raw output validation failed at frame '+str(f))
            records.append({'frame':f,'seconds':time.monotonic()-t})
            if f%24==0:print('CHECKPOINT',f,'of',end,'elapsed',round(time.monotonic()-started,1),flush=True)
            state={'status':'running','last_frame':f,'requested':[a.start,end],'rendered':records,'skipped':skipped,'elapsed':time.monotonic()-started};(out/'progress.json').write_text(json.dumps(state,indent=2),encoding='utf-8')
            if a.max_seconds and time.monotonic()-started>=a.max_seconds:status='budget-paused';break
        else:status='complete'
    except Exception:
        status='failed';(out/'error.txt').write_text(traceback.format_exc(),encoding='utf-8');raise
    finally:
        (out/'progress.json').write_text(json.dumps({'status':status,'last_frame':current,'requested':[a.start,end],'rendered':records,'skipped':skipped,'elapsed':time.monotonic()-started},indent=2),encoding='utf-8');print('RENDER_STATUS',status,len(records),'rendered',len(skipped),'skipped',flush=True)

if __name__=='__main__':main()
