"""Independent known-input outline checks plus actual Eevee fragment fixtures.

Consumes a separately reviewed scalar oracle JSON. Geometry checks compare
source-derived cached coordinates; fragment checks read linear EXR center ROIs.
No claim of website GPU raster/depth/stencil equivalence.
"""
import argparse,sys,json,math,time,copy
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).parent))
import source_outline as impl
from render_source_probe import setup_raw

def camera(scene,orthographic=False):
    data=bpy.data.cameras.new('Fixture camera');obj=bpy.data.objects.new('Fixture camera',data);scene.collection.objects.link(obj);scene.camera=obj
    if orthographic:data.type='ORTHO';data.ortho_scale=10;obj.location=(0,0,10)
    else:data.sensor_fit='VERTICAL';data.sensor_height=36;data.lens=36/(2*math.tan(math.pi/6))
    return obj

def geometry_checks(oracle):
    bpy.ops.wm.read_factory_settings(use_empty=True);s=bpy.context.scene;s.render.resolution_x=s.render.resolution_y=540;cam=camera(s);mesh=bpy.data.meshes.new('known vertices');mesh.from_pydata([(0,0,-4)]*3,[],[(0,1,2)]);obj=bpy.data.objects.new('known vertices',mesh);s.collection.objects.link(obj)
    attrs={'NORMAL':np.tile([1.,0,0],(3,1)),'TANGENT':np.tile([0.,0,-1,1],(3,1)),'_PGRCOLOR':np.ones((3,4))};base={'distance_scale':.015,'width':1,'z_max_offset':0,'z_offset':0,'vertex_color_enabled':True};results=[]
    variants={'d4_fov60':{},'d16_fov60':{'point':[0,0,-16]},'d4_fov90':{'fov':90},'b_at_discard_threshold':{'b':.1},'offaxis_push_plus_zoffset':{'point':[3,0,-4],'zmax':.2,'zoffset':.02},'camera_facing_normal':{'normal':[0,0,1]},'small_xy_normal':{'normal':[.001,0,1]},'distance_scale_times4':{'distance':.06}}
    for name,v in variants.items():
        point=v.get('point',[0,0,-4]);normal=np.array(v.get('normal',[1,0,0]));attrs['NORMAL']=np.tile(normal[[0,2,1]]*[1,1,-1],(3,1));attrs['_PGRCOLOR'][:,2]=v.get('b',1);cam.data.lens=36/(2*math.tan(math.radians(v.get('fov',60))/2))
        for vert in mesh.vertices:vert.co=point
        mesh.update();p=dict(base,distance_scale=v.get('distance',.015),z_max_offset=v.get('zmax',0),z_offset=v.get('zoffset',0));bpy.context.view_layer.update();actual,_,_,metrics=impl.compute_vertices(s,obj,attrs,p);expected=np.array(oracle['vertex_cases'][name]['q']);err=float(np.abs(actual[0]-expected).max());results.append({'case':name,'world':actual[0].tolist(),'expected':expected.tolist(),'max_error':err,'pass':err<1e-6});assert err<1e-6,(name,err)
    # Original defect: a pivot vertex stays still under rotation while tangent moves.
    for vert in mesh.vertices:vert.co=(0,0,0)
    mesh.update();cam.location=(0,0,4);cam.data.lens=36/(2*math.tan(math.pi/6));adata=bpy.data.armatures.new('pivot rig');arm=bpy.data.objects.new('pivot rig',adata);s.collection.objects.link(arm);bpy.context.view_layer.objects.active=arm;arm.select_set(True);bpy.ops.object.mode_set(mode='EDIT');bone=adata.edit_bones.new('pivot');bone.head=(0,0,0);bone.tail=(0,1,0);bpy.ops.object.mode_set(mode='OBJECT');vg=obj.vertex_groups.new(name='pivot');vg.add([0,1,2],1,'REPLACE');mod=obj.modifiers.new('linear skin','ARMATURE');mod.object=arm;pb=arm.pose.bones['pivot'];pb.rotation_mode='XYZ';pb.rotation_euler.z=math.pi/2
    attrs={'NORMAL':np.tile([0.,1,0],(3,1)),'TANGENT':np.tile([1.,0,0,1],(3,1)),'_PGRSMOOTHNORMAL':np.tile([1.,.5,.5],(3,1)),'_PGRCOLOR':np.ones((3,4))};bpy.context.view_layer.update();actual,_,_,metrics=impl.compute_vertices(s,obj,attrs,base);expected=np.array([0,oracle['vertex_cases']['d4_fov60']['q'][0],0]);err=float(np.abs(actual[0]-expected).max());results.append({'case':'stationary_position_rotated_tangent','world':actual[0].tolist(),'expected':expected.tolist(),'max_error':err,'skin_position_error':metrics['skin_position_max_error'],'pass':err<1e-6});assert err<1e-6,results[-1]
    # Explicit limitations must fail before producing a plausible cache.
    obj.shape_key_add(name='Basis');k=obj.shape_key_add(name='unsupported morph');k.value=.5
    try:impl.compute_vertices(s,obj,attrs,base)
    except ValueError as e:results.append({'case':'active_morph_rejected','pass':'Active morph' in str(e),'message':str(e)})
    else:raise AssertionError('Active morph silently accepted')
    return results

