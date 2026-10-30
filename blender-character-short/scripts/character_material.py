"""Source-derived Character material graph for external asset profiles.

This implements documented algebra, not the website render scheduler. Diagnostic
adaptations are returned as explicit gaps: shadow maps, exact interpolated TBN,
cubemap resources/LOD, stencil/depth queues and secondary weight-only passes.
"""
import math
from pathlib import Path
import bpy

def linear(c):return c/12.92 if c<.04045 else ((c+.055)/1.055)**2.4
def color(c):return tuple(linear(float(v)) for v in c[:3])

class Graph:
    def __init__(self,mat):self.nt=mat.node_tree;self.nt.nodes.clear();self.i=0
    def node(self,kind,name):
        n=self.nt.nodes.new(kind);n.name=name;n.label=name;n.location=((self.i%10)*210,-(self.i//10)*180);self.i+=1;return n
    def put(self,value,socket):
        if isinstance(value,bpy.types.NodeSocket):self.nt.links.new(value,socket)
        else:
            if socket.type=='RGBA' and hasattr(value,'__len__') and len(value)==3:value=(*value,1)
            socket.default_value=value
    def m(self,op,a,b=0,name=None):
        n=self.node('ShaderNodeMath',name or op);n.operation=op;self.put(a,n.inputs[0]);self.put(b,n.inputs[1]);return n.outputs[0]
    def v(self,op,a,b=None,name=None):
        n=self.node('ShaderNodeVectorMath',name or op);n.operation=op;self.put(a,n.inputs[0])
        if b is not None:self.put(b,n.inputs[3 if op=='SCALE' else 1])
        return n.outputs['Value' if op in ('DOT_PRODUCT','LENGTH','DISTANCE') else 'Vector']
    def mix(self,a,b,t,name='mix'):
        n=self.node('ShaderNodeMixRGB',name);n.blend_type='MIX';self.put(t,n.inputs[0]);self.put(a,n.inputs[1]);self.put(b,n.inputs[2]);return n.outputs[0]
    def mixf(self,a,b,t):return self.m('ADD',a,self.m('MULTIPLY',self.m('SUBTRACT',b,a),t))
    def sat(self,a):return self.m('MINIMUM',self.m('MAXIMUM',a,0),1)
    def sep(self,a):
        n=self.node('ShaderNodeSeparateXYZ','components');self.put(a,n.inputs[0]);return list(n.outputs)
    def combine(self,x,y,z=0):
        n=self.node('ShaderNodeCombineXYZ','vector');self.put(x,n.inputs[0]);self.put(y,n.inputs[1]);self.put(z,n.inputs[2]);return n.outputs[0]
    def smooth(self,x):return self.m('MULTIPLY',self.m('MULTIPLY',x,x),self.m('SUBTRACT',3,self.m('MULTIPLY',2,x)))
    def aov(self,name,value,typ='COLOR'):
        n=self.node('ShaderNodeOutputAOV',name);n.aov_name=name;self.put(value,n.inputs['Color' if typ=='COLOR' else 'Value'])

def build_character(raw,texture_paths,texture_defs,runtime,attributes=()):
    e=raw['extras'];s=e['shader'];f=s['floats'];cs=s['colors'];vec=s.get('vectors',{});kw=set(s['keywords']);bindings=s['textures'];render=e['render'];gaps=[]
    mat=bpy.data.materials.new('SRC_'+raw['name']);mat.use_nodes=True;g=Graph(mat)
    def F(key,default=0):return float(f.get(key,default))
    def C(key,default=(1,1,1,1)):return color(cs.get(key,default))
    geo=g.node('ShaderNodeNewGeometry','Surface geometry');normal=geo.outputs['Normal'];V=geo.outputs['Incoming'];uvs={}
    def uv(index):
        if index not in uvs:
            n=g.node('ShaderNodeUVMap','UV'+str(index));n.uv_map='UVMap' if index==0 else f'UVMap.{index:03}';uvs[index]=n.outputs[0]
        return uvs[index]
    def tex(index,coords=None,data=None,label=None):
        desc=texture_defs[index];image=bpy.data.images.load(str(texture_paths[index]),check_existing=True)
        is_data=data if data is not None else desc.get('extras',{}).get('colorSpace')!='sRGB'
        image.colorspace_settings.name='Non-Color' if is_data else 'sRGB';image.alpha_mode='CHANNEL_PACKED' if is_data else 'STRAIGHT'
        n=g.node('ShaderNodeTexImage',label or desc.get('name','texture'));n.image=image;n.interpolation='Linear';n.extension='EXTEND' if 'Skin' in desc.get('name','') else 'REPEAT';g.put(coords if coords is not None else uv(0),n.inputs[0]);return n.outputs['Color'],n.outputs['Alpha']
    def binding(key,coords=None):
        b=bindings.get(key)
        if b is None:return (1,1,1),1
        if coords is None:
            coords=uv(b.get('texCoord',0));sx,sy=b.get('scale',[1,1]);ox,oy=b.get('offset',[0,0]);coords=g.v('ADD',g.v('MULTIPLY',coords,(sx,sy,1)),(ox,1-sy-oy,0))
        return tex(b['index'],coords,label=key)
    main,alpha=binding('_MainTex');base=g.v('MULTIPLY',main,C('_AlbedoColor'));base=g.v('SCALE',base,F('_AlbedoColorIntensity',1),'Base albedo');alpha=g.m('MULTIPLY',alpha,cs.get('_AlbedoColor',[1,1,1,1])[3])
    if raw.get('normalTexture'):
        nd=raw['normalTexture'];nm,_=tex(nd['index'],uv(nd.get('texCoord',0)),True,'GLTF normalTexture (not extras ST)');n=g.node('ShaderNodeNormalMap','Tangent normal adapter');n.space='TANGENT';n.uv_map='UVMap' if nd.get('texCoord',0)==0 else 'UVMap.%03d'%nd['texCoord'];n.inputs['Strength'].default_value=nd.get('scale',1);g.put(nm,n.inputs['Color']);normal=n.outputs[0];gaps.append('Blender Normal Map adapter; exact interpolated source TBN not GPU-compared')
    L=runtime['light_direction'];rimdir=runtime['rim_direction'];H=g.m('ADD',g.m('MULTIPLY',g.v('DOT_PRODUCT',normal,L),.5),.5,'Half Lambert')
    mask,maskA=binding('_MaskTex');mr,mg,mb=g.sep(mask)
    if '_SHADOW_OBJECT_SPACE_NORMAL_MAP' in kw and '_MaskTex' in bindings:
        yn=g.node('ShaderNodeCombineXYZ','FaceObjectY');zn=g.node('ShaderNodeCombineXYZ','FaceObjectZ')
        for i in range(3):yn.inputs[i].default_value=runtime['face_object_y'][i];zn.inputs[i].default_value=runtime['face_object_z'][i]
        OY=yn.outputs[0];OZ=zn.outputs[0];orig=uv(bindings['_MaskTex'].get('texCoord',0));u,v,z=g.sep(orig)
        mirror=g.m('SUBTRACT',1,g.m('GREATER_THAN',g.v('DOT_PRODUCT',OZ,L),0));u=g.mixf(u,g.m('SUBTRACT',1,u),mirror)
        fm,fa=binding('_MaskTex',g.combine(u,v));fb=g.sep(fm)[2];ny=g.m('ADD',g.m('MULTIPLY',F('IF_SHADOW_OBJECT_SPACE_NORMAL_MAP_Y'),g.m('SUBTRACT',g.m('MULTIPLY',2,fa),2)),1);nz=g.m('SUBTRACT',g.m('MULTIPLY',2,fb),1)
        nf=g.v('NORMALIZE',g.v('ADD',g.v('SCALE',OY,ny),g.v('SCALE',OZ,nz)));light_xy=(L[0],L[1],0);ll=math.hypot(*light_xy[:2]);light_xy=tuple(v/ll for v in light_xy);H=g.m('ADD',g.m('MULTIPLY',g.v('DOT_PRODUCT',nf,light_xy),.5),.5,'Face horizontal Lambert')
    NoV=g.sat(g.v('DOT_PRODUCT',normal,V));NoH=g.sat(g.v('DOT_PRODUCT',normal,g.v('NORMALIZE',g.v('ADD',V,L))))
    maskg=g.mixf(mg,alpha,F('IF_MAIN_ALPHA_FOR_SHADOWMASK'))
    branch=g.m('SUBTRACT',1,g.m('FLOOR',g.m('SUBTRACT',1.5,maskg)));edge=g.mixf(g.m('SUBTRACT',g.m('MULTIPLY',maskg,1.25),.12),g.m('SUBTRACT',g.m('MULTIPLY',maskg,1.2),.1),branch)
    first=F('_FirstShadow',.51);second=F('_SecondShadow',.51);sm=max(F('_SmoothFactor'),.0001)
    fv=g.m('SUBTRACT',g.m('ADD',g.m('MULTIPLY',g.m('ADD',H,edge),.5),1),first)
    hard=g.m('SUBTRACT',1,g.m('FLOOR',fv));soft=g.m('SUBTRACT',1,g.sat(g.m('DIVIDE',g.m('ADD',g.m('SUBTRACT',fv,1),sm),2*sm)));w1=g.mixf(hard,soft,F('IF_SMOOTH_SHADOW'))
    intensity=runtime.get('shadow_intensity',1);w1=g.m('MULTIPLY',w1,intensity);w2=g.m('MULTIPLY',g.m('SUBTRACT',1,g.m('FLOOR',g.m('SUBTRACT',g.m('ADD',g.m('MULTIPLY',g.m('ADD',H,maskg),.5),1),second))),intensity);a2=g.m('MULTIPLY',g.m('SUBTRACT',1,g.m('FLOOR',g.m('ADD',maskg,.9))),intensity)
    band=g.mix(g.mix((*C('_NoShadowColor'),1),(*C('_FirstShadowColor'),1),w1),g.mix((*C('_FirstShadowColor'),1),(*C('_SecondShadowColor'),1),w2),a2,'Cel band')
    if '_CHAR_SHADOWMAP' in kw:gaps.append('Source head/body shadow maps absent; shadowMapLit=1 diagnostic')
    albedo=base
    if '_PBR' in kw or '_SIMPLE_PBR' in kw:
        pm,pa=binding('_PBRMask');rough,metal,ao=g.sep(pm);rough=g.sat(g.m('MULTIPLY',rough,F('_RoughnessMapScale',1)));metal=g.sat(g.m('MULTIPLY',metal,F('_MetallicMapScale',1)));ao=g.mixf(1,ao,F('_AOScale',1))
        if '_SIMPLE_PBR' in kw:rough=F('_Roughness',1);metal=F('_Metallic',1);ao=1;pa=1
        f0=g.mix((.04,.04,.04,1),base,metal);f0g=g.sep(f0)[1]
        rx=g.m('SUBTRACT',1,rough);ry=g.m('ADD',g.m('MULTIPLY',rough,-.0275),.0425);rz=g.m('ADD',g.m('MULTIPLY',rough,-.572),1.04);rw=g.m('ADD',g.m('MULTIPLY',rough,.022),-.04)
        a004=g.m('ADD',g.m('MULTIPLY',g.m('MINIMUM',g.m('MULTIPLY',rx,rx),g.m('POWER',2,g.m('MULTIPLY',-9.28,NoV))),rx),ry)
        abx=g.m('ADD',g.m('MULTIPLY',-1.04,a004),rz);aby=g.m('MULTIPLY',g.m('ADD',g.m('MULTIPLY',1.04,a004),rw),g.sat(g.m('MULTIPLY',50,f0g)))
        env=g.v('ADD',g.v('SCALE',f0,abx),g.combine(aby,aby,aby));rough4=g.m('POWER',g.m('MAXIMUM',g.m('MULTIPLY',rough,rough),.002),2);den=g.m('ADD',g.m('MULTIPLY',NoH,g.m('SUBTRACT',g.m('MULTIPLY',NoH,rough4),NoH)),1.00001);D=g.m('DIVIDE',g.m('MULTIPLY',rough4,.318309873),g.m('ADD',g.m('MULTIPLY',den,den),1e-7))
        # The resource is unresolved: use the source's documented missing-cube
        # constant, explicitly tagged as a diagnostic, never inferred as loaded.
        cube=runtime.get('diagnostic_cube',(128/255)**2*6);cubeSpec=g.v('SCALE',env,cube);ggx=g.v('SCALE',env,g.m('MULTIPLY',D,F('_PBRSpecularIntensity',1)));diff=g.v('SCALE',base,g.m('MULTIPLY',.96,g.m('SUBTRACT',1,metal)));direct=g.v('SCALE',g.v('ADD',cubeSpec,ggx),g.sat(g.v('DOT_PRODUCT',normal,L)));indirect=g.v('SCALE',g.v('ADD',g.v('SCALE',diff,F('_IndirectLightIntensity',1)),cubeSpec),ao);pbr=g.v('ADD',direct,indirect);albedo=g.mix(base,pbr,g.m('MULTIPLY',pa,F('_PBRRate',1)),'PBR over base');gaps.append('External cube unavailable: source gray fallback diagnostic, no verified reflection/LOD')
    skinrate=0
    if F('IF_SKIN') and '_SkinRamp' in bindings:
        skinrate=F('_SkinRate',1);row=.5;skinc=C('_SkinColor');skini=F('_SkinIntensity',1)
        if '_MUTLI_CHANEL_SKIN' in kw:
            # This branch is only legal for an asset profile that proves zone X
            # constant. General varying zones require a full zone selector.
            if runtime.get('constant_skin_zone') is None:raise ValueError('Varying zone skin requires explicit zone selector')
            zone=int(runtime['constant_skin_zone']);skinrate=vec['_MutliSkinRate'][zone];skini=vec['_MutliSkinIntensity'][zone];skinc=C('_SkinColor'+str(zone+1));row=[.875,.625,.375,.125][zone]
        if '_SKIN_VERTEX_COLOR' in kw:
            if '_PGRCOLOR' not in attributes:raise ValueError('Skin gate requires source vertex color or validated transferred attribute')
            at=g.node('ShaderNodeAttribute','Skin vertex gate');at.attribute_name='_PGRCOLOR';skinrate=g.m('MULTIPLY',skinrate,g.sep(at.outputs['Color'])[0])
        # Source SkinRamp UV is authored top-down in GLTF; Blender image rows use
        # bottom-up coordinates, so the explicit row is flipped once here.
        ramp,_=binding('_SkinRamp',g.combine(H,1-row));skin=g.v('MULTIPLY',albedo,g.v('SCALE',g.v('MULTIPLY',ramp,skinc),skini));albedo=g.mix(albedo,skin,skinrate,'Skin-modified albedo')
    atten=1
    if F('IF_SPEC_ATTENUATION'):
        atten=g.smooth(g.sat(g.m('DIVIDE',g.m('POWER',NoV,F('_SpecAttenuationPow',5)),max(F('_SpecAttenuationSmoothness',.1),.0001))))
    noh=g.m('MAXIMUM',NoH,.0001);noh=g.mixf(noh,g.m('SUBTRACT',1,noh),F('IF_INVERT_SPECULAR'));lobe=g.m('ADD',g.m('POWER',noh,F('_SpecularShiness',5)),mr);smooth=max(F('_SpecularSmoothFactor',.0001),.0001);highlight=g.m('MULTIPLY',g.sat(g.m('DIVIDE',g.m('SUBTRACT',g.m('SUBTRACT',lobe,smooth),1),smooth)),atten)
    if F('IF_SPECULAR_SHADOW_INTENSITY'):
        shaded=g.m('GREATER_THAN',g.m('ADD',w1,a2),.00009999);highlight=g.m('MULTIPLY',highlight,g.mixf(1,F('_SpecularShadowIntensity',1),shaded))
    specular=g.v('SCALE',g.v('MULTIPLY',albedo,C('_SpecularColor')),g.m('MULTIPLY',highlight,g.m('MULTIPLY',mb,F('_SpecularIntensity'))),'Style specular')
    rim=(0,0,0)
    if F('IF_RIM'):
        edge=g.smooth(g.sat(g.m('DIVIDE',g.m('SUBTRACT',g.m('SUBTRACT',1,NoV),F('_RimMin')) ,max(F('_RimMax')-F('_RimMin'),.0001))))
        allowed=g.m('SUBTRACT',1,g.m('LESS_THAN',g.m('ADD',g.v('DOT_PRODUCT',normal,V),F('_RimThreshold')) ,0));front=g.m('SUBTRACT',1,geo.outputs['Backfacing']);scale=g.m('MULTIPLY',g.m('MULTIPLY',g.m('MULTIPLY',edge,F('_RimIntensity')),allowed),g.m('MULTIPLY',front,g.sat(g.v('DOT_PRODUCT',normal,rimdir))));rim=g.v('SCALE',C('_RimColor'),scale,'Rim')
    matcap=(0,0,0)
    if '_MatCapTex' in bindings:
        key='_MatCapTex';tr=g.node('ShaderNodeVectorTransform','World to camera normal');tr.vector_type='NORMAL';tr.convert_from='WORLD';tr.convert_to='CAMERA';g.put(normal,tr.inputs[0]);nx,ny,nz=g.sep(tr.outputs[0]);worldup=g.sep(normal)[2];nv=g.v('NORMALIZE',g.combine(nx,g.mixf(ny,worldup,F('_MatCapYScale',.2)),nz));nx,ny,nz=g.sep(nv);cap,_=binding(key,g.combine(g.m('ADD',g.m('MULTIPLY',nx,.5),.5),g.m('ADD',g.m('MULTIPLY',ny,.5),.5)));matcap=g.v('SCALE',cap,g.mixf(1,g.m('MULTIPLY',mr,atten),F('_MatcapMask',1)),'Matcap')
    rgb=g.v('MULTIPLY',g.v('ADD',g.v('ADD',g.v('MULTIPLY',albedo,band),specular),g.v('ADD',rim,matcap)),runtime.get('light_color',[1,1,1]));rgb=g.v('MULTIPLY',rgb,runtime.get('ambient',[1,1,1]));rgb=g.v('MULTIPLY',rgb,C('_GlobalTint'),'Source final linear')
    emission=g.node('ShaderNodeEmission','Formula output');g.put(rgb,emission.inputs[0]);out=g.node('ShaderNodeOutputMaterial','Output');blended=render.get('blend') is not None
    coverage=alpha if blended else 1
    if render.get('alphaTest',0)>0:coverage=g.m('MULTIPLY',coverage,g.m('SUBTRACT',1,g.m('LESS_THAN',alpha,render['alphaTest'])))
    if blended:
        tr=g.node('ShaderNodeBsdfTransparent','Coverage');mix=g.node('ShaderNodeMixShader','Over approximation');g.put(coverage,mix.inputs[0]);g.put(tr.outputs[0],mix.inputs[1]);g.put(emission.outputs[0],mix.inputs[2]);g.put(mix.outputs[0],out.inputs['Surface']);mat.surface_render_method='BLENDED';gaps.append('Eevee blended coverage; source depthWrite/stencil/MRT blend not reproduced')
    else:g.put(emission.outputs[0],out.inputs['Surface'])
    mat.use_backface_culling=render.get('cull')=='back'
    weight=alpha if '_ALPHABLEND_ON' in kw or blended else F('_BloomFactor',.03)
    g.aov('HX_BloomWeight',weight,'VALUE');g.aov('BaseAlbedo',base);g.aov('ShadowBand',band);g.aov('SourceNormal',g.v('ADD',g.v('SCALE',normal,.5),(.5,.5,.5)));g.aov('HalfLambert',H,'VALUE');g.aov('SkinRate',skinrate,'VALUE');g.aov('StyleSpecular',specular);g.aov('RimTerm',rim);g.aov('MatcapTerm',matcap)
    return mat,{'material':raw['name'],'branch':'Character','keywords':sorted(kw),'gaps':sorted(set(gaps)),'node_count':len(g.nt.nodes)}
