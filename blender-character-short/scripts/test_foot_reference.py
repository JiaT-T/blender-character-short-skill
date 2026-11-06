import copy,unittest
import numpy as np
from body_motion_plan import validate_plan
from foot_reference import validate,heading_alignment
from test_recorded_body_plan import fixture

def references(source):
    row={'source_frame':1,'ankle_rotation':np.eye(3).tolist(),'toe_rotation':np.eye(3).tolist(),'forward':[1,0,0]}
    return {'source_glb_sha256':source,'review_sha256':'b'*64,'feet':{'left':copy.deepcopy(row),'right':copy.deepcopy(row)}}

class FootReferences(unittest.TestCase):
    def test_default_plan_preserved(self):
        cfg=fixture();original=copy.deepcopy(cfg);self.assertEqual(validate_plan(cfg),original)
    def test_bound_reference_integrates_with_body_plan(self):
        cfg=fixture();cfg['foot_orientation_references']=references(cfg['source']['sha256']['source_glb']);self.assertEqual(validate_plan(cfg),cfg)
    def test_other_source_clip_refused(self):
        with self.assertRaises(ValueError):validate(references('a'*64),'c'*64,np.eye(3))
    def test_reflection_and_nonfinite_refused(self):
        for matrix in [np.diag([1,-1,1]).tolist(),[[float('nan'),0,0],[0,1,0],[0,0,1]]]:
            cfg=references('a'*64);cfg['feet']['right']['ankle_rotation']=matrix
            with self.assertRaises(ValueError):validate(cfg,'a'*64,np.eye(3))
    def test_vertical_or_incomplete_reference_refused(self):
        cfg=references('a'*64);cfg['feet']['right']['forward']=[0,0,1]
        with self.assertRaises(ValueError):validate(cfg,'a'*64,np.eye(3))
        cfg=references('a'*64);del cfg['feet']['right']
        with self.assertRaises(ValueError):validate(cfg,'a'*64,np.eye(3))
    def test_horizontal_heading_preserves_level(self):
        r=heading_alignment([0,-1,0],np.eye(3),[1,0,0]);np.testing.assert_allclose(r@[1,0,0],[0,-1,0],atol=1e-12);np.testing.assert_allclose(r@[0,0,1],[0,0,1],atol=1e-12);self.assertAlmostEqual(np.linalg.det(r),1)

if __name__=='__main__':unittest.main()