def fragment_checks(oracle,out):
    bpy.ops.wm.read_factory_settings(use_empty=True);s=bpy.context.scene;s.render.engine='BLENDER_EEVEE_NEXT';s.eevee.taa_render_samples=16;s.render.resolution_x=500;s.render.resolution_y=400;s.render.resolution_percentage=100;s.render.film_transparent=True;s.view_settings.view_transform='Standard';s.view_settings.look='None';s.view_settings.exposure=0;s.view_settings.gamma=1;camera(s,True)
    for name in ['HX_BloomWeight','SourceOutlineMask']:a=s.view_layers[0].aovs.add();a.name=name;a.type='VALUE'
    vals=oracle['color_inputs'];params={'colors_linear':vals['bands_already_linear'],'brightness':vals['brightness'],'global_tint':vals['global_tint_linear'],'bloom':vals['bloom'],'multi_color':True};cases=[]
    for c in oracle['color_boundary_cases']:cases.append(dict(c,b=1,label='g='+str(c['g'])))
    for c in oracle['b_discard_cases']:cases.append(dict(c,label='b='+str(c['b'])))
    # Non-multi branch and attribute-disabled effective-control=ones contract.
    for i,c in enumerate(oracle['variants']):cases.append(dict(c,g=c.get('effective_control',[0,.5,0,0])[1],b=c.get('effective_control',[0,.5,0,0])[2],multi='_MULTI_OUTLINE_COLOR' in c['keywords'],label='branch '+str(i)))
    for i,c in enumerate(cases):
        col=i%5;row=i//5;x=-4+col*2;y=3-row*2;mesh=bpy.data.meshes.new(c['label']);mesh.from_pydata([(x-.9,y-.9,0),(x+.9,y-.9,0),(x+.9,y+.9,0),(x-.9,y+.9,0)],[],[(0,1,2,3)]);obj=bpy.data.objects.new(c['label'],mesh);s.collection.objects.link(obj);attr=mesh.attributes.new(impl.CONTROL,'FLOAT_COLOR','POINT');attr.data.foreach_set('color',np.tile([1,c['g'],c['b'],1],4).astype(np.float32));mesh.materials.append(impl.material(dict(params,multi_color=c.get('multi',True)),c['label']));c['sample_xy_bottom_origin']=[col*100+50,350-row*100]
    out.mkdir(parents=True,exist_ok=True);setup_raw(s,out,['Image','HX_BloomWeight','SourceOutlineMask']);s.frame_set(1);s.render.filepath=str(out/'fixtures.png');bpy.ops.wm.save_as_mainfile(filepath=str(out/'fixtures.blend'));bpy.ops.render.render(write_still=True);images={}
    for name in ['Image','HX_BloomWeight','SourceOutlineMask']:
        path=out/(name+'_0001.exr');im=bpy.data.images.load(str(path),check_existing=False);pixels=np.empty(len(im.pixels),np.float32);im.pixels.foreach_get(pixels);images[name]=pixels.reshape(im.size[1],im.size[0],4);bpy.data.images.remove(im)
    results=[]
    for c in cases:
        x,y=c['sample_xy_bottom_origin'];actual={k:v[y-2:y+2,x-2:x+2].mean(axis=(0,1)).tolist() for k,v in images.items()};expected=np.zeros(4) if c['discard'] else np.array(c['linear_rgba']);weight=0 if c['discard'] else vals['bloom'];mask=0 if c['discard'] else 1;error=max(float(np.abs(np.array(actual['Image'])-expected).max()),abs(actual['HX_BloomWeight'][0]-weight),abs(actual['SourceOutlineMask'][0]-mask));results.append({'case':c['label'],'actual':actual,'expected_rgba':expected.tolist(),'expected_weight':weight,'max_error':error,'pass':error<=.002})
    return results

def main():
    p=argparse.ArgumentParser();p.add_argument('--oracle',required=True);p.add_argument('--output',required=True);p.add_argument('--geometry-only',action='store_true');a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.output);out.mkdir(parents=True,exist_ok=True);oracle=json.loads(Path(a.oracle).read_text('utf-8'));report={'scope':'Known-input geometry and Eevee linear fragment/AOV checks; no website GPU equivalence','geometry':geometry_checks(oracle)}
    if not a.geometry_only:report['fragments']=fragment_checks(oracle,out)
    report['pass']=all(c['pass'] for group in ['geometry','fragments'] for c in report.get(group,[]));(out/'report.json').write_text(json.dumps(report,indent=2),'utf-8');print('OUTLINE_FIXTURES',report['pass']);assert report['pass'],'See per-case output; tolerance does not establish raster equivalence'

if __name__=='__main__':main()
