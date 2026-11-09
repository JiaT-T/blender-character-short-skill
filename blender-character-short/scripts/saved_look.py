"""Transfer a reviewed packed look without replacing the target MMD/MMR rig."""
from pathlib import Path
import argparse,json,sys,datetime
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy,numpy as np
import scene_integrity as pi
from production_contract import sha,digest,declared_file,write_json

SKIP={'rna_type','type','inputs','outputs','internal_links','dimensions','parent','name','select','location','width','height','color','use_custom_color','show_options','show_preview','show_texture','hide','mute','label','bl_idname','bl_label','bl_description','bl_icon','bl_static_type','bl_width_default','bl_width_min','bl_width_max','bl_height_default','bl_height_min','bl_height_max'}
def node_properties(node):
    result={}
    for p in node.bl_rna.properties:
        k=p.identifier
        if k in SKIP or p.is_readonly:continue
        if p.type in ('BOOLEAN','INT','FLOAT','STRING','ENUM'):
            v=getattr(node,k);result[k]=list(v) if getattr(p,'is_array',False) else v
    return result
def socket_value(socket):
    if not hasattr(socket,'default_value'):return None
    v=socket.default_value
    if isinstance(v,(str,int,float,bool)):return v
    try:return list(v)
    except TypeError:return None
def graph_identity(tree,scene):
    nodes={}
    for n in tree.nodes:
        d={'type':n.bl_idname,'muted':n.mute,'properties':node_properties(n),'inputs':[socket_value(s) for s in n.inputs]}
        if n.bl_idname=='CompositorNodeImage' and n.image:
            im=n.image
            if not im.packed_file:raise ValueError('Compositor look image must be packed')
            d['image']={'sha256':__import__('hashlib').sha256(im.packed_file.data).hexdigest(),'colorspace':im.colorspace_settings.name}
        if hasattr(n,'node_tree') and n.node_tree:d['group']=graph_identity(n.node_tree,scene)
        if hasattr(n,'scene') and n.scene:d['scene']='self' if n.scene==scene else n.scene.name
        nodes[n.name]=d
    return {'nodes':nodes,'links':sorted([l.from_node.name,list(l.from_node.outputs).index(l.from_socket),l.to_node.name,list(l.to_node.inputs).index(l.to_socket)] for l in tree.links)}
