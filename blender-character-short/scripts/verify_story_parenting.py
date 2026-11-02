"""Own geometry-only parenting checks; always run in a background Blender process."""
import argparse,bpy,hashlib,importlib.util,json,math,pathlib,sys
import numpy as np
from mathutils import Euler,Matrix,Vector
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from story_stage import add_story_objects

def main():
    if not bpy.app.background:raise RuntimeError('Use factory-startup background Blender; do not clear an interactive project')
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=pathlib.Path);p.add_argument('--reference-stage',type=pathlib.Path);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=a.output.resolve();out.mkdir(exist_ok=False)
    def reset():bpy.ops.wm.read_factory_settings(use_empty=True)
    default={'materials':{'matte':{'color':[.2,.3,.4]}},'objects':[{'name':'Default box','position':[.2,-.1,.4],'size':[.2,.1,.3],'material':'matte','rotation':[0,0,20],'bevel':.01},{'name':'Default cylinder','shape':'cylinder','position':[-.3,.1,.2],'size':[.1,.1,.3],'material':'matte','bevel':.005}]}
    def capture(function):
        reset();s=bpy.context.scene;record=function(s,default,2,.3,lambda t:round(t*24)+1);bpy.context.view_layer.update();objects={}
        for obj in s.objects:
            ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh()
            try:objects[obj.name]={'matrix':[list(row) for row in ev.matrix_world],'vertices':[list(ev.matrix_world@v.co) for v in mesh.vertices],'faces':[list(p.vertices) for p in mesh.polygons]}
            finally:ev.to_mesh_clear()
        return {'record':record,'objects':objects}
    reference=None
    if a.reference_stage:
        spec=importlib.util.spec_from_file_location('reference_story_stage',a.reference_stage);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        old=capture(module.add_story_objects);new=capture(add_story_objects);assert old==new,'Default geometry/record regression'
        reference={'source_sha256':hashlib.sha256(a.reference_stage.read_bytes()).hexdigest(),'objects':2,'world_geometry_and_record_exact':True}
    reset();s=bpy.context.scene;s.frame_start=1;s.frame_end=3;bpy.ops.mesh.primitive_cube_add(size=.1);root=bpy.context.object;root.name='AnimatedRoot';root.rotation_mode='XYZ'
    for frame,location,rotation,scale in [(1,(3,4,5),(0,0,.3),(.5,2,1.5)),(2,(-2,1,3),(.2,-.1,.8),(2,.75,1)),(3,(1,-3,2),(-.3,.4,-.6),(.7,1.2,2.1))]:
        root.location=location;root.rotation_euler=rotation;root.scale=scale
        for field in ['location','rotation_euler','scale']:root.keyframe_insert(field,frame=frame)
    s.frame_set(1)
    cfg={'materials':{'matte':{'color':[.2,.3,.4]}},'objects':[{'name':'Grandchild','parent':'Child','position':[-.2,.1,.15],'size':[.1,.1,.1],'material':'matte','rotation':[10,20,0]},
       {'name':'Child','parent':'AnimatedRoot','position':[.1,.2,.3],'size':[.1,.2,.15],'material':'matte','rotation':[0,0,30]},
       {'name':'World box','position':[.2,-.1,.4],'size':[.2,.1,.3],'material':'matte'}]}
    add_story_objects(s,cfg,2,.3,lambda t:round(t*24)+1)
    child_local=Matrix.Translation(Vector((.2,.4,.6)))@Euler((0,0,math.radians(30))).to_matrix().to_4x4()
    grand_local=Matrix.Translation(Vector((-.4,.2,.3)))@Euler(tuple(math.radians(v) for v in [10,20,0])).to_matrix().to_4x4()
    def check():
        s=bpy.context.scene;maximum=0.
        for frame in [1,2,3]:
            s.frame_set(frame);bpy.context.view_layer.update();objects=s.objects;expected=objects['AnimatedRoot'].matrix_world@child_local
            maximum=max(maximum,float(np.max(abs(np.array(expected)-np.array(objects['Child'].matrix_world)))),float(np.max(abs(np.array(expected@grand_local)-np.array(objects['Grandchild'].matrix_world)))))
            assert (objects['World box'].matrix_world.translation-Vector((.4,-.2,1.1))).length<1e-6,'World ground offset changed'
            assert objects['Child'].parent.name=='AnimatedRoot' and objects['Grandchild'].parent.name=='Child'
        assert maximum<2e-6,maximum
        return maximum
    before=check();scene=out/'hierarchy.blend';bpy.ops.wm.save_as_mainfile(filepath=str(scene));bpy.ops.wm.open_mainfile(filepath=str(scene));after=check()
    negatives=[]
    for name,items in [('cycle',[{'name':'A','parent':'B'},{'name':'B','parent':'A'}]),('missing',[{'name':'C','parent':'Missing'}]),('collision',[{'name':'Child','parent':'AnimatedRoot'}])]:
        count=(len(bpy.data.objects),len(bpy.data.materials))
        try:add_story_objects(bpy.context.scene,{'objects':items},2,.3,lambda t:1)
        except ValueError:pass
        else:raise AssertionError('Invalid graph was accepted: '+name)
        assert count==(len(bpy.data.objects),len(bpy.data.materials)),'Invalid parent graph changed scene'
        negatives.append(name)
    result={'status':'pass','own_geometry_only':True,'height':2,'ground':.3,'animated_frames':3,'nonuniform_scale_and_rotation':True,'child_before_parent_definition':True,
            'maximum_world_matrix_error_before_save':before,'maximum_world_matrix_error_after_reopen':after,'world_ground_preserved':True,'parent_local_ground_not_added':True,'pre_mutation_rejections':negatives,'default_reference':reference,
            'scope':'Object-level parent transform/geometry and saved hierarchy only; not bone attachments, contact, collision, physics or cross-character acceptance.'}
    (out/'result.json').write_text(json.dumps(result,indent=2),'utf-8');print('STORY_PARENTING_VERIFIED',json.dumps(result),flush=True)

if __name__=='__main__':main()
