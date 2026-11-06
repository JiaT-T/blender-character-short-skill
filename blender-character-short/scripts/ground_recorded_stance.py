"""Bounded root-height adaptation for explicitly stationary recorded actions.

Keep recorded joint rotations, horizontal travel and all non-root-location keys.
Set only an unconstrained ancestral controller's location to place the lowest
actual weighted sole on the supplied floor at integer frames. No XY footplant,
flight detection, rigid forces, subframe or naturalness acceptance is implied.
"""
from pathlib import Path
import argparse,datetime,hashlib,json,math,sys
sys.dont_write_bytecode=True;sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy,numpy as np
from mathutils import Matrix,Vector
from body_motion_runtime import character_rig,geometry_identity,select_feet,foot_points,bone_worlds,linear_curves

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ['blend','plan','output','report']:parser.add_argument('--'+key,required=True,type=Path)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    if not bpy.app.background:raise ValueError('Use an isolated background process')
    if args.output.exists() or args.report.exists() or args.output.suffix.lower()!='.blend' or args.report.suffix.lower()!='.json':raise ValueError('New blend/report outputs required')
    if args.plan.stat().st_size>65536:raise ValueError('Standing support plan exceeds64KB')
    plan=json.loads(args.plan.read_text(encoding='utf-8'))
    fields={'schema','source_sha256','mode','root_bone','height','ground','frames','fps','feet','weight_threshold','maximum_correction_H','maximum_step_H'}
    if not isinstance(plan,dict) or set(plan)!=fields or type(plan['schema']) is not int or plan['schema']!=1 or plan['mode']!='declared-stationary':raise ValueError('Explicit stationary-support schema1 required')
    if not isinstance(plan['root_bone'],str) or not plan['root_bone']:raise ValueError('Original unconstrained ancestor controller required')
    if not isinstance(plan['frames'],list) or len(plan['frames'])!=2 or any(type(v) is not int for v in plan['frames']) or not 1<=plan['frames'][0]<plan['frames'][1]<=20000:raise ValueError('Explicit integer standing range required')
    if type(plan['fps']) is not int or not 1<=plan['fps']<=120:raise ValueError('Explicit fps required')
    for key,lo,hi in [('height',.1,10),('ground',-100,100),('maximum_correction_H',.00001,.03),('maximum_step_H',.000001,.01),('weight_threshold',.001,1)]:
        x=plan[key]
        if type(x) not in [int,float] or not math.isfinite(x) or not lo<=x<=hi:raise ValueError('Invalid support bound: '+key)
    if not isinstance(plan['feet'],dict) or set(plan['feet'])!={'left','right'} or any(not isinstance(v,dict) or set(v)!={'deform_root'} or not isinstance(v['deform_root'],str) or not v['deform_root'] for v in plan['feet'].values()):raise ValueError('Two actual weighted foot deform roots required')
    source_hash=sha(args.blend)
    if plan['source_sha256']!=source_hash:raise ValueError('Standing source scene changed')
    bpy.ops.wm.open_mainfile(filepath=str(args.blend.resolve()),load_ui=False,use_scripts=False)
    scene=bpy.context.scene;arm,actor=character_rig(scene);first,last=plan['frames'];count=last-first+1
    if [scene.frame_start,scene.frame_end]!=[first,last] or scene.render.fps/scene.render.fps_base!=plan['fps'] or scene.rigidbody_world is not None:raise ValueError('Support adaptation requires the full pre-physics source interval')
    meshes=[o for o in scene.objects if o.type=='MESH' and any(m.type=='ARMATURE' and m.object==arm for m in o.modifiers)]
    if count>480 or count*len(arm.pose.bones)>500000 or count*sum(len(o.data.vertices) for o in meshes)>25000000:raise ValueError('Standing support evaluation work bound exceeded')
    root=arm.pose.bones.get(plan['root_bone'])
    if root is None or any(not c.mute and c.influence>0 for c in root.constraints) or not arm.animation_data or not arm.animation_data.action:raise ValueError('Unconstrained keyed original root controller required')
    path=root.path_from_id('location')
    if any(c.data_path==path for c in arm.animation_data.drivers):raise ValueError('Driven root location is outside this route')
    allowed={root.name,*[b.name for b in root.children_recursive]};names=list(arm.pose.bones.keys());selection=select_feet(scene,arm,plan);identity=geometry_identity(scene,arm)
    def signature():return [(c.data_path,c.array_index,[(list(k.co),k.interpolation,list(k.handle_left),list(k.handle_right)) for k in c.keyframe_points]) for c in arm.animation_data.action.fcurves if c.data_path!=path]
    preserved=signature();states=[]
    for frame in range(first,last+1):
        scene.frame_set(frame);bpy.context.view_layer.update()
        minimum=min(p.z for side in ['left','right'] for _,_,p in foot_points(selection,side))
        correction=plan['ground']-minimum
        if not math.isfinite(correction) or abs(correction)>plan['maximum_correction_H']*plan['height']:raise ValueError('Measured sole correction exceeds declared bound at '+str(frame))
        if states and abs(correction-states[-1]['correction'])>plan['maximum_step_H']*plan['height']:raise ValueError('Sole correction would create an excessive root step at '+str(frame))
        states.append({'frame':frame,'correction':correction,'minimum_before':minimum,'location':root.location.copy(),'worlds':bone_worlds(arm,names)})
    old=arm.animation_data.action;slot=arm.animation_data.action_slot.identifier if arm.animation_data.action_slot else None
    arm.animation_data.action=old.copy()
    if slot:
        slots=[s for s in arm.animation_data.action.slots if s.identifier==slot]
        if len(slots)!=1:raise ValueError('Source action slot cannot be preserved')
        arm.animation_data.action_slot=slots[0]
    for state in states:
        scene.frame_set(state['frame']);root.location=state['location'];bpy.context.view_layer.update()
        world=arm.matrix_world@root.matrix;world.translation+=Vector((0,0,state['correction']))
        desired=arm.matrix_world.inverted()@world
        basis=root.bone.convert_local_to_pose(desired,root.bone.matrix_local,parent_matrix=root.parent.matrix if root.parent else Matrix.Identity(4),parent_matrix_local=root.parent.bone.matrix_local if root.parent else Matrix.Identity(4),invert=True)
        root.location=basis.to_translation();root.keyframe_insert('location',frame=state['frame'])
    for curve in arm.animation_data.action.fcurves:
        if curve.data_path==path:
            for key in curve.keyframe_points:key.interpolation='LINEAR'
    maximum_world=0.;maximum_floor=0.;rows=[]
    for state in states:
        scene.frame_set(state['frame']);bpy.context.view_layer.update();expected=state['worlds'].copy()
        for i,name in enumerate(names):
            if name in allowed:expected[i,2,3]+=state['correction']
        maximum_world=max(maximum_world,float(np.max(np.abs(bone_worlds(arm,names)-expected))))
        minimum=min(p.z for side in ['left','right'] for _,_,p in foot_points(selection,side));maximum_floor=max(maximum_floor,abs(minimum-plan['ground']))
        rows.append({'frame':state['frame'],'root_height_correction_m':state['correction'],'minimum_sole_before_m':state['minimum_before'],'minimum_sole_after_m':minimum})
    if maximum_world>1e-5 or maximum_floor>1e-5 or signature()!=preserved or geometry_identity(scene,arm)!=identity or sha(args.blend)!=source_hash:raise ValueError('Root-only body/sole/source preservation check failed: '+str([maximum_world,maximum_floor]))
    scene.frame_set(first);args.output.parent.mkdir(parents=True,exist_ok=True);bpy.ops.wm.save_as_mainfile(filepath=str(args.output.resolve()),check_existing=False)
    report={'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'stationary-root-height-adapted-await-reopen-and-visuals',
            'input_sha256':source_hash,'output':str(args.output.resolve()),'output_sha256':sha(args.output),'plan_sha256':sha(args.plan),'writer_sha256':sha(Path(__file__)),
            'root_bone':root.name,'frames':[first,last],'fps':plan['fps'],'geometry_identity':identity,'source_unchanged':True,
            'non_root_location_channels_unchanged':True,'maximum_bone_world_expected_translation_error':maximum_world,
            'maximum_integer_lowest_sole_floor_error_m':maximum_floor,'maximum_root_correction_m':max(abs(r['root_height_correction_m']) for r in rows),'rows':rows,
            'normal_speed_continuous_viewing':False,'scope':'Explicit stationary support only, signed vertical ancestor-controller translation measured from actual weighted soles. Recorded joint rotations/scale/horizontal motion retained, original rest/skin/weights/morphs retained. No horizontal material pin, per-foot full support, force/friction, subframe, physics or naturalness acceptance.'}
    args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in report.items() if k!='rows'}))

if __name__=='__main__':main()
