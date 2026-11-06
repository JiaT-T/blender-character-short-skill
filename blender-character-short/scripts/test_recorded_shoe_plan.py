import copy,json,tempfile,unittest
from pathlib import Path
from recorded_shoe_plan import validate,load

def example():
    legs={s:[s+'_'+n for n in ['thigh','knee','ankle','toe']] for s in ['left','right']}
    return {'schema':1,'blend_sha256':'0'*64,'root_bone':'pelvis','height':1.8,'ground':0.,'frames':[1,2],'fps':30,'legs':legs,'feet':{s:{'deform_root':s+'_shoe'} for s in legs},'weight_threshold':.35,
            'existing_IK':[{'side':s,'bone':legs[s][1 if count==2 else 2],'constraint':'IK','target_bone':s+('_goal' if count==2 else '_toe_goal'),'chain_count':count} for s in legs for count in [2,1]],
            'ankle_pitch_bias_degrees':{'left':0.,'right':10.},'desired_initial_toe_direction_pitch_degrees':{},'maximum_ankle_pitch_bias_degrees':30.,'ankle_pitch_axis_local':[1,0,0],'stride_scale':1.,'maximum_root_lowering_H':.06,'reach_fraction':.999,'reach_margin_H':.001,
            'maximum_height_error_H':.001,'maximum_horizontal_error_H':.001,'maximum_segment_length_error_H':.0001,'iterations_per_frame':12,
            'rows':[{'frame':f,'source_frame':100+f,'feet':{s:{'source_heel_y_m':-.001,'source_toe_tip_y_m':0.,'unclamped_source_proxy_y_m':-.001,'target_lowest_sole_z_m':0.} for s in legs}} for f in [1,2]]}

class ShoePlan(unittest.TestCase):
    def test_explicit_two_foot_original_ik_example(self):self.assertEqual(validate(example())['frames'],[1,2])
    def test_nonfinite_geometry_targets_fail(self):
        for value in [float('nan'),float('inf'),float('-inf')]:
            cfg=example();cfg['rows'][0]['feet']['left']['target_lowest_sole_z_m']=value
            with self.subTest(value=value),self.assertRaises(ValueError):validate(cfg)
    def test_no_silent_budget_or_tolerance_increase(self):
        for key,value in [('iterations_per_frame',13),('maximum_root_lowering_H',.061),('maximum_height_error_H',.002),('maximum_ankle_pitch_bias_degrees',31),('stride_scale',1.1),('height',True)]:
            cfg=example();cfg[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):validate(cfg)
    def test_original_ik_mapping_cannot_duplicate_or_change_chain(self):
        cfg=example();cfg['existing_IK'][1]=copy.deepcopy(cfg['existing_IK'][0])
        with self.assertRaises(ValueError):validate(cfg)
        cfg=example();cfg['existing_IK'][0]['chain_count']=3
        with self.assertRaises(ValueError):validate(cfg)
    def test_pitch_needs_reviewed_direction_or_bounded_explicit_bias(self):
        cfg=example();cfg['ankle_pitch_bias_degrees']['right']=None
        with self.assertRaises(ValueError):validate(cfg)
        cfg['desired_initial_toe_direction_pitch_degrees']['right']=70;validate(cfg)
        cfg['ankle_pitch_bias_degrees']['right']=31
        with self.assertRaises(ValueError):validate(cfg)
    def test_missing_or_misordered_integer_samples_fail(self):
        cfg=example();cfg['rows'].pop()
        with self.assertRaises(ValueError):validate(cfg)
        cfg=example();cfg['rows'].reverse()
        with self.assertRaises(ValueError):validate(cfg)
    def test_unexpected_fields_and_nonunit_axis_fail(self):
        cfg=example();cfg['invented_contact_success']=True
        with self.assertRaises(ValueError):validate(cfg)
        cfg=example();cfg['ankle_pitch_axis_local']=[2,0,0]
        with self.assertRaises(ValueError):validate(cfg)
    def test_duplicate_json_and_nonfinite_constant_fail(self):
        workspace=Path.cwd().resolve()
        with tempfile.TemporaryDirectory(dir=workspace) as directory:
            root=Path(directory).resolve();self.assertTrue(root.is_relative_to(workspace));path=root/'plan.json'
            path.write_text('{"schema":1,"schema":1}','utf-8')
            with self.assertRaises(ValueError):load(path)
            path.write_text('{"schema":NaN}','utf-8')
            with self.assertRaises(ValueError):load(path)
    def test_valid_saved_plan_and_file_size_bound(self):
        workspace=Path.cwd().resolve()
        with tempfile.TemporaryDirectory(dir=workspace) as directory:
            root=Path(directory).resolve();self.assertTrue(root.is_relative_to(workspace));path=root/'plan.json';path.write_text(json.dumps(example()),'utf-8');self.assertEqual(load(path)['fps'],30)
            path.write_text(' '*(1024*1024+1),'utf-8')
            with self.assertRaises(ValueError):load(path)

if __name__=='__main__':unittest.main()
