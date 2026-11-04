"""Generated local fixtures for coupled timing; contains no third-party assets."""
import argparse,json,math,sys
from pathlib import Path
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy,numpy as np
from bake_scene_tempo import bake,main as bake_cli,sha
from scene_tempo_plan import validate_plan

DOCUMENT={'schema':1,'knots':[{'output':1,'source':1},{'output':5,'source':3},{'output':9,'source':7},{'output':10,'source':10}]}

def fixture():
    bpy.ops.wm.read_factory_settings(use_empty=True);scene=bpy.context.scene
    scene.sequence_editor_create()  # Empty editor is not timed media content.
    scene.frame_start=1;scene.frame_end=10;scene.render.fps=24
    data=bpy.data.armatures.new('Generated rig');arm=bpy.data.objects.new('Generated rig',data);scene.collection.objects.link(arm)
    bpy.context.view_layer.objects.active=arm;arm.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
    parent=None
    for index in range(3):
        bone=data.edit_bones.new('joint'+str(index));bone.head=(0,0,index);bone.tail=(0,0,index+1);bone.parent=parent;parent=bone
    bpy.ops.object.mode_set(mode='OBJECT')
    mesh=bpy.data.meshes.new('Generated triangle');mesh.from_pydata([(0,0,0),(1,0,0),(0,1,0)],[],[(0,1,2)])
    obj=bpy.data.objects.new('Generated shape',mesh);scene.collection.objects.link(obj);obj.parent=arm
    obj.shape_key_add(name='Basis');key=obj.shape_key_add(name='Test shape');key.data[0].co.z=.5
    material=bpy.data.materials.new('Generated keyed material');material.use_nodes=True;mesh.materials.append(material)
    rgb=material.node_tree.nodes.new('ShaderNodeRGB');rgb.name='Generated keyed color'
    # Blender4.5 may automatically put object and shape-key channels into two
    # slots of one Action. Make the supported fixture explicitly one owner per
    # action; keep multi-slot actions as a separately tested refusal below.
    for index,owner in enumerate((arm,obj,obj.data.shape_keys,material.node_tree)):
        owner.animation_data_create();owner.animation_data.action=bpy.data.actions.new('Generated single-owner action'+str(index))
    cameras=[]
    for index in range(2):
        camera=bpy.data.objects.new('Camera'+str(index),bpy.data.cameras.new('CameraData'+str(index)));scene.collection.objects.link(camera);camera.location=(index,-4,2);cameras.append(camera)
    scene.camera=cameras[0]
    for frame,camera in ((1,cameras[0]),(5,cameras[1]),(9,cameras[0])):
        marker=scene.timeline_markers.new('Cut'+str(frame),frame=frame);marker.camera=camera
    for frame,weight in ((1,0.),(5,.8),(10,.2)):
        arm.location=(weight*.2,0,0);arm.keyframe_insert('location',frame=frame)
        arm.pose.bones['joint1'].rotation_mode='XYZ';arm.pose.bones['joint1'].rotation_euler.z=weight*.3;arm.pose.bones['joint1'].keyframe_insert('rotation_euler',frame=frame)
        obj['keyed_value']=weight;obj.keyframe_insert(data_path='["keyed_value"]',frame=frame)
        key.value=weight;key.keyframe_insert('value',frame=frame)
        rgb.outputs[0].default_value=(weight,.2,.3,1.);rgb.outputs[0].keyframe_insert('default_value',frame=frame)
    # BEZIER source interpolation exercises fractional source evaluation.
    scene.frame_set(1)
    return scene

def visible_state(scene):
    obj=scene.objects['Generated shape'];ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh()
    vertices=[list(ev.matrix_world@v.co) for v in mesh.vertices];ev.to_mesh_clear()
    material=obj.data.materials[0]
    return {'vertices':vertices,'keyed_value':obj['keyed_value'],'shape_value':obj.data.shape_keys.key_blocks['Test shape'].value,
            'color':list(material.node_tree.nodes['Generated keyed color'].outputs[0].default_value),
            'camera':scene.camera.name if scene.camera else None}

