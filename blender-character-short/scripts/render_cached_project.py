"""Render a saved Cycles project with its materials/cut cameras, bounded and resumable.

This does not modify the source project, rebuild physics, or certify performance.
Use a fresh Blender process for each checkpoint after a complex physical bake.
"""
from pathlib import Path
import argparse,datetime,hashlib,json,sys,time
import bpy

def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def main(arguments=None):
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--start',type=int,required=True);parser.add_argument('--end',type=int,required=True);parser.add_argument('--width',type=int,default=640);parser.add_argument('--height',type=int,default=360);parser.add_argument('--samples',type=int,default=4);parser.add_argument('--batch-frames',type=int,default=90);parser.add_argument('--budget-seconds',type=float,default=240);parser.add_argument('--require-cache',action='store_true')
    args=parser.parse_args(arguments if arguments is not None else sys.argv[sys.argv.index('--')+1:])
    if not 1<=args.start<=args.end<=10000 or args.end-args.start+1>480:raise ValueError('Require1..480 bounded frames')
    if not 64<=args.width<=1920 or not 64<=args.height<=1080 or args.width*args.height>2073600 or not 1<=args.samples<=64 or not 1<=args.batch_frames<=120 or not 1<=args.budget_seconds<=1800:raise ValueError('Explicit bounded CPU render settings required')
    source=args.source.resolve();root=args.output.resolve()
    if not source.is_file() or root==source or root.is_relative_to(source):raise ValueError('Existing source and separate output directory required')
    source_sha=sha(source);frames=list(range(args.start,args.end+1));signature={'source_sha256':source_sha,'writer_sha256':sha(Path(__file__)),'size':[args.width,args.height],'samples':args.samples,'frames':frames,'require_cache':args.require_cache,'engine':'CYCLES','device':'CPU','threads':1,'denoise':True,'camera':'Saved cut markers, otherwise saved active camera','compositor':'Saved project settings preserved'}
    root.mkdir(parents=True,exist_ok=True);signature_file=root/'signature.json';progress=root/'progress.json'
    if signature_file.exists():
        if json.loads(signature_file.read_text('utf-8'))!=signature:raise ValueError('Input/producer/settings differ; use a new output directory')
    else:
        if any(root.iterdir()):raise ValueError('New render directory must be empty')
        signature_file.write_text(json.dumps(signature,indent=2,allow_nan=False),'utf-8')
    prior=json.loads(progress.read_text('utf-8')) if progress.exists() else {'frames':[]}
    if not isinstance(prior.get('frames'),list):raise ValueError('Malformed progress')
    done={row['frame']:row for row in prior['frames']}
    if len(done)!=len(prior['frames']) or not set(done).issubset(frames):raise ValueError('Unexpected/duplicate progress frames')
    for frame,row in done.items():
        expected=str(frame).zfill(4)+'.png'
        if row.get('file')!=expected or not (root/expected).is_file() or sha(root/expected)!=row.get('sha256'):raise ValueError('Existing frame/progress differs')
    bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False);scene=bpy.context.scene
    if scene.render.engine!='CYCLES':raise ValueError('Saved Cycles project required; no implicit shader/engine conversion')
    if args.start<scene.frame_start or args.end>scene.frame_end or not scene.camera:raise ValueError('Requested range/camera differs from saved display range')
    world=scene.rigidbody_world
    if args.require_cache and (not world or not world.point_cache.is_baked or world.point_cache.frame_start>args.start or world.point_cache.frame_end<args.end):raise ValueError('Actual baked cache must cover the requested display range')
    scene.cycles.device='CPU';scene.cycles.samples=args.samples;scene.cycles.use_denoising=True;scene.cycles.denoiser='OPENIMAGEDENOISE';scene.render.threads_mode='FIXED';scene.render.threads=1;scene.render.resolution_x=args.width;scene.render.resolution_y=args.height;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.render.use_file_extension=True;scene.render.use_persistent_data=True
    cuts=sorted((m for m in scene.timeline_markers if m.camera),key=lambda m:m.frame);fallback=scene.camera;started=time.monotonic();new=0
    for frame in frames:
        if frame in done:continue
        path=root/(str(frame).zfill(4)+'.png')
        if path.exists():raise ValueError('Unrecorded frame exists; preserve it and review rather than overwrite')
        scene.frame_set(frame);active=[m for m in cuts if m.frame<=frame];scene.camera=active[-1].camera if active else fallback;scene.render.filepath=str(path);bpy.ops.render.render(write_still=True)
        if not path.is_file() or path.stat().st_size==0:raise ValueError('Render did not produce a frame')
        done[frame]={'frame':frame,'file':path.name,'sha256':sha(path),'camera':scene.camera.name};new+=1
        data={'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'signature':signature,'frames':[done[f] for f in sorted(done)],'complete':len(done)==len(frames),'fps':scene.render.fps/scene.render.fps_base,'normal_speed_continuous_viewing':False,'scope':'Actual saved-project integer renders only; no new physics bake, motion correction, decoding or naturalness acceptance.'}
        temporary=progress.with_suffix('.json.partial');temporary.write_text(json.dumps(data,indent=2,allow_nan=False),'utf-8');temporary.replace(progress);print('CACHED_PROJECT_RENDER_FRAME',frame,len(done),len(frames),flush=True)
        if new>=args.batch_frames or time.monotonic()-started>=args.budget_seconds:break
    if sha(source)!=source_sha:raise ValueError('Read-only source changed')
    print('CACHED_PROJECT_RENDER_BATCH',len(done),len(frames),len(done)==len(frames),flush=True)

if __name__=='__main__':main()
