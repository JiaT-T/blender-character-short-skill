import copy,json,math,sys,unittest
from pathlib import Path
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parent))
from hand_control_plan import profile,motion,value_at

def source_profile():return {'schema':1,'id':'synthetic','hands':{'left':'wrist'},'joints':[{'id':'index','bone':'joint','side':'left','digit':'index','max_total_degrees':60,'axes':[{'id':'flex','axis_local':[1,0,0],'limit_degrees':60}]}]}
def source_motion():return {'schema':1,'frames':[1,60],'fps':24,'channels':[{'joint':'index','axis':'flex','keys':[[1,0],[20,1],[40,1],[60,0]]}]}

class HandPlan(unittest.TestCase):
    def test_mapping_and_curve_are_external_without_mutation(self):
        p=source_profile();m=source_motion();before=copy.deepcopy((p,m));parsed=profile(p);plan=motion(m,parsed);self.assertEqual((p,m),before);self.assertEqual(plan['frames'],[1,60]);self.assertEqual(parsed['joints'][0]['bone'],'joint')
    def test_smooth_curve_is_bounded_monotonic_and_holds(self):
        keys=source_motion()['channels'][0]['keys'];values=[value_at(keys,1+i*.1) for i in range(191)];self.assertTrue(all(0<=x<=1 for x in values));self.assertTrue(all(a<=b+1e-12 for a,b in zip(values,values[1:])));self.assertEqual(value_at(keys,30),1);self.assertEqual(value_at(keys,60),0);self.assertLess(value_at(keys,1.001),1e-10);self.assertLess(1-value_at(keys,19.999),1e-10)
    def test_two_axes_remain_ordered(self):
        p=source_profile();p['joints'][0]['axes'].append({'id':'spread','axis_local':[0,0,1],'limit_degrees':10});self.assertEqual([a['id'] for a in profile(p)['joints'][0]['axes']],['flex','spread'])
    def test_profile_rejects_nonfinite_bool_and_bad_norm(self):
        for field,value in [('limit_degrees',float('nan')),('limit_degrees',True),('limit_degrees',91),('axis_local',[2,0,0]),('axis_local',[1,float('inf'),0])]:
            with self.subTest(field=field,value=value):
                p=source_profile();p['joints'][0]['axes'][0][field]=value
                with self.assertRaises(ValueError):profile(p)
    def test_profile_rejects_duplicate_bones_and_axes(self):
        p=source_profile();other=copy.deepcopy(p['joints'][0]);other['id']='other';p['joints'].append(other)
        with self.assertRaises(ValueError):profile(p)
        p=source_profile();p['joints'][0]['axes']*=2
        with self.assertRaises(ValueError):profile(p)
    def test_profile_rejects_bad_schema_binding_and_reserved_region(self):
        for mutate in [lambda p:p.update(schema=True),lambda p:p.update(binding_sha256='not-a-hash'),lambda p:p['joints'][0].update(digit='palm')]:
            p=source_profile();mutate(p)
            with self.assertRaises(ValueError):profile(p)
    def test_motion_rejects_stale_channels_and_work_growth(self):
        for mutate in [lambda m:m['channels'][0].update(joint='missing'),lambda m:m.update(frames=[1,241]),lambda m:m.update(fps=True),lambda m:m.update(schema=True),lambda m:m['channels'].append(copy.deepcopy(m['channels'][0]))]:
            m=source_motion();mutate(m)
            with self.assertRaises(ValueError):motion(m,profile(source_profile()))
    def test_motion_rejects_gaps_duplicates_and_nonfinite(self):
        for keys in [[[2,0],[60,0]],[[1,0],[20,1],[20,0],[60,0]],[[1,0],[60,float('nan')]],[[1,0],[60,1.1]],[[1.,0],[60,0]]]:
            m=source_motion();m['channels'][0]['keys']=keys
            with self.assertRaises(ValueError):motion(m,profile(source_profile()))

if __name__=='__main__':unittest.main(verbosity=2)
