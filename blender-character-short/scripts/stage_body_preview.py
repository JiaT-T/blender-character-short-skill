"""Save a new minimal full-body inspection stage and external flat-preview profile."""
from pathlib import Path
import argparse,itertools,json,sys,math,hashlib
sys.dont_write_bytecode=True;sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy,numpy as np
from mathutils import Vector
from body_motion_plan import sha
from body_motion_runtime import character_rig,meshes_for,geometry_identity

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['blend','mapping','output','profile','report']:p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);paths=[getattr(a,k).resolve() for k in ['blend','mapping','output','profile','report']]
    if len(set(paths))!=5 or any(p.exists() for p in [a.output,a.profile,a.report]) or a.output.suffix!='.blend':raise ValueError('Preserve inputs and choose new distinct outputs')
    cfg=json.loads(a.mapping.read_text('utf-8'));preview=cfg.get('preview',{});size=preview.get('size',[512,384]);samples=preview.get('samples',2);margin=preview.get('margin',1.08);ground=cfg['ground'];h=cfg['height']
    if len(size)!=2 or any(type(v) is not int or not 32<=v<=640 for v in size) or type(samples) is not int or not 1<=samples<=4 or not 1<=margin<=1.5 or not math.isfinite(ground) or not .1<h<10:raise ValueError('Bounded preview dimensions/samples/margin/ground/height required')
    original=sha(a.blend);bpy.ops.wm.open_mainfile(filepath=str(a.blend.resolve()),load_ui=False,use_scripts=False);scene=bpy.context.scene;arm,actor=character_rig(scene);meshes=meshes_for(scene,arm);identity=geometry_identity(scene,arm);first,last=scene.frame_start,scene.frame_end
    follow=preview.get('follow_bone');axes=preview.get('follow_axes',[True,True,False])
    if follow is not None and (not isinstance(follow,str) or follow not in arm.pose.bones):raise ValueError('Preview follow_bone must be an existing original bone')
    if not isinstance(axes,list) or len(axes)!=3 or any(type(x) is not bool for x in axes):raise ValueError('Preview follow_axes requires three booleans')
    def origin():
        if follow is None:return Vector((0,0,0))
        point=(arm.matrix_world@arm.pose.bones[follow].matrix).translation
        return Vector(tuple(point[i] if axes[i] else 0 for i in range(3)))
    def action_identity():
        action=arm.animation_data.action if arm.animation_data else None
        return hashlib.sha256(json.dumps([(c.data_path,c.array_index,[list(k.co) for k in c.keyframe_points]) for c in action.fcurves]).encode()).hexdigest() if action else None
    body_before=action_identity()
    if not 1<=first<last<=480:raise ValueError('Bounded animation timeline required')
    frames=sorted(set(round(first+(last-first)*i/8) for i in range(9))|{m.frame for m in scene.timeline_markers if first<=m.frame<=last}|set(preview.get('key_frames',[])))
    if len(frames)>64 or any(type(f) is not int or not first<=f<=last for f in frames):raise ValueError('Bounded in-range key frames required')
    points=[]
    for f in frames:
        scene.frame_set(f);bpy.context.view_layer.update();following_origin=np.asarray(origin())
        for obj in meshes:
            ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh()
            try:
                v=np.empty(len(me.vertices)*3,np.float32);me.vertices.foreach_get('co',v);v=v.reshape(-1,3);m=np.asarray(ev.matrix_world);v=v@m[:3,:3].T+m[:3,3]-following_origin
                if not np.isfinite(v).all():raise ValueError('Nonfinite sampled skin')
                lo,hi=v.min(axis=0),v.max(axis=0);points.extend([[lo[k] if bit[k]==0 else hi[k] for k in range(3)] for bit in itertools.product([0,1],repeat=3)])
            finally:ev.to_mesh_clear()
    owned={o for o in scene.objects if o.get('owned_story_prop')};prop=scene.objects.get(cfg.get('prop',{}).get('name',''))
    if prop:owned.update({prop,*prop.children_recursive})
    collection=bpy.data.collections.new('Owned visible story props');scene.collection.children.link(collection)
    for obj in owned:
        for old in list(obj.users_collection):old.objects.unlink(obj)
        collection.objects.link(obj);obj.hide_render=False;obj.hide_set(False)
    for obj in list(scene.objects):
        if obj.type in ['CAMERA','LIGHT','CURVE'] or obj.type=='MESH' and obj not in meshes and obj not in owned:obj.hide_render=True;obj.hide_set(True)
    for marker in list(scene.timeline_markers):
        if marker.camera:scene.timeline_markers.remove(marker)
    pts=np.asarray(points);center=(pts.min(axis=0)+pts.max(axis=0))/2;z=Vector(preview.get('camera_direction',[.65,-1,.25])).normalized();up=Vector((0,0,1))-z*z.z
    if up.length<1e-6:raise ValueError('Inspection camera must have a horizontal component')
    up.normalize();right=up.cross(z).normalized();relative=pts-center;scale=max(float(np.ptp(relative@np.asarray(right))),float(np.ptp(relative@np.asarray(up)))*size[0]/size[1])*margin;camera=bpy.data.objects.new('Full-body inspection camera',bpy.data.cameras.new('Full-body inspection camera'));scene.collection.objects.link(camera);camera.location=Vector(center)+z*5;camera.rotation_euler=(Vector(center)-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.type='ORTHO';camera.data.ortho_scale=scale;scene.camera=camera;scene.render.resolution_x,scene.render.resolution_y=size;scene.render.resolution_percentage=100
    def material(name,colour):
        m=bpy.data.materials.new(name);m.diffuse_color=(*colour,1);m.use_nodes=True;m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(*colour,1);return m
    bpy.ops.mesh.primitive_plane_add(size=20,location=(0,0,ground));bpy.context.object.name='Owned action floor';bpy.context.object.data.materials.append(material('Owned action floor',(.11,.14,.16)));grid=material('Owned action grid',(.18,.22,.23))
    for axis in [0,1]:
        for i in range(-8,9):
            bpy.ops.mesh.primitive_plane_add(size=1,location=(i*.5 if axis==0 else 0,i*.5 if axis==1 else 0,ground+.0003));o=bpy.context.object;o.name='Owned ground reference grid';o.scale=(.006,8,1) if axis==0 else (8,.006,1);o.data.materials.append(grid)
    materials={}
    for mat in {m for o in scene.objects if o.type=='MESH' and not o.hide_render for m in o.data.materials if m}:
        images=[n for n in mat.node_tree.nodes if n.type=='TEX_IMAGE' and n.image] if mat.use_nodes else [];images.sort(key=lambda n:100 if n.name=='mmd_base_tex' else 10 if any(s in n.name.lower() for s in ['base','diffuse']) else 0,reverse=True);base=images[0] if images else None;opacity=float(mat.get('mmd_material',{}).get('alpha',mat.diffuse_color[3]));bsdf=mat.node_tree.nodes.get('Principled BSDF') if mat.use_nodes else None;colour=list(bsdf.inputs['Base Color'].default_value[:3]) if bsdf else list(mat.diffuse_color[:3]);materials[mat.name]={'image_node':base.name,'use_image_alpha':base.image.alpha_mode=='STRAIGHT','opacity':opacity} if base else {'color':colour,'opacity':opacity}
    views={'side':{'follow_object':actor.name,'camera_offset_m':[2.2*h,0,.63*h],'target_offset_m':[0,0,.52*h],'ortho_scale_m':h*1.68},'feet':{'follow_object':actor.name,'camera_offset_m':[1.65*h,0,.22*h],'target_offset_m':[0,0,.154*h],'ortho_scale_m':h*.66},'face':{'follow_bone':{'armature':arm.name,'bone':cfg['bones']['head']},'camera_offset_m':[.044*h,-1.65*h,.055*h],'target_offset_m':[0,-.0165*h,.044*h],'ortho_scale_m':h*.36}};face_frames=preview.get('face_frames',[m.frame for m in scene.timeline_markers][-3:]);profile={'size':size,'samples':samples,'brightness':.9,'background':[.027,.045,.058],'materials':materials,'views':views,'keys':[{'frame':f,'view':view} for view in ['wide','side','feet'] for f in frames]+[{'frame':f,'view':'face'} for f in face_frames if first<=f<=last]}
    if follow is not None:
        offset=Vector(center)+z*5;target=Vector(center);binding={'armature':arm.name,'bone':follow}
        views['follow']={'follow_bone':binding,'follow_axes':axes,'camera_offset_m':list(offset),'target_offset_m':list(target),'ortho_scale_m':scale}
        for label in ['side','feet']:
            views[label].pop('follow_object');views[label].update(follow_bone=binding,follow_axes=axes)
        profile['video_view']='follow'
        for row in profile['keys']:
            if row['view']=='wide':row['view']='follow'
        for f in range(first,last+1):
            scene.frame_set(f);bpy.context.view_layer.update();camera.location=offset+origin();camera.keyframe_insert('location',frame=f)
        for curve in camera.animation_data.action.fcurves:
            for key in curve.keyframe_points:key.interpolation='LINEAR'
    scene.frame_set(first)
    if geometry_identity(scene,arm)!=identity or sha(a.blend)!=original or action_identity()!=body_before:raise ValueError('Original source geometry/body action changed')
    for path in [a.output,a.profile,a.report]:path.parent.mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(a.output.resolve()));a.profile.write_text(json.dumps(profile,ensure_ascii=False,indent=2),'utf-8');a.report.write_text(json.dumps({'source_sha256':original,'staged_sha256':sha(a.output),'mapping_sha256':sha(a.mapping),'profile_sha256':sha(a.profile),'writer_sha256':sha(Path(__file__)),'frames':[first,last],'camera_ortho_m':scale,'sampled_bounds_min':pts.min(axis=0).tolist(),'sampled_bounds_max':pts.max(axis=0).tolist(),'owned_story_objects':[o.name for o in owned],'follow_bone':follow,'follow_axes':axes if follow else None,'body_action_signature_preserved':body_before,'camera_motion_baked_integer_frames':last-first+1 if follow else 0,'scope':'Same rig/body action, new diagnostic floor/grid and camera. Optional bone following uses root-relative sampled bounds and saved integer camera keys; rendering and whole-frame containment remain separate.'},ensure_ascii=False,indent=2),'utf-8');print('BODY_PREVIEW_STAGED',str(a.output),flush=True)

if __name__=='__main__':main()
