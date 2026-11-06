"""Native-Blender regression tests for finite original-physics pose evidence.

No model, bake, installation, network, or scene mutation is needed.
Run with enabled MMD Tools for config tests; this module imports bpy.
"""
from pathlib import Path
import sys,unittest,numpy as np
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parent))
from mmd_physics import finite_matrix,pose_error

class PhysicsEvidence(unittest.TestCase):
    def test_finite_copy_survives_source_mutation(self):
        original=np.eye(4);saved=finite_matrix(original,'fixture');original[:]=0
        np.testing.assert_array_equal(saved,np.eye(4))
    def test_nonfinite_actual_or_expected_rejected_before_max(self):
        for value in [float('nan'),float('inf'),-float('inf')]:
            invalid=np.eye(4);invalid[0,3]=value
            for a,b in [(invalid,np.eye(4)),(np.eye(4),invalid)]:
                with self.subTest(value=value),self.assertRaises(ValueError):pose_error(a,b,'invalid fixture')
    def test_wrong_shape_rejected(self):
        for a in [np.eye(3),np.ones((4,4,1)),[1,2,3,4]]:
            with self.assertRaises(ValueError):finite_matrix(a,'shape fixture')
    def test_finite_difference_is_measured(self):
        a=np.eye(4);a[2,3]=.125
        self.assertEqual(pose_error(a,np.eye(4),'translated fixture'),.125)

if __name__=='__main__':unittest.main()
