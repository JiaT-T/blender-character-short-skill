"""Reopen a saved project, audit packed resources, optionally render one verification frame."""
import sys as _device_sys
from pathlib import Path as _DevicePath
_device_sys.path.insert(0, str(_DevicePath(__file__).resolve().parent))
from render_device_policy import render_with_policy, prepare_render
from render_engine_policy import apply_sampling
import bpy,argparse,json,pathlib,sys,time,hashlib
p=argparse.ArgumentParser();p.add_argument('--blend',required=True);p.add_argument('--report',required=True);p.add_argument('--preview');p.add_argument('--frame',type=int,default=1);p.add_argument('--width',type=int,default=640);p.add_argument('--samples',type=int,default=16);a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
source=pathlib.Path(a.blend).resolve();source_hash=hashlib.sha256(source.read_bytes()).hexdigest();bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False);s=bpy.context.scene
images=[{'name':i.name,'packed':bool(i.packed_file),'path':i.filepath,'size':list(i.size),'missing':not i.packed_file and not pathlib.Path(bpy.path.abspath(i.filepath)).exists()} for i in bpy.data.images if i.users and i.source=='FILE']
report={'blend':bpy.data.filepath,'version':bpy.app.version_string,'engine':s.render.engine,'resolution':[s.render.resolution_x,s.render.resolution_y],'fps':s.render.fps/s.render.fps_base,'frame_range':[s.frame_start,s.frame_end],'compositor':s.use_nodes and s.render.use_compositing,'camera':s.camera.name if s.camera else None,'images':images,'armatures':[{'name':o.name,'bones':len(o.data.bones),'action':o.animation_data.action.name if o.animation_data and o.animation_data.action else None} for o in s.objects if o.type=='ARMATURE'],'meshes':[{'name':o.name,'vertices':len(o.data.vertices),'shape_keys':len(o.data.shape_keys.key_blocks) if o.data.shape_keys else 0,'armature_modifiers':sum(m.type=='ARMATURE' for m in o.modifiers)} for o in s.objects if o.type=='MESH']}
assert s.camera,'No active camera'
assert s.frame_start<=a.frame<=s.frame_end,'Verification frame outside saved range'
assert not any(i['missing'] for i in images),'Missing image'
report['source_sha256']=source_hash;report['saved_samples']=s.eevee.taa_render_samples
if a.preview:
    ratio=s.render.resolution_y/s.render.resolution_x;s.render.resolution_x=a.width;s.render.resolution_y=round(a.width*ratio);s.render.resolution_percentage=100;apply_sampling(s,a.samples);s.render.image_settings.file_format='PNG';s.render.filepath=str(pathlib.Path(a.preview).resolve());s.frame_set(a.frame);t=time.time();render_with_policy(write_still=True);report['verification_render']={'frame':a.frame,'width':a.width,'seconds':time.time()-t,'path':s.render.filepath,'actual_render_camera':s.camera.name if s.camera else None,'actual_camera_world_location':list(s.camera.matrix_world.translation) if s.camera else None,'actual_ortho_scale':s.camera.data.ortho_scale if s.camera and s.camera.data.type=='ORTHO' else None}
assert hashlib.sha256(source.read_bytes()).hexdigest()==source_hash,'Source scene changed during read-only verification'
report['source_bytes_unchanged']=True
pathlib.Path(a.report).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print('VERIFIED',report['blend'],report.get('verification_render'))
