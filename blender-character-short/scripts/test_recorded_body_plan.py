"""Native-Blender contract tests: unknown captured contacts never imply plants."""
import copy,unittest
from body_motion_plan import validate_plan,SOURCE_KEYS
from plant_body_motion import plant

def fixture():
    limbs={};node=1
    for side,count in [('left_leg',4),('right_leg',4),('left_arm',3),('right_arm',3)]:
        limbs[side]={'bones':[side+str(i) for i in range(count)],'source':list(range(node,node+count))};node+=count
    return {'schema':1,'source':{'files':{k:k+'.json' for k in SOURCE_KEYS},'sha256':{k:'a'*64 for k in SOURCE_KEYS}},'fps':30,'basis':[[1,0,0],[0,1,0],[0,0,1]],'body':[{'bone':'hip','source':0}],
            'limbs':limbs,'hips':'hip','scale_reference':{'bones':limbs['left_leg']['bones'][:3],'source':limbs['left_leg']['source'][:3]},'feet':{s:{'deform_root':s+'_leg2','contacts':[]} for s in ['left','right']},
            'travel':{'direction':[0,-1,0],'sole_height':0,'maximum_vertical_change_H':.03,'fit_threshold_H':.05,'speed_range_H_per_second':[.1,3],'grounding_mode':'lowest-sole'},
            'release_frames':6,'compose':{'gait_start':1,'minimum_stop_frames':2,'maximum_stop_frames':10,'reference_side':'left','landing_lift_H':0,'target_object':'owned'},'weight_threshold':.75,'root_motion':'recorded'}

class CapturedContacts(unittest.TestCase):
    def test_unknown_contacts_allowed_without_mutation_for_recorded_fit(self):
        p=fixture();before=copy.deepcopy(p);self.assertEqual(validate_plan(p),before);self.assertEqual(p,before)
    def test_legacy_route_still_requires_contacts(self):
        p=fixture();del p['root_motion']
        with self.assertRaises(ValueError):validate_plan(p)
    def test_unknown_contacts_cannot_be_called_planted(self):
        with self.assertRaisesRegex(ValueError,'requires explicit reviewed contact'):plant(None,None,fixture(),{})
    def test_malformed_or_overlapping_recorded_contacts_still_refused(self):
        for intervals in [[[True,2]],[[1,4],[5,8]],[[1,241]],None]:
            p=fixture();p['feet']['left']['contacts']=intervals
            with self.subTest(intervals=intervals),self.assertRaises(ValueError):validate_plan(p)

if __name__=='__main__':unittest.main()
