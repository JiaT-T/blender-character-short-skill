"""Save a separate unbaked one-character physics scene with one passive BOX floor."""
from pathlib import Path
import argparse,datetime,hashlib,json,sys
import bpy
sys.dont_write_bytecode=True;sys.path.insert(0,str(Path(__file__).resolve().parent))
from elbow_pole_plan import load_json
from body_motion_plan import sha
from body_motion_runtime import character_rig,geometry_identity
from passive_ground_plan import validate

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['blend','plan','output','report']:p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);paths=[getattr(a,k).resolve() for k in ['blend','plan','output','report']];cfg=validate(load_json(a.plan))
    if len(set(paths))!=4 or a.output.exists() or a.report.exists() or a.output.suffix.lower()!='.blend' or not bpy.app.background or list(bpy.app.version)!=cfg['blender_version'] or sha(a.blend)!=cfg['source_sha256']:raise ValueError('New distinct outputs, reviewed version and unchanged source required')
    types={e.identifier:e.description for e in bpy.types.RigidBodyObject.bl_rna.properties['type'].enum_items};shapes={e.identifier:e.description for e in bpy.types.RigidBodyObject.bl_rna.properties['collision_shape'].enum_items}
    if 'PASSIVE' not in types or 'BOX' not in shapes:raise ValueError('Reviewed native passive BOX interface is unavailable')
    bpy.ops.wm.open_mainfile(filepath=str(a.blend.resolve()),load_ui=False,use_scripts=False);scene=bpy.context.scene;world=scene.rigidbody_world;arm,_=character_rig(scene);identity=geometry_identity(scene,arm)
    if not world or world.point_cache.is_baked or any(o.get('owned_story_passive_floor') for o in scene.objects) or not 1<=scene.frame_start<scene.frame_end<=480 or abs(scene.gravity.x)>1e-6 or abs(scene.gravity.y)>1e-6 or scene.gravity.z>=0:raise ValueError('Unbaked bounded Z-up character world without an existing owned floor required')
    def action_signature():
        action=arm.animation_data.action
        if action is None:raise ValueError('Prepared keyed character action required')
        return hashlib.sha256(json.dumps([(c.data_path,c.array_index,[list(k.co) for k in c.keyframe_points]) for c in action.fcurves],ensure_ascii=False).encode()).hexdigest()
    def properties():return {o.name:[o.rigid_body.type,o.rigid_body.kinematic,o.rigid_body.mass,o.rigid_body.friction,o.rigid_body.restitution,o.rigid_body.collision_shape,list(o.rigid_body.collision_collections)] for o in world.collection.objects if not o.get('owned_story_passive_floor')}
    def settings():return [world.enabled,world.time_scale,world.substeps_per_frame,world.solver_iterations,world.point_cache.frame_start,world.point_cache.frame_end,len(world.constraints.objects),list(scene.gravity),scene.render.fps,scene.render.fps_base]
    original=properties();world_settings=settings();action=action_signature()
    if len(original)+1>1024 or (len(original)+1)*(scene.frame_end-scene.frame_start+1)>500000:raise ValueError('Original physics workload bounds would be exceeded')
    scene.frame_set(scene.frame_start)
    if bpy.context.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT');bpy.ops.mesh.primitive_cube_add(size=2,location=(*cfg['center_xy'],cfg['top_z']-cfg['thickness']/2));floor=bpy.context.object;floor.name='Owned passive story floor collider';floor.scale=(*[n/2 for n in cfg['size_xy']],cfg['thickness']/2);bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);floor['owned_story_passive_floor']=True;floor.hide_render=True
    if 'FINISHED' not in bpy.ops.rigidbody.object_add(type='PASSIVE'):raise RuntimeError('Native documented passive-body operation did not finish')
    floor.rigid_body.collision_shape='BOX'
    if floor.name not in world.collection.objects or floor.rigid_body.type!='PASSIVE' or floor.rigid_body.collision_margin*2>=min(floor.dimensions):raise ValueError('New floor membership/default-margin bounds differ')
    if properties()!=original or settings()!=world_settings or action_signature()!=action or geometry_identity(scene,arm)!=identity:raise ValueError('Original model/action/physics changed')
    data={'object':floor.name,'dimensions':list(floor.dimensions),'top_z':max((floor.matrix_world@v.co).z for v in floor.data.vertices),'type':floor.rigid_body.type,'shape':floor.rigid_body.collision_shape,'friction':floor.rigid_body.friction,'restitution':floor.rigid_body.restitution,'collision_margin':floor.rigid_body.collision_margin,'use_margin':floor.rigid_body.use_margin,'collision_collections':list(floor.rigid_body.collision_collections)}
    if abs(data['top_z']-cfg['top_z'])>1e-7:raise ValueError('Actual box top differs from planned visual floor')
    a.output.parent.mkdir(parents=True,exist_ok=True);bpy.ops.wm.save_as_mainfile(filepath=str(a.output.resolve()),check_existing=False);bpy.ops.wm.open_mainfile(filepath=str(a.output.resolve()),load_ui=False,use_scripts=False);scene=bpy.context.scene;world=scene.rigidbody_world;arm,_=character_rig(scene)
    if properties()!=original or settings()!=world_settings or action_signature()!=action or geometry_identity(scene,arm)!=identity or world.point_cache.is_baked or len(world.collection.objects)!=len(original)+1 or sha(a.blend)!=cfg['source_sha256']:raise ValueError('Separate ground copy failed preservation/reopen')
    result={'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'passive-ground-added-reopened-unbaked-await-simulation','source_sha256':cfg['source_sha256'],'output_sha256':sha(a.output),'plan_sha256':sha(a.plan),'writer_sha256':sha(Path(__file__)),'validator_sha256':sha(Path(__file__).with_name('passive_ground_plan.py')),'runtime_sha256':sha(Path(__file__).with_name('body_motion_runtime.py')),'instructions_review_sha256':cfg['instructions_review_sha256'],'native_object_add_doc':bpy.ops.rigidbody.object_add.__doc__,'native_PASSIVE_description':types['PASSIVE'],'native_BOX_description':shapes['BOX'],'geometry_identity':identity,'original_world_bodies':len(original),'world_bodies_with_owned_ground':len(world.collection.objects),'original_settings':world_settings,'original_action_signature':action,'ground':data,'normal_speed_continuous_viewing':False,'scope':'One additional passive BOX; original rigid-body properties, solver/cache range/gravity, action and model rest/skin preserved. Caller must review matching authoritative instructions before use and align the later display floor. No bake, force/cloth-collision or naturalness approval.'}
    a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),'utf-8');print('PASSIVE_GROUND_ADDED',len(original),len(world.collection.objects))

if __name__=='__main__':main()
