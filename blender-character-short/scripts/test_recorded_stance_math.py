import unittest,numpy as np
from recorded_stance_math import matched_knee

class CapturedPlane(unittest.TestCase):
    def test_preserves_segment_lengths_and_target(self):
        h=np.array([0.,0,1]);k=np.array([0,-.08,.6]);a=np.array([0,0,.15]);t=np.array([.05,0,.15]);r=matched_knee(h,k,a,t)
        self.assertAlmostEqual(np.linalg.norm(r-h),np.linalg.norm(k-h),places=10);self.assertAlmostEqual(np.linalg.norm(t-r),np.linalg.norm(a-k),places=10)
    def test_unchanged_target_retains_captured_knee(self):
        h=[0,0,1];k=[.02,-.1,.6];a=[0,0,.15];np.testing.assert_allclose(matched_knee(h,k,a,a),k,atol=1e-12)
    def test_rigid_world_transform_invariant(self):
        points=np.array([[0,0,1],[.02,-.1,.6],[0,0,.15],[.05,.02,.15]]);R=np.array([[0,0,1],[1,0,0],[0,1,0]]);T=np.array([1,2,-3]);r=matched_knee(*points);np.testing.assert_allclose(matched_knee(*(points@R.T+T)),R@r+T,atol=1e-12)
    def test_near_straight_side_shift_does_not_pin_old_knee(self):
        h=np.array([0,0,1.]);k=np.array([0,-.02,.6]);a=np.array([0,0,.15]);t=np.array([.04,0,.152]);r=matched_knee(h,k,a,t)
        oldnormal=np.cross(k-h,a-k);newnormal=np.cross(r-h,t-r);oldnormal/=np.linalg.norm(oldnormal);newnormal/=np.linalg.norm(newnormal)
        self.assertGreater(np.dot(oldnormal,newnormal),.998)
    def test_rejects_nonfinite_straight_unreachable_or_ambiguous(self):
        for points in [([0,0,1],[0,0,.5],[0,0,0],[.01,0,.02]),([0,0,1],[0,-.1,.5],[0,0,0],[0,0,-1]),([0,0,1],[0,-.1,.5],[0,0,0],[float('nan'),0,0]),([0,0,1],[0,-.1,.5],[0,0,0],[0,0,2])]:
            with self.assertRaises(ValueError):matched_knee(*points)

if __name__=='__main__':unittest.main()
