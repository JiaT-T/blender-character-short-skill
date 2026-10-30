"""Project diagnostic: test an existing binocular control without new rigging."""
import argparse,sys,json,math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
import bpy
from mathutils import Vector,Matrix,Quaternion

from gaze_control import aim_existing_control as eye_aim

def main():
    p=argparse.ArgumentParser();p.add_argument('--blend',required=True);p.add_argument('--config',required=True);p.add_argument('--output',required=True);p.add_argument('--frames',default='72,100,160');p.add_argument('--face-close',action='store_true');a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    bpy.ops.wm.open_mainfile(filepath=a.blend);s=bpy.context.scene;arm=next(o for o in s.objects if o.type=='ARMATURE');prop=s.objects['Story prop'];cfg=json.loads(Path(a.config).read_text('utf-8'));out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
    control=arm.pose.bones[cfg['control']];control.rotation_mode='QUATERNION';records=[]
    # Render evaluation re-applies keyed controls and camera markers. Remove only
    # the tested control curves in this unsaved diagnostic copy; retain its rig
    # constraints and all body animation. Select original shots explicitly.
    prefix=control.path_from_id()
    if arm.animation_data and arm.animation_data.action:
        for curve in list(arm.animation_data.action.fcurves):
            if curve.data_path.startswith(prefix+'.'):arm.animation_data.action.fcurves.remove(curve)
    shots=sorted([(m.frame,m.camera) for m in s.timeline_markers if m.camera],key=lambda x:x[0]);fallback=s.camera;s.timeline_markers.clear()
    if a.face_close:
        data=bpy.data.cameras.new('Gaze diagnostic camera');diagnostic=bpy.data.objects.new(data.name,data);s.collection.objects.link(diagnostic)
    s.render.resolution_x=640;s.render.resolution_y=360;s.render.resolution_percentage=100;s.eevee.taa_render_samples=16
    for frame in map(int,a.frames.split(',')):
        s.frame_set(frame);s.camera=next((c for f,c in reversed(shots) if f<=frame),fallback);control.matrix_basis=Matrix.Identity(4);bpy.context.view_layer.update()
        if a.face_close:
            eye_origin=arm.matrix_world@((arm.pose.bones[cfg['left']].head+arm.pose.bones[cfg['right']].head)*.5)
            diagnostic.matrix_world=s.camera.matrix_world.copy();diagnostic.data.type='ORTHO';diagnostic.data.ortho_scale=max((arm.matrix_world.to_3x3()@(arm.pose.bones[cfg['left']].head-arm.pose.bones[cfg['right']].head)).length*8,1e-4)
            diagnostic.rotation_euler=(eye_origin-diagnostic.location).to_track_quat('-Z','Y').to_euler();s.camera=diagnostic
        for active in [False,True]:
            if active:record=eye_aim(arm,cfg,arm.matrix_world.inverted()@prop.matrix_world.translation)
            else:record={'control_rotation':list(control.rotation_quaternion)}
            control.keyframe_insert('rotation_quaternion',frame=frame);before=list(control.rotation_quaternion);camera_name=s.camera.name;s.render.image_settings.file_format='PNG';s.render.filepath=str(out/f'{frame:04}_{"eyes" if active else "baseline"}.png');bpy.ops.render.render(write_still=True)
            after=list(control.rotation_quaternion)
            if max(abs(x-y) for x,y in zip(before,after))>1e-5 or s.camera.name!=camera_name:raise RuntimeError('Render evaluation replaced the diagnostic control or camera')
            record.update(frame=frame,enabled=active,path=s.render.filepath,control_before_render=before,control_after_render=after,camera=camera_name,camera_width=s.camera.data.ortho_scale);records.append(record)
    (out/'report.json').write_text(json.dumps({'input':a.blend,'config':cfg,'records':records,'scope':'diagnostic raw-composite Standard PNG; actual geometry/control movement; not final source color'},ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':main()
