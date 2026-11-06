import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from action_sequence_plan import validate,timeline

def fixture():
    clips=[]
    for name,frames in [('a',[11,30]),('b',[41,70])]:
        clips.append({'scene':name+'.blend','sha256':'a'*64,'frames':frames,
                      'source':'Owned synthetic source','credit':'Owned fixture',
                      'license':'CC0','modifications':'Fixture only','restrictions':'No external assets'})
    return {'schema':1,'fps':30,'transition_frames':6,'clips':clips}

class SequenceTests(unittest.TestCase):
    def test_complete_source_timeline_bounds(self):
        rows=timeline(fixture());self.assertEqual(len(rows),44)
        self.assertEqual(rows[0],{'frame':1,'a':11,'b':None,'weight':0.})
        self.assertEqual(rows[-1],{'frame':44,'a':None,'b':70,'weight':1.})
    def test_overlap_endpoints_and_cadence(self):
        rows=timeline(fixture());blend=[r for r in rows if r['a'] is not None and r['b'] is not None]
        self.assertEqual([(blend[0]['a'],blend[0]['b']),(blend[-1]['a'],blend[-1]['b'])],[(25,41),(30,46)])
        self.assertEqual((blend[0]['weight'],blend[-1]['weight']),(0.,1.))
        self.assertTrue(all(a['weight']<b['weight'] for a,b in zip(blend,blend[1:])))
    def test_no_source_frame_is_repeated_outside_overlap(self):
        rows=timeline(fixture());a=[r['a'] for r in rows if r['a'] is not None];b=[r['b'] for r in rows if r['b'] is not None]
        self.assertEqual(a,list(range(11,31)));self.assertEqual(b,list(range(41,71)))
    def test_boolean_overlap_refused(self):
        p=fixture();p['transition_frames']=True
        with self.assertRaises(ValueError):validate(p)
    def test_oversized_overlap_refused(self):
        p=fixture();p['transition_frames']=11
        with self.assertRaises(ValueError):validate(p)
    def test_missing_source_terms_refused(self):
        p=fixture();del p['clips'][0]['restrictions']
        with self.assertRaises(ValueError):validate(p)
    def test_unknown_plan_field_refused(self):
        p=fixture();p['guess_root_alignment']=True
        with self.assertRaises(ValueError):validate(p)
    def test_nonlocal_source_refused(self):
        p=fixture();p['clips'][0]['scene']='//host/share/a.blend'
        with self.assertRaises(ValueError):validate(p)
    def test_invalid_hash_refused(self):
        p=fixture();p['clips'][0]['sha256']='unknown'
        with self.assertRaises(ValueError):validate(p)

if __name__=='__main__':unittest.main()
