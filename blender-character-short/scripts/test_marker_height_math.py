import copy,unittest
from marker_height_math import derive
from recorded_shoe_plan import validate
from test_recorded_shoe_plan import example

def data():
    calibration={s:{'ankle_y_m':.12,'toe_joint_y_m':.04} for s in ['left','right']}
    samples=[{'frame':i,'source_frame':i+100,'feet':copy.deepcopy(calibration)} for i in [1,2]]
    return samples,calibration

class MarkerHeights(unittest.TestCase):
    def test_reference_offsets_cancel_actual_marker_height(self):
        s,c=data();rows,details=derive(s,c,2.,-.001,1.8);self.assertEqual(rows[0]['feet']['left']['target_lowest_sole_z_m'],-.001);self.assertFalse(details[0]['feet']['left']['negative_offset_clamped'])
    def test_both_raised_markers_retain_flight(self):
        s,c=data()
        for p in s[1]['feet'].values():
            for k in p:p[k]+=.1
        rows,_=derive(s,c,2.,0.,1.8);self.assertAlmostEqual(rows[1]['feet']['left']['target_lowest_sole_z_m'],.2)
    def test_low_marker_retains_geometric_roll_proxy(self):
        s,c=data();s[1]['feet']['left']['ankle_y_m']+=.1;rows,_=derive(s,c,1.,0.,1.8);self.assertEqual(rows[1]['feet']['left']['target_lowest_sole_z_m'],0.)
    def test_negative_clamp_is_explicit(self):
        s,c=data();s[1]['feet']['left']['toe_joint_y_m']-=.01;rows,d=derive(s,c,1.,0.,1.8);self.assertEqual(rows[1]['feet']['left']['target_lowest_sole_z_m'],0.);self.assertTrue(d[1]['feet']['left']['negative_offset_clamped'])
    def test_nonfinite_order_and_work_bound_refused(self):
        for kind in ['nan','order','work']:
            s,c=data()
            if kind=='nan':s[0]['feet']['left']['ankle_y_m']=float('nan')
            if kind=='order':s[1]['source_frame']=s[0]['source_frame']
            if kind=='work':s=s*121
            with self.subTest(kind=kind),self.assertRaises(ValueError):derive(s,c,1.,0.,1.8)
    def test_unbounded_marker_flight_refused(self):
        s,c=data()
        for p in s[1]['feet'].values():
            for k in p:p[k]+=10
        with self.assertRaises(ValueError):derive(s,c,1.,0.,1.8)

class TypedShoeGoals(unittest.TestCase):
    def plan(self):
        cfg=example();cfg['schema']=2;cfg['height_proxy']={'kind':'recorded-joint-offsets','derivation_report_sha256':'a'*64}
        for row in cfg['rows']:
            for side in row['feet']:row['feet'][side]={'target_lowest_sole_z_m':0.}
        return cfg
    def test_typed_goal_contract(self):self.assertEqual(validate(self.plan())['schema'],2)
    def test_missing_or_mislabelled_source_kind_refused(self):
        for kind in ['missing','invented']:
            cfg=self.plan()
            if kind=='missing':del cfg['height_proxy']
            else:cfg['height_proxy']['kind']='recorded-toe-tip-contact'
            with self.subTest(kind=kind),self.assertRaises(ValueError):validate(cfg)
    def test_legacy_payload_cannot_masquerade_as_typed_goals(self):
        cfg=self.plan();cfg['rows'][0]['feet']['left']['source_toe_tip_y_m']=0.
        with self.assertRaises(ValueError):validate(cfg)

if __name__=='__main__':unittest.main()
