"""Synthetic Blender checks for stationary support, with no character assets."""
import argparse,copy,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
import bpy
from mathutils import Vector
from build_performance import two_bone
from support_motion import bake_support


def fixture(translated=False):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene=bpy.context.scene;scene.frame_start=1;scene.frame_end=16
    data=bpy.data.armatures.new('Fixture rig')
    arm=bpy.data.objects.new('Fixture rig',data);scene.collection.objects.link(arm)
    bpy.context.view_layer.objects.active=arm;arm.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    specifications=[('hips',(0,0,1),(0,0,1.2),None),
                    ('upper',(0,0,1),(0,0,.55),'hips'),
                    ('knee',(0,0,.55),(0,0,.1),'upper'),
                    ('ankle',(0,0,.1),(0,-.15,.1),'knee')]
    for name,head,tail,parent in specifications:
        bone=data.edit_bones.new(name);bone.head=head;bone.tail=tail
        if parent:bone.parent=data.edit_bones[parent]
    bpy.ops.object.mode_set(mode='OBJECT')
    if translated:
        arm.location=(.2,.1,0);arm.rotation_euler[2]=.3
    bpy.context.view_layer.update()
    target=arm.matrix_world@arm.pose.bones['ankle'].head
    controller=bpy.data.objects.new('Original IK target',None)
    scene.collection.objects.link(controller);controller.location=target
    constraint=arm.pose.bones['knee'].constraints.new('IK')
    constraint.target=controller;constraint.chain_count=2
    hips=arm.pose.bones['hips']
    for frame,location in [(1,(0,0,0)),(8,(.03,-.08,.015)),(16,(0,0,0))]:
        hips.location=location;hips.keyframe_insert('location',frame=frame)
    scene.frame_set(1);bpy.context.view_layer.update()
    cfg={'left':{'upper':'upper','knee':'knee','ankle':'ankle',
                 'target':list(target),'pole':list(target+Vector((0,-1,.4)))}}
    return scene,arm,cfg,target


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);a.output=a.output.resolve();a.output.mkdir(parents=True,exist_ok=True)
    results=[]
    for translated in (False,True):
        scene,arm,cfg,target=fixture(translated)
        report=bake_support(scene,arm,cfg,two_bone,1,0)
        assert report['maximum_target_error_height']<1e-5,report
        saved=a.output/('translated.blend' if translated else 'origin.blend')
        bpy.ops.wm.save_as_mainfile(filepath=str(saved))
        bpy.ops.wm.open_mainfile(filepath=str(saved))
        scene=bpy.context.scene;arm=scene.objects['Fixture rig'];errors=[]
        for frame in range(1,17):
            scene.frame_set(frame);bpy.context.view_layer.update()
            errors.append((arm.matrix_world@arm.pose.bones['ankle'].head-target).length)
        assert max(errors)<1e-5,errors
        assert arm.pose.bones['knee'].constraints[0].mute
        results.append({'case':'translated-reopened' if translated else 'origin-reopened',
                        'passed':True,'maximum_world_error':max(errors)})
    scene,arm,cfg,target=fixture()
    before=arm.pose.bones['knee'].constraints[0].mute
    assert bake_support(scene,arm,{},two_bone,1,0)=={'status':'not-requested'}
    assert arm.pose.bones['knee'].constraints[0].mute==before
    results.append({'case':'not-requested-preserves-IK','passed':True})
    for name,modify in [
        ('unreachable',lambda c:c['left'].update(target=[5,0,.1])),
        ('invalid-chain',lambda c:c['left'].update(knee='hips')),
        ('nonfinite',lambda c:c['left'].update(target=[float('nan'),0,.1])),
    ]:
        scene,arm,cfg,target=fixture();modify(cfg)
        try:bake_support(scene,arm,cfg,two_bone,1,0)
        except ValueError as exc:results.append({'case':name,'passed':True,'expected_error':str(exc)})
        else:raise AssertionError('Expected rejection: '+name)
    (a.output/'results.json').write_text(json.dumps(results,indent=2),'utf-8')
    print('SUPPORT_CHECKS_PASSED',len(results),flush=True)


if __name__=='__main__':main()
