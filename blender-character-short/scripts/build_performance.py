"""Build a configured original-rig performance from a freshly imported baseline.

Character config owns names, proportions, palm/face axes and materials. Story
config owns beats, targets, prop trajectory, cameras, environment and timing.
"""
import argparse,json,math,sys,hashlib,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
import bpy
from mathutils import Vector,Matrix,Euler,Quaternion
from prepare_materials import prepare,flat_material
from gaze_control import aim_existing_control
from contact_motion import bake_contacts
from story_stage import add_story_objects
from support_motion import bake_support
from source_motion_layer import bake_source_layers
from scene_surface_style import apply_matte_style
from scene_asset_import import add_scene_assets

def point(obj,target):obj.rotation_euler=(Vector(target)-obj.location).to_track_quat('-Z','Y').to_euler()

def aim_bone(pb,direction,current_direction=None):
    bpy.context.view_layer.update();current=Vector(current_direction) if current_direction is not None else pb.vector;delta=current.normalized().rotation_difference(Vector(direction).normalized());q=delta@pb.matrix.to_quaternion();desired=Matrix.Translation(pb.head)@q.to_matrix().to_4x4()
    pb.matrix_basis=pb.bone.convert_local_to_pose(desired,pb.bone.matrix_local,parent_matrix=pb.parent.matrix if pb.parent else Matrix.Identity(4),parent_matrix_local=pb.parent.bone.matrix_local if pb.parent else Matrix.Identity(4),invert=True)
    bpy.context.view_layer.update()

def two_bone(upper,lower,wrist,target,pole,reach_fraction=.96):
    # MMD display tails often end at twist helpers. Segment lengths must use
    # anatomical joint heads, not PoseBone.length or the displayed tail.
    s=upper.head.copy();upper_vector=lower.head-s;lu=upper_vector.length;ll=(wrist.head-lower.head).length;delta=target-s;distance=delta.length
    if distance<1e-7:raise ValueError('Hand target coincides with shoulder')
    direction=delta.normalized();reach=min(max(distance,abs(lu-ll)+1e-5),(lu+ll)*reach_fraction);along=(lu*lu-ll*ll+reach*reach)/(2*reach);rise=max(lu*lu-along*along,0)**.5;pv=pole-s;pv-=direction*pv.dot(direction)
    if pv.length<1e-7:raise ValueError('Elbow pole is collinear with shoulder and hand')
    elbow=s+direction*along+pv.normalized()*rise;end=s+direction*reach;aim_bone(upper,elbow-s,upper_vector);aim_bone(lower,end-lower.head,wrist.head-lower.head)
    return {'segment_lengths':[lu,ll],'shoulder':list(s),'requested_target':list(target),'used_target':list(end),'requested_distance':distance,'reach':reach,'clamped':abs(reach-distance)>1e-4,'endpoint_error':(wrist.head-target).length,'used_target_error':(wrist.head-end).length}

def palm_frame(pb,finger,normal,rest_normal):
    u=(pb.bone.tail_local-pb.bone.head_local).normalized();n=Vector(rest_normal);v=n.cross(u).normalized();n=u.cross(v).normalized();rest=Matrix((u,v,n)).transposed();tu=Vector(finger).normalized();tn=Vector(normal);tv=tn.cross(tu).normalized();tn=tu.cross(tv).normalized();dest=Matrix((tu,tv,tn)).transposed();q=dest@rest.transposed()@pb.bone.matrix_local.to_3x3();desired=Matrix.Translation(pb.head)@q.to_4x4();pb.matrix_basis=pb.bone.convert_local_to_pose(desired,pb.bone.matrix_local,parent_matrix=pb.parent.matrix if pb.parent else Matrix.Identity(4),parent_matrix_local=pb.parent.bone.matrix_local if pb.parent else Matrix.Identity(4),invert=True);bpy.context.view_layer.update()

def look_at(pb,target,forward,max_angle):
    rotation=pb.matrix.to_3x3()@pb.bone.matrix_local.to_3x3().inverted();current=rotation@Vector(forward);desired=(target-pb.head).normalized();delta=current.normalized().rotation_difference(desired);limit=math.radians(max_angle)
    if delta.angle>limit:delta=Quaternion().slerp(delta,limit/delta.angle)
    q=delta@pb.matrix.to_quaternion();matrix=Matrix.Translation(pb.head)@q.to_matrix().to_4x4();pb.matrix_basis=pb.bone.convert_local_to_pose(matrix,pb.bone.matrix_local,parent_matrix=pb.parent.matrix if pb.parent else Matrix.Identity(4),parent_matrix_local=pb.parent.bone.matrix_local if pb.parent else Matrix.Identity(4),invert=True)

