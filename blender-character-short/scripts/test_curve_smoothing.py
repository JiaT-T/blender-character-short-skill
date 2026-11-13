"""Asset-free tests for geometric bounds and independent arc approximation."""
import unittest
from types import SimpleNamespace as NS
import numpy as np
from curve_smoothing import arc_length, evaluate, fit_bow, prepare_samples
from smooth_curve import inspect, validate_plan


def poly_cord(distance, length=.12):
    t=np.linspace(0,1,13);base=np.column_stack((np.zeros(13),np.zeros(13),distance*t))
    bow=np.column_stack((np.sin(np.pi*t),np.zeros(13),np.zeros(13)))
    low,high=0.,length
    for _ in range(48):
        mid=(low+high)/2
        if np.linalg.norm(np.diff(base+mid*bow,axis=0),axis=1).sum()<length:low=mid
        else:high=mid
    return base+(low+high)/2*bow


class CurveSmoothingTests(unittest.TestCase):
    def test_curve_integral_agrees_with_dense_independent_chords(self):
        source=poly_cord(.085)
        dense=evaluate(source,np.linspace(0,1,20001))
        chord_sum=np.linalg.norm(np.diff(dense,axis=0),axis=1).sum()
        self.assertLess(abs(chord_sum-arc_length(source,32)),2e-9)
        np.testing.assert_array_equal(dense[[0,-1]],source[[0,-1]])

    def test_fit_preserves_endpoints_and_chord_projection(self):
        source=poly_cord(.085)
        fitted,report=fit_bow(source,.12,.0005)
        np.testing.assert_array_equal(fitted[[0,-1]],source[[0,-1]])
        np.testing.assert_allclose(fitted[:,2],source[:,2],atol=1e-15,rtol=0)
        self.assertLess(abs(arc_length(fitted,32)-.12),1e-9)
        self.assertLess(report['maximum_point_shift'],.0005)

    def test_nearly_straight_fit_uses_actual_displacement(self):
        t=np.linspace(0,1,13)
        source=np.column_stack((.0001*np.sin(np.pi*t),np.zeros(13),.119999*t))
        fitted,report=fit_bow(source,.12,.0005,tolerance=1e-8)
        self.assertGreater(report['scale'],1.05)
        self.assertLess(report['maximum_point_shift'],.0005)
        self.assertLess(abs(arc_length(fitted,32)-.12),1e-9)

    def test_unreachable_or_budget_exhausted_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'unreachable'):
            fit_bow(poly_cord(.1),.09,.0005)
        with self.assertRaisesRegex(ValueError,'budget'):
            fit_bow(poly_cord(.1),.12,1e-8)
        with self.assertRaisesRegex(ValueError,'no bow'):
            fit_bow(np.column_stack((np.zeros(13),np.zeros(13),np.linspace(0,.1,13))),.12,.0005)

    def test_translation_rotation_do_not_change_fit(self):
        source=poly_cord(.085)
        q=np.array([[0,-1,0],[0,0,1],[-1,0,0.]])
        fitted,_=fit_bow(source,.12,.0005)
        shifted,_=fit_bow(source@q.T+[4.,-3.,2.],.12,.0005)
        np.testing.assert_allclose(shifted,fitted@q.T+[4.,-3.,2.],atol=2e-12,rtol=0)

    def test_adaptive_fit_resolves_coarse_time_interpolation(self):
        def sample(t):return poly_cord(.11-.025*np.sin(np.pi*t))
        proposal=prepare_samples(sample,[0,1],target_length=.12,max_displacement=.0005,
                                 refinement_passes=8,max_samples=2000)
        self.assertGreater(proposal['summary']['refinement_rounds'],0)
        self.assertLessEqual(proposal['summary']['maximum_interval_length_error'],7.5e-7)
        self.assertLessEqual(proposal['summary']['maximum_interval_point_shift'],.0005+1e-12)
        with self.assertRaisesRegex(ValueError,'budget'):
            prepare_samples(sample,[0,1],target_length=.12,max_displacement=.0005,refinement_passes=0)

    def test_nonfinite_and_nonmonotone_inputs_rejected(self):
        for target in (float('nan'),float('inf'),0,-1):
            with self.assertRaises(ValueError):fit_bow(poly_cord(.1),target,.0005)
        source=poly_cord(.1);source[5,2]=-.1
        with self.assertRaisesRegex(ValueError,'progress'):fit_bow(source,.12,.0005)

    def test_plan_requires_explicit_finite_bounded_values(self):
        plan=dict(schema=1,object='Cord',frames=[1,24],sample_times=[1,12.5,24],
                  target_length=.12,max_displacement=.0005,length_tolerance=1e-6,maximum_key_step=.25)
        self.assertEqual(validate_plan(plan),plan)
        for key,value in [('sample_times',[0,24]),('maximum_key_step',.000001),('target_length',float('inf'))]:
            bad=dict(plan);bad[key]=value
            with self.assertRaises(ValueError):validate_plan(bad)
        bad=dict(plan);bad['extra']=1
        with self.assertRaises(ValueError):validate_plan(bad)

    def test_unit_weight_coordinate_animation_is_preserved_input(self):
        channels=[]
        for point in range(4):
            for axis in range(4):
                value=1. if axis==3 else 0.
                channels.append(NS(data_path=f'splines[0].points[{point}].co',array_index=axis,
                    mute=False,modifiers=[],sampled_points=[],extrapolation='CONSTANT',
                    keyframe_points=[NS(co=NS(x=1.,y=value),interpolation='LINEAR'),
                                     NS(co=NS(x=24.,y=value),interpolation='LINEAR')]))
        action=NS(fcurves=channels,library=None,users=1,use_fake_user=False)
        data=NS(users=1,library=None,shape_keys=None,dimensions='3D',
                animation_data=NS(action=action,drivers=[],nla_tracks=[]),
                splines=[NS(type='POLY',points=[NS(co=[0,0,float(i),1]) for i in range(4)],use_cyclic_u=False)])
        cord=NS(type='CURVE',parent=None,constraints=[],modifiers=[],rigid_body=None,
                data=data,library=None,matrix_world=np.eye(4),animation_data=None)
        _,accepted,_=inspect(cord)
        self.assertEqual(len(accepted),16)
        channels[3].keyframe_points[-1].co.y=.99
        with self.assertRaisesRegex(ValueError,'weights'):inspect(cord)


if __name__=='__main__':unittest.main()
