import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'blender-character-short/scripts'))
from short_project import physics
from mcp_jobs import sha

class PhysicsAdapter(unittest.TestCase):
    def fixture(self,root):
        (root/'source.blend').write_bytes(b'fixture')
        plan={'source_sha256':sha(root/'source.blend')}
        (root/'plan.json').write_text(json.dumps(plan))
        return {'physics':{'source':{'path':'source.blend','sha256':plan['source_sha256']},'plan':'plan.json','output':'new.blend','report':'bake.json','verify_report':'verify.json'}}

    def test_existing_cache_bake_then_fresh_verification(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td).resolve();project=self.fixture(root);stages=[]
            def native(project,base,script,args,stage):
                stages.append(stage);self.assertEqual(script,'cache_existing_physics.py')
                if stage=='physics-bake':
                    (root/'new.blend').write_bytes(b'baked-fixture')
                    (root/'bake.json').write_text(json.dumps({'cache_baked':True,'output_sha256':sha(root/'new.blend'),'source_sha256':sha(root/'source.blend')}))
                else:
                    self.assertEqual(json.loads((root/'verify-plan.json').read_text())['source_sha256'],sha(root/'new.blend'))
                    (root/'verify.json').write_text(json.dumps({'fresh_process_reopen_verified':True,'cache_baked':True,'source_sha256':sha(root/'new.blend')}))
            with patch('short_project.run_native',side_effect=native):result=physics(project,root)
            self.assertEqual(stages,['physics-bake','physics-fresh-verify']);self.assertEqual(result,root/'verify.json')
            self.assertEqual((root/'source.blend').read_bytes(),b'fixture')

    def test_existing_outputs_refused(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td).resolve();p=self.fixture(root);(root/'new.blend').write_bytes(b'existing')
            with patch('short_project.run_native') as native:
                with self.assertRaises(ValueError):physics(p,root)
                native.assert_not_called()

    def test_plan_source_mismatch_refused(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td).resolve();p=self.fixture(root);(root/'plan.json').write_text(json.dumps({'source_sha256':'0'*64}))
            with self.assertRaises(ValueError):physics(p,root)

if __name__=='__main__':unittest.main()