def clone_compositor(source,target):
    if not source.use_nodes or not source.node_tree:raise ValueError('Reviewed native compositor missing')
    allowed={'CompositorNodeRLayers','CompositorNodeComposite','CompositorNodeViewer','CompositorNodeMath','CompositorNodeSeparateColor','CompositorNodeCombineColor','CompositorNodeSepRGBA','CompositorNodeCombRGBA','CompositorNodeMixRGB','CompositorNodeSetAlpha','CompositorNodePremulKey','CompositorNodeGlare','CompositorNodeImage','CompositorNodeMapUV','CompositorNodeCombineXYZ','CompositorNodeSeparateXYZ','CompositorNodeGroup','NodeReroute','NodeFrame'}
    unknown={n.bl_idname for n in source.node_tree.nodes}-allowed
    if unknown:raise ValueError('Unreviewed compositor node types: '+repr(sorted(unknown)))
    target.use_nodes=True;target.node_tree.nodes.clear();mapping={}
    for old in source.node_tree.nodes:
        new=target.node_tree.nodes.new(old.bl_idname);new.name=old.name;new.label=old.label;new.location=old.location;new.mute=old.mute
        for k in ['image','node_tree']:
            if k=='image' and old.bl_idname!='CompositorNodeImage':continue
            if hasattr(old,k) and getattr(old,k):setattr(new,k,getattr(old,k))
        if hasattr(old,'scene'):new.scene=target if old.scene==source else old.scene
        for k,v in node_properties(old).items():
            current=getattr(new,k)
            if (list(current) if getattr(old.bl_rna.properties[k],'is_array',False) else current)==v:continue
            try:setattr(new,k,v)
            except Exception as exc:raise ValueError('Cannot preserve compositor property '+old.bl_idname+'.'+k+'='+repr(v)) from exc
        for a,b in zip(old.inputs,new.inputs):
            if hasattr(a,'default_value') and socket_value(a) is not None:b.default_value=socket_value(a)
        mapping[old.name]=new
    for old in source.node_tree.nodes:
        if old.parent:mapping[old.name].parent=mapping[old.parent.name]
    for link in source.node_tree.links:target.node_tree.links.new(mapping[link.from_node.name].outputs[list(link.from_node.outputs).index(link.from_socket)],mapping[link.to_node.name].inputs[list(link.to_node.inputs).index(link.to_socket)])
    if graph_identity(source.node_tree,source)!=graph_identity(target.node_tree,target):raise ValueError('Native compositor transfer differs')
    for field in ['view_transform','look','exposure','gamma','use_curve_mapping']:
        if hasattr(source.view_settings,field):setattr(target.view_settings,field,getattr(source.view_settings,field))
    target.display_settings.display_device=source.display_settings.display_device
    for field in ['use_compositing','compositor_device','compositor_precision','film_transparent']:
        if hasattr(source.render,field):setattr(target.render,field,getattr(source.render,field))
    return digest(graph_identity(target.node_tree,target))
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--plan',required=True);a=parser.parse_args(sys.argv[sys.argv.index('--')+1:]);p=Path(a.plan).resolve();plan=json.loads(p.read_text('utf-8'));base=p.parent
    target_input=declared_file(plan['target'],base);donor_input=declared_file(plan['donor'],base);profile_input=declared_file(plan['profile'],base);profile=json.loads(Path(profile_input['path']).read_text('utf-8'))
    output=(base/plan['output']).resolve();report=(base/plan['report']).resolve()
    if output.exists() or report.exists():raise FileExistsError('Use a new look version')
    bpy.ops.wm.open_mainfile(filepath=target_input['path'],load_ui=False,use_scripts=False);scene=bpy.context.scene
    if scene.render.engine!='BLENDER_EEVEE_NEXT':raise ValueError('Reviewed Eevee baseline required; no implicit engine conversion')
    body=bpy.data.objects[profile['target_mesh']];old_objects={o.name:o for o in bpy.data.objects};old_cols={c.name:c for c in bpy.data.collections};rigs=[o for o in scene.objects if o.type=='ARMATURE'];actions={v.name:v for v in bpy.data.actions};allowed=set()
    def protected():
        record=pi._mesh(body.data)
        for attr in allowed:record['attributes'].pop(attr,None)
        return {'rig_objects':digest({o.name:pi._object(o) for o in rigs}),'rig_data':digest({o.name:pi._armature(o.data) for o in rigs}),'body':digest(pi._object(body)),'mesh':digest(record),'actions':digest({n:pi._action(v) for n,v in actions.items()}),'camera':scene.camera.name if scene.camera else None,'cuts':[(m.name,m.frame,m.camera.name if m.camera else None) for m in scene.timeline_markers],'range':[scene.frame_start,scene.frame_end],'fps':[scene.render.fps,scene.render.fps_base]}
    bpy.context.view_layer.update();before=protected()
    with bpy.data.libraries.load(donor_input['path'],link=False) as (src,dst):
        names=list(src.objects);col_names=list(src.collections);dst.objects=names.copy();dst.collections=col_names.copy();dst.scenes=[profile['donor_scene']]
    objects=dict(zip(names,dst.objects));collections=dict(zip(col_names,dst.collections));donor_scene=dst.scenes[0];donor=objects[profile['donor_mesh']]
    if donor_scene.render.engine!=scene.render.engine:raise ValueError('Look donor engine mismatch')
    # Geometry/UV identity is a real mapping precondition, not a material-name guess.
    own=pi._mesh(body.data);other=pi._mesh(donor.data)
    for k in ['coordinates','loop_vertices','polygon_loop_start','polygon_loop_total','uv_layers','has_custom_normals','corner_normals']:
        if k not in own or own[k]!=other[k]:raise ValueError('Look mesh mapping differs: '+k)
    a=np.empty(len(body.data.polygons),np.int32);b=np.empty(len(donor.data.polygons),np.int32);body.data.polygons.foreach_get('material_index',a);donor.data.polygons.foreach_get('material_index',b)
    if not np.array_equal(a,b):raise ValueError('Source/target polygon material assignments differ')
    if len(body.data.materials)!=len(donor.data.materials):raise ValueError('Material slot count differs')
    for name in profile.get('look_attributes',[]):
        attr=donor.data.color_attributes[name]
        if body.data.color_attributes.get(name):raise ValueError('Look attribute already exists; do not overlay twice')
        dest=body.data.color_attributes.new(name=name,type=attr.data_type,domain=attr.domain);values=np.empty(len(attr.data)*4,np.float32);attr.data.foreach_get('color',values);dest.data.foreach_set('color',values);allowed.add(name)
    for i,mat in enumerate(donor.data.materials):
        if body.data.materials[i].name!=mat.get('hx_original_slot'):raise ValueError('Unreviewed material slot mapping')
        body.data.materials[i]=mat
    for old_name,target_name in profile.get('object_aliases',{}).items():
        if old_name not in objects or target_name not in old_objects:raise ValueError('Missing explicit object mapping')
    aliases=dict(profile.get('object_aliases',{}));remapped=[]
    for name,obj in objects.items():
        target=aliases.get(name,name)
        if target in old_objects:obj.user_remap(old_objects[target]);remapped.append(name)
    for name,col in collections.items():
        if name in old_cols:col.user_remap(old_cols[name])
    for col in list(donor_scene.collection.children):
        if col.name.startswith('HX_') and col.name not in scene.collection.children:scene.collection.children.link(col)
    helpers=[]
    for name,obj in objects.items():
        if name.startswith('HX_') and name not in remapped:
            if obj.name not in scene.objects:scene.collection.objects.link(obj)
            helpers.append(obj.name)
    # Transfer the saved node graph exactly. No reimplementation and no second LUT/Bloom pass.
    compositor_hash=clone_compositor(donor_scene,scene);scene.world=donor_scene.world
    for name in profile.get('source_lights',[]):
        if name not in old_objects or name not in objects:raise ValueError('Declared lighting object missing')
        old_objects[name].data=objects[name].data
    for k,v in donor_scene.items():
        if k.startswith(('huaxu_','hx_','HX_')):scene[k]=v
    for name in remapped:bpy.data.objects.remove(objects[name],do_unlink=True)
    donor_scene.user_remap(scene);bpy.data.scenes.remove(donor_scene)
    for name,col in collections.items():
        if name in old_cols:bpy.data.collections.remove(col)
    bpy.context.view_layer.update();after=protected();checks={k:before[k]==after[k] for k in before}
    result={'target_input':target_input,'look_donor':donor_input,'profile':profile_input,'protected_checks':checks,'compositor_sha256':compositor_hash,'helpers':helpers,'producer':{n:sha(Path(__file__).with_name(n)) for n in ['saved_look.py','scene_integrity.py','production_contract.py']},'accepted':False,'ui_used':False,'post_mode':'saved-native','website_pixel_parity':False}
    if not all(checks.values()):write_json(report,result);raise ValueError('Protected baseline changed during look transfer')
    scene['short_post_chain']='saved-native';scene['short_look_identity']=json.dumps({'donor_sha256':donor_input['sha256'],'profile_sha256':profile_input['sha256'],'compositor_sha256':compositor_hash})
    if 'shadow_pool_mib' in profile:scene.eevee.shadow_pool_size=str(profile['shadow_pool_mib'])
    bpy.ops.file.pack_all();output.parent.mkdir(parents=True,exist_ok=True);bpy.ops.wm.save_as_mainfile(filepath=str(output),check_existing=False)
    result.update(accepted=True,output=str(output),output_sha256=sha(output),target_unchanged=sha(target_input['path'])==target_input['sha256'],donor_unchanged=sha(donor_input['path'])==donor_input['sha256'],post_applied_once=True,utc=datetime.datetime.now(datetime.timezone.utc).isoformat());write_json(report,result);print(json.dumps(result,ensure_ascii=True))
if __name__=='__main__':main()
