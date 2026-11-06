import copy,math,unittest
from recorded_stance_plan import validate,weight

def fixture():
    return {'schema':1,'mode':'declared-stationary-transition','source_sha256':'a'*64,'frames':[1,180],'fps':30,'height':1.8,'reference_frame':60,'match_frames':[61,72],
            'limbs':{s:{'bones':[s+n for n in ['hip','knee','ankle']],'axis_local':[1,0,0],'bend_sign':-1} for s in ['left','right']},
            'align_ankle_orientation':True,'maximum_shift_H':.04,'maximum_ankle_orientation_degrees':5,'maximum_leg_rotation_degrees':20,'endpoint_tolerance_H':.00005}

class RecordedStance(unittest.TestCase):
    def test_valid_input_not_mutated(self):
        p=fixture();before=copy.deepcopy(p);self.assertEqual(validate(p),before);self.assertEqual(p,before)
    def test_weight_endpoints_no_pop_and_no_overshoot(self):
        values=[weight(f,[61,72]) for f in range(1,181)]
        self.assertTrue(all(0<=v<=1 for v in values));self.assertTrue(all(a<=b for a,b in zip(values,values[1:])));self.assertEqual(weight(61,[61,72]),0);self.assertEqual(weight(72,[61,72]),1)
        self.assertLess(weight(61.001,[61,72]),1e-10);self.assertLess(1-weight(71.999,[61,72]),1e-10)
    def test_work_and_out_of_range_reference_refused(self):
        for k,v in [('frames',[1,481]),('reference_frame',73),('match_frames',[61,120]),('match_frames',[60,60]),('fps',True)]:
            p=fixture();p[k]=v
            with self.subTest(key=k),self.assertRaises(ValueError):validate(p)
    def test_nonfinite_and_boolean_bounds_refused(self):
        for k in ['height','maximum_shift_H','maximum_ankle_orientation_degrees','maximum_leg_rotation_degrees','endpoint_tolerance_H']:
            for v in [True,float('nan'),float('inf')]:
                p=fixture();p[k]=v
                with self.subTest(key=k,value=v),self.assertRaises(ValueError):validate(p)
    def test_duplicate_bones_and_unreviewed_hinge_refused(self):
        for mutate in [lambda p:p['limbs']['right'].update(bones=p['limbs']['left']['bones']),lambda p:p['limbs']['left'].update(axis_local=[2,0,0]),lambda p:p['limbs']['left'].update(bend_sign=True)]:
            p=fixture();mutate(p)
            with self.assertRaises(ValueError):validate(p)
    def test_automatic_locomotion_or_unknown_fields_refused(self):
        for mutate in [lambda p:p.update(mode='locomotion'),lambda p:p.update(guess_foot_contacts=True)]:
            p=fixture();mutate(p)
            with self.assertRaises(ValueError):validate(p)

if __name__=='__main__':unittest.main()
