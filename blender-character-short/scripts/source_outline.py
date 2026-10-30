"""Source-derived GLB outline geometry/material and frozen integer-frame bake.

Requires restored source attributes and the verified GLB import convention.
No PMX attribute guessing, live handler or topology change. Active source morphs
require verified named relative POSITION-only targets; other morphs are rejected.
"""
import json,math,hashlib
import numpy as np
import bpy
from mathutils import Matrix

CONTROL='HX_SourceOutlineControl'

def require_finite(label,*values):
    if any(not np.isfinite(value).all() for value in values):
        raise ValueError('Non-finite outline data: '+label)

def parameters(raw,global_tint=(1,1,1)):
    shader=raw['extras']['shader'];f=shader['floats'];colors=shader['colors'];keywords=shader['keywords']
    # Pinned bundle lf(), including its strict threshold and rounded constants.
    def linear(c):return [v*.0773993808 if v<.04045 else (v*.9478672986+.0521327014)**2.4 for v in c[:3]]
    return {'width':f['_XCharOutlineWidth'],'distance_scale':f['_XOutlineDitanceScale'],'z_max_offset':f['_XOutlineZMaxOffset'],'z_offset':f['_XOutlineZOffset'],'brightness':f['_XOutlineBrightness'],'bloom':f['_OutlineBloom'],'vertex_color_enabled':any(k in keywords for k in ['_MULTI_OUTLINE_COLOR','_OUTLINE_VERTEX_COLOR']),'multi_color':'_MULTI_OUTLINE_COLOR' in keywords,'colors_linear':[linear(colors['_OutlineColor'+(str(i) if i>1 else '')]) for i in range(1,6)],'global_tint':list(global_tint),'source_material':raw['name']}

def material(params,name):
    m=bpy.data.materials.new(name);m.use_nodes=True;m.use_backface_culling=True;m.surface_render_method='DITHERED';nt=m.node_tree;nt.nodes.clear()
    def mathnode(op,a,b=None):
        n=nt.nodes.new('ShaderNodeMath');n.operation=op
        for socket,value in zip(n.inputs,[a,b]):
            if value is None:continue
            if isinstance(value,(int,float)):socket.default_value=value
            else:nt.links.new(value,socket)
        return n.outputs[0]
    def rgb(value):n=nt.nodes.new('ShaderNodeRGB');n.outputs[0].default_value=(*value,1);return n.outputs[0]
    def vector(op,a,b):
        n=nt.nodes.new('ShaderNodeVectorMath');n.operation=op;nt.links.new(a,n.inputs[0]);nt.links.new(b,n.inputs[1]);return n.outputs['Vector']
    def scale(color,value):
        n=nt.nodes.new('ShaderNodeVectorMath');n.operation='SCALE';nt.links.new(color,n.inputs[0])
        if isinstance(value,(int,float)):n.inputs['Scale'].default_value=value
        else:nt.links.new(value,n.inputs['Scale'])
        return n.outputs['Vector']
    attr=nt.nodes.new('ShaderNodeAttribute');attr.attribute_name=CONTROL;attr.name='Source vertex control';sep=nt.nodes.new('ShaderNodeSeparateRGB');nt.links.new(attr.outputs['Color'],sep.inputs[0]);g=sep.outputs['G'];b=sep.outputs['B'];bands=[rgb(c) for c in params['colors_linear']]
    color=bands[0]
    if params['multi_color']:
        base=vector('ADD',scale(bands[0],mathnode('SUBTRACT',1,g)),scale(bands[1],g));parts=[]
        for lo,hi,band in [(.001,.5,base),(.5,.7,bands[2]),(.7,.9,bands[3]),(.9,1,bands[4])]:
            gate=mathnode('MULTIPLY',mathnode('SUBTRACT',1,mathnode('LESS_THAN',g,lo)),mathnode('SUBTRACT',1,mathnode('GREATER_THAN',g,hi)));parts.append(scale(band,gate))
        color=parts[0]
        for part in parts[1:]:color=vector('ADD',color,part)
    color=scale(vector('MULTIPLY',color,rgb(params['global_tint'])),params['brightness'])
    emission=nt.nodes.new('ShaderNodeEmission');emission.name='Source outline linear RGB';nt.links.new(color,emission.inputs[0]);emission.inputs[1].default_value=1
    tr=nt.nodes.new('ShaderNodeBsdfTransparent');mix=nt.nodes.new('ShaderNodeMixShader');discard=mathnode('LESS_THAN',b,.1);nt.links.new(discard,mix.inputs[0]);nt.links.new(emission.outputs[0],mix.inputs[1]);nt.links.new(tr.outputs[0],mix.inputs[2]);out=nt.nodes.new('ShaderNodeOutputMaterial');nt.links.new(mix.outputs[0],out.inputs['Surface'])
    for aov,value in [('HX_BloomWeight',params['bloom']),('SourceOutlineMask',1)]:
        n=nt.nodes.new('ShaderNodeOutputAOV');n.aov_name=aov;nt.links.new(mathnode('MULTIPLY',mathnode('SUBTRACT',1,discard),value),n.inputs['Value'])
    m['source_outline_parameters']=json.dumps(params,sort_keys=True);return m

