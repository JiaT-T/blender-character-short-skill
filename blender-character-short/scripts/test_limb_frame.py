import unittest,numpy as np
from limb_frame import hinge_alignment,bend_floor

class LimbFrame(unittest.TestCase):
    def test_nearly_straight_capture_noise_cannot_reverse_thigh_plane(self):
        previous=np.array([1.,0,0]);rotations=[]
        for noise in [.002,.001,-.0005,.0015,.002]:
            lower,added=bend_floor([0,0,-1],[0,noise,-1],5,previous)
            rotation,previous=hinge_alignment([0,0,-1],[1,0,0],[0,0,-1],lower,1,previous)
            self.assertGreater(added,4);self.assertGreater(lower[1],0);self.assertGreater(previous[0],.999)
            rotations.append(rotation)
        for a,b in zip(rotations,rotations[1:]):np.testing.assert_allclose(a,b,atol=1e-8)
    def test_clear_source_bend_is_not_reflected_by_previous_hint(self):
        original=np.array([0,-.4,-1]);observed,added=bend_floor([0,0,-1],original,5,[1,0,0])
        np.testing.assert_allclose(observed,original/np.linalg.norm(original));self.assertEqual(added,0)
    def test_underbent_parallel_hint_is_rejected(self):
        with self.assertRaises(ValueError):bend_floor([0,0,-1],[0,.001,-1],5,[0,0,-1])
    def test_bend_floor_changes_only_underbent_source_in_same_plane(self):
        l,change=bend_floor([0,0,-1],[0,.01,-1],5);self.assertGreater(change,4);self.assertAlmostEqual(np.linalg.norm(l),1);self.assertAlmostEqual(np.degrees(np.arccos(-l[2])),5);self.assertGreater(l[1],0)
        original=np.array([0,.4,-1]);same,delta=bend_floor([0,0,-1],original,5);np.testing.assert_allclose(same,original/np.linalg.norm(original));self.assertEqual(delta,0)
    def test_bend_floor_straight_requires_explicit_plane(self):
        with self.assertRaises(ValueError):bend_floor([0,0,-1],[0,0,-1],5)
        l,_=bend_floor([0,0,-1],[0,0,-1],5,[1,0,0]);self.assertGreater(l[1],0)
    def test_negative_hinge_bend_preserves_upper_and_plane(self):
        u=np.array([.2,.3,-1.]);u/=np.linalg.norm(u);l=np.array([.4,-.8,-.6]);l/=np.linalg.norm(l);r,axis=hinge_alignment([0,0,-1],[1,0,0],u,l,-1);np.testing.assert_allclose(r@np.array([0,0,-1]),u,atol=1e-8);np.testing.assert_allclose(r@np.array([1,0,0]),axis,atol=1e-8);self.assertAlmostEqual(np.linalg.det(r),1)
    def test_bend_sign_changes_roll_without_reversing_limb(self):
        a,x=hinge_alignment([0,0,-1],[1,0,0],[0,-1,-1],[0,-1,0],-1);b,y=hinge_alignment([0,0,-1],[1,0,0],[0,-1,-1],[0,-1,0],1);np.testing.assert_allclose(x,-y);np.testing.assert_allclose(a@np.array([0,0,-1]),b@np.array([0,0,-1]))
    def test_straight_joint_retains_previous_plane(self):
        r,a=hinge_alignment([0,0,-1],[1,0,0],[0,0,-1],[0,0,-1],-1,[1,0,0]);np.testing.assert_allclose(r,np.eye(3));np.testing.assert_allclose(a,[1,0,0])
    def test_invalid_or_degenerate_input_refused(self):
        for args in [([0,0,0],[1,0,0],[0,0,-1],[0,-1,0],-1),([0,0,-1],[0,0,1],[0,0,-1],[0,-1,0],-1),([0,0,-1],[1,0,0],[float('nan'),0,-1],[0,-1,0],-1),([0,0,-1],[1,0,0],[0,0,-1],[0,-1,0],0)]:
            with self.assertRaises(ValueError):hinge_alignment(*args)

if __name__=='__main__':unittest.main()
