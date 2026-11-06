import copy,unittest
from body_motion_plan import validate_plan
from test_recorded_body_plan import fixture

class CapturedArms(unittest.TestCase):
    def test_existing_direction_route_remains_unchanged(self):
        cfg=fixture();before=copy.deepcopy(cfg);self.assertEqual(validate_plan(cfg),before)
        cfg['arm_rotation']='direction-fit';self.assertEqual(validate_plan(cfg)['arm_rotation'],'direction-fit')
    def test_captured_arms_need_captured_wrist_calibration(self):
        cfg=fixture();cfg['arm_rotation']='source-first-fitted'
        with self.assertRaises(ValueError):validate_plan(cfg)
        cfg['wrist_rotation']='source-first-fitted';self.assertEqual(validate_plan(cfg)['arm_rotation'],'source-first-fitted')
    def test_unknown_arm_route_is_rejected(self):
        for value in [True,None,{},'invented']:
            cfg=fixture();cfg['arm_rotation']=value
            with self.subTest(value=value),self.assertRaises(ValueError):validate_plan(cfg)

if __name__=='__main__':unittest.main()
