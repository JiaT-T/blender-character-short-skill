"""Synthetic boundary tests; no model or motion-library assets are bundled."""
from pathlib import Path
import copy,hashlib,json,sys,tempfile,unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
from bvh_source_plan import load_plan,probe_bvh

BVH='''HIERARCHY
ROOT Pelvis
{
 OFFSET 0 0 0
 CHANNELS 6 Xposition Yposition Zposition Zrotation Xrotation Yrotation
 JOINT Spine
 {
  OFFSET 0 10 0
  CHANNELS 3 Zrotation Xrotation Yrotation
  End Site { OFFSET 0 10 0 }
 }
}
MOTION
Frames: 2
Frame Time: 0.0333333
0 100 0 0 0 0 0 0 0
1 100 0 0 0 0 0 0 0
'''

class SourcePlanTests(unittest.TestCase):
    def setUp(self):
        intended=Path.cwd().resolve()
        self.tmp=tempfile.TemporaryDirectory(prefix='bvh-fixture-',dir=intended)
        if not Path(self.tmp.name).resolve().is_relative_to(intended):raise RuntimeError('Fixture escaped intended workspace')
        self.addCleanup(self.tmp.cleanup)
        self.source=Path(self.tmp.name)/'owned.bvh';self.config=Path(self.tmp.name)/'plan.json'
        self.source.write_text(BVH,encoding='ascii')
        self.plan={'schema':1,'source_sha256':hashlib.sha256(self.source.read_bytes()).hexdigest(),
                   'frames':[1,2,1],'fps':30,'scale':.01,'axes':{'forward':'-Z','up':'Y'},
                   'reference':{'mode':'first-frame','pelvis':'Pelvis'},
                   'rights':{'source':'Synthetic test','credit':'Owned fixture','license':'CC0',
                             'modifications':'None','restrictions':'No external source data'}}
    def write(self):self.config.write_text(json.dumps(self.plan),encoding='utf-8')
    def load(self):self.write();return load_plan(self.config,self.source)
    def test_synthetic_valid_input(self):
        p=self.load();d=probe_bvh(self.source,p)
        self.assertEqual((d['bones'],d['channels'],d['raw_frames']),(2,9,2))
    def test_changed_source_refused(self):
        self.source.write_text(BVH+'\n')
        with self.assertRaisesRegex(ValueError,'changed'):self.load()
    def test_boolean_frames_refused(self):
        self.plan['frames'][0]=True
        with self.assertRaises(ValueError):self.load()
    def test_sample_budget_refused(self):
        self.plan['frames']=[1,241,1]
        with self.assertRaisesRegex(ValueError,'budget'):self.load()
    def test_unknown_reference_refused(self):
        self.plan['reference']['mode']='guess'
        with self.assertRaises(ValueError):self.load()
    def test_captured_calibration_outside_cut_preserves_explicit_frame(self):
        self.source.write_text(BVH.replace('Frames: 2','Frames: 3')+'2 100 0 0 0 0 0 0 0\n',encoding='ascii')
        self.plan['source_sha256']=hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.plan['frames']=[2,3,1];self.plan['reference']={'mode':'captured-horizontal','pelvis':'Pelvis','frame':1}
        parsed=self.load();self.assertEqual(parsed['reference']['frame'],1);self.assertEqual(probe_bvh(self.source,parsed)['raw_frames'],3)
    def test_captured_calibration_requires_reviewed_integer_frame(self):
        for frame in [True,0,20001,1.5]:
            self.plan['reference']={'mode':'captured-horizontal','pelvis':'Pelvis','frame':frame}
            with self.subTest(frame=frame),self.assertRaises(ValueError):self.load()
    def test_calibration_frame_outside_source_refused_before_import(self):
        self.plan['reference']={'mode':'captured-horizontal','pelvis':'Pelvis','frame':3}
        parsed=self.load()
        with self.assertRaisesRegex(ValueError,'calibration frame exceeds'):probe_bvh(self.source,parsed)
    def test_legacy_reference_rejects_ignored_calibration_fields(self):
        self.plan['reference']['frame']=1
        with self.assertRaises(ValueError):self.load()
    def test_missing_license_refused(self):
        del self.plan['rights']['license']
        with self.assertRaises(ValueError):self.load()
    def test_infinite_scale_refused(self):
        self.plan['scale']=float('inf')
        with self.assertRaises(ValueError):self.load()
    def test_boolean_scale_refused(self):
        self.plan['scale']=True
        with self.assertRaises(ValueError):self.load()
    def test_collinear_axes_refused(self):
        self.plan['axes']['forward']='-Y'
        with self.assertRaises(ValueError):self.load()
    def test_duplicate_plan_key_refused(self):
        self.write();text=self.config.read_text();self.config.write_text(text[:-1]+',"schema":1}')
        with self.assertRaisesRegex(ValueError,'Duplicate'):load_plan(self.config,self.source)
    def test_input_size_bounded_before_read(self):
        with self.source.open('r+b') as f:f.truncate(16*1024*1024+1)
        with self.assertRaisesRegex(ValueError,'16MB'):self.load()
    def test_frame_count_mismatch_refused(self):
        self.source.write_text(BVH.replace('Frames: 2','Frames: 3'))
        with self.assertRaisesRegex(ValueError,'count mismatch'):probe_bvh(self.source,self.plan)
    def test_nonfinite_channel_refused(self):
        self.source.write_text(BVH.replace('1 100 0','nan 100 0'))
        with self.assertRaisesRegex(ValueError,'channel'):probe_bvh(self.source,self.plan)
    def test_tempo_change_refused(self):
        self.plan['fps']=60
        with self.assertRaisesRegex(ValueError,'tempo'):probe_bvh(self.source,self.plan)
    def test_import_work_bounded(self):
        self.source.write_text(BVH.replace('Frames: 2','Frames: 20001'))
        with self.assertRaisesRegex(ValueError,'budget'):probe_bvh(self.source,self.plan)
    def test_multiple_roots_refused(self):
        self.source.write_text(BVH.replace('JOINT Spine','ROOT Spine'))
        with self.assertRaisesRegex(ValueError,'one BVH root'):probe_bvh(self.source,self.plan)

if __name__=='__main__':unittest.main()