def morph_positions(obj,attrs,rest):
    require_finite('source positions',rest)
    keys=obj.data.shape_keys;metrics={'active_morphs':False,'morph_weights':{},'morph_basis_max_error':0.0,'morph_target_max_error':0.0}
    if not keys:return rest,metrics
    if obj.show_only_shape_key:raise ValueError('Active morph targets cannot use show_only_shape_key')
    require_finite('morph weights',[k.value for k in keys.key_blocks])
    active=[k for k in keys.key_blocks[1:] if not k.mute and abs(k.value)>1e-7]
    if not active:return rest,metrics
    names=attrs.get('_MORPH_TARGET_NAMES');deltas=attrs.get('_MORPH_POSITION_DELTAS')
    if not keys.use_relative or names is None or deltas is None or attrs.get('_MORPH_UNSUPPORTED_SEMANTICS'):
        raise ValueError('Active morph targets require verified named relative POSITION-only source targets')
    if len(set(names))!=len(names) or len(names)!=len(deltas):raise ValueError('Active morph targets have ambiguous source names/count')
    basis=keys.key_blocks[0];basis_coords=np.array([p.co[:] for p in basis.data]);require_finite('morph basis',basis_coords);metrics['morph_basis_max_error']=float(np.abs(basis_coords-rest).max())
    if metrics['morph_basis_max_error']>1e-5:raise ValueError('Active morph targets differ from the verified source basis')
    result=rest.copy()
    for key in active:
        if key.name not in names or key.relative_key!=basis or key.vertex_group:raise ValueError('Active morph targets require an unmasked source-named delta relative to Basis: '+key.name)
        delta=deltas[names.index(key.name)]
        if delta.shape!=rest.shape:raise ValueError('Active morph target vertex count differs: '+key.name)
        actual=np.array([p.co[:] for p in key.data])-rest;require_finite('morph target '+key.name,actual,delta);error=float(np.abs(actual-delta).max());metrics['morph_target_max_error']=max(metrics['morph_target_max_error'],error)
        if error>1e-5:raise ValueError('Active morph target differs from source POSITION delta: '+key.name)
        result+=float(key.value)*delta;metrics['morph_weights'][key.name]=float(key.value)
    metrics['active_morphs']=True
    return result,metrics