def compare(a,b):
    if a['camera']!=b['camera']:raise AssertionError('Active camera differs after reopen')
    return max(float(np.max(np.abs(np.asarray(a[key])-np.asarray(b[key])))) for key in ('vertices','keyed_value','shape_value','color'))

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:]);out=args.output.resolve();out.mkdir(exist_ok=False,parents=True)
    results=[];scene=fixture();plan=validate_plan(DOCUMENT,1,10);expected=[]
    for time in plan['source_times']:
        scene.frame_set(math.floor(time),subframe=time-math.floor(time));bpy.context.view_layer.update();expected.append(visible_state(scene))
    source=out/'source.blend';scene.frame_set(1);bpy.ops.wm.save_as_mainfile(filepath=str(source));before=sha(source)
    plan_file=out/'plan.json';plan_file.write_text(json.dumps(DOCUMENT),'utf-8');destination=out/'retimed.blend';report=out/'retimed-report.json'
    bake_cli(['--blend',str(source),'--plan',str(plan_file),'--output',str(destination),'--report',str(report)])
    if sha(source)!=before:raise AssertionError('Source file changed')
    bpy.ops.wm.open_mainfile(filepath=str(destination),load_ui=False,use_scripts=False);scene=bpy.context.scene;maximum=0.
    for frame,state in enumerate(expected,1):
        scene.frame_set(frame);bpy.context.view_layer.update();maximum=max(maximum,compare(state,visible_state(scene)))
    if maximum>1e-5:raise AssertionError('Saved mapped deformation/material state changed')
    results.append({'case':'fractional-fast-slow-coupled-save-reopen','status':'pass','maximum_deformed_vertex_shape_property_material_error':maximum,'source_unchanged':True})
    def refuses(name,change,document=DOCUMENT,message=None):
        scene=fixture();change(scene)
        try:bake(scene,document)
        except ValueError as exc:
            if message and message not in str(exc):raise AssertionError('Wrong refusal for '+name+': '+str(exc))
            results.append({'case':name,'status':'expected-refusal','reason':str(exc)});return
        raise AssertionError('Unsupported fixture accepted: '+name)
    def add_driver(scene):scene.objects['Generated shape'].driver_add('location',0).driver.expression='frame/10'
    refuses('driver',add_driver,message='Drivers')
    refuses('NLA',lambda s:s.objects['Generated rig'].animation_data.nla_tracks.new(),message='NLA')
    refuses('geometry-nodes',lambda s:s.objects['Generated shape'].modifiers.new('Generated time modifier','NODES'),message='geometry-node')
    refuses('multiple-scenes',lambda s:bpy.data.scenes.new('Other scene'),message='One local scene')
    refuses('multiple-action-slots',lambda s:s.objects['Generated rig'].animation_data.action.slots.new(id_type='OBJECT',name='Generated extra slot'),message='Multi-slot')
    refuses('collapsed-camera-cuts',lambda s:None,{'schema':1,'knots':[{'output':1,'source':1},{'output':2,'source':10}]},message='camera cuts')
    def overflow(scene):
        parent=None
        for index in range(12):
            obj=bpy.data.objects.new('Finite scale chain'+str(index),None);scene.collection.objects.link(obj);obj.parent=parent;obj.scale=(1e30,1e30,1e30);parent=obj
    refuses('finite-local-values-nonfinite-world',overflow,message='Nonfinite')
    skipped={'schema':1,'knots':[{'output':1,'source':1},{'output':2,'source':10}]}
    def narrow_key_peak(scene,scale):
        scene.timeline_markers.clear();parent=None
        for index in range(4):
            obj=bpy.data.objects.new('Original fractional peak'+str(index),None);scene.collection.objects.link(obj);obj.parent=parent;parent=obj
            for frame,size in ((1,1.),(4.24,1.),(4.25,scale),(4.26,1.),(10,1.)):
                obj.scale=(size,size,size);obj.keyframe_insert('scale',frame=frame)
            for curve in obj.animation_data.action.fcurves:
                for key in curve.keyframe_points:key.interpolation='LINEAR'
    refuses('skipped-original-fractional-key-overflow',lambda s:narrow_key_peak(s,1e12),skipped,message='Nonfinite')
    scene=fixture();narrow_key_peak(scene,2.);finite=bake(scene,skipped)
    if finite['source_numeric_sample_count']<13:raise AssertionError('Original fractional keys were omitted')
    results.append({'case':'finite-fractional-original-key-coverage','status':'pass','source_numeric_sample_count':finite['source_numeric_sample_count']})
    scene=fixture();narrow_key_peak(scene,1e12);invalid_source=out/'invalid-original-peak.blend';bpy.ops.wm.save_as_mainfile(filepath=str(invalid_source))
    invalid_plan=out/'skipped-plan.json';invalid_plan.write_text(json.dumps(skipped),'utf-8')
    invalid_output=out/'must-not-save.blend';invalid_report=out/'must-not-report.json'
    try:bake_cli(['--blend',str(invalid_source),'--plan',str(invalid_plan),'--output',str(invalid_output),'--report',str(invalid_report)])
    except ValueError as exc:
        if 'Nonfinite' not in str(exc):raise
    else:raise AssertionError('CLI accepted known-invalid original key')
    if invalid_output.exists() or invalid_report.exists():raise AssertionError('Numeric failure left an output or success report')
    results.append({'case':'invalid-original-key-cli-no-output-or-success-report','status':'expected-refusal'})
    # CLI boundary checks must not leave a success report or overwrite evidence.
    for case,arguments,error in (
        ('existing-output',['--blend',str(source),'--plan',str(plan_file),'--output',str(destination),'--report',str(out/'must-not-exist.json')],FileExistsError),
        ('wrong-output-suffix',['--blend',str(source),'--plan',str(plan_file),'--output',str(out/'bad.txt'),'--report',str(out/'must-not-exist.json')],ValueError)):
        try:bake_cli(arguments)
        except error:results.append({'case':case,'status':'expected-refusal'})
        else:raise AssertionError('CLI boundary was accepted')
        if (out/'must-not-exist.json').exists():raise AssertionError('Failure left a misleading success report')
    result={'schema':1,'status':'generated-fixtures-pass','cases':results,'writer_sha256':sha(Path(__file__).with_name('bake_scene_tempo.py')),
            'scope':'Generated assets only. Technical mapped-state and explicit refusal tests, not a second production character, third-party action acquisition, physical or continuous visual acceptance.'}
    (out/'verification.json').write_text(json.dumps(result,indent=2,allow_nan=False),'utf-8');print('SCENE_TEMPO_VERIFICATION',len(results),'PASS',flush=True)

if __name__=='__main__':main()
