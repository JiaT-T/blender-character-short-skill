import copy,unittest
from passive_ground_plan import validate

def example():return {'schema':1,'source_sha256':'a'*64,'instructions_review_sha256':'b'*64,'blender_version':[4,5,15],'center_xy':[0,0],'size_xy':[20,20],'top_z':-.0015,'thickness':.1}

class GroundPlan(unittest.TestCase):
    def test_explicit_documented_new_copy(self):self.assertEqual(validate(example()),example())
    def test_nonfinite_and_invalid_dimensions_refused(self):
        for key,value in [('top_z',float('nan')),('thickness',0),('size_xy',[-20,20]),('center_xy',[float('inf'),0])]:
            cfg=example();cfg[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):validate(cfg)
    def test_missing_instruction_review_and_extra_controls_refused(self):
        cfg=example();del cfg['instructions_review_sha256']
        with self.assertRaises(ValueError):validate(cfg)
        cfg=example();cfg['disable_collisions']=True
        with self.assertRaises(ValueError):validate(cfg)
    def test_exact_version_and_hashes_required(self):
        for key,value in [('blender_version',[True,5,15]),('source_sha256','not-a-hash'),('instructions_review_sha256','0'*63)]:
            cfg=example();cfg[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):validate(cfg)

if __name__=='__main__':unittest.main()
