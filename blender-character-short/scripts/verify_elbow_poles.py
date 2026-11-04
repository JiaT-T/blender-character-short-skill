"""Generated-rig verification; no user model, clip, texture or network required."""
from pathlib import Path
import argparse,sys,json,hashlib,math
sys.dont_write_bytecode=True
import bpy,numpy as np
from mathutils import Euler,Vector,Quaternion
sys.path.insert(0,str(Path(__file__).resolve().parent))
from bake_elbow_poles import bake,main as cli,angle,checked
from elbow_pole_plan import load_json,validate_plan

def fingerprint(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def make_fixture(path,transformed=False):
    bpy.ops.wm.read_factory_settings(use_empty=True);s=bpy.context.scene;s.frame_start=1;s.frame_end=5
    actor=bpy.data.objects.new('Generated moving actor',None);s.collection.objects.link(actor)
    data=bpy.data.armatures.new('Generated armature');arm=bpy.data.objects.new('Generated armature',data);s.collection.objects.link(arm);arm.parent=actor;bpy.context.view_layer.objects.active=arm;arm.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
    definitions=[('upper',(0,0,1),(.4,0,.8),None),('lower',(.4,0,.8),(.75,0,.9),'upper'),('wrist',(.75,0,.9),(.9,0,.9),'lower'),('protected',(-.4,0,1),(-.4,0,1.4),None),('dependent',(-.2,.1,.5),(-.2,.1,.7),None)]
    for name,head,tail,parent in definitions:
        b=data.edit_bones.new(name);b.head=head;b.tail=tail
        if parent:b.parent=data.edit_bones[parent]
    bpy.ops.object.mode_set(mode='OBJECT');con=arm.pose.bones['dependent'].constraints.new('COPY_ROTATION');con.target=arm;con.subtarget='lower'
    marker=bpy.data.objects.new('Generated wrist attachment',None);s.collection.objects.link(marker);marker.parent=arm;marker.parent_type='BONE';marker.parent_bone='wrist';marker.location=(.03,.02,.01)
    if transformed:actor.rotation_euler=(.3,-.2,.6);actor.scale=(.7,)*3
    for f in range(1,6):
        s.frame_set(f);actor.location=(1.2+.03*f,-.7+.01*f,.4) if transformed else (.02*f,0,0);actor.keyframe_insert('location',frame=f)
        for name,angles in [('upper',(.03*f,.02*f,.04*f)),('lower',(-.02*f,.03*f,-.02*f)),('wrist',(.01*f,.03*f,.02*f)),('protected',(.01*f,0,0))]:
            b=arm.pose.bones[name];b.rotation_mode='QUATERNION';b.rotation_quaternion=Euler(angles).to_quaternion();b.keyframe_insert('rotation_quaternion',frame=f)
    for obj in [actor,arm]:
        for curve in obj.animation_data.action.fcurves:
            for key in curve.keyframe_points:key.interpolation='LINEAR'
    s.frame_set(1);bpy.ops.wm.save_as_mainfile(filepath=str(path));return s,arm

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);records=[]
    character={'height':1.4,'ground':0.,'bones':{'left_arm':'upper','left_elbow':'lower','left_wrist':'wrist'}}
    plan={'schema':1,'side':'left','start':2,'blend_end':3,'end':4,'pole':[.3,.9,.2]}
    def check(name,condition,detail=None):
        records.append({'name':name,'pass':bool(condition),'detail':detail})
        if not condition:raise AssertionError(name+': '+str(detail))
    for transformed in (False,True):
        base=out/('transformed-baseline.blend' if transformed else 'origin-baseline.blend');s,arm=make_fixture(base,transformed);before=fingerprint(base);expected=[]
        for f in range(1,6):s.frame_set(f);bpy.context.view_layer.update();expected.append(np.asarray(arm.matrix_world@arm.pose.bones['wrist'].matrix))
        result=bake(s,arm,character,plan);candidate=out/('transformed-result.blend' if transformed else 'origin-result.blend');bpy.ops.wm.save_as_mainfile(filepath=str(candidate));bpy.ops.wm.open_mainfile(filepath=str(candidate),load_ui=False,use_scripts=False);s=bpy.context.scene;arm=s.objects['Generated armature'];maximum=0.
        for f in range(1,6):s.frame_set(f);bpy.context.view_layer.update();maximum=max(maximum,float(np.max(np.abs(np.asarray(arm.matrix_world@arm.pose.bones['wrist'].matrix)-expected[f-1]))))
        check('saved-reopen-'+('transformed-moving-parent' if transformed else 'origin-moving-parent'),maximum<1e-5 and fingerprint(base)==before and 'dependent' in result['allowed_dependency_bones'],{'wrist_world_matrix_error':maximum,'errors':result['maximum_errors']})
        bpy.ops.wm.open_mainfile(filepath=str(base),load_ui=False,use_scripts=False);s=bpy.context.scene;arm=s.objects['Generated armature']
        release_plan={**plan,'schema':2,'start':1,'blend_end':2,'release_start':3,'end':5};released=bake(s,arm,character,release_plan);release_path=out/('transformed-release.blend' if transformed else 'origin-release.blend');bpy.ops.wm.save_as_mainfile(filepath=str(release_path));bpy.ops.wm.open_mainfile(filepath=str(release_path),load_ui=False,use_scripts=False);s=bpy.context.scene;arm=s.objects['Generated armature'];maximum=0.
        for f in range(1,6):s.frame_set(f);bpy.context.view_layer.update();maximum=max(maximum,float(np.max(np.abs(np.asarray(arm.matrix_world@arm.pose.bones['wrist'].matrix)-expected[f-1]))))
        check('smooth-release-saved-reopen-'+('transformed' if transformed else 'origin'),maximum<1e-5 and fingerprint(base)==before and max(released['maximum_errors'].values())<.05,{'wrist_world_matrix_error':maximum,'errors':released['maximum_errors']})
    positive=Euler((.2,.4,.3)).to_quaternion();negative=positive.copy();negative.negate();check('quaternion-sign-equivalence',angle(positive.rotation_difference(negative))<.001)
    base=out/'origin-baseline.blend';bpy.ops.wm.open_mainfile(filepath=str(base),load_ui=False,use_scripts=False);s=bpy.context.scene;arm=s.objects['Generated armature'];s.frame_set(2);bpy.context.view_layer.update();elbow=arm.matrix_world@arm.pose.bones['lower'].head;noop={**plan,'start':2,'blend_end':2,'end':2,'pole':[elbow.x/1.4,elbow.y/1.4,elbow.z/1.4]};result=bake(s,arm,character,noop);check('existing-elbow-noop',max(result['maximum_errors'].values())<1e-5,result['maximum_errors'])
    def refusal(name,operation,expected):
        try:operation()
        except (ValueError,FileExistsError) as exc:check(name,expected in str(exc),str(exc))
        else:check(name,False,'Expected refusal did not occur')
    for name,bad in [('boolean-frame',{**plan,'start':True}),('nan-pole',{**plan,'pole':[0,float('nan'),0]}),('out-of-scene',{**plan,'end':6}),('reversed-window',{**plan,'start':4}),('unknown-field',{**plan,'typo':1})]:refusal(name,lambda bad=bad:validate_plan(bad,1,5,1.4,0),'')
    for name,bad in [('release-end-equal',{**plan,'schema':2,'release_start':4}),('release-before-blend',{**plan,'schema':2,'release_start':2}),('release-boolean',{**plan,'schema':2,'release_start':True}),('schema1-extra-release',{**plan,'release_start':3})]:refusal(name,lambda bad=bad:validate_plan(bad,1,5,1.4,0),'')
    refusal('nonfinite-matrix-cannot-report-zero-error',lambda:checked([[float('nan')]]),'Nonfinite')
    refusal('nonfinite-quaternion-cannot-report-zero-angle',lambda:angle(Quaternion((float('nan'),0,0,0))),'Invalid evaluated wrist quaternion')
    refusal('overflowed-quaternion-norm-rejected',lambda:angle(Quaternion((1e38,1e38,0,0))),'Invalid evaluated wrist quaternion')
    duplicate=out/'duplicate.json';duplicate.write_text('{"schema":1,"schema":1}','utf-8');refusal('duplicate-json-key',lambda:load_json(duplicate),'Duplicate JSON key')
    bpy.ops.wm.open_mainfile(filepath=str(base),load_ui=False,use_scripts=False);s=bpy.context.scene;arm=s.objects['Generated armature'];bad_character={**character,'bones':{**character['bones'],'left_arm':'wrist'}};refusal('invalid-bone-chain',lambda:bake(s,arm,bad_character,plan),'Missing/distinct')
    constraint=arm.pose.bones['lower'].constraints.new('IK');refusal('active-ik-preserved-and-refused',lambda:bake(s,arm,character,plan),'Active arm IK');check('ik-not-muted',not constraint.mute)
    bpy.ops.wm.open_mainfile(filepath=str(base),load_ui=False,use_scripts=False);s=bpy.context.scene;arm=s.objects['Generated armature'];s.frame_end=1201;refusal('bounded-runtime-work',lambda:bake(s,arm,character,plan),'Bake exceeds')
    s.frame_end=1000
    for index in range(500):s.collection.objects.link(bpy.data.objects.new('Owned budget object'+str(index),None))
    refusal('combined-bone-object-frame-budget',lambda:bake(s,arm,character,plan),'Combined bone/object-frame budget')
    cfg=out/'character.json';cfg.write_text(json.dumps(character),'utf-8');jp=out/'plan.json';jp.write_text(json.dumps(plan),'utf-8');existing=out/'origin-result.blend';existing_hash=fingerprint(existing);refusal('existing-output-preserved',lambda:cli(['--blend',str(base),'--character',str(cfg),'--plan',str(jp),'--output',str(existing),'--report',str(out/'must-not-exist.json')]),'Preserve existing outputs');check('existing-output-bytes-unchanged',fingerprint(existing)==existing_hash and not (out/'must-not-exist.json').exists())
    report={'pass':all(r['pass'] for r in records),'cases':records,'scope':'Generated original rigs only: saved/reopened moving-parent and transformed/uniform-scale preservation, wrist attachment, dependent COPY_ROTATION, no-op, sign equivalence, validation and refusal paths. No user character, clearance, naturalness, rendering or cross-character production acceptance.'};(out/'verification.json').write_text(json.dumps(report,indent=2,allow_nan=False),'utf-8');print('ELBOW_POLE_VERIFIED',len(records),flush=True)
if __name__=='__main__':main()