def principled(name,rgb,rough=.65,metal=0,emission=0):
    m=bpy.data.materials.new(name);m.use_nodes=True;p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*rgb,1);p.inputs['Roughness'].default_value=rough;p.inputs['Metallic'].default_value=metal;p.inputs['Emission Color'].default_value=(*rgb,1);p.inputs['Emission Strength'].default_value=emission;return m

def geometry(name,verts,faces,material):
    me=bpy.data.meshes.new(name);me.from_pydata(verts,[],faces);me.update();o=bpy.data.objects.new(name,me);bpy.context.scene.collection.objects.link(o);o.data.materials.append(material);return o

def make_prop(kind,h,material):
    if kind=='token':
        bpy.ops.mesh.primitive_cube_add(size=1)
        o=bpy.context.object;o.name='Story prop'
        for vertex in o.data.vertices:vertex.co=Vector((vertex.co.x*.075*h,vertex.co.y*.014*h,vertex.co.z*.075*h))
        o.data.materials.append(material);be=o.modifiers.new('Token edge','BEVEL');be.width=.006*h;be.segments=3
        return o
    if kind=='paper-plane':
        verts=[(.10,0,0),(-.08,0,-.025),(-.08,-.08,.018),(-.025,0,.014),(-.08,.08,.018)]
        o=geometry('Story prop',[(h*x,h*y,h*z) for x,y,z in verts],[(0,1,2),(0,3,1),(0,4,1)],material)
        solid=o.modifiers.new('Paper thickness','SOLIDIFY');solid.thickness=h*.0008;return o
    if kind=='star':
        verts=[]
        for y in (-.012,.012):
            for i in range(10):
                a=math.pi/2+i*math.pi/5;r=.05 if i%2==0 else .022;verts.append((h*math.cos(a)*r,h*y,h*math.sin(a)*r))
        return geometry('Story prop',verts,[tuple(reversed(range(10))),tuple(range(10,20))]+[(i,(i+1)%10,(i+1)%10+10,i+10) for i in range(10)],material)
    raise ValueError('Unsupported prop kind: '+kind)

def add_stage(scene,cfg,h,ground):
    floor=principled('Creative set floor',cfg['floor']);panel=principled('Creative set panel',cfg['panel']);trim=principled('Creative set trim',cfg['trim'],.4,.15)
    bpy.ops.mesh.primitive_plane_add(size=h*200,location=(0,0,ground-h*.003));bpy.context.object.name='Studio floor';bpy.context.object.data.materials.append(floor)
    # Architectural panels belong to the set; no extra animated story props.
    panels=cfg.get('panels',[{'position':[x,.7,.8],'size':[.5,.07,1.7]} for x in [-1.1,1.1]])
    for item in panels:
        x,y,z=item['position'];size=item['size'];bevel=item.get('bevel',.08)
        if len(size)!=3 or min(size)<=0 or bevel<0:raise ValueError('Set panel size must be positive and bevel nonnegative')
        bpy.ops.mesh.primitive_cube_add(size=1,location=(h*x,h*y,ground+h*z));o=bpy.context.object;o.name='Backdrop panel';o.scale=Vector(size)*h;o.data.materials.append(panel);be=o.modifiers.new('Soft edges','BEVEL');be.width=h*bevel;be.segments=4
    if cfg.get('stand'):
        s=cfg['stand'];bpy.ops.mesh.primitive_cylinder_add(vertices=48,radius=h*s['radius'],depth=h*s['height'],location=(h*s['x'],h*s['y'],ground+h*s['height']/2));o=bpy.context.object;o.name='Landing pedestal';o.data.materials.append(trim);be=o.modifiers.new('Soft edge','BEVEL');be.width=h*.01;be.segments=3
    strength=cfg.get('world_strength',.35)
    if strength<0:raise ValueError('Set world strength must be nonnegative')
    world=bpy.data.worlds.new('Creative studio world');world.use_nodes=True;world.node_tree.nodes['Background'].inputs[0].default_value=(*cfg.get('world',[.18,.2,.24]),1);world.node_tree.nodes['Background'].inputs[1].default_value=strength;scene.world=world
    defaults=[{'name':name,'location':loc,'energy_per_height_squared':energy,'size':size,'color':rgb,'target':[0,0,.65]} for name,loc,energy,size,rgb in [('Key',(-1.2,-1.7,2.5),150,1.6,(1,.89,.78)),('Fill',(1.4,-.6,1.5),75,1.5,(.72,.86,1)),('Separation',(.5,1,1.9),110,1.0,(1,.92,.82))]]
    lights=cfg.get('lights',defaults)
    for item in lights:
        energy=item['energy_per_height_squared'];size=item['size'];name=item['name']
        if energy<0 or size<=0:raise ValueError('Set light energy must be nonnegative and size positive')
        d=bpy.data.lights.new(name,'AREA');d.energy=energy*h*h;d.shape='DISK';d.size=size*h;d.color=item['color'];o=bpy.data.objects.new(name,d);scene.collection.objects.link(o);o.location=Vector(item['location'])*h;point(o,Vector(item.get('target',[0,0,.65]))*h)
    scene['creative_set_parameters']=json.dumps({'panels':panels,'lights':lights,'world_strength':strength},ensure_ascii=False)
    return {'floor':floor,'panel':panel,'trim':trim}

