"""Run with blender -b --python render_queue.py -- --jobs jobs.json. One GPU job at a time."""
import bpy,json,pathlib,sys,time,argparse,struct
p=argparse.ArgumentParser();p.add_argument('--jobs',required=True);args=p.parse_args(sys.argv[sys.argv.index('--')+1:])
jobs=json.loads(pathlib.Path(args.jobs).read_text(encoding='utf-8'))
for j in jobs:
    project=pathlib.Path(j['blend']);dest=pathlib.Path(j['output']);dest.mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(project));s=bpy.context.scene;s.render.engine='BLENDER_EEVEE_NEXT';s.render.resolution_x=j.get('width',960);s.render.resolution_y=j.get('height',540);s.render.resolution_percentage=100;s.eevee.taa_render_samples=j.get('samples',32);s.render.image_settings.file_format='PNG';s.render.image_settings.color_mode='RGB';s.render.image_settings.compression=15;s.render.use_compositing=True;s.render.fps=24
    manifest={'blend':str(project),'width':s.render.resolution_x,'height':s.render.resolution_y,'fps':s.render.fps,'samples':s.eevee.taa_render_samples,'start':j['start'],'end':j['end'],'compositor':s.use_nodes and s.render.use_compositing,'started':time.strftime('%Y-%m-%dT%H:%M:%S'),'timings':[]}
    try:
        import gpu
        manifest['gpu']={'vendor':gpu.platform.vendor_get(),'renderer':gpu.platform.renderer_get(),'version':gpu.platform.version_get()}
    except Exception as e:manifest['gpu_error']=str(e)
    mf=dest/f"render-{j['start']:04}-{j['end']:04}.json"
    for f in range(j['start'],j['end']+1):
        target=dest/f'{f:04}.png';valid=False
        if target.exists() and target.stat().st_size>1000:
            with target.open('rb') as fh:header=fh.read(24)
            valid=header[:8]==b'\x89PNG\r\n\x1a\n' and struct.unpack('>II',header[16:24])==(s.render.resolution_x,s.render.resolution_y)
        if valid:continue
        s.frame_set(f);s.render.filepath=str(target);t=time.time();bpy.ops.render.render(write_still=True);manifest['timings'].append([f,time.time()-t])
        if f%24==0 or f==j['end']:
            manifest['last_frame']=f;mf.write_text(json.dumps(manifest,indent=2),encoding='utf-8');print('CHECKPOINT',str(project),f,flush=True)
    manifest['completed']=time.strftime('%Y-%m-%dT%H:%M:%S');mf.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print('JOB_COMPLETE',str(dest),flush=True)
