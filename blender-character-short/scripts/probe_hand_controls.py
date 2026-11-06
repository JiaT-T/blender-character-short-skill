"""Read actual local-axis skin response, including protected nonfinger bones."""
from pathlib import Path
import argparse,json,sys,datetime,math
sys.dont_write_bytecode=True;sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy,numpy as np
from mathutils import Quaternion
from hand_control_plan import profile
from hand_control_runtime import sha,bind,geometry_signature,protection,worlds,evaluated

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['blend','profile','report']:p.add_argument('--'+name,required=True,type=Path)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);assert not a.report.exists();before=sha(a.blend);mapping=profile(json.loads(a.profile.read_text('utf-8')));bpy.ops.wm.open_mainfile(filepath=str(a.blend),load_ui=False,use_scripts=False);scene=bpy.context.scene;scene.frame_set(scene.frame_start);arm,meshes,selection,regions,binding=bind(scene,mapping,require_bound=False);identity=geometry_signature(arm,meshes);bases={j['bone']:arm.pose.bones[j['bone']].matrix_basis.copy() for j in mapping['joints']};names=sorted(arm.pose.bones.keys());original_world=worlds(arm,names);baseline=evaluated(scene,meshes,selection);rows=[]
    for joint in mapping['joints']:
        for axis in joint['axes']:
            for name,basis in bases.items():arm.pose.bones[name].matrix_basis=basis
            pose=arm.pose.bones[joint['bone']];pose.rotation_mode='QUATERNION';degrees=min(15.,axis['limit_degrees']);pose.rotation_quaternion=bases[pose.name].to_quaternion()@Quaternion(axis['axis_local'],math.radians(degrees));bpy.context.view_layer.update();allowed,protected,objects,attached=protection(arm,scene,[joint['bone']]);after=evaluated(scene,meshes,selection);distances=[]
            for name,selected in selection.items():distances.extend((after[name][i]-baseline[name][i]).length for i in selected['indices'])
            protected_indices=[names.index(name) for name in protected];error=float(np.max(np.abs(worlds(arm,protected)-original_world[protected_indices]))) if protected else 0.;rows.append({'joint':joint['id'],'axis':axis['id'],'bone':joint['bone'],'test_degrees':degrees,'moved_weighted_hand_vertices':sum(x>1e-6 for x in distances),'maximum_hand_displacement_world':max(distances,default=0),'protected_nonselected_bone_world_error':error,'exact_allowed_bone_names':sorted(allowed),'attached_object_names':attached});print('HAND_AXIS_RESPONSE',joint['id'],axis['id'],rows[-1]['moved_weighted_hand_vertices'],error,flush=True)
    for name,basis in bases.items():arm.pose.bones[name].matrix_basis=basis
    bpy.context.view_layer.update();assert sha(a.blend)==before and geometry_signature(arm,meshes)==identity
    result={'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'readonly-evaluated-hand-axis-probe-complete','source_sha256':before,'profile_sha256':sha(a.profile),'writer_sha256':sha(Path(__file__)),'runtime_sha256':sha(Path(__file__).with_name('hand_control_runtime.py')),'binding_sha256':binding,'bone_count':len(names),'source_fps':scene.render.fps,'source_frame_range':[scene.frame_start,scene.frame_end],'skin_geometry_signature':identity,'axis_responses':rows,'all_axes_have_evaluated_response':all(r['moved_weighted_hand_vertices']>0 for r in rows),'all_protected_bones_unchanged_within1e-5':all(r['protected_nonselected_bone_world_error']<1e-5 for r in rows),'source_unchanged':True,'scope':'Actual configured local-axis response of original weighted geometry; no automatic anatomical/palm-polarity correctness, combined-pose collision, contact or naturalness acceptance.'};a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf-8')
if __name__=='__main__':main()
