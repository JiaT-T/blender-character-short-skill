"""Blender 4.5 source-material probe; isolated factory startup only.

Consumes an external node blueprint and GLB, exports raw EXR/NPZ and editable
project. Does not imply website parity: camera, outline, AA and coverage have
separate acceptance checks. Third-party assets remain outside this script.
"""
import argparse,json,struct,sys,tempfile,hashlib,time
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector

def socket(xs,address):
    if isinstance(address,int) or str(address).isdecimal():return xs[int(address)]
    return next((s for s in xs if s.identifier==address),None) or xs[address]

def prop(obj,path,value):
    bits=path.split('.')
    for bit in bits[:-1]:obj=getattr(obj,bit)
    setattr(obj,bits[-1],value)

def build_shader_blueprint(path,scene):
    path=Path(path);spec=json.loads(path.read_text('utf-8'));images={};built={}
    for name,desc in spec['images'].items():
        p=(path.parent/desc['file']).resolve()
        if not p.is_file():raise FileNotFoundError('Blueprint image missing: '+str(p))
        im=bpy.data.images.load(str(p),check_existing=False);im.colorspace_settings.name=desc['colorspace'];im.alpha_mode=desc['alpha_mode'];images[name]=im
    for desc in spec['trees']:
        if desc['tree_type']!='ShaderNodeTree':continue
        m=bpy.data.materials.new(desc['name']);m.use_nodes=True;nt=m.node_tree;nt.nodes.clear();nodes={}
        for key,value in spec.get('material_settings',{}).get(desc['name'],{}).items():prop(m,key,value)
        for nd in desc['nodes']:
            n=nt.nodes.new(nd['type']);n.name=nd['id'];n.label=nd.get('label',nd['id']);nodes[n.name]=n
            for key,value in nd.get('properties',{}).items():prop(n,key,value)
            if 'image' in nd:n.image=images[nd['image']]
            if 'location' in nd:n.location=nd['location']
            for key,value in nd.get('inputs',{}).items():socket(n.inputs,key).default_value=value
            for key,value in nd.get('outputs',{}).items():socket(n.outputs,key).default_value=value
        for link in desc['links']:
            a,sa=link['from'];b,sb=link['to'];nt.links.new(socket(nodes[a].outputs,sa),socket(nodes[b].inputs,sb))
        built[m.name]=m
    return built,spec

