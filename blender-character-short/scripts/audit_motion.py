"""Read evaluated motion from a frozen scene; metrics locate review frames.

No .blend is saved. Numeric continuity is not visual or acting acceptance.
"""
import argparse,json,math,sys
from pathlib import Path
import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

def main():
    p=argparse.ArgumentParser();p.add_argument('--blend',required=True);p.add_argument('--character',required=True);p.add_argument('--output',required=True);p.add_argument('--prop-name',default='Story prop');a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    cfg=json.loads(Path(a.character).read_text('utf-8'));bpy.ops.wm.open_mainfile(filepath=str(Path(a.blend).resolve()));scene=bpy.context.scene;arms=[o for o in scene.objects if o.type=='ARMATURE']
    if len(arms)!=1:raise ValueError('Expected one armature')
    arm=arms[0];bones={k:arm.pose.bones[v] for k,v in cfg['bones'].items()};prop=scene.objects.get(a.prop_name);h=cfg['height'];fps=scene.render.fps/scene.render.fps_base;records=[];previous={};steps=[]
    for frame in range(scene.frame_start,scene.frame_end+1):
        scene.frame_set(frame);bpy.context.view_layer.update();record={'frame':frame,'camera':scene.camera.name if scene.camera else None,'joints':{},'projection':{}}
        for key,bone in bones.items():
            pos=arm.matrix_world@bone.head;q=(arm.matrix_world@bone.matrix).to_quaternion().normalized();record['joints'][key]=list(pos)
            if scene.camera:record['projection'][key]=list(world_to_camera_view(scene,scene.camera,pos))
            if key in previous:
                oldp,oldq=previous[key];dot=min(1,max(0,abs(q.dot(oldq))));steps.append({'frame':frame,'bone':key,'distance_height':(pos-oldp).length/h,'rotation_degrees':math.degrees(2*math.acos(dot))})
            previous[key]=(pos.copy(),q.copy())
        if prop:
            pos=prop.matrix_world.translation;record['prop_world']=list(pos)
            if scene.camera:record['prop_projection']=list(world_to_camera_view(scene,scene.camera,pos))
        records.append(record)
    support={}
    for key in ('left_foot','right_foot'):
        base=Vector(records[0]['joints'][key]);support[key]={'max_drift_world':max((Vector(r['joints'][key])-base).length for r in records),'max_drift_height':max((Vector(r['joints'][key])-base).length/h for r in records)}
    signs=[]
    if arm.animation_data and arm.animation_data.action:
        action=arm.animation_data.action
        for key,bone in bones.items():
            path=bone.path_from_id('rotation_quaternion');curves=[action.fcurves.find(path,index=i) for i in range(4)]
            if not all(curves):continue
            times=sorted(set(k.co.x for fc in curves for k in fc.keyframe_points));previous_q=None
            for t in times:
                q=Vector([fc.evaluate(t) for fc in curves]).normalized()
                if previous_q is not None and q.dot(previous_q)<0:signs.append({'bone':key,'frame':t,'dot_previous_key':q.dot(previous_q)})
                previous_q=q
    report={'scope':'Evaluated all-frame joint/prop/camera audit; no render and no visual acceptance','blend':str(Path(a.blend).resolve()),'frames':len(records),'fps':fps,'support':support,'quaternion_sign_discontinuities':signs,'largest_position_steps':sorted(steps,key=lambda x:x['distance_height'],reverse=True)[:12],'largest_rotation_steps':sorted(steps,key=lambda x:x['rotation_degrees'],reverse=True)[:12],'records':records}
    out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print('MOTION_AUDIT',len(records),support,flush=True)

if __name__=='__main__':main()
