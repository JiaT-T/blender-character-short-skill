"""Latch a subtle scene response after evaluated stable placement in a box tray."""
import argparse,json,sys,hashlib,math
from pathlib import Path
sys.dont_write_bytecode=True;sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy,numpy as np
from scene_feedback_plan import validate_plan,confirmation_frame,response_weight,number,load_json
from bake_scene_tempo import preflight
from body_motion_runtime import geometry_identity

def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def evaluated_points(obj):
    ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh()
    try:
        if not 1<=len(mesh.vertices)<=100000:raise ValueError('Feedback mesh exceeds100000 evaluated vertices')
        p=np.asarray([list(ev.matrix_world@v.co) for v in mesh.vertices],float)
        if not np.isfinite(p).all():raise ValueError('Nonfinite feedback geometry')
        return p
    finally:ev.to_mesh_clear()
def bounds(obj):
    p=evaluated_points(obj);return p.min(0),p.max(0),len(p)
def receiver_box(obj,height,margin):
    if len(obj.data.vertices)!=8 or len(obj.data.polygons)!=6 or any(len(p.vertices)!=4 for p in obj.data.polygons):raise ValueError('Receiver must be a static cuboid before optional bevel')
    points=np.asarray([v.co[:] for v in obj.data.vertices],float);lo=points.min(0);hi=points.max(0)
    if not np.isfinite(points).all() or np.min(hi-lo)<=1e-8:raise ValueError('Degenerate receiver box')
    expected={tuple((hi if mask&(1<<i) else lo)[i] for i in range(3)) for mask in range(8)}
    if {tuple(p) for p in points}!=expected:raise ValueError('Receiver vertices do not form a cuboid')
    expected_faces={frozenset(i for i,p in enumerate(points) if p[axis]==edge) for axis in range(3) for edge in (lo[axis],hi[axis])}
    if {frozenset(p.vertices) for p in obj.data.polygons}!=expected_faces:raise ValueError('Receiver must contain all six distinct box faces')
    matrix=np.asarray(obj.matrix_world);axes=matrix[:3,:3];lengths=np.linalg.norm(axes,axis=0)
    if not np.isfinite(matrix).all() or min(lengths)<=1e-6 or max(lengths)>1e6 or np.linalg.det(axes)<=0:raise ValueError('Invalid receiver transform')
    unit=axes/lengths
    if not np.allclose(np.abs(unit),np.eye(3),atol=1e-6):raise ValueError('Receiver must be aligned to horizontal world axes')
    for mod in obj.modifiers:
        if mod.type!='BEVEL':raise ValueError('Only a bounded bevel is supported on the receiver box')
        if not math.isfinite(mod.width) or mod.width<0 or mod.width*max(lengths)>margin*height:raise ValueError('XY margin must cover a finite receiver bevel width')
    for poly in obj.data.polygons:
        xyz=points[list(poly.vertices)]
        if not any(np.max(xyz[:,i])-np.min(xyz[:,i])<1e-8 for i in range(3)):raise ValueError('Receiver has a nonplanar box face')

