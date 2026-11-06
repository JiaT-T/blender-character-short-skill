"""Build a bounded original-rig arm gesture and supported primitive-prop scene."""
from pathlib import Path
import argparse,json,sys,math,datetime
sys.dont_write_bytecode=True;sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy,numpy as np
from mathutils import Matrix,Vector,Quaternion
from hand_control_runtime import sha,rigs,set_frame,geometry_signature,linear_new_keys
from hand_control_plan import value_at,number,text
from build_performance import two_bone,principled
from bake_elbow_poles import orient

def cord_points(top,bottom,length,segments,side):
    top=np.asarray(top,dtype=float);bottom=np.asarray(bottom,dtype=float);direction=bottom-top;distance=float(np.linalg.norm(direction));side=np.asarray(side,dtype=float).copy()
    if not np.isfinite([*top,*bottom,length,*side]).all() or not 1e-6<distance<=length+1e-7 or not 2<=segments<=32:raise ValueError('Finite reachable cord endpoints and2..32segments required')
    side-=direction*np.dot(side,direction)/max(distance*distance,1e-20);side/=max(float(np.linalg.norm(side)),1e-20);u=np.linspace(0,1,segments+1);base=top[None,:]+u[:,None]*direction;wave=np.sin(np.pi*u)[:,None]*side[None,:]
    def points(amplitude):return base+amplitude*wave
    lo,hi=0.,length
    for _ in range(40):
        mid=(lo+hi)/2;p=points(mid);measured=float(np.linalg.norm(np.diff(p,axis=0),axis=1).sum())
        if measured<length:lo=mid
        else:hi=mid
    result=points((lo+hi)/2)
    if not np.isfinite(result).all() or abs(float(np.linalg.norm(np.diff(result,axis=0),axis=1).sum())-length)>1e-7:raise ValueError('Cord length solution failed')
    return result

