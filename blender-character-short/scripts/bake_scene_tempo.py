"""Resample a baked scene and verify its mapped integer-frame states.

This is a timing adaptation, not continuous motion, physics or acting acceptance.
"""
import argparse,hashlib,json,math,sys
from pathlib import Path
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy,numpy as np
from scene_tempo_plan import load_json,validate_plan,map_marker,check_work,MAX_MATRIX_FRAMES,MAX_KEY_SAMPLES

def sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
    return digest.hexdigest()

def all_ids():
    # Include drivers/NLA on meshes, shape keys and shader trees, not just objects.
    seen=set()
    for prop in bpy.data.bl_rna.properties:
        if prop.type!='COLLECTION':continue
        collection=getattr(bpy.data,prop.identifier,None)
        if collection is None:continue
        for item in collection:
            if not isinstance(item,bpy.types.ID):continue
            for data in (item,getattr(item,'node_tree',None)):
                if data is not None and data.as_pointer() not in seen:
                    seen.add(data.as_pointer());yield data

def preflight(scene):
    if len(bpy.data.scenes)!=1 or len(bpy.data.libraries):raise ValueError('One local scene without linked libraries is required')
    if scene.rigidbody_world:raise ValueError('Rigid-body worlds are unsupported')
    editor=scene.sequence_editor
    if editor is not None:
        strips=getattr(editor,'strips_all',getattr(editor,'sequences_all',None))
        if strips is None or len(strips):raise ValueError('Sequencer content or an unsupported sequencer API is unsupported')
    if getattr(scene.render,'use_motion_blur',False):raise ValueError('Motion-blur subframe integration is outside this bake contract')
    for data in all_ids():
        animation=getattr(data,'animation_data',None)
        if animation and (len(animation.drivers) or len(animation.nla_tracks)):
            raise ValueError('Drivers or NLA tracks are unsupported: '+data.name)
    for image in bpy.data.images:
        if image.source in ('SEQUENCE','MOVIE'):raise ValueError('Frame-dependent image sequences and movies are unsupported')
    for obj in scene.objects:
        if obj.rigid_body or len(obj.particle_systems) or obj.get('source_outline_cache'):
            raise ValueError('Time-dependent simulation/cache object is unsupported: '+obj.name)
        if any(m.type in ('NODES','CLOTH','SOFT_BODY','PARTICLE_SYSTEM','FLUID','DYNAMIC_PAINT','MESH_CACHE','MESH_SEQUENCE_CACHE','OCEAN') for m in obj.modifiers):
            raise ValueError('Simulation, geometry-node or cached modifier is unsupported: '+obj.name)
    actions=[a for a in bpy.data.actions if a.users];curves=[]
    for action in actions:
        if hasattr(action,'slots') and len(action.slots)>1:raise ValueError('Multi-slot actions are unsupported')
        for curve in action.fcurves:
            if len(curve.modifiers) or len(curve.sampled_points):raise ValueError('F-curve modifiers and sampled-point curves are unsupported')
            if len(curve.keyframe_points):curves.append(curve)
    if not curves:raise ValueError('At least one existing keyed animation channel is required')
    return actions,curves

def checked_array(value,label):
    array=np.asarray(value,dtype=np.float64)
    if not np.isfinite(array).all():raise ValueError('Nonfinite '+label)
    return array