def compute_vertices(scene,obj,attrs,params):
    dg=bpy.context.evaluated_depsgraph_get();evaluated=obj.evaluated_get(dg);mesh=evaluated.to_mesh()
    try:
        rest=np.array([v.co[:] for v in obj.data.vertices]);actual=np.array([v.co[:] for v in mesh.vertices]);morphed,morph_metrics=morph_positions(obj,attrs,rest)
        if rest.shape!=actual.shape:raise ValueError('Outline source topology changed')
        require_finite('evaluated positions and source attributes',rest,actual,attrs['NORMAL'],attrs['TANGENT'])
        normal=attrs['NORMAL'][:,[0,2,1]]*np.array([1,-1,1]);tangent=attrs['TANGENT'];T=tangent[:,[0,2,1]]*np.array([1,-1,1])
        if len(rest)!=len(normal):raise ValueError('Source attribute order/count mismatch')
        mods=[m for m in obj.modifiers if m.type=='ARMATURE' and m.show_render];skin_error=0.0;weight_error=0.0
        if mods:
            if len(mods)!=1 or mods[0].use_deform_preserve_volume:raise ValueError('Only one verified linear Armature modifier is supported')
            arm=mods[0].object;to_arm=arm.matrix_world.inverted()@obj.matrix_world;from_arm=to_arm.inverted();matrices={}
            for vg in obj.vertex_groups:
                pb=arm.pose.bones.get(vg.name)
                if pb:matrices[vg.index]=np.array(from_arm@pb.matrix@pb.bone.matrix_local.inverted()@to_arm)
            deform=np.zeros((len(rest),4,4),dtype=np.float64)
            for i,v in enumerate(obj.data.vertices):
                total=0
                for group in v.groups:
                    if group.group in matrices:deform[i]+=matrices[group.group]*group.weight;total+=group.weight
                if total>0:weight_error=max(weight_error,abs(total-1));deform[i]/=total
                else:deform[i]=np.eye(4)
            predicted=np.einsum('nij,nj->ni',deform,np.column_stack([morphed,np.ones(len(rest))]))[:,:3];require_finite('skinned positions',predicted);skin_error=float(np.abs(predicted-actual).max())
            if skin_error>2e-5:raise ValueError('Source linear skin position check failed: '+str(skin_error))
            # Always skin N/T when a rig exists, even if all positions stay fixed.
            normal=np.einsum('nij,nj->ni',deform[:,:3,:3],normal);T=np.einsum('nij,nj->ni',deform[:,:3,:3],T)
        elif np.max(np.abs(morphed-actual))>1e-5:raise ValueError('Unsupported non-armature deformation')
        B=np.cross(normal,T)*tangent[:,3:4];smooth=attrs.get('_PGRSMOOTHNORMAL');sn=normal if smooth is None else T*(smooth[:,0:1]*2-1)+B*(smooth[:,1:2]*2-1)+normal*(smooth[:,2:3]*2-1)
        control=attrs['_PGRCOLOR'] if params['vertex_color_enabled'] and '_PGRCOLOR' in attrs else np.ones((len(actual),4),np.float32)
        MV=np.array(scene.camera.matrix_world.inverted()@obj.matrix_world);pts=np.column_stack([actual,np.ones(len(actual))])@MV.T;proj=scene.camera.calc_matrix_camera(dg,x=scene.render.resolution_x,y=scene.render.resolution_y,scale_x=scene.render.pixel_aspect_x,scale_y=scene.render.pixel_aspect_y)
        distance=params['distance_scale']
        if distance<=0 or proj[1][1]<=0:raise ValueError('Outline distance scale/projection must be positive')
        lengths=np.linalg.norm(pts[:,:3],axis=1,keepdims=True)
        if np.any(lengths<1e-12):raise ValueError('Outline vertex coincides with camera; source normalize is undefined')
        push=pts[:,:3]/lengths*(params['z_max_offset']*distance*.5);width=np.sqrt(np.maximum(-pts[:,2],0)/proj[1][1]/distance)*distance*params['width']*.018*control[:,2]
        direction=sn@MV[:3,:3].T;direction[:,2]=.001;direction[:,:2]/=np.linalg.norm(direction,axis=1,keepdims=True);q=pts[:,:3]+push;q[:,:2]+=direction[:,:2]*width[:,None];q[:,2]+=params['z_offset'];world=np.column_stack([q,np.ones(len(q))])@np.array(scene.camera.matrix_world).T
        require_finite('projected vertices and control',world,control,width)
        return world[:,:3].astype(np.float32),control.astype(np.float32),[tuple(reversed(p.vertices)) for p in mesh.polygons],{'skin_position_max_error':skin_error,'weight_sum_max_error':weight_error,'width_min':float(width.min()),'width_max':float(width.max()),'projection_y':float(proj[1][1]),'vertices':len(actual),**morph_metrics}
    finally:evaluated.to_mesh_clear()

def bake(scene,entries,frames):
    """entries: [(source_object, attrs, params, label)]. Save all integer frames.

    Cached world-space vertices require rebaking after camera/pose/topology edits.
    Absolute shape keys make saved scenes self-contained without handlers.
    """
    if frames!=list(range(frames[0],frames[-1]+1)):raise ValueError('Bake every integer frame, without gaps')
    objects=[];records=[]
    for source,attrs,params,label in entries:
        mesh=bpy.data.meshes.new(label+' baked mesh');obj=bpy.data.objects.new(label,mesh);scene.collection.objects.link(obj);obj['source_outline_cache']=True;objects.append(obj)
    for frame in frames:
        scene.frame_set(frame);bpy.context.view_layer.update();record={'frame':frame,'camera':scene.camera.name,'camera_matrix':list(map(list,scene.camera.matrix_world)),'entries':[]}
        for (source,attrs,params,label),obj in zip(entries,objects):
            vertices,control,faces,metrics=compute_vertices(scene,source,attrs,params)
            if frame==frames[0]:
                obj.data.from_pydata(vertices.tolist(),[],faces);obj.data.update();obj.data.materials.append(material(params,label+' material'));attr=obj.data.attributes.new(CONTROL,'FLOAT_COLOR','POINT');attr.data.foreach_set('color',control.ravel());obj.shape_key_add(name='Basis');obj.data.shape_keys.use_relative=False
            key=obj.shape_key_add(name=f'Frame {frame:04}');key.data.foreach_set('co',vertices.ravel());key.interpolation='KEY_LINEAR';obj.data.shape_keys.eval_time=key.frame;obj.data.shape_keys.keyframe_insert('eval_time',frame=frame);metrics.update(source=source.name,outline=label,cache_key_time=key.frame);record['entries'].append(metrics)
        records.append(record)
    for obj in objects:
        for fc in obj.data.shape_keys.animation_data.action.fcurves:
            for key in fc.keyframe_points:key.interpolation='LINEAR'
    scene.frame_set(frames[0]);bpy.context.view_layer.update();scene['outline_bake_range']=json.dumps([frames[0],frames[-1]]);scene['outline_bake_warning']='Rebake after any camera, pose, projection, topology, source-parameter or output-aspect edit. Integer-frame cache; no motion-blur/subframe equivalence.'
    return objects,records