def validate_scene_plan(plan):
    if not isinstance(plan,dict) or type(plan.get('schema')) is not int or plan['schema']!=1:raise ValueError('Scene plan schema1 required')
    frames=plan.get('frames')
    if not isinstance(frames,list) or len(frames)!=2 or any(type(f) is not int for f in frames) or not 1<=frames[0]<frames[1] or frames[1]-frames[0]+1>120:raise ValueError('Bounded2..120integer frames required')
    first,last=frames
    if type(plan.get('fps')) is not int or not 1<=plan['fps']<=60 or type(plan.get('reference_frame')) is not int or plan['reference_frame']<1:raise ValueError('Positive integer reference/fps required')
    phases=[plan[k] for k in ['close_frames','held_frames','release_frames']]
    if any(not isinstance(v,list) or len(v)!=2 or any(type(x) is not int for x in v) or not first<=v[0]<v[1]<=last for v in phases) or phases[0][1]!=phases[1][0] or phases[1][1]!=phases[2][0]:raise ValueError('Ordered close/hold/release phases required')
    if plan.get('side') not in ['left','right']:raise ValueError('Explicit side required')
    names=[text(plan['arm_bones'][k],'bone') for k in ['arm','elbow','wrist']]
    if len(set(names))!=3:raise ValueError('Distinct arm mappings required')
    def vector(key,size):
        value=plan[key]
        if not isinstance(value,list) or len(value)!=size:raise ValueError('Explicit vector required:'+key)
        return np.asarray([number(x,key) for x in value])
    approach=vector('approach_offset_hand_m',3);lift=vector('lift_world_m',3);axis=vector('inspection_axis_world',3)
    if np.linalg.norm(approach)>.1 or np.linalg.norm(lift)>.08 or abs(float(np.linalg.norm(axis))-1)>1e-4 or not 0<=number(plan['inspection_degrees'],'inspection')<=15:raise ValueError('Bounded metre offsets and unit axis required')
    transform=np.asarray(plan['hand_frame_from_wrist'],dtype=float)
    if transform.shape!=(4,4) or not np.isfinite(transform).all() or np.max(np.abs(transform[3]-[0,0,0,1]))>1e-8 or np.max(np.abs(transform[:3,:3].T@transform[:3,:3]-np.eye(3)))>.002 or abs(np.linalg.det(transform[:3,:3])-1)>.002:raise ValueError('Finite rigid hand frame required')
    if type(plan['cord_segments']) is not int or not 2<=plan['cord_segments']<=32 or not 0<number(plan['cord_length_m'],'cord length')<=.5 or not 0<number(plan['cord_radius_m'],'cord radius')<=.005:raise ValueError('Bounded cord allocation/size required')
    for key in ['contact_gap_limit_m','penetration_tolerance_m','stability_tolerance_m','cord_length_tolerance_m']:
        if not 0<number(plan[key],key)<=.01:raise ValueError('Explicit positive metric tolerance required')
    for key in ['ball_base_colour','ball_accent_colour']:
        if any(not 0<=v<=1 for v in vector(key,4)):raise ValueError('Bounded RGBA required')
    for key in ['prop_name','cord_name']:
        if len(text(plan[key],key))>63:raise ValueError('Object name exceeds Blender name contract')
    if plan['prop_name']==plan['cord_name']:raise ValueError('Distinct prop/cord names required')
    for key in ['approach_keys','lift_keys']:
        rows=plan[key]
        if not isinstance(rows,list) or not 2<=len(rows)<=64:raise ValueError('Bounded body keys required')
        previous=first-1
        for row in rows:
            if not isinstance(row,list) or len(row)!=2 or type(row[0]) is not int or not previous<row[0]<=last or not first<=row[0] or not 0<=number(row[1],key)<=1:raise ValueError('Ordered normalized body keys required')
            previous=row[0]
        if rows[0][0]!=first or rows[-1][0]!=last:raise ValueError('Body keys must include both boundaries')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for k in ['blend','plan','fit','output','report']:p.add_argument('--'+k,required=True,type=Path)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);output=a.output.resolve();assert not output.exists() and not a.report.exists();plan=json.loads(a.plan.read_text('utf-8'));validate_scene_plan(plan);fit=json.loads(a.fit.read_text('utf-8'));assert fit['static_candidate_pass'] and plan['fit_sha256']==sha(a.fit);first,last=plan['frames'];fps=plan['fps'];start_hold,end_hold=plan['held_frames']
    if type(first) is not int or type(last) is not int or not 1<=first<last or last-first+1>120 or not first<start_hold<end_hold<last or type(fps) is not int or not 1<=fps<=60:raise ValueError('Bounded120-frame gesture and ordered hold required')
    before=sha(a.blend);bpy.ops.wm.open_mainfile(filepath=str(a.blend.resolve()),load_ui=False,use_scripts=False);scene=bpy.context.scene;arm,meshes=rigs(scene)
    if (last-first+1)*len(arm.pose.bones)>300000 or scene.render.fps!=fps or abs(scene.render.fps_base-1)>1e-8:raise ValueError('Integer source fps and bounded bone-frame work required')
    names=[plan['arm_bones'][k] for k in ['arm','elbow','wrist']]
    if len(set(names))!=3 or any(n not in arm.pose.bones for n in names):raise ValueError('Distinct existing arm/elbow/wrist mappings required')
    upper,lower,wrist=[arm.pose.bones[n] for n in names]
    if upper not in lower.parent_recursive or lower not in wrist.parent_recursive:raise ValueError('Original arm ancestor chain required')
    if any(not c.mute and c.influence>1e-8 for b in [upper,lower,wrist] for c in b.constraints):raise ValueError('Indirect/constrained arm needs separate validated route')
    if arm.animation_data and any(not t.mute and t.strips for t in arm.animation_data.nla_tracks):raise ValueError('Active arm NLA not supported for this bounded pose source')
    if not scene.frame_start<=plan['reference_frame']<=scene.frame_end:raise ValueError('Reference frame outside source timeline')
    set_frame(scene,plan['reference_frame']);identity=geometry_signature(arm,meshes);bases={b.name:b.matrix_basis.copy() for b in arm.pose.bones};W0=(arm.matrix_world@wrist.matrix).copy();H0=W0@Matrix(plan['hand_frame_from_wrist']).inverted();pole=arm.matrix_world@lower.head;arm_inverse=arm.matrix_world.inverted();approach=H0.to_3x3()@Vector(plan['approach_offset_hand_m']);lift=Vector(plan['lift_world_m']);axis=Vector(plan['inspection_axis_world']).normalized()
    if max(abs(x-1) for x in W0.to_scale())>1e-5 or not 0<=number(plan['inspection_degrees'],'inspection degrees')<=15 or approach.length>.1 or lift.length>.08:raise ValueError('Unit world rig and bounded physical movement required')
    if arm.animation_data:arm.animation_data.action=None
    for name,basis in bases.items():arm.pose.bones[name].matrix_basis=basis
    arm.animation_data_create();previous={};rows=[];paths=set()
    for frame in range(first,last+1):
        set_frame(scene,frame)
        for n in names:arm.pose.bones[n].matrix_basis=bases[n]
        bpy.context.view_layer.update();u=value_at(plan['approach_keys'],frame);v=value_at(plan['lift_keys'],frame);target=W0.translation+approach*u+lift*v;answer=two_bone(upper,lower,wrist,arm_inverse@target,arm_inverse@pole,reach_fraction=1)
        if answer['clamped'] or answer['endpoint_error']>1e-5:raise ValueError('Required wrist target unreachable at'+str(frame))
        q=Quaternion(axis,math.radians(plan['inspection_degrees'])*v)@W0.to_quaternion();orient(arm,wrist,q);actual=arm.matrix_world@wrist.matrix;error=(actual.translation-target).length
        if error>1e-5:raise ValueError('Wrist endpoint mismatch')
        for n in names:
            b=arm.pose.bones[n];b.rotation_mode='QUATERNION';q=b.rotation_quaternion.copy()
            if n in previous and q.dot(previous[n])<0:q.negate()
            b.rotation_quaternion=q;previous[n]=q.copy();b.keyframe_insert('rotation_quaternion',frame=frame);paths.add(b.path_from_id('rotation_quaternion'))
        rows.append({'frame':frame,'wrist_endpoint_error_m':error,'wrist_position_world':list(actual.translation)})
    linear_new_keys(arm,paths,first,last);scene.frame_start=first;scene.frame_end=last
    for obj in scene.objects:
        if obj.type in ['MESH','CURVE'] and obj not in meshes:obj.hide_render=True
    silver=principled('Owned sphere silver',plan['ball_base_colour'][:3],.32,.45);gold=principled('Owned sphere accent',plan['ball_accent_colour'][:3],.35,.4);radius=fit['best']['radius_m'];bpy.ops.mesh.primitive_uv_sphere_add(segments=48,ring_count=24,radius=radius);sphere=bpy.context.object;sphere.name=plan['prop_name'];sphere.data.materials.append(silver);sphere.data.materials.append(gold)
    for face in sphere.data.polygons:face.use_smooth=True;face.material_index=1 if abs(face.center.z)<radius*.12 else 0
    curve=bpy.data.curves.new(plan['cord_name'],'CURVE');curve.dimensions='3D';curve.resolution_u=1;curve.bevel_depth=plan['cord_radius_m'];curve.bevel_resolution=1;curve.use_fill_caps=True;spline=curve.splines.new('POLY');spline.points.add(plan['cord_segments']);cord=bpy.data.objects.new(plan['cord_name'],curve);scene.collection.objects.link(cord);curve.materials.append(gold)
    G=W0.inverted()@H0@Matrix.Translation(Vector(fit['best']['center_hand_m']));M0=W0@G;attach_local=M0.to_3x3().inverted()@Vector((0,0,radius));bottom0=M0@attach_local;top=bottom0+Vector((0,0,plan['cord_length_m']));bow=(H0.to_3x3()@Vector((1,0,0))).normalized();last_q=None
    for i in range((last-first)*2+1):
        frame=first+i/2;set_frame(scene,frame);W=arm.matrix_world@wrist.matrix;M=W@G if start_hold<=frame<=end_hold else M0;sphere.matrix_world=M;sphere.rotation_mode='QUATERNION';q=M.to_quaternion()
        if last_q and q.dot(last_q)<0:q.negate()
        sphere.rotation_quaternion=q;last_q=q.copy();sphere.keyframe_insert('location',frame=frame);sphere.keyframe_insert('rotation_quaternion',frame=frame);bottom=M@attach_local;points=cord_points(top,bottom,plan['cord_length_m'],plan['cord_segments'],bow)
        for point,value in zip(spline.points,points):point.co=(*value,1);point.keyframe_insert('co',frame=frame)
    for data in [sphere,curve]:
        for layer in data.animation_data.action.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    for fc in bag.fcurves:
                        for key in fc.keyframe_points:key.interpolation='LINEAR'
    assert geometry_signature(arm,meshes)==identity and sha(a.blend)==before;set_frame(scene,first);output.parent.mkdir(parents=True,exist_ok=True);bpy.ops.wm.save_as_mainfile(filepath=str(output));a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps({'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'new-body-and-supported-sphere-base-saved-await-fingers-and-audit','source_sha256':before,'output_sha256':sha(output),'plan_sha256':sha(a.plan),'fit_sha256':sha(a.fit),'writer_sha256':sha(Path(__file__)),'geometry_signature':identity,'frames':[first,last],'fps':fps,'sphere_name':sphere.name,'cord_name':cord.name,'radius_m':radius,'sphere_in_wrist':[list(row) for row in G],'rest_sphere_world':[list(row) for row in M0],'cord_top_world':list(top),'cord_attach_sphere_local':list(attach_local),'cord_length_m':plan['cord_length_m'],'rows':rows,'source_unchanged':True,'scope':'Original bones/rest/weights/morph data unchanged. New sampled arm FK and analytic supported-prop choreography; not finger-contact, self-collision, dynamic friction or continuous visual acceptance.'},ensure_ascii=False,indent=2),'utf-8');print('SPHERE_BODY_BASE_SAVED',str(output),flush=True)
if __name__=='__main__':main()
