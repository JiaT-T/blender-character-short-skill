"""Prepare explicitly mapped PMX material slots; no filename inference.
All asset, material, texture and coordinate mappings come from character config.
"""
from pathlib import Path
import copy,json
import bpy,numpy as np
from mathutils import Vector,kdtree
from render_source_probe import build_shader_blueprint,read_glb
from character_material import build_character,Graph

def flat_material(name,image,rgba,transparent=False,hidden=False,weight=.03):
    m=bpy.data.materials.new('Prepared '+name);m.use_nodes=True;g=Graph(m);em=g.node('ShaderNodeEmission','Base image display adaptation');coverage=rgba[3]
    if image:
        tex=g.node('ShaderNodeTexImage','Original PMX base');tex.image=image;image.colorspace_settings.name='sRGB';image.alpha_mode='STRAIGHT';g.put(tex.outputs['Color'],em.inputs[0]);coverage=tex.outputs['Alpha']
    else:em.inputs[0].default_value=rgba
    output=g.node('ShaderNodeOutputMaterial','Output')
    if transparent or hidden:
        tr=g.node('ShaderNodeBsdfTransparent','Coverage');mix=g.node('ShaderNodeMixShader','Coverage mix');g.put(0 if hidden else coverage,mix.inputs[0]);g.put(tr.outputs[0],mix.inputs[1]);g.put(em.outputs[0],mix.inputs[2]);g.put(mix.outputs[0],output.inputs[0]);m.surface_render_method='BLENDED'
    else:g.put(em.outputs[0],output.inputs[0])
    g.aov('HX_BloomWeight',0 if hidden else weight,'VALUE');return m

def prepare(scene,meshes,cfg):
    settings=cfg['materials'];by_name=settings['slots'];audit=[];blueprint=None;source=None;texture_paths={};texture_defs=None;records={}
    if settings.get('dorm_blueprint'):blueprint,_=build_shader_blueprint(settings['dorm_blueprint'],scene)
    if settings.get('source_glb'):
        _,_,source,read=read_glb(settings['source_glb']);texture_defs=source['textures'];manifest=json.loads((Path(settings['source_textures'])/'manifest.json').read_text('utf-8'));images={v['index']:Path(v['path']) for v in manifest};texture_paths={i:images[t.get('source',t.get('extensions',{}).get('EXT_texture_webp',{}).get('source'))] for i,t in enumerate(texture_defs)}
        for m in source['meshes']:
            for primitive in m['primitives']:
                attrs=primitive['attributes']
                if '_PGRCOLOR' in attrs:
                    uv=read(attrs['TEXCOORD_0']);vc=read(attrs['_PGRCOLOR']);tree=kdtree.KDTree(len(uv))
                    for i,p in enumerate(uv):tree.insert(Vector((p[0],1-p[1],0)),i)
                    tree.balance();records[primitive['material']]=(tree,vc)
    mapped={}
    for mesh in meshes:
        transfer_errors=[];attribute=None
        for slot_index,old in enumerate(list(mesh.data.materials)):
            if old is None:continue
            name=old.name
            if name not in by_name:raise ValueError('Unmapped PMX material slot: '+name)
            rule=by_name[name];tex=old.node_tree.nodes.get('mmd_base_tex') if old.use_nodes else None;image=tex.image if tex else None
            if rule.get('base_image'):
                p=Path(rule['base_image'])
                if not p.is_file():raise FileNotFoundError('Configured base image missing: '+str(p))
                image=bpy.data.images.load(str(p),check_existing=True)
            if rule['shader']=='dorm':
                mat=blueprint[rule.get('blueprint_material','HX_Dorm_Main')].copy();mat.name='Prepared '+name;nt=mat.node_tree;nt.nodes['Main'].image=image
                for link in list(nt.nodes['AlbedoBlend'].inputs[0].links):nt.links.remove(link)
                nt.nodes['AlbedoBlend'].inputs[0].default_value=0
                # PMX local orientation differs from the source GLB. Explicit
                # external basis applies to every constant world light vector.
                basis=np.array(settings['source_vector_basis'])
                for n in nt.nodes:
                    for s in n.inputs:
                        if s.type=='VECTOR' and not s.is_linked:
                            v=np.array(s.default_value[:]);
                            if any(np.max(np.abs(v-np.array(x)))<1e-6 for x in settings.get('transform_vectors',[])):s.default_value=basis@v
                detail={'shader':'Dorm formula on PMX body UV0','gaps':['PMX topology/normals differ','FaceMap removed because PMX face is separate geometry','source AO UV alignment requires actual-render check']}
            elif rule['shader']=='character':
                raw=copy.deepcopy(source['materials'][rule['source_material']]);paths=texture_paths.copy();main_index=raw['extras']['shader']['textures']['_MainTex']['index']
                if image:paths[main_index]=Path(bpy.path.abspath(image.filepath))
                attrs=list(mesh.data.attributes.keys())
                if rule.get('transfer_vertex_color'):
                    if attribute is None:attribute=mesh.data.attributes.get('_PGRCOLOR') or mesh.data.attributes.new('_PGRCOLOR','FLOAT_COLOR','CORNER')
                    tree,values=records[rule['source_material']];uv=mesh.data.uv_layers.active.data
                    for poly in mesh.data.polygons:
                        if poly.material_index!=slot_index:continue
                        for li in poly.loop_indices:
                            u,v=uv[li].uv;co,index,error=tree.find(Vector((u,v,0)));attribute.data[li].color=values[index];transfer_errors.append(float(error))
                    attrs=list(mesh.data.attributes.keys())
                mat,detail=build_character(raw,paths,texture_defs,settings['runtime'],attrs)
                detail['migration']='PMX base retained; source auxiliary maps by explicit slot mapping'
                if rule.get('transfer_vertex_color'):detail['gaps'].append('Source skin gate transferred by nearest UV corner; topology correspondence is an adaptation')
            elif rule['shader']=='flat':
                mat=flat_material(name,image,tuple(old.diffuse_color),rule.get('transparent',False),rule.get('hidden',False),rule.get('bloom_weight',.03));detail={'shader':'PMX supplied face/overlay adaptation','gaps':['Separate PMX face or effect has no exact source geometry/material equivalent']}
            else:raise ValueError('Unknown shader in slot '+name)
            mat['original_slot_name']=name;mesh.data.materials[slot_index]=mat;mapped[name]=mat;audit.append({'slot':name,'slot_index':slot_index,'base_image':image.filepath if image else None,**detail})
        if transfer_errors:audit.append({'mesh':mesh.name,'uv_skin_transfer_count':len(transfer_errors),'uv_error_max':max(transfer_errors),'uv_error_p95':float(np.percentile(transfer_errors,95)),'exact_fraction':sum(v<1e-5 for v in transfer_errors)/len(transfer_errors)})
    aovs=[('HX_BloomWeight','VALUE')]
    for name,typ in aovs:
        av=next((a for a in scene.view_layers[0].aovs if a.name==name),None) or scene.view_layers[0].aovs.add();av.name=name;av.type=typ
    return audit,mapped
