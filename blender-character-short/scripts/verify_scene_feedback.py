"""Synthetic receiver/prop cases; run only in a fresh factory background Blender."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy,json,argparse,hashlib,datetime
from bake_scene_feedback import bake

def cube(name,location,dimensions):
    bpy.ops.mesh.primitive_cube_add(size=1,location=location);o=bpy.context.object;o.name=name;o.scale=dimensions;return o
def fixture(kind):
    bpy.ops.wm.read_factory_settings(use_empty=True);scene=bpy.context.scene;scene.frame_start=1;scene.frame_end=16;scene.render.fps=24
    floor=cube('Fixture receiver',(0,0,-.05),(1,1,.1));indicator=cube('Fixture indicator',(0,-.48,.03),(1,.04,.06));prop=cube('Fixture prop',(1,0,.0203),(.2,.2,.04));material=bpy.data.materials.new('Fixture shared material');material.use_nodes=True;indicator.data.materials.append(material);floor.data.materials.append(material);before=list(material.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value)
    if kind=='toon-stable':
        nt=material.node_tree;p=nt.nodes['Principled BSDF'];output=nt.nodes['Material Output'];emission=nt.nodes.new('ShaderNodeEmission');mix=nt.nodes.new('ShaderNodeMixShader');mix.inputs[0].default_value=.35;nt.links.new(p.outputs[0],mix.inputs[1]);nt.links.new(emission.outputs[0],mix.inputs[2]);nt.links.new(mix.outputs[0],output.inputs['Surface'])
    for f in range(1,17):
        prop.location=(1 if f<6 else 0,0,.0203);prop.rotation_euler=(0,0,0)
        if kind=='floating':prop.location=(0,0,.2)
        if kind=='below-floor':prop.location=(0,0,0)
        if kind=='brief':prop.location=(0 if 6<=f<=8 else 1,0,.0203)
        if kind=='spinning':prop.location=(0,0,.0203);prop.rotation_euler.z=f*.2
        prop.keyframe_insert('location',frame=f);prop.keyframe_insert('rotation_euler',frame=f)
    for c in prop.animation_data.action.fcurves:
        for k in c.keyframe_points:k.interpolation='LINEAR'
    if kind=='moving-receiver':
        for f,x in [(1,0),(16,.05)]:floor.location.x=x;floor.keyframe_insert('location',frame=f)
    plan={'schema':1,'prop':prop.name,'receiver':floor.name,'indicator':indicator.name,'search_frames':[1,16],'stable_frames':3,'xy_margin_H':.006,'bottom_gap_H':[-.0004,.0015],'max_prop_height_H':.08,'max_step_H':.001,'ramp_frames':3,'mix':.75,'on_color':[.7,.43,.1],'emission_strength':1.6,'bloom_weight':.035}
    return scene,indicator,floor,material,before,plan

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);destination=a.output.resolve()
    if not bpy.app.background or bpy.data.filepath:raise ValueError('Use a new factory background process without a loaded project')
    if destination.exists() or destination.suffix.lower()!='.json':raise ValueError('Choose a new JSON verification report')
    cases=[]
    for kind in ('stable','toon-stable','floating','below-floor','brief','spinning','moving-receiver'):
        scene,indicator,floor,material,before,plan=fixture(kind)
        try:result=bake(scene,{'height':1},plan)
        except ValueError as exc:
            if kind in ('stable','toon-stable'):raise
            assert indicator.material_slots[0].material==material and list(material.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value)==before
            cases.append({'kind':kind,'passed':True,'result':'rejected-before-material-change','reason':str(exc)})
        else:
            assert kind in ('stable','toon-stable'),'Invalid placement unexpectedly accepted: '+kind
            assert result['source_event_frame']==9 and result['source_full_response_frame']==12 and result['protected_bone_object_world_max_error']==0 and result['no_response_before_confirmation']
            assert floor.material_slots[0].material==material and list(material.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value)==before
            new=indicator.material_slots[0].material;assert new!=material and new.node_tree!=material.node_tree
            strengths=[]
            for f in (1,8,9,12,16):scene.frame_set(f);bpy.context.view_layer.update();strengths.append(float(new.node_tree.nodes['Scene response weight'].outputs[0].default_value))
            assert max(strengths[:3])==0 and abs(strengths[3]-1)<1e-6 and abs(strengths[4]-1)<1e-6
            cases.append({'kind':kind,'passed':True,'event_frame':9,'full_response_frame':12,'sampled_strengths':strengths,'original_shared_material_retained':True})
        print('SCENE_FEEDBACK_CASE',kind,'pass',flush=True)
    result={'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'cases':cases,'passed':all(c['passed'] for c in cases),'writer_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'scope':'Seven actual Blender synthetic box cases, including original-style MixShader surface support. Fast rotation with stationary origin, below-floor/floating/brief placement and moving receiver refusals; original shared material and all object states preserved. No character/cross-character, source rendering or continuous visual acceptance.'};destination.parent.mkdir(parents=True,exist_ok=True);destination.write_text(json.dumps(result,indent=2),'utf-8')
if __name__=='__main__':main()
