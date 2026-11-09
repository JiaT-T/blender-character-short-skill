"""Create a short head/blink/cut test copy, not a story or library-action film."""
from pathlib import Path
import argparse,sys,json,math
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
from mathutils import Vector,Quaternion
from production_contract import declared_file,write_json,sha
from production_defaults import new_video_settings
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);path=Path(a.plan).resolve();plan=json.loads(path.read_text('utf-8'));base=path.parent;source=declared_file(plan['source'],base);pf=declared_file(plan['profile'],base);profile=json.loads(Path(pf['path']).read_text('utf-8'));output=(base/plan['output']).resolve();report=(base/plan['report']).resolve();frames=plan['frames'];settings=new_video_settings({k:plan[k] for k in ['fps'] if k in plan});fps=settings['fps'];size=plan.get('size',[settings['width'],settings['height']])
    if output.exists() or report.exists():raise FileExistsError('Keep earlier diagnostic copies')
    if type(frames) is not int or not 6<=frames<=120 or type(fps) is not int or not 1<=fps<=120:raise ValueError('Small declared diagnostic range required')
    bpy.ops.wm.open_mainfile(filepath=source['path'],load_ui=False,use_scripts=False);scene=bpy.context.scene;rig=bpy.data.objects[profile['controller']];mesh=bpy.data.objects[profile['mesh']];head=rig.pose.bones[profile['head_control']];blink=mesh.data.shape_keys.key_blocks[profile['blink_shape']]
    if (rig.animation_data and (rig.animation_data.action or rig.animation_data.nla_tracks)) or (mesh.data.shape_keys.animation_data and mesh.data.shape_keys.animation_data.action):raise ValueError('Unanimated look baseline required')
    if scene.rigidbody_world:raise ValueError('This technical fixture does not alter physical caches')
    q=head.matrix_basis.to_quaternion();up=((rig.matrix_world@head.matrix).to_3x3().inverted()@Vector((0,0,1))).normalized();neutral_blink=blink.value;scene.frame_start=1;scene.frame_end=frames;scene.render.fps=fps;scene.render.fps_base=1
    rows=[]
    for frame in range(1,frames+1):
        t=(frame-1)/(frames-1);yaw=math.radians(12)*math.sin(2*math.pi*t);b=max(0.,1-abs(t-.42)/.1);head.rotation_mode='QUATERNION';head.rotation_quaternion=q@Quaternion(up,yaw);head.keyframe_insert('rotation_quaternion',frame=frame);blink.value=b;blink.keyframe_insert('value',frame=frame);rows.append({'frame':frame,'yaw_radians':yaw,'blink':b})
    cameras={};by={c['id']:c for c in profile['cases']}
    for role in ['front','side']:
        original=bpy.data.objects[by[role]['camera']];new=original.copy();new.data=original.data.copy();new.name=original.name+'__Diagnostic';scene.collection.objects.link(new);new.data.sensor_fit='VERTICAL'
        if new.data.type=='PERSP':new.data.lens*=new.data.sensor_height/new.data.sensor_width*.8
        elif new.data.type=='ORTHO':new.data.ortho_scale*=1.5
        else:raise ValueError('Reviewed perspective/orthographic camera required')
        cameras[role]=new
    scene.timeline_markers.clear()
    for frame,role in [(1,'front'),(1+frames//3,'side'),(1+2*frames//3,'front')]:m=scene.timeline_markers.new('Diagnostic '+role,frame=frame);m.camera=cameras[role]
    scene.camera=cameras['front'];scene.frame_set(1);scene.render.resolution_x=size[0];scene.render.resolution_y=size[1];scene.render.resolution_percentage=100;scene.render.film_transparent=False;scene['short_post_chain']='saved-native'
    output.parent.mkdir(parents=True,exist_ok=True);bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(output),check_existing=False)
    result={'accepted':True,'source':source,'profile':pf,'output':str(output),'output_sha256':sha(output),'frames':frames,'fps':fps,'size':size,'tracks':rows,'cuts':[[m.frame,m.camera.name] for m in scene.timeline_markers],'scope':'New technical head/blink/camera diagnostic only; not library-motion authoring, physics, full story or visual acceptance','source_unchanged':sha(source['path'])==source['sha256'],'ui_used':False};write_json(report,result);print('LOOK_DIAGNOSTIC_SAVED',str(output))
if __name__=='__main__':main()
