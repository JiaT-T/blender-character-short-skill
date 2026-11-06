"""Native-Blender tests of actual cord geometry math; no model or render needed."""
from pathlib import Path
import sys,unittest,json,copy
sys.dont_write_bytecode=True;sys.path.insert(0,str(Path(__file__).resolve().parent))
import numpy as np
from bake_sphere_grasp_scene import cord_points,validate_scene_plan
from fit_sphere_grasp import checked_center_grid

def source_plan():
    return {'schema':1,'frames':[1,48],'fps':24,'reference_frame':1,'side':'left','arm_bones':{'arm':'upper','elbow':'lower','wrist':'wrist'},'close_frames':[1,10],'held_frames':[10,30],'release_frames':[30,40],'approach_offset_hand_m':[0,0,-.02],'lift_world_m':[0,0,.02],'inspection_axis_world':[0,0,1],'inspection_degrees':3,'hand_frame_from_wrist':np.eye(4).tolist(),'cord_segments':12,'cord_length_m':.12,'cord_radius_m':.0004,'contact_gap_limit_m':.0012,'penetration_tolerance_m':.0002,'stability_tolerance_m':.0005,'cord_length_tolerance_m':.0005,'ball_base_colour':[.5,.5,.5,1],'ball_accent_colour':[.5,.3,.1,1],'prop_name':'sphere','cord_name':'cord','approach_keys':[[1,1],[10,0],[40,0],[48,1]],'lift_keys':[[1,0],[10,0],[20,1],[30,0],[48,0]]}

class CordGeometry(unittest.TestCase):
    def assert_length(self,points,length):
        self.assertTrue(np.isfinite(points).all());self.assertAlmostEqual(float(np.linalg.norm(np.diff(points,axis=0),axis=1).sum()),length,places=7)
    def test_taut_and_slack_preserve_endpoints(self):
        for distance in [.12,.085,.03]:
            top=[0,0,distance];bottom=[0,0,0];points=cord_points(top,bottom,.12,12,[1,0,0]);self.assert_length(points,.12);np.testing.assert_allclose(points[0],top,atol=1e-12);np.testing.assert_allclose(points[-1],bottom,atol=1e-12)
    def test_slack_uses_transverse_bow(self):
        points=cord_points([0,0,.085],[0,0,0],.12,12,[1,0,0]);self.assertGreater(float(points[:,0].max()),.02);self.assertLess(float(np.abs(points[:,1]).max()),1e-10)
    def test_rigid_world_transform_invariance(self):
        R=np.asarray([[0,0,1],[1,0,0],[0,1,0]],dtype=float);T=np.asarray([.5,-1,2]);a=np.asarray([.02,.01,.08]);b=np.zeros(3);side=np.asarray([1,0,0]);base=cord_points(a,b,.12,12,side);moved=cord_points(R@a+T,R@b+T,.12,12,R@side);np.testing.assert_allclose(moved,base@R.T+T,atol=1e-8);self.assert_length(moved,.12)
    def test_rejects_unreachable_and_coincident_ends(self):
        for top in [[0,0,.13],[0,0,0]]:
            with self.assertRaises(ValueError):cord_points(top,[0,0,0],.12,12,[1,0,0])
    def test_rejects_nonfinite_endpoints(self):
        for value in [float('nan'),float('inf'),-float('inf')]:
            with self.assertRaises(ValueError):cord_points([0,0,value],[0,0,0],.12,12,[1,0,0])
    def test_rejects_segment_work_outside_bound(self):
        for segments in [1,33]:
            with self.assertRaises(ValueError):cord_points([0,0,.085],[0,0,0],.12,segments,[1,0,0])
    def test_rejects_slack_without_perpendicular_bow(self):
        for side in [[0,0,0],[0,0,1]]:
            with self.assertRaises(ValueError):cord_points([0,0,.085],[0,0,0],.12,12,side)
    def test_keeps_caller_arrays_unchanged(self):
        top=np.asarray([.02,.01,.08]);bottom=np.zeros(3);side=np.asarray([1.,0,0]);before=[v.copy() for v in [top,bottom,side]];cord_points(top,bottom,.12,12,side)
        for a,b in zip([top,bottom,side],before):np.testing.assert_array_equal(a,b)
    def test_center_product_limit_precedes_allocation(self):
        bounds=np.asarray([[-1,1]]*3)
        with self.assertRaises(ValueError):checked_center_grid([[0]*16]*3,bounds)
        with self.assertRaises(ValueError):checked_center_grid([[0],[0],[float('nan')]],bounds)
    def test_center_grid_matches_bounded_coordinates(self):
        bounds=np.asarray([[-1,1]]*3);rows=checked_center_grid([[0,.5],[0],[0]],bounds);self.assertEqual(len(rows),2);np.testing.assert_array_equal(rows[1],[.5,0,0])
        with self.assertRaises(ValueError):checked_center_grid([[2],[0],[0]],bounds)
    def test_scene_preflight_rejects_allocations_and_nonfinite(self):
        validate_scene_plan(source_plan())
        for key,value in [('cord_segments',1000000),('approach_offset_hand_m',[0,0,float('nan')]),('inspection_axis_world',[0,0,0])]:
            d=source_plan();d[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):validate_scene_plan(d)
    def test_scene_preflight_rejects_bad_timing(self):
        for key,value in [('frames',[1,121]),('held_frames',[11,30]),('approach_keys',[[1,1],[1,0],[48,0]])]:
            d=source_plan();d[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):validate_scene_plan(d)

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(CordGeometry));print('GRASP_NATIVE_MATH_TESTS',json.dumps({'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors)}),flush=True)
    if not result.wasSuccessful():raise RuntimeError('Cord math regression failed')