def bake(scene,character,document):
    h=number(character['height'],'height',1e-6,1e6);plan=validate_plan(document,scene.frame_start,scene.frame_end);preflight(scene)
    roles={k:scene.objects.get(plan[k]) for k in ('prop','receiver','indicator')}
    if any(o is None or o.type!='MESH' or o.hide_render for o in roles.values()):raise ValueError('Feedback roles require existing visible mesh objects')
    if any(o.find_armature() is not None or o.parent_type=='BONE' for o in roles.values()):raise ValueError('Feedback may not change or use the character mesh as a scene role')
    prop,receiver,indicator=[roles[k] for k in ('prop','receiver','indicator')];scene.frame_set(1);bpy.context.view_layer.update();receiver_box(receiver,h,plan['xy_margin_H'])
    if any(m.type not in ('BEVEL','SOLIDIFY') for m in prop.modifiers):raise ValueError('Feedback prop requires baked geometry with only bevel/solidify modifiers')
    if len(indicator.material_slots)!=1 or indicator.material_slots[0].material is None:raise ValueError('Indicator requires exactly one existing material')
    original=indicator.material_slots[0].material
    if not original.use_nodes or original.node_tree.animation_data:raise ValueError('Indicator material must have an unanimated supported node tree')
    outputs=[n for n in original.node_tree.nodes if n.type=='OUTPUT_MATERIAL' and n.is_active_output]
    if len(outputs)!=1 or len(outputs[0].inputs['Surface'].links)!=1 or outputs[0].inputs['Volume'].is_linked or outputs[0].inputs['Displacement'].is_linked:raise ValueError('Indicator needs one supported opaque surface without volume/displacement')
    if any(n.type in ('GROUP','BSDF_TRANSPARENT','BSDF_REFRACTION','BSDF_GLASS','HOLDOUT') for n in original.node_tree.nodes):raise ValueError('Indicator shader groups/transparency/transmission are unsupported')
    for node in original.node_tree.nodes:
        if node.type=='BSDF_PRINCIPLED' and (node.inputs['Alpha'].is_linked or node.inputs['Alpha'].default_value<.999 or node.inputs['Transmission Weight'].is_linked or node.inputs['Transmission Weight'].default_value>0):raise ValueError('Indicator requires opaque nontransmissive Principled branches')
    objects=sorted(scene.objects,key=lambda o:o.name);bones=[(o,b.name) for o in objects if o.type=='ARMATURE' for b in o.pose.bones]
    if len(bones)>512 or scene.frame_end*(len(objects)+len(bones))>500000:raise ValueError('Feedback protection exceeds bounded work')
    geometry={o.name:geometry_identity(scene,o) for o in objects if o.type=='ARMATURE'}
    def snapshot():
        data=np.asarray([list(map(list,o.matrix_world)) for o in objects]+[list(map(list,o.matrix_world@o.pose.bones[n].matrix)) for o,n in bones],float)
        if not np.isfinite(data).all():raise ValueError('Nonfinite feedback scene matrix')
        return data
    reference=[];rows=[];previous=None;vertices=0;receiver_matrix=np.asarray(receiver.matrix_world).copy();r0,r1,_=bounds(receiver)
    if np.any(r1[:2]-r0[:2]<=2*plan['xy_margin_H']*h):raise ValueError('Receiver has no usable inner footprint after margins')
    for frame in range(1,scene.frame_end+1):
        scene.frame_set(frame);bpy.context.view_layer.update();reference.append(snapshot())
        if np.max(np.abs(np.asarray(receiver.matrix_world)-receiver_matrix))>1e-7:raise ValueError('Receiver must remain static throughout the clip')
        if plan['search_frames'][0]<=frame<=plan['search_frames'][1]:
            points=evaluated_points(prop);a=points.min(0);b=points.max(0);vertices+=len(points)
            if vertices>5000000:raise ValueError('Feedback prop sampling exceeds5000000 vertex-frames')
            if previous is not None and previous.shape!=points.shape:raise ValueError('Feedback prop topology must stay fixed across samples')
            step=float(np.max(np.linalg.norm(points-previous,axis=1))/h) if previous is not None else None;previous=points.copy();inside=bool(np.all(a[:2]>=r0[:2]+plan['xy_margin_H']*h) and np.all(b[:2]<=r1[:2]-plan['xy_margin_H']*h));gap=float((a[2]-r1[2])/h);extent=float((b[2]-a[2])/h);qualifies=inside and plan['bottom_gap_H'][0]<=gap<=plan['bottom_gap_H'][1] and extent<=plan['max_prop_height_H'] and step is not None and step<=plan['max_step_H']
            rows.append({'frame':frame,'inside':inside,'bottom_gap_H':gap,'prop_height_H':extent,'step_H':step,'qualifies':bool(qualifies)})
    event=confirmation_frame(rows,plan['stable_frames'])
    if event is None:raise ValueError('No stable placement satisfies the declared geometric conditions; no indicator material changed')
    if event+plan['ramp_frames']>scene.frame_end:raise ValueError('Not enough source time for the declared response ramp')
    material=original.copy();material.name=original.name+' / placement response'
    if material.node_tree==original.node_tree:raise ValueError('Independent copied indicator node tree required')
    indicator.material_slots[0].link='OBJECT';indicator.material_slots[0].material=material;nt=material.node_tree;output=next(n for n in nt.nodes if n.type=='OUTPUT_MATERIAL' and n.is_active_output);old_surface=output.inputs['Surface'].links[0].from_socket
    control=nt.nodes.new('ShaderNodeValue');control.name='Scene response weight';control.outputs[0].default_value=0
    factor=nt.nodes.new('ShaderNodeMath');factor.operation='MULTIPLY';factor.name='Scene response bounded mix';nt.links.new(control.outputs[0],factor.inputs[0]);factor.inputs[1].default_value=plan['mix']
    emission=nt.nodes.new('ShaderNodeEmission');emission.name='Scene response emission';emission.inputs['Color'].default_value=tuple(plan['on_color'])+(1,);emission.inputs['Strength'].default_value=plan['emission_strength']
    surface=nt.nodes.new('ShaderNodeMixShader');surface.name='Scene response original-style mix';nt.links.new(factor.outputs[0],surface.inputs[0]);nt.links.new(old_surface,surface.inputs[1]);nt.links.new(emission.outputs[0],surface.inputs[2]);nt.links.new(surface.outputs[0],output.inputs['Surface'])
    aovs=[n for n in nt.nodes if n.type=='OUTPUT_AOV' and n.aov_name=='HX_BloomWeight']
    if len(aovs)>1:raise ValueError('Ambiguous original Bloom-weight AOV')
    aov=aovs[0] if aovs else nt.nodes.new('ShaderNodeOutputAOV');aov.aov_name='HX_BloomWeight';old_weight=aov.inputs['Value'].links[0].from_socket if aov.inputs['Value'].is_linked else None;old_value=aov.inputs['Value'].default_value
    inverse=nt.nodes.new('ShaderNodeMath');inverse.operation='SUBTRACT';inverse.inputs[0].default_value=1;nt.links.new(factor.outputs[0],inverse.inputs[1]);base_weight=nt.nodes.new('ShaderNodeMath');base_weight.operation='MULTIPLY'
    if old_weight:nt.links.new(old_weight,base_weight.inputs[0])
    else:base_weight.inputs[0].default_value=old_value
    nt.links.new(inverse.outputs[0],base_weight.inputs[1]);overlay_weight=nt.nodes.new('ShaderNodeMath');overlay_weight.operation='MULTIPLY';overlay_weight.inputs[0].default_value=plan['bloom_weight'];nt.links.new(factor.outputs[0],overlay_weight.inputs[1]);combined=nt.nodes.new('ShaderNodeMath');combined.operation='ADD';nt.links.new(base_weight.outputs[0],combined.inputs[0]);nt.links.new(overlay_weight.outputs[0],combined.inputs[1]);nt.links.new(combined.outputs[0],aov.inputs['Value'])
    av=next((a for a in scene.view_layers[0].aovs if a.name=='HX_BloomWeight'),None) or scene.view_layers[0].aovs.add();av.name='HX_BloomWeight';av.type='VALUE'
    weights=[]
    for frame in range(1,scene.frame_end+1):
        w=response_weight(frame,event,plan['ramp_frames']);control.outputs[0].default_value=w;control.outputs[0].keyframe_insert('default_value',frame=frame);weights.append(w)
    for curve in material.node_tree.animation_data.action.fcurves:
        for key in curve.keyframe_points:key.interpolation='LINEAR'
    maximum=0.
    for frame,expected in enumerate(reference,1):scene.frame_set(frame);bpy.context.view_layer.update();maximum=max(maximum,float(np.max(np.abs(snapshot()-expected))))
    if maximum>1e-5 or geometry!={o.name:geometry_identity(scene,o) for o in objects if o.type=='ARMATURE'}:raise ValueError('Feedback changed protected scene/character state')
    scene.frame_set(1)
    return {'status':'placement-response-baked-await-output-and-visual-checks','source_event_frame':event,'source_full_response_frame':event+plan['ramp_frames'],'source_fps':scene.render.fps/scene.render.fps_base,'rows':rows,'plan':plan,'step_metric':'maximum evaluated corresponding vertex displacement per source frame, including rotation','material_mode':'independent copy, preserve original surface and Bloom input at zero, bounded emission overlay at confirmation','indicator_material_before':original.name,'indicator_material_after':material.name,'protected_bone_object_world_max_error':maximum,'character_rest_mesh_weights_morphs_unchanged':True,'no_response_before_confirmation':all(v==0 for v in weights[:event]),'prop_vertex_frames':vertices,'scope':'One latched material response after explicit consecutive source integer samples of evaluated bbox containment, signed bottom gap, flatness and maximum vertex step. Receiver is a static axis-aligned cuboid with a covered bevel margin. Not closed-volume contact, friction, a live sensor, continuous/subframe stability or artistic/naturalness acceptance. Indicator is an external existing mesh; only its independent object material is changed.'}