def raw_compositor(scene):
    scene.use_nodes=True;nt=scene.node_tree;nt.nodes.clear();rl=nt.nodes.new('CompositorNodeRLayers');out=nt.nodes.new('CompositorNodeComposite');nt.links.new(rl.outputs['Image'],out.inputs[0]);scene.render.use_compositing=True
    scene['final_postprocess']='source_post.py: raw linear Image + HX_BloomWeight -> source box/Bloom/curve/LUT. Composite here is raw checkpoint, not final display master.'

def main():
    p=argparse.ArgumentParser();p.add_argument('--baseline',required=True);p.add_argument('--character',required=True);p.add_argument('--story',required=True);p.add_argument('--output',required=True);p.add_argument('--variant',default='A');p.add_argument('--duration',type=float);p.add_argument('--width',type=int,default=640);p.add_argument('--height',type=int,default=360);p.add_argument('--samples',type=int,default=16);p.add_argument('--key-frames',default='');a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);cfg=json.loads(Path(a.character).read_text('utf-8'));story=json.loads(Path(a.story).read_text('utf-8'));out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True)
    if (out/'scene.blend').exists():raise FileExistsError('Version already exists; choose a new output directory')
    bpy.ops.wm.open_mainfile(filepath=str(Path(a.baseline).resolve()));scene=bpy.context.scene;arms=[o for o in scene.objects if o.type=='ARMATURE'];
    if len(arms)!=1:raise ValueError('Expected exactly one character armature; got '+str(len(arms)))
    arm=arms[0];meshes=[o for o in scene.objects if o.type=='MESH' and any(m.type=='ARMATURE' and m.object==arm for m in o.modifiers)]
    for o in list(scene.objects):
        if o.type in ('CAMERA','LIGHT'):bpy.data.objects.remove(o,do_unlink=True)
    for o in [arm,*meshes]:o.animation_data_clear()
    for mesh in meshes:
        if mesh.data.shape_keys:mesh.data.shape_keys.animation_data_clear()
    for pb in arm.pose.bones:pb.matrix_basis=Matrix.Identity(4)
    bones={k:arm.pose.bones.get(v) for k,v in cfg['bones'].items()};missing=[k for k,v in bones.items() if v is None]
    if missing:raise ValueError('Character bone mapping is invalid: '+','.join(missing))
    h=cfg['height'];ground=cfg['ground'];fps=story.get('fps',24);duration=a.duration or story['duration'];end=round(fps*duration);scene.frame_start=1;scene.frame_end=end;scene.render.fps=fps;scene.render.fps_base=1
    scale_time=duration/story['duration'];frame=lambda seconds:max(1,min(end,round(seconds*scale_time*fps)+1));pos=lambda xyz:Vector((xyz[0]*h,xyz[1]*h,ground+xyz[2]*h));inv=arm.matrix_world.inverted();to_arm=lambda xyz:inv@pos(xyz)
    mats_audit,mapped=prepare(scene,meshes,cfg);stage_materials=add_stage(scene,story['set'],h,ground);prop=make_prop(story['prop']['kind'],h,principled('Paper / story color',story['prop']['color'],.7,0,story['prop'].get('emission',0)))
    story_materials={};stage_audit=add_story_objects(scene,story['set'],h,ground,frame,material_sink=story_materials)
    scene_asset_audit=add_scene_assets(scene,a.story,h,ground,story_materials)
    surface_style_audit=apply_matte_style(scene,story['set'].get('matte_style'),stage_materials,story_materials)
    prop_scale=float(story['prop'].get('scale',1))
    if prop_scale<=0:raise ValueError('Prop scale must be positive')
    prop.scale=(prop_scale,)*3
    for key in story['prop']['keys']:
        f=frame(key['t']);prop.location=pos(key['p']);prop.rotation_euler=tuple(math.radians(v) for v in key.get('rotation',[0,0,0]));prop.keyframe_insert('location',frame=f);prop.keyframe_insert('rotation_euler',frame=f)
    # New stories own their choreography. Legacy named performances remain
    # readable for historical scenes; new character mappings need no story table.
    action_audit=[];keys=story['poses'] if 'poses' in story else cfg['performance'][story['performance']]
    if not keys:raise ValueError('Story requires nonempty poses (or a legacy named performance)')
    for key in keys:
        f=frame(key['t']);scene.frame_set(f)
        for pb in arm.pose.bones:pb.matrix_basis=Matrix.Identity(4)
        for semantic,angles in key.get('rotations',{}).items():
            pb=bones[semantic];pb.rotation_mode='QUATERNION';pb.rotation_quaternion=Euler(tuple(math.radians(v) for v in angles),'XYZ').to_quaternion()
        bpy.context.view_layer.update()
        translations=key.get('translations',{})
        for semantic in sorted(translations,key=lambda name:len(bones[name].parent_recursive)):
            offset=translations[semantic]
            if len(offset)!=3 or not all(math.isfinite(float(v)) for v in offset):raise ValueError('Pose translations require three finite world offsets')
            pb=bones[semantic];desired=pb.matrix.copy();desired.translation+=inv.to_3x3()@(Vector(offset)*h)
            pb.matrix_basis=pb.bone.convert_local_to_pose(desired,pb.bone.matrix_local,parent_matrix=pb.parent.matrix if pb.parent else Matrix.Identity(4),parent_matrix_local=pb.parent.bone.matrix_local if pb.parent else Matrix.Identity(4),invert=True)
            bpy.context.view_layer.update()
        bpy.context.view_layer.update();rec={'frame':f,'hands':{}}
        for side in ('left','right'):
            hand=key.get(side+'_hand')
            if hand is None:continue
            rec['hands'][side]=two_bone(bones[side+'_arm'],bones[side+'_elbow'],bones[side+'_wrist'],to_arm(hand['target']),to_arm(hand['pole']),cfg.get('reach_fraction',.96))
            if hand.get('contact') and rec['hands'][side]['endpoint_error']>h*cfg.get('contact_tolerance',.005):raise ValueError(f'Unreachable contact target: {side} frame {f}; correct character/story input before rendering')
            if 'finger' in hand:palm_frame(bones[side+'_wrist'],hand['finger'],hand['normal'],cfg['palm_rest_normal'][side])
        if key.get('look'):look_at(bones['head'],to_arm(key['look']),cfg['head_forward'],cfg.get('head_angle_limit',35))
        if cfg.get('gaze'):
            gaze_target=key.get('eye_look',key.get('look'))
            if gaze_target is not None:rec['gaze']=aim_existing_control(arm,cfg['gaze'],to_arm(gaze_target))
            control=arm.pose.bones[cfg['gaze']['control']];control.rotation_mode='QUATERNION';control.keyframe_insert('rotation_quaternion',frame=f)
        for semantic,pb in bones.items():
            if semantic.endswith('_foot'):continue
            pb.rotation_mode='QUATERNION';pb.keyframe_insert('rotation_quaternion',frame=f)
            pb.keyframe_insert('location',frame=f)
        action_audit.append(rec)
    shape_report={}
    for semantic,keys in story.get('expressions',{}).items():
        name=cfg.get('shapes',{}).get(semantic);found=False
        for mesh in meshes:
            if name and mesh.data.shape_keys and name in mesh.data.shape_keys.key_blocks:
                block=mesh.data.shape_keys.key_blocks[name]
                for t,value in keys:block.value=value*cfg.get('expression_scale',{}).get(semantic,1);block.keyframe_insert('value',frame=frame(t))
                found=True
        shape_report[semantic]={'name':name,'keyed':found}
    for obj in [arm,prop]:
        if obj.animation_data and obj.animation_data.action:
            for fc in obj.animation_data.action.fcurves:
                for key in fc.keyframe_points:key.interpolation='BEZIER';key.handle_left_type='AUTO_CLAMPED';key.handle_right_type='AUTO_CLAMPED'
    source_motion_audit=bake_source_layers(scene,arm,cfg,story.get('source_motion_layers',[]),fps,scale_time)
    support_audit=bake_support(scene,arm,cfg.get('stationary_support',{}),two_bone,h,ground)
    contact_audit=bake_contacts(scene,arm,prop,cfg.get('contact_anchors',{}),story['prop'].get('contacts',[]),h,fps,scale_time,end)
    cameras=[];shot_table=[]
    for i,shot in enumerate(story['camera_variants'][a.variant]):
        d=bpy.data.cameras.new('Shot '+str(i+1));o=bpy.data.objects.new(d.name,d);scene.collection.objects.link(o);o.location=pos(shot['location']);point(o,pos(shot['target']));d.type='ORTHO';d.ortho_scale=shot['scale']*h
        start=frame(shot['start']);stop=frame(shot['end']);marker=scene.timeline_markers.new(shot['purpose'],frame=start);marker.camera=o;cameras.append(o)
        for f,mult in [(start,1),(stop,shot.get('end_scale',1))]:d.ortho_scale=shot['scale']*h*mult;d.keyframe_insert('ortho_scale',frame=f)
        shot_table.append({'shot':i+1,'start':start,'end':stop,'purpose':shot['purpose'],'camera':shot})
    scene.camera=cameras[0];scene.render.engine='BLENDER_EEVEE_NEXT';scene.eevee.taa_render_samples=a.samples;scene.render.resolution_x=a.width;scene.render.resolution_y=a.height;scene.render.resolution_percentage=100;scene.render.film_transparent=False;scene.view_settings.view_transform='Standard';scene.view_settings.look='None';scene.view_settings.exposure=0;scene.view_settings.gamma=1;raw_compositor(scene)
    # Bake the animated head frame into named shader inputs. No runtime handler
    # or external script is needed when the saved project is reopened.
    face_mats=[m for m in mapped.values() if m.use_nodes and m.node_tree.nodes.get('FaceObjectY')];face_baked=0
    foot=[];prop_trace=[]
    for f in range(1,end+1):
        scene.frame_set(f);bpy.context.view_layer.update();head=bones['head'];R=arm.matrix_world.to_3x3()@head.matrix.to_3x3()@head.bone.matrix_local.to_3x3().inverted()
        for m in face_mats:
            for name,key in [('FaceObjectY','face_rest_y'),('FaceObjectZ','face_rest_z')]:
                axis=(R@Vector(cfg[key])).normalized();node=m.node_tree.nodes[name]
                for i in range(3):node.inputs[i].default_value=axis[i];node.inputs[i].keyframe_insert('default_value',frame=f)
        if f in (1,end) or f%12==0:
            foot.append({'frame':f,**{k:list(arm.matrix_world@bones[k].head) for k in ('left_foot','right_foot')}});prop_trace.append({'frame':f,'position':list(prop.location)})
    face_baked=len(face_mats);scene.frame_set(1);bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(out/'scene.blend'))
    report={'character':cfg['id'],'baseline':str(Path(a.baseline).resolve()),'character_config':str(Path(a.character).resolve()),'story':story['title'],'story_config':str(Path(a.story).resolve()),'variant':a.variant,'fps':fps,'frames':end,'duration':end/fps,'control':'Original MMD deformation skeleton; analytic arm target poses baked as FK quaternions; original legs/IK preserved','material_audit':mats_audit,'poses':action_audit,'shapes':shape_report,'face_materials_with_baked_axes':face_baked,'feet':foot,'prop_trace':prop_trace,'shots':shot_table,'strict_render_pass':False,'postprocess_required':True}
    report['prop_contact']=contact_audit
    report['stationary_support']=support_audit
    if support_audit['status']=='baked-stationary-FK':
        report['control']='Original MMD deform bones; analytic arm targets baked as FK; configured stationary leg support baked as FK with original IK constraints muted'
    report['source_motion_layers']=source_motion_audit
    report['creative_set']=json.loads(scene['creative_set_parameters'])
    report['narrative_set']=stage_audit
    if scene_asset_audit is not None:report['scene_assets']=scene_asset_audit
    if surface_style_audit is not None:report['scene_surface_style']=surface_style_audit
    (out/'build-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');(out/'character.json').write_text(json.dumps(cfg,ensure_ascii=False,indent=2),encoding='utf-8');(out/'story.json').write_text(json.dumps(story,ensure_ascii=False,indent=2),encoding='utf-8')
    timings=[]
    for f in [int(v) for v in a.key_frames.split(',') if v]:
        scene.frame_set(f);scene.render.image_settings.file_format='PNG';scene.render.filepath=str(out/f'key-raw-{f:04}.png');t=time.monotonic();bpy.ops.render.render(write_still=True);timings.append([f,time.monotonic()-t])
    (out/'key-render-times.json').write_text(json.dumps(timings),encoding='utf-8');print('PERFORMANCE_BUILT',cfg['id'],end,face_baked,timings,flush=True)

if __name__=='__main__':main()
