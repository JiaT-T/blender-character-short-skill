import copy,unittest
from acting_clip_plan import compile_plan,values

def fixture():
    return {'schema':1,'frames':[1,120],'fps':24,'channels':{'hand':{'width':1,'base':[0],'range':[0,1]},'body':{'width':3,'base':[0,0,0],'range':[-30,30]}},'clips':{'tap':{'tracks':{'hand':[[0,[0]],[.5,[1]],[1,[0]]]}},'lean':{'tracks':{'body':[[0,[0,0,0]],[.5,[5,0,0]],[1,[0,0,0]]]}}},'instances':[{'id':'first','clip':'tap','start':10,'end':30},{'id':'repeat','clip':'tap','start':50,'end':90,'amplitude':.5},{'id':'body','clip':'lean','start':12,'end':40}]}

class ActingClips(unittest.TestCase):
    def test_retime_repeat_scale_and_independent_tracks(self):
        p=compile_plan(fixture());self.assertEqual(values(p,20)['hand'],[1]);self.assertEqual(values(p,70)['hand'],[.5]);self.assertEqual(values(p,45)['hand'],[0]);self.assertGreater(values(p,20)['body'][0],0);self.assertEqual(values(p,120)['body'],[0,0,0])
    def test_hold_nonzero_end_until_next_clip(self):
        d=fixture();d['instances']=d['instances'][:1];d['clips']['tap']['tracks']['hand'][-1][1]=[.7];p=compile_plan(d);self.assertEqual(values(p,120)['hand'],[.7])
    def test_no_mutation_and_continuity(self):
        d=fixture();before=copy.deepcopy(d);p=compile_plan(d);values(p,19.5);self.assertEqual(before,d)
        for f in [10,20,30,50,70,90]:self.assertLess(abs(values(p,f-1e-5)['hand'][0]-values(p,f+1e-5)['hand'][0]),1e-5)
    def test_reject_overlap_or_entry_jump(self):
        d=fixture();d['instances'][1]['start']=20
        with self.assertRaises(ValueError):compile_plan(d)
        d=fixture();d['clips']['tap']['tracks']['hand'][-1][1]=[.5]
        with self.assertRaises(ValueError):compile_plan(d)
    def test_reject_nonfinite_bad_shapes_or_limits(self):
        changes=[lambda d:d['channels']['hand'].update(base=[float('nan')]),lambda d:d['clips']['tap']['tracks']['hand'][1].__setitem__(0,0),lambda d:d['instances'][0].update(amplitude=2),lambda d:d.update(frames=[1,1000000]),lambda d:d['channels']['body'].update(base=[0])]
        for change in changes:
            d=fixture();change(d)
            with self.assertRaises(ValueError):compile_plan(d)
    def test_shared_boundaries_and_outside_refusal(self):
        d=fixture();d['instances'][1].update(start=30,end=60);p=compile_plan(d);self.assertEqual(values(p,30)['hand'],[0])
        with self.assertRaises(ValueError):values(p,0)

if __name__=='__main__':unittest.main()