def main(arguments=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('blend','character','plan','output','report'):parser.add_argument('--'+key,required=True,type=Path)
    a=parser.parse_args(arguments if arguments is not None else sys.argv[sys.argv.index('--')+1:]);paths={k:getattr(a,k).resolve() for k in ('blend','character','plan','output','report')}
    if len(set(paths.values()))!=5 or paths['output'].suffix.lower()!='.blend' or paths['report'].suffix.lower()!='.json' or paths['output'].exists() or paths['report'].exists():raise ValueError('Distinct inputs and new.blend/.json outputs required')
    hashes={p:sha(p) for p in list(paths.values())[:3]};document=load_json(paths['plan']);character=load_json(paths['character']);bpy.ops.wm.open_mainfile(filepath=str(paths['blend']),load_ui=False,use_scripts=False);result=bake(bpy.context.scene,character,document)
    if any(sha(p)!=value for p,value in hashes.items()):raise ValueError('Feedback input changed during bake')
    paths['output'].parent.mkdir(parents=True,exist_ok=True);paths['report'].parent.mkdir(parents=True,exist_ok=True);bpy.ops.wm.save_as_mainfile(filepath=str(paths['output']));result.update(schema=1,input_scene_sha256=hashes[paths['blend']],character_sha256=hashes[paths['character']],plan_sha256=hashes[paths['plan']],output_scene_sha256=sha(paths['output']),writer_sha256=sha(Path(__file__)),dependency_sha256={name:sha(Path(__file__).with_name(name)) for name in ('scene_feedback_plan.py','bake_scene_tempo.py','scene_tempo_plan.py','body_motion_runtime.py','elbow_pole_plan.py')});paths['report'].write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),'utf-8');print('SCENE_RESPONSE_BAKED',result['source_event_frame'],result['protected_bone_object_world_max_error'],flush=True)
if __name__=='__main__':main()
