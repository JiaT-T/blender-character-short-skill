from pathlib import Path
import copy,os,tempfile,unittest
from production_contract import sha,baseline_identity,require_baseline_binding,require_look_binding,declared_file,producer_identity,require_saved_producer

class ArtifactBindingTests(unittest.TestCase):
    def setUp(self):
        parent=Path(os.environ['BLENDER_TEST_OUTPUT']);parent.mkdir(parents=True,exist_ok=True)
        self.root=Path(tempfile.mkdtemp(prefix='binding-',dir=parent))
        self.source=self.row('source.blend','source');self.profile=self.row('profile.json','{}');self.mapping=self.row('mapping.json','{}')
        self.plan={'mode':'provided','source':self.source,'profile':self.profile,'output':'new.blend','fps':24}
        self.prior={'plan_identity':baseline_identity(self.plan,self.root)}
    def row(self,name,content):
        p=self.root/name;p.write_text(content,'utf-8');return {'path':name,'sha256':sha(p)}
    def test_matching_baseline(self):require_baseline_binding(self.plan,self.prior,self.root)
    def test_changed_source_with_updated_declared_hash_is_not_old_baseline(self):
        self.plan['source']=self.row('source.blend','different')
        with self.assertRaises(ValueError):require_baseline_binding(self.plan,self.prior,self.root)
    def test_changed_profile_with_updated_hash_is_not_old_baseline(self):
        self.plan['profile']=self.row('profile.json','{"new":1}')
        with self.assertRaises(ValueError):require_baseline_binding(self.plan,self.prior,self.root)
    def test_fps_change_is_not_old_baseline(self):
        self.plan['fps']=30
        with self.assertRaises(ValueError):require_baseline_binding(self.plan,self.prior,self.root)
    def test_output_change_is_not_old_baseline(self):
        self.plan['output']='other.blend'
        with self.assertRaises(ValueError):require_baseline_binding(self.plan,self.prior,self.root)
    def test_legacy_unbound_receipt_is_not_adopted(self):
        with self.assertRaises(ValueError):require_baseline_binding(self.plan,{},self.root)
    def test_generation_mapping_is_bound(self):
        self.plan.update(mode='generate',mapping=self.mapping,generation_guidance_acknowledged=True)
        prior={'plan_identity':baseline_identity(self.plan,self.root)};self.plan['mapping']=self.row('mapping.json','{"new":1}')
        with self.assertRaises(ValueError):require_baseline_binding(self.plan,prior,self.root)
    def test_look_inputs_all_bound(self):
        plan={'target':self.source,'donor':self.row('look.blend','look'),'profile':self.profile,'output':'looked.blend'}
        prior={r:declared_file(plan[k],self.root) for k,r in [('target','target_input'),('donor','look_donor'),('profile','profile')]};prior['output']=str((self.root/plan['output']).resolve())
        require_look_binding(plan,prior,self.root)
        for key in ['target','donor','profile']:
            changed=copy.deepcopy(plan);changed[key]=self.row('changed-'+key,'changed')
            with self.subTest(key=key),self.assertRaises(ValueError):require_look_binding(changed,prior,self.root)
    def test_encoder_rejects_added_producer(self):
        scripts=self.root/'scripts';scripts.mkdir();(scripts/'a.py').write_text('x=1');(self.root/'version.json').write_text('{}')
        signature={'producer':producer_identity(scripts),'version_sha256':sha(self.root/'version.json')};require_saved_producer(signature,scripts)
        (scripts/'b.py').write_text('x=2')
        with self.assertRaises(ValueError):require_saved_producer(signature,scripts)
    def test_encoder_rejects_version_change(self):
        scripts=self.root/'scripts';scripts.mkdir();(scripts/'a.py').write_text('x=1');(self.root/'version.json').write_text('{}')
        signature={'producer':producer_identity(scripts),'version_sha256':sha(self.root/'version.json')};(self.root/'version.json').write_text('{"new":1}')
        with self.assertRaises(ValueError):require_saved_producer(signature,scripts)

if __name__=='__main__':unittest.main()
