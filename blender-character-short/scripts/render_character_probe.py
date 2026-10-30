"""Render a Character-branch GLB probe from external source profile/config.
Runs in factory startup; existing scenes and baseline projects are never opened.
"""
import argparse,json,sys,time,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
import bpy,numpy as np
from mathutils import Vector,Matrix,Quaternion
from render_source_probe import import_glb,setup_raw
from character_material import build_character

def source_world(doc,index):
    parents={c:i for i,n in enumerate(doc['nodes']) for c in n.get('children',[])}
    def local(i):
        n=doc['nodes'][i]
        if 'matrix' in n:return Matrix(np.array(n['matrix']).reshape(4,4).T.tolist())
        x,y,z,w=n.get('rotation',[0,0,0,1]);return Matrix.Translation(Vector(n.get('translation',[0,0,0])))@Quaternion((w,x,y,z)).to_matrix().to_4x4()@Matrix.Diagonal(Vector((*n.get('scale',[1,1,1]),1)))
    m=local(index)
    while index in parents:index=parents[index];m=local(index)@m
    return m

def main():
    p=argparse.ArgumentParser();p.add_argument('--asset',required=True);p.add_argument('--textures',required=True);p.add_argument('--config',required=True);p.add_argument('--output',required=True);p.add_argument('--render',action='store_true');a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);cfg=json.loads(Path(a.config).read_text('utf-8'));out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True)
    if (out/'probe.blend').exists():raise FileExistsError('Use a new output version directory')
    bpy.ops.wm.read_factory_settings(use_empty=True);scene=bpy.context.scene;scene.render.engine='BLENDER_EEVEE_NEXT';scene.render.film_transparent=True;scene.render.resolution_x=cfg.get('width',640);scene.render.resolution_y=cfg.get('height',640);scene.render.resolution_percentage=100;scene.eevee.taa_render_samples=cfg.get('samples',32);scene.view_settings.view_transform='Standard';scene.view_settings.look='None';scene.view_settings.exposure=0;scene.view_settings.gamma=1
    objects,doc,records,audit,digest=import_glb(a.asset,out);manifest=json.loads((Path(a.textures)/'manifest.json').read_text('utf-8'));impaths={im['index']:Path(im['path']) for im in manifest};texture_paths={i:impaths[t.get('source',t.get('extensions',{}).get('EXT_texture_webp',{}).get('source'))] for i,t in enumerate(doc['textures'])}
    runtime=cfg['runtime'].copy();head=doc['scenes'][doc.get('scene',0)]['extras']['anchors']['head'];wm=source_world(doc,head);C=Matrix(((1,0,0),(0,0,-1),(0,1,0)));runtime['face_object_y']=list((C@wm.to_3x3().col[1]).normalized());runtime['face_object_z']=list((C@wm.to_3x3().col[2]).normalized());built={};reports=[];selected=[];omitted=[]
    for obj in objects:
        if obj.type!='MESH':continue
        index=obj['source_material_index'];raw=doc['materials'][index]
        if raw['extras']['family']!='character':obj.hide_render=True;omitted.append({'object':obj.name,'material':raw['name'],'family':raw['extras']['family']});continue
        if index not in built:built[index],report=build_character(raw,texture_paths,doc['textures'],runtime,tuple(obj.data.attributes.keys()));reports.append(report)
        obj.data.materials.clear();obj.data.materials.append(built[index]);selected.append(obj)
    passes=['Image'];types={'HX_BloomWeight':'VALUE','BaseAlbedo':'COLOR','ShadowBand':'COLOR','SourceNormal':'COLOR','HalfLambert':'VALUE','SkinRate':'VALUE','StyleSpecular':'COLOR','RimTerm':'COLOR','MatcapTerm':'COLOR'}
    for name,typ in types.items():av=scene.view_layers[0].aovs.add();av.name=name;av.type=typ;passes.append(name)
    bpy.context.view_layer.update();coords=[]
    for obj in selected:
        ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh();coords.extend(ev.matrix_world@v.co for v in me.vertices);ev.to_mesh_clear()
    low=Vector([min(v[i] for v in coords) for i in range(3)]);high=Vector([max(v[i] for v in coords) for i in range(3)]);extent=high.z-low.z;center=(low+high)*.5;cd=bpy.data.cameras.new('Character source probe');cam=bpy.data.objects.new(cd.name,cd);scene.collection.objects.link(cam);cam.location=center+Vector(cfg['camera_offset'])*extent;target=center+Vector(cfg.get('target_offset',[0,0,0]))*extent;cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cd.lens=cfg.get('lens',50);scene.camera=cam
    setup_raw(scene,out,passes);scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGBA';scene.render.filepath=str(out/'unprocessed-standard.png');bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(out/'probe.blend'));report={'asset_sha256':digest,'config':cfg,'runtime':runtime,'import':audit,'materials':reports,'omitted':omitted,'source_head_node':head,'source_head_name':doc['nodes'][head]['name'],'passes':passes,'strict_pass':False,'gaps':['source outline/AA absent','unmatched camera and runtime settings','HairHET stencil scheduling absent','XT weight-only passes absent','unimplemented effect families omitted'],'rendered':False}
    if a.render:
        t=time.monotonic();bpy.ops.render.render(write_still=True);report['render_seconds']=time.monotonic()-t;arrays={}
        for name in passes:
            im=bpy.data.images.load(str(out/(name+'_0001.exr')),check_existing=False);arr=np.empty(len(im.pixels),np.float32);im.pixels.foreach_get(arr);arrays[name]=arr.reshape(im.size[1],im.size[0],4)
        np.savez_compressed(out/'raw.npz',rgba=arrays['Image'],weight=arrays['HX_BloomWeight'][...,:1]);report['rendered']=True;report['rgba_max']=float(arrays['Image'].max());report['weight_max']=float(arrays['HX_BloomWeight'][...,0].max())
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print('CHARACTER_PROBE',json.dumps({k:v for k,v in report.items() if k not in ['materials','import']},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
