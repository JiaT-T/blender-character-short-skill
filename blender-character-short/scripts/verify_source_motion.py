"""Synthetic rotation-layer checks; no third-party animation is bundled."""
import argparse,copy,json,math,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
import bpy
from mathutils import Quaternion
from mathutils import Vector
from source_motion_layer import bake_source_layers


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);a.output=a.output.resolve();a.output.mkdir(parents=True,exist_ok=True)
    skeleton=a.output/'skeleton.json';skeleton.write_text(json.dumps({'nodes':[{'name':'spine'}]}),'utf-8')
    clip=a.output/'quarter-turn.json';clip.write_text(json.dumps({
        'version':1,'packing':{'times':[0,1],'rotationBits':16,'valueDigits':5},
        'tracks':[{'node':0,'property':'quaternion','deltas':[0,0,0,0,0,32767],
                   'dropped':[{'at':0,'component':3}]}]}),'utf-8')
    def fixture(transformed=False):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        s=bpy.context.scene;s.frame_start=1;s.frame_end=25
        data=bpy.data.armatures.new('Rig');arm=bpy.data.objects.new('Rig',data);s.collection.objects.link(arm)
        bpy.context.view_layer.objects.active=arm;arm.select_set(True)
        bpy.ops.object.mode_set(mode='EDIT');bone=data.edit_bones.new('spine');bone.head=(0,0,0);bone.tail=(0,0,1)
        bpy.ops.object.mode_set(mode='OBJECT')
        if transformed:arm.location=(.2,-.1,.3);arm.rotation_euler[0]=.4
        bpy.context.view_layer.update()
        layer={'clip':str(clip),'skeleton':str(skeleton),'basis':[[1,0,0],[0,1,0],[0,0,1]],
               'mapping':{'spine':0},'start':0,'end':1,'duration':1,'loop':False,'strength':.5}
        return s,arm,layer
    results=[]
    for transformed in (False,True):
        s,arm,layer=fixture(transformed)
        original=(arm.matrix_world@arm.pose.bones['spine'].matrix).copy()
        report=bake_source_layers(s,arm,{'bones':{'spine':'spine'}},[layer],24,1)
        saved=a.output/('world-rotated.blend' if transformed else 'origin.blend')
        bpy.ops.wm.save_as_mainfile(filepath=str(saved));bpy.ops.wm.open_mainfile(filepath=str(saved))
        s=bpy.context.scene;arm=s.objects['Rig'];s.frame_set(25);bpy.context.view_layer.update()
        actual=arm.matrix_world@arm.pose.bones['spine'].matrix
        delta=actual.to_quaternion()@original.to_quaternion().inverted()
        assert abs(math.degrees(delta.angle)-45)<.001,delta
        assert abs(abs(delta.axis.z)-1)<1e-5,delta.axis
        assert (actual.translation-original.translation).length<1e-6
        results.append({'case':'world-basis-save-reopen' if transformed else 'known-90-source-45-target',
                        'passed':True,'target_angle_degrees':math.degrees(delta.angle)})
    s,arm,layer=fixture()
    assert bake_source_layers(s,arm,{'bones':{'spine':'spine'}},[],24,1)=={'status':'not-requested'}
    assert arm.animation_data is None
    results.append({'case':'absent-layer-no-op','passed':True})
    for name,change in [('reflected-basis',lambda l:l.update(basis=[[-1,0,0],[0,1,0],[0,0,1]])),
                        ('missing-node',lambda l:l.update(mapping={'spine':99})),
                        ('nonfinite-phase',lambda l:l.update(phase=float('nan')))]:
        s,arm,layer=fixture();change(layer)
        try:bake_source_layers(s,arm,{'bones':{'spine':'spine'}},[layer],24,1)
        except ValueError as exc:results.append({'case':name,'passed':True,'expected_error':str(exc)})
        else:raise AssertionError(name)
    # An own nested source inherits a quarter-turn around X. A target child's
    # local offset must survive even when it is not marked connected in Blender.
    nested_skeleton=a.output/'nested-skeleton.json';nested_skeleton.write_text(json.dumps({'nodes':[{'children':[1]},{'translation':[0,0,1]}]}),'utf-8')
    nested_clip=a.output/'nested-quarter-turn-X.json';nested_clip.write_text(json.dumps({'version':1,'packing':{'times':[0,1],'rotationBits':16,'valueDigits':5},'tracks':[{'node':0,'property':'quaternion','deltas':[0,32767,0,0,0,0],'dropped':[{'at':0,'component':3}]}]}),'utf-8')
    for transformed,inactive in [(False,False),(True,False),(True,True)]:
        bpy.ops.wm.read_factory_settings(use_empty=True);s=bpy.context.scene;s.frame_start=1;s.frame_end=25
        data=bpy.data.armatures.new('Nested');arm=bpy.data.objects.new('Nested',data);s.collection.objects.link(arm);bpy.context.view_layer.objects.active=arm;arm.select_set(True)
        bpy.ops.object.mode_set(mode='EDIT');parent=data.edit_bones.new('parent');parent.head=(0,0,0);parent.tail=(0,0,1);child=data.edit_bones.new('child');child.head=(.2 if transformed else 0,0,1);child.tail=(.2 if transformed else 0,0,2);child.parent=parent;child.use_connect=False;bpy.ops.object.mode_set(mode='OBJECT')
        if transformed:
            arm.location=(.2,-.1,.3);arm.rotation_euler=(.2,-.3,.4);arm.scale=(1.5,1.5,1.5)
            child=arm.pose.bones['child'];child.rotation_mode='XYZ';child.rotation_euler=(.15,-.1,.2);child.location=(.08,-.04,.03);child.scale=(1.1,1.1,1.1)
        bpy.context.view_layer.update();bones={name:arm.pose.bones[name] for name in ['parent','child']};originals={name:{'world':(arm.matrix_world@bone.matrix).copy(),'location':bone.location.copy(),'scale':bone.scale.copy()} for name,bone in bones.items()};distance=(originals['child']['world'].translation-originals['parent']['world'].translation).length
        layer={'clip':str(nested_clip),'skeleton':str(nested_skeleton),'basis':[[1,0,0],[0,1,0],[0,0,1]],'mapping':{'parent':0,'child':1},'start':.25 if inactive else 0,'end':.75 if inactive else 1,'duration':1,'loop':False,'strength':.5}
        bake_source_layers(s,arm,{'bones':{'parent':'parent','child':'child'}},[layer],24,1)
        saved=a.output/('nested-inactive.blend' if inactive else ('nested-transformed-offset.blend' if transformed else 'nested-origin.blend'));bpy.ops.wm.save_as_mainfile(filepath=str(saved));bpy.ops.wm.open_mainfile(filepath=str(saved));s=bpy.context.scene;arm=s.objects['Nested'];maximum_distance_error=maximum_local_error=maximum_scale_error=0.
        for frame in range(1,26):
            s.frame_set(frame);bpy.context.view_layer.update();bones={name:arm.pose.bones[name] for name in ['parent','child']};actual_distance=((arm.matrix_world@bones['child'].matrix).translation-(arm.matrix_world@bones['parent'].matrix).translation).length;maximum_distance_error=max(maximum_distance_error,abs(actual_distance-distance))
            for name,bone in bones.items():
                maximum_local_error=max(maximum_local_error,(bone.location-originals[name]['location']).length);maximum_scale_error=max(maximum_scale_error,(bone.scale-originals[name]['scale']).length)
                if inactive and frame in [1,25]:
                    actual=arm.matrix_world@bone.matrix;assert max(abs(actual[r][c]-originals[name]['world'][r][c]) for r in range(4) for c in range(4))<1e-5
        assert max(maximum_distance_error,maximum_local_error,maximum_scale_error)<1e-5
        if not inactive:
            for name,bone in bones.items():
                delta=(arm.matrix_world@bone.matrix).to_quaternion()@originals[name]['world'].to_quaternion().inverted();expected=Quaternion((1,0,0),math.radians(45));assert math.degrees(delta.rotation_difference(expected).angle)<.005
        results.append({'case':'nested-inactive-interval' if inactive else ('nested-transformed-Euler-local-offset-scale-save-reopen' if transformed else 'nested-origin-save-reopen'),'passed':True,'maximum_joint_distance_error':maximum_distance_error,'maximum_local_translation_error':maximum_local_error,'maximum_local_scale_error':maximum_scale_error})
    (a.output/'results.json').write_text(json.dumps(results,indent=2),'utf-8')
    print('SOURCE_LAYER_CHECKS_PASSED',len(results),flush=True)


if __name__=='__main__':main()