def read_glb(path):
    raw=Path(path).read_bytes();offset=12;chunks=[]
    while offset<len(raw):
        length,kind=struct.unpack_from('<II',raw,offset);offset+=8;chunks.append((kind,raw[offset:offset+length]));offset+=length
    doc=json.loads(next(v for k,v in chunks if k==0x4e4f534a));binary=next(v for k,v in chunks if k==0x004e4942)
    def accessor(i):
        a=doc['accessors'][i];v=doc['bufferViews'][a['bufferView']];fmt='<'+{5120:'b',5121:'B',5122:'h',5123:'H',5125:'I',5126:'f'}[a['componentType']]*{'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}[a['type']]
        step=v.get('byteStride',struct.calcsize(fmt));base=v.get('byteOffset',0)+a.get('byteOffset',0)
        values=np.array([struct.unpack_from(fmt,binary,base+j*step) for j in range(a['count'])])
        if a.get('normalized'):
            if a['componentType'] in (5121,5123):values=values/(255 if a['componentType']==5121 else 65535)
            elif a['componentType'] in (5120,5122):values=np.maximum(values/(127 if a['componentType']==5120 else 32767),-1)
        return values
    return raw,chunks,doc,accessor

def import_glb(path,tempdir):
    raw,chunks,doc,read=read_glb(path);records=[]
    for mi,mesh in enumerate(doc['meshes']):
        for pi,p in enumerate(mesh['primitives']):
            record={'mesh_index':mi,'primitive':pi,'name':mesh.get('name',''),'material':p.get('material'),'attrs':{k:read(i) for k,i in p['attributes'].items()},'indices':read(p['indices']).ravel() if 'indices' in p else None}
            records.append(record);p['attributes']={k:i for k,i in p['attributes'].items() if not k.startswith('_')}
    payload=json.dumps(doc,separators=(',',':'),ensure_ascii=False).encode('utf-8');payload+=b' '*(-len(payload)%4)
    body=b''.join(struct.pack('<II',len(payload if k==0x4e4f534a else v),k)+(payload if k==0x4e4f534a else v) for k,v in chunks)
    with tempfile.NamedTemporaryFile(suffix='.glb',prefix='compat_',dir=tempdir,delete=False) as h:
        h.write(struct.pack('<III',0x46546c67,2,12+len(body))+body);tmp=Path(h.name)
    before=set(bpy.data.objects)
    try:bpy.ops.import_scene.gltf(filepath=str(tmp))
    finally:tmp.unlink(missing_ok=True)
    # The glTF importer also creates unlinked custom bone-shape mesh datablocks.
    # Only scene-linked objects correspond to imported asset geometry.
    imported=[o for o in bpy.context.scene.objects if o not in before]
    custom_shapes={pb.custom_shape for arm in imported if arm.type=='ARMATURE' for pb in arm.pose.bones if pb.custom_shape}
    objects=[o for o in imported if o not in custom_shapes];audit=[]
    for shape in custom_shapes:shape.hide_render=True
    for o in objects:
        if o.type!='MESH':continue
        verts=np.array([v.co[:] for v in o.data.vertices]);matches=[]
        for rec in records:
            p=rec['attrs']['POSITION']
            if len(p)!=len(verts):continue
            target=p[:,[0,2,1]]*np.array([1,-1,1]);err=np.max(np.abs(verts-target))
            if err<1e-5:matches.append((rec,float(err)))
        if len(matches)!=1:
            raise ValueError(f'Cannot uniquely restore source attributes for {o.name}: {len(matches)} position matches; no guessed mapping allowed')
        rec,err=matches[0];restored=[]
        for name,values in rec['attrs'].items():
            if not name.startswith('_'):continue
            channels=values.shape[1]
            if channels==2:
                values=np.pad(values,((0,0),(0,1)));kind,field='FLOAT_VECTOR','vector'
            elif channels==3:kind,field='FLOAT_VECTOR','vector'
            elif channels==4:kind,field='FLOAT_COLOR','color'
            else:raise ValueError('Unsupported custom attribute '+name)
            old=o.data.attributes.get(name)
            if old:o.data.attributes.remove(old)
            a=o.data.attributes.new(name,kind,'POINT');a.data.foreach_set(field,values.astype(np.float32).ravel());restored.append(name)
        o['source_material_index']=rec['material'];o['source_mesh_index']=rec['mesh_index']
        audit.append({'object':o.name,'source_mesh':rec['mesh_index'],'source_material':rec['material'],'position_error':err,'restored':restored})
    return objects,doc,records,audit,hashlib.sha256(raw).hexdigest()

def setup_raw(scene,out,passes):
    scene.use_nodes=True;nt=scene.node_tree;nt.nodes.clear();rl=nt.nodes.new('CompositorNodeRLayers');co=nt.nodes.new('CompositorNodeComposite');nt.links.new(rl.outputs['Image'],co.inputs[0])
    fo=nt.nodes.new('CompositorNodeOutputFile');fo.name='Raw stage outputs';fo.base_path=str(out);fo.format.file_format='OPEN_EXR';fo.format.color_depth='32';fo.format.color_mode='RGBA';fo.file_slots.clear()
    for name in passes:fo.file_slots.new(name);fo.file_slots[-1].path=name+'_';nt.links.new(rl.outputs[name],fo.inputs[name])
    return fo

def static_source_outline(scene,obj,record,cfg,material):
    """Source outline.vert extrusion for a verified undeformed imported GLB.

    Refuses animated/deformed input until a matching skinned tangent basis is
    supplied. This keeps the static proof separate from a production fallback.
    """
    dg=bpy.context.evaluated_depsgraph_get();ev=obj.evaluated_get(dg);me=ev.to_mesh()
    try:
        rest=np.array([v.co[:] for v in obj.data.vertices]);actual=np.array([v.co[:] for v in me.vertices]);err=float(np.max(np.abs(actual-rest)))
        attrs=record['attrs'];normals=attrs['NORMAL'][:,[0,2,1]]*np.array([1,-1,1]);tangent=attrs['TANGENT'];T=tangent[:,[0,2,1]]*np.array([1,-1,1]);skin_error=err
        if err>1e-5:
            mods=[m for m in obj.modifiers if m.type=='ARMATURE' and m.show_render]
            if len(mods)!=1 or mods[0].use_deform_preserve_volume:raise ValueError('Cannot reproduce source linear skinning basis for outline')
            arm=mods[0].object;to_arm=arm.matrix_world.inverted()@obj.matrix_world;from_arm=to_arm.inverted();matrices={}
            for vg in obj.vertex_groups:
                pb=arm.pose.bones.get(vg.name)
                if pb:matrices[vg.index]=np.array(from_arm@pb.matrix@pb.bone.matrix_local.inverted()@to_arm)
            deform=np.zeros((len(rest),4,4),dtype=np.float64)
            for i,vtx in enumerate(obj.data.vertices):
                total=0
                for group in vtx.groups:
                    if group.group in matrices:deform[i]+=matrices[group.group]*group.weight;total+=group.weight
                if total>0:deform[i]/=total
                else:deform[i]=np.eye(4)
            predicted=np.einsum('nij,nj->ni',deform,np.concatenate([rest,np.ones((len(rest),1))],axis=1))[:,:3]
            skin_error=float(np.max(np.abs(predicted-actual)))
            if skin_error>2e-5:raise ValueError(f'Outline skinning positions differ from evaluated mesh by {skin_error}')
            normals=np.einsum('nij,nj->ni',deform[:,:3,:3],normals);T=np.einsum('nij,nj->ni',deform[:,:3,:3],T)
        B=np.cross(normals,T)*tangent[:,3:4]
        smooth=attrs[cfg['smooth_attribute']]*2-1;sn=T*smooth[:,0:1]+B*smooth[:,1:2]+normals*smooth[:,2:3]
        # The attribute's presence does not enable the source shader branch.
        # Dorm outline's verified variant has no PGR_VERTEX_COLOR define.
        vertex_control=bool(cfg.get('vertex_color_enabled',False))
        control=attrs[cfg['color_attribute']] if vertex_control else np.ones((len(actual),4),np.float32)
        MV=scene.camera.matrix_world.inverted()@obj.matrix_world;M=np.array(MV);pts=np.concatenate([actual,np.ones((len(actual),1))],axis=1)@M.T
        proj=scene.camera.calc_matrix_camera(dg,x=scene.render.resolution_x,y=scene.render.resolution_y,scale_x=scene.render.pixel_aspect_x,scale_y=scene.render.pixel_aspect_y)
        push=pts[:,:3]/np.maximum(np.linalg.norm(pts[:,:3],axis=1,keepdims=True),1e-12)*(cfg['z_max_offset']*cfg['distance_scale']*.5)
        width=np.sqrt(np.maximum(-pts[:,2],0)/proj[1][1]/cfg['distance_scale'])*cfg['distance_scale']*cfg['width']*.018*control[:,2]
        direction=sn@M[:3,:3].T;direction[:,2]=.001;direction[:,:2]/=np.linalg.norm(direction,axis=1,keepdims=True)
        q=pts[:,:3]+push;q[:,:2]+=direction[:,:2]*width[:,None];q[:,2]+=cfg['z_offset'];world=np.concatenate([q,np.ones((len(q),1))],axis=1)@np.array(scene.camera.matrix_world).T
        faces=[tuple(reversed(p.vertices)) for p in me.polygons];mesh=bpy.data.meshes.new('Source outline projected hull');mesh.from_pydata(world[:,:3].tolist(),[],faces);mesh.update();outline=bpy.data.objects.new('Source outline projected hull',mesh);scene.collection.objects.link(outline);mesh.materials.append(material)
        attr=mesh.attributes.new(cfg['color_attribute'],'FLOAT_COLOR','POINT');attr.data.foreach_set('color',control.astype(np.float32).ravel())
        # Vertex control.b also discards the fragment below .1 in outline.frag.
        nt=material.node_tree;output=next(n for n in nt.nodes if n.type=='OUTPUT_MATERIAL');surface=output.inputs['Surface'].links[0].from_socket
        at=nt.nodes.new('ShaderNodeAttribute');at.attribute_name=cfg['color_attribute'];sep=nt.nodes.new('ShaderNodeSeparateRGB');nt.links.new(at.outputs['Color'],sep.inputs[0]);gate=nt.nodes.new('ShaderNodeMath');gate.operation='LESS_THAN';gate.inputs[1].default_value=.1;nt.links.new(sep.outputs['B'],gate.inputs[0]);tr=nt.nodes.new('ShaderNodeBsdfTransparent');mix=nt.nodes.new('ShaderNodeMixShader');nt.links.new(gate.outputs[0],mix.inputs[0]);nt.links.new(surface,mix.inputs[1]);nt.links.new(tr.outputs[0],mix.inputs[2]);nt.links.new(mix.outputs[0],output.inputs['Surface']);material.surface_render_method='DITHERED'
        return {'bind_position_max_error':err,'linear_skin_position_max_error':skin_error,'vertices':len(actual),'vertex_color_enabled':vertex_control,'projection_y':proj[1][1],'width_range':list(map(float,[width.min(),width.max()])),'scope':'single-frame verified linear skinning basis; no continuous animation or AA equivalence claim'}
    finally:ev.to_mesh_clear()

def main():
    p=argparse.ArgumentParser();p.add_argument('--asset',required=True);p.add_argument('--blueprint',required=True);p.add_argument('--config',required=True);p.add_argument('--output',required=True);p.add_argument('--render',action='store_true');a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True);cfg=json.loads(Path(a.config).read_text('utf-8'))
    if (out/'probe.blend').exists():raise FileExistsError('Version directory already contains probe.blend; use a new output directory')
    bpy.ops.wm.read_factory_settings(use_empty=True);scene=bpy.context.scene;scene.render.engine='BLENDER_EEVEE_NEXT';scene.render.film_transparent=True;scene.render.resolution_x=cfg.get('width',640);scene.render.resolution_y=cfg.get('height',640);scene.render.resolution_percentage=100;scene.eevee.taa_render_samples=cfg.get('samples',32);scene.view_settings.view_transform='Standard';scene.view_settings.look='None';scene.view_settings.exposure=0;scene.view_settings.gamma=1
    mats,spec=build_shader_blueprint(a.blueprint,scene)
    objects,doc,records,audit,digest=import_glb(a.asset,out)
    selected=[]
    for o in objects:
        if o.type!='MESH':continue
        mapping=cfg['material_map'].get(str(o['source_material_index']))
        if mapping is None:o.hide_render=True;continue
        o.data.materials.clear();o.data.materials.append(mats[mapping]);selected.append(o)
    if not selected:raise ValueError('material_map selected no meshes')
    layer=scene.view_layers[0];passes=['Image']
    for av in spec['scene'].get('view_layer_aovs',[]):
        v=layer.aovs.add();v.name=av['name'];v.type=av['type'];passes.append(v.name)
    for item in cfg.get('diagnostic_aovs',[]):
        av=layer.aovs.add();av.name=item['name'];av.type=item.get('type','COLOR');passes.append(av.name)
        nt=mats[item['material']].node_tree;n=nt.nodes.new('ShaderNodeOutputAOV');n.aov_name=av.name;nt.links.new(socket(nt.nodes[item['node']].outputs,item.get('socket',0)),n.inputs['Color' if av.type=='COLOR' else 'Value'])
    bpy.context.view_layer.update();coords=[]
    for o in selected:
        ev=o.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh();coords.extend(ev.matrix_world@v.co for v in me.vertices);ev.to_mesh_clear()
    low=Vector([min(v[i] for v in coords) for i in range(3)]);high=Vector([max(v[i] for v in coords) for i in range(3)]);extent=high.z-low.z;center=(low+high)*.5
    cd=bpy.data.cameras.new('Source probe camera');cam=bpy.data.objects.new(cd.name,cd);scene.collection.objects.link(cam);cam.location=center+Vector(cfg['camera_offset'])*extent;target=center+Vector(cfg.get('target_offset',[0,0,0]))*extent;cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cd.type=cfg.get('camera_type','PERSP');cd.lens=cfg.get('lens',50);cd.ortho_scale=cfg.get('ortho_scale',1.2)*extent;scene.camera=cam
    outline_reports=[]
    if cfg.get('outline'):
        bpy.context.view_layer.update()
        for o in selected:
            rec=next(r for r in records if r['mesh_index']==o['source_mesh_index'])
            outline_reports.append(static_source_outline(scene,o,rec,cfg['outline'],mats[cfg['outline']['material']]))
    setup_raw(scene,out,passes);scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGBA';scene.render.filepath=str(out/'unprocessed-standard.png');bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(out/'probe.blend'))
    report={'asset_sha256':digest,'asset':str(Path(a.asset).resolve()),'blueprint':a.blueprint,'config':cfg,'blender':bpy.app.version_string,'import':audit,'bounds':[list(low),list(high)],'passes':passes,'strict_gaps':['outline geometry absent','SMAA absent','source camera/runtime parameters require matching'],'rendered':False}
    report['outline']=outline_reports
    if outline_reports:report['strict_gaps'].remove('outline geometry absent')
    if a.render:
        t=time.monotonic();bpy.ops.render.render(write_still=True);report['render_seconds']=time.monotonic()-t;arrays={}
        for name in passes:
            im=bpy.data.images.load(str(out/(name+'_0001.exr')),check_existing=False);arr=np.empty(len(im.pixels),dtype=np.float32);im.pixels.foreach_get(arr);arrays[name]=arr.reshape(im.size[1],im.size[0],4)
        np.savez_compressed(out/'raw.npz',rgba=arrays['Image'],weight=arrays['HX_BloomWeight'][...,:1]);report['rendered']=True;report['raw_rgba_max']=float(arrays['Image'].max());report['weight_max']=float(arrays['HX_BloomWeight'][...,0].max())
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print('SOURCE_PROBE',json.dumps(report,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