def bake(scene,document):
    plan=validate_plan(document,scene.frame_start,scene.frame_end)
    actions,curves=preflight(scene)
    objects=sorted(scene.objects,key=lambda o:o.name)
    bones=[(arm,bone.name) for arm in objects if arm.type=='ARMATURE' for bone in sorted(arm.pose.bones,key=lambda b:b.name)]
    work=check_work(plan,len(objects)+len(bones),len(curves))
    markers=[{'name':m.name,'source_frame':m.frame,'output_frame':map_marker(m.frame,plan),'camera':m.camera.name if m.camera else None} for m in scene.timeline_markers]
    cuts=[m['output_frame'] for m in markers if m['camera']]
    if len(cuts)!=len(set(cuts)):raise ValueError('Time map collapses multiple camera cuts onto one output frame')
    def snapshot():
        matrices=[list(map(list,arm.matrix_world@arm.pose.bones[name].matrix)) for arm,name in bones]
        matrices.extend(list(map(list,o.matrix_world)) for o in objects)
        return checked_array(matrices,'evaluated bone/object world matrix')
    # A skipped source key must not hide known numerically invalid input. Check
    # every source integer frame AND all original in-range key times, with one
    # combined source/output work budget. This still is not a continuous proof.
    matrix_count=len(objects)+len(bones)
    capacity=min(MAX_MATRIX_FRAMES//max(1,matrix_count),MAX_KEY_SAMPLES//len(curves))-2*plan['output_last']
    source_checks=set(float(f) for f in range(plan['source_first'],plan['source_last']+1))
    if len(source_checks)>capacity:raise ValueError('Combined source/output validation exceeds tempo work limits')
    key_count=0
    for curve in curves:
        key_count+=len(curve.keyframe_points)
        if key_count>MAX_KEY_SAMPLES:raise ValueError('Original key count exceeds tempo work limit')
        for key in curve.keyframe_points:
            checked_array([list(key.co),list(key.handle_left),list(key.handle_right)],'original key/handle')
            time=float(key.co.x)
            if plan['source_first']<=time<=plan['source_last']:
                source_checks.add(time)
                if len(source_checks)>capacity:raise ValueError('Combined original-key/output validation exceeds tempo work limits')
    for time in sorted(source_checks):
        scene.frame_set(math.floor(time),subframe=time-math.floor(time));bpy.context.view_layer.update();snapshot()
        original=checked_array([curve.evaluate(time) for curve in curves],'original source sample')
        if np.max(np.abs(original))>np.finfo(np.float32).max:raise ValueError('Original source curve values exceed float32 storage')
    reference=[];cameras=[]
    for time in plan['source_times']:
        scene.frame_set(math.floor(time),subframe=time-math.floor(time));bpy.context.view_layer.update()
        reference.append(snapshot());cameras.append(scene.camera.name if scene.camera else None)
    values=checked_array([[curve.evaluate(t) for t in plan['source_times']] for curve in curves],'source curve value')
    if np.max(np.abs(values))>np.finfo(np.float32).max:raise ValueError('Curve values exceed finite float32 storage')
    values=values.astype(np.float32)
    frames=np.arange(1,plan['output_last']+1,dtype=np.float32)
    for curve,row in zip(curves,values):
        points=curve.keyframe_points
        if not all(callable(getattr(points,key,None)) for key in ('clear','add','foreach_set')):
            raise ValueError('Installed Blender API lacks the supported keyframe collection methods')
        points.clear();points.add(len(frames));points.foreach_set('co',np.column_stack((frames,row)).ravel())
        for key in points:key.interpolation='LINEAR'
        curve.update()
    for marker,row in zip(scene.timeline_markers,markers):marker.frame=row['output_frame']
    scene.frame_end=plan['output_last'];scene.frame_preview_start=1;scene.frame_preview_end=plan['output_last']
    maximum=0.;curve_error=0.;camera_changes=[]
    for index,expected in enumerate(reference):
        scene.frame_set(index+1);bpy.context.view_layer.update()
        difference=checked_array(snapshot()-expected,'mapped world difference')
        if difference.size:maximum=max(maximum,float(np.max(np.abs(difference))))
        actual=scene.camera.name if scene.camera else None
        if actual!=cameras[index]:camera_changes.append({'frame':index+1,'expected':cameras[index],'actual':actual})
    for curve,row in zip(curves,values):
        sampled=checked_array([curve.evaluate(f) for f in frames],'output curve value')
        curve_error=max(curve_error,float(np.max(np.abs(sampled-row))))
    if maximum>1e-5 or curve_error>1e-5 or camera_changes:
        raise ValueError('Mapped scene state changed: '+json.dumps({'world_matrix':maximum,'curve':curve_error,'cameras':camera_changes[:5]}))
    scene.frame_set(1)
    return {'plan':plan,'work':work,'source_numeric_sample_count':len(source_checks),'original_key_count':key_count,
            'combined_matrix_frames':(len(source_checks)+2*plan['output_last'])*matrix_count,
            'combined_curve_samples':(len(source_checks)+2*plan['output_last'])*len(curves),
            'action_count':len(actions),'curve_count':len(curves),'bone_count':len(bones),'object_count':len(objects),
            'maximum_mapped_world_matrix_difference':maximum,'maximum_mapped_curve_difference':curve_error,
            'camera_identity_mismatches':camera_changes,'markers':markers,'fps':scene.render.fps/scene.render.fps_base,
            'scope':'All output integer frames verified against mapped source bone/object world matrices, source F-curve samples and active camera identity. Dense LINEAR keys are a new interpolation between these states. No proof of subframe safety, unchanged velocity/acceleration, physical validity, collision-free interpolated motion, natural acting, continuous playback or listening. No rig rest, weights, mesh geometry or texture assets are edited.'}

def main(arguments=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('blend','plan','output','report'):parser.add_argument('--'+key,required=True,type=Path)
    if arguments is None:arguments=sys.argv[sys.argv.index('--')+1:]
    a=parser.parse_args(arguments);source=a.blend.resolve();plan=a.plan.resolve();destination=a.output.resolve();report=a.report.resolve()
    if destination.suffix.lower()!='.blend' or report.suffix.lower()!='.json' or len({source,plan,destination,report})!=4:
        raise ValueError('Choose distinct inputs, a new .blend and a new .json report')
    if destination.exists() or report.exists():raise FileExistsError('Preserve existing outputs; choose a new version')
    document=load_json(plan);before={p:sha(p) for p in (source,plan)}
    bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False);result=bake(bpy.context.scene,document)
    if any(sha(p)!=value for p,value in before.items()):raise ValueError('Input changed during tempo bake')
    destination.parent.mkdir(parents=True,exist_ok=True);report.parent.mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(destination))
    result.update(schema=1,status='new-scene-saved-mapped-states-verified-await-motion-and-visual-audits',
                  input_scene_sha256=before[source],output_scene_sha256=sha(destination),plan_sha256=before[plan],
                  writer_sha256=sha(Path(__file__)),plan_validator_sha256=sha(Path(__file__).with_name('scene_tempo_plan.py')),
                  json_validator_sha256=sha(Path(__file__).with_name('elbow_pole_plan.py')))
    report.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),'utf-8')
    print('SCENE_TEMPO_BAKE',json.dumps(result['work']),flush=True)

if __name__=='__main__':main()
