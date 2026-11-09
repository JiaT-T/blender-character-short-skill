"""Bounded device-policy flat-texture acting preview, explicitly separate from final shading."""
import sys as _device_sys
from pathlib import Path as _DevicePath
_device_sys.path.insert(0, str(_DevicePath(__file__).resolve().parent))
from render_device_policy import render_with_policy, prepare_render
from render_engine_policy import EEVEE, CYCLES, require_engine, apply_sampling
from pathlib import Path
import argparse,datetime,hashlib,json,sys,time
sys.dont_write_bytecode=True
import bpy
from mathutils import Vector
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def configured_camera(scene,camera,spec):
    """Apply one explicitly configured view, shared by renders and saved previews."""
    if spec.get('follow_object') or spec.get('follow_bone'):
        if spec.get('follow_object') and spec.get('follow_bone'):raise ValueError('Choose one following origin')
        if spec.get('follow_object'):origin=scene.objects[spec['follow_object']].matrix_world.translation
        else:
            follow=spec['follow_bone'];rig=scene.objects[follow['armature']]
            if rig.type!='ARMATURE':raise ValueError('Following bone requires an armature')
            origin=(rig.matrix_world@rig.pose.bones[follow['bone']].matrix).translation
        axes=spec.get('follow_axes',[True,True,True])
        if not isinstance(axes,list) or len(axes)!=3 or any(type(x) is not bool for x in axes):raise ValueError('Following axes require three explicit boolean values')
        origin=Vector(tuple(origin[i] if axes[i] else 0 for i in range(3)))
        camera.location=origin+Vector(spec['camera_offset_m']);target=origin+Vector(spec['target_offset_m'])
    else:camera.location=spec['location'];target=Vector(spec['target'])
    camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.ortho_scale=spec['ortho_scale_m']

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--engine',choices=['eevee','cycles'],help='Assert the saved engine; does not convert existing materials')
    for k in ['blend','profile','out']:p.add_argument('--'+k,required=True,type=Path)
    p.add_argument('--mode',required=True,choices=['keys','video','scene']);p.add_argument('--preview-blend',type=Path);p.add_argument('--budget',type=float,default=300);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);cfg=json.loads(a.profile.read_text('utf-8'));width,height=cfg['size'];samples=cfg['samples']
    if a.mode=='scene':
        if not a.preview_blend or a.preview_blend.suffix.lower()!='.blend' or a.preview_blend.exists() or a.preview_blend.resolve()==a.blend.resolve():raise ValueError('Scene mode requires a new separate --preview-blend file')
        if cfg.get('video_view') not in cfg.get('views',{}):raise ValueError('Saved preview requires an explicit configured video_view')
    elif a.preview_blend:raise ValueError('--preview-blend is only valid for scene mode')
    denoise=cfg.get('denoise',False)
    if type(denoise) is not bool:raise ValueError('Explicit preview denoise flag must be boolean')
    if any(type(v) is not int for v in [width,height,samples]) or not 32<=min(width,height)<=max(width,height)<=640 or not 1<=samples<=4 or not 0<a.budget<=360:raise ValueError('Small preview bounds exceeded')
    bpy.ops.wm.open_mainfile(filepath=str(a.blend.resolve()),load_ui=False,use_scripts=False);scene=bpy.context.scene
    if scene.camera is None:raise ValueError('Saved scene requires an inspection camera')
    requested={'eevee':EEVEE,'cycles':CYCLES}.get(a.engine)
    require_engine(scene,requested)
    sampling=apply_sampling(scene,samples,denoise);denoise=sampling['denoise']
    device_report=prepare_render(scene)
    a.out.mkdir(parents=True,exist_ok=True);signature={'scene_sha256':sha(a.blend),'profile_sha256':sha(a.profile),'writer_sha256':sha(Path(__file__)),'device_policy_sha256':sha(Path(__file__).with_name('render_device_policy.py')),'engine_policy_sha256':sha(Path(__file__).with_name('render_engine_policy.py')),'sampling':sampling,'device':device_report};receipt=a.out/'inputs.json'
    if receipt.exists():
        if json.loads(receipt.read_text('utf-8'))!=signature:raise ValueError('Preview producer/input changed; choose a new output')
    else:receipt.write_text(json.dumps(signature,indent=2),'utf-8')
    visible=[o for o in scene.objects if o.type=='MESH' and not o.hide_render];cache={};adapters=[]
    for obj in visible:
        for slot,old in enumerate(list(obj.data.materials)):
            if old is None:raise ValueError('Unnamed material slot requires an explicit adapter')
            if old.name in cache:obj.data.materials[slot]=cache[old.name];continue
            spec=cfg['materials'].get(old.name)
            if spec is None:
                matches=[r for r in cfg.get('owned_material_prefixes',[]) if old.name.startswith(r['prefix'])]
                if len(matches)!=1:raise ValueError('Unmapped visible preview material: '+old.name)
                spec=matches[0]
            m=bpy.data.materials.new('Flat acting preview '+old.name);m.use_nodes=True;nt=m.node_tree;nt.nodes.clear();shader=spec.get('shader','emission')
            if shader not in ['emission','diffuse']:raise ValueError('Explicit preview shader must be emission or diffuse')
            emit=nt.nodes.new('ShaderNodeEmission' if shader=='emission' else 'ShaderNodeBsdfDiffuse');emit.inputs['Color'].default_value=(*spec.get('color',[.7,.7,.7]),1)
            if shader=='emission':emit.inputs['Strength'].default_value=cfg.get('brightness',.85)
            else:emit.inputs['Roughness'].default_value=.6
            out=nt.nodes.new('ShaderNodeOutputMaterial');opacity=float(spec.get('opacity',1));image=None;tex=None
            if not 0<=opacity<=1:raise ValueError('Explicit opacity must be in [0,1]')
            if spec.get('image_node'):
                original=old.node_tree.nodes.get(spec['image_node']) if old.use_nodes else None
                if original is None or original.type!='TEX_IMAGE' or original.image is None:raise ValueError('Missing declared source image node')
                image=original.image;tex=nt.nodes.new('ShaderNodeTexImage');tex.image=image;nt.links.new(tex.outputs['Color'],emit.inputs['Color'])
            if opacity<1 or spec.get('use_image_alpha'):
                transparent=nt.nodes.new('ShaderNodeBsdfTransparent');mix=nt.nodes.new('ShaderNodeMixShader');nt.links.new(transparent.outputs[0],mix.inputs[1]);nt.links.new(emit.outputs[0],mix.inputs[2]);mix.inputs[0].default_value=opacity
                if spec.get('use_image_alpha'):
                    if tex is None:raise ValueError('Alpha requires an explicit source image')
                    multiply=nt.nodes.new('ShaderNodeMath');multiply.operation='MULTIPLY';nt.links.new(tex.outputs['Alpha'],multiply.inputs[0]);multiply.inputs[1].default_value=opacity;nt.links.new(multiply.outputs[0],mix.inputs[0])
                nt.links.new(mix.outputs[0],out.inputs[0])
            else:nt.links.new(emit.outputs[0],out.inputs[0])
            cache[old.name]=m;obj.data.materials[slot]=m;adapters.append({'source':old.name,'image':image.name if image else None,'image_alpha':bool(spec.get('use_image_alpha')),'opacity':opacity,'shader':shader,'mode':'Explicit emission preview or diffuse shadow receiver; not final source lighting/shader equivalence'})
    if scene.render.engine==CYCLES:
        scene.cycles.max_bounces=8;scene.cycles.transparent_max_bounces=8
    scene.render.threads_mode='FIXED';scene.render.threads=1;scene.render.use_persistent_data=True;scene.render.resolution_x=width;scene.render.resolution_y=height;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.render.film_transparent=False;scene.render.use_compositing=False;scene.view_settings.view_transform='Standard';scene.view_settings.look='None';scene.view_settings.exposure=0;scene.view_settings.gamma=1
    world=bpy.data.worlds.new('Flat acting preview background');world.use_nodes=True;world.node_tree.nodes['Background'].inputs['Color'].default_value=(*cfg['background'],1);world.node_tree.nodes['Background'].inputs['Strength'].default_value=1;scene.world=world
    camera=scene.camera;matrix=camera.matrix_world.copy();scale=camera.data.ortho_scale
    if scene.frame_end-scene.frame_start+1>480:raise ValueError('Preview interval exceeds 480 frames')
    if a.mode=='scene':
        if camera.data.type!='ORTHO':raise ValueError('Saved preview route requires an orthographic inspection camera')
        if camera.constraints:raise ValueError('Saved preview camera must not have constraints')
        # Bake only the owned inspection camera. Original body/cache and model
        # transforms are not edited; the original source file is never saved.
        camera.animation_data_clear();camera.data.animation_data_clear();view=cfg['views'][cfg['video_view']]
        for f in range(scene.frame_start,scene.frame_end+1):
            scene.frame_set(f);bpy.context.view_layer.update();configured_camera(scene,camera,view)
            camera.keyframe_insert('location',frame=f);camera.keyframe_insert('rotation_euler',frame=f);camera.data.keyframe_insert('ortho_scale',frame=f)
        for owner in [camera,camera.data]:
            for curve in owner.animation_data.action.fcurves:
                for key in curve.keyframe_points:key.interpolation='LINEAR'
        unpacked=[i.name for i in bpy.data.images if i.source=='FILE' and i.packed_file is None]
        if unpacked:raise ValueError('Pack local resources before saved-preview export: '+str(unpacked[:8]))
        scene.frame_set(scene.frame_start);bpy.context.view_layer.update();a.preview_blend.parent.mkdir(parents=True,exist_ok=True)
        if sha(a.blend)!=signature['scene_sha256']:raise ValueError('Source file changed')
        bpy.ops.wm.save_as_mainfile(filepath=str(a.preview_blend.resolve()),check_existing=False)
        result={'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'signature':signature,'preview_blend':str(a.preview_blend.resolve()),'preview_sha256':sha(a.preview_blend),'camera_frames':[scene.frame_start,scene.frame_end],'video_view':cfg['video_view'],'device':device_report,'samples':samples,'denoise':denoise,'size':[width,height],'source_scene_saved':False,'normal_speed_continuous_viewing':False,'reopened_render_match_verified':False,'scope':'Separate packed preview-shading project with integer-frame camera bake. Fresh reopen, cache/body preservation and render agreement require independent checks.'}
        (a.out/'saved-preview-scene.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf-8');(a.out/'material-adapters.json').write_text(json.dumps(adapters,ensure_ascii=False,indent=2),'utf-8');print('SAVED_PREVIEW_SCENE',str(a.preview_blend));return
    jobs=[{'frame':f,'view':cfg.get('video_view','wide')} for f in range(scene.frame_start,scene.frame_end+1)] if a.mode=='video' else cfg['keys']
    if len(jobs)>480 or any(type(r['frame']) is not int or not scene.frame_start<=r['frame']<=scene.frame_end or r['view'] not in ['wide',*cfg.get('views',{}).keys()] for r in jobs):raise ValueError('Bounded known views/frames required')
    # Configured views supply every camera transform in the unsaved render copy.
    # Clear an owned saved-follow camera action so its animation cannot override
    # a diagnostic side/foot view during a still render. Legacy wide jobs retain
    # their native camera animation.
    if jobs and all(j['view']!='wide' for j in jobs):camera.animation_data_clear()
    report=a.out/(a.mode+'-frames.json');records=json.loads(report.read_text('utf-8'))['frames'] if report.exists() else [];known={(r['frame'],r['view']):r for r in records};started=time.monotonic()
    (a.out/'material-adapters.json').write_text(json.dumps(adapters,ensure_ascii=False,indent=2),'utf-8')
    for job in jobs:
        f,view=job['frame'],job['view'];folder=a.out/('motion' if a.mode=='video' else 'keys');folder.mkdir(exist_ok=True);file=folder/(str(f).zfill(4)+('.png' if a.mode=='video' else '-'+view+'.png'));key=(f,view)
        if key in known:
            if not file.exists() or sha(file)!=known[key]['sha256']:raise ValueError('Existing preview frame mismatch')
            continue
        if time.monotonic()-started>a.budget:break
        if file.exists():raise ValueError('Untracked preview output exists')
        scene.frame_set(f);camera.matrix_world=matrix;camera.data.ortho_scale=scale
        if view in cfg.get('views',{}):
            configured_camera(scene,camera,cfg['views'][view])
        scene.render.filepath=str(file.resolve());t=time.monotonic();render_with_policy(write_still=True);row={'frame':f,'view':view,'file':file.relative_to(a.out).as_posix(),'sha256':sha(file),'seconds':time.monotonic()-t};records.append(row);known[key]=row
        report.write_text(json.dumps({'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'signature':signature,'complete':len(known)==len(jobs),'fps':scene.render.fps/scene.render.fps_base,'size':[width,height],'device':device_report,'samples':samples,'denoise':denoise,'frames':records,'normal_speed_continuous_viewing':False,'source_scene_saved':False,'mode':'Flat-texture device-policy inspection'},indent=2),'utf-8');print('ACTING_PREVIEW_FRAME',f,view,flush=True)
    if sha(a.blend)!=signature['scene_sha256']:raise ValueError('Source file changed')
    print('ACTING_PREVIEW_RESULT',len(known),len(jobs),flush=True)

if __name__=='__main__':main()
