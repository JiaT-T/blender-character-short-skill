"""Asset-free regressions for source-knot coverage and bounded verification."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
import sys
import unittest
from unittest.mock import patch
import numpy as np
from curve_smoothing import arc_length
from curve_native_metrics import native_length_witness
from curve_verification import verification_times
import verify_smoothed_curve as verify


class Vec(list):
    @property
    def x(self):return self[0]
    @property
    def y(self):return self[1]


class Channel:
    def __init__(self,i,axis,times,values):
        self.data_path=f'splines[0].points[{i}].co';self.array_index=axis
        self.mute=False;self.modifiers=[];self.sampled_points=[];self.extrapolation='CONSTANT'
        self.keyframe_points=[NS(co=Vec([t,v]),handle_left=Vec([t,v]),handle_right=Vec([t,v]),
            interpolation='LINEAR',handle_left_type='VECTOR',handle_right_type='VECTOR') for t,v in zip(times,values)]
    def evaluate(self,t):
        return float(np.interp(t,[k.co.x for k in self.keyframe_points],[k.co.y for k in self.keyframe_points]))


def cord(candidate):
    channels=[]
    for i in range(4):
        for axis in range(3):
            if not candidate and i==1 and axis==1:
                times,values=[0,.05,.1,.15,1],[0,0,.02,0,0]
            else:times,values=[0,1],[i/3 if axis==0 else 0]*2
            channels.append(Channel(i,axis,times,values))
    action=NS(fcurves=channels,library=None,users=1,use_fake_user=False)
    spline=NS(type='NURBS' if candidate else 'POLY',points=[NS(co=[i/3,0,0,1.]) for i in range(4)],
              order_u=4,use_endpoint_u=True,use_cyclic_u=False,use_bezier_u=False)
    return NS(type='CURVE',parent=None,constraints=[],modifiers=[],rigid_body=None,library=None,
              matrix_world=np.eye(4),animation_data=None,
              data=NS(users=1,library=None,shape_keys=None,dimensions='3D',splines=[spline],
                      animation_data=NS(action=action,drivers=[],nla_tracks=[])))


class ProbePoints(list):
    def add(self,n):self.extend(NS(co=[0.,0.,0.,1.]) for _ in range(n))


class ProbeSpline:
    def __init__(self):self.points=ProbePoints([NS(co=[0.,0.,0.,1.])])
    def calc_length(self,resolution):return arc_length([p.co[:3] for p in self.points],32)


class Curves:
    def new(self,*_args):return NS(splines=NS(new=lambda _kind:ProbeSpline()))
    def remove(self,_probe):pass


class CurveVerificationTests(unittest.TestCase):
    def test_real_verifier_rejects_peak_omitted_from_candidate_knots(self):
        with TemporaryDirectory() as directory:
            root=Path(directory);source=root/'original.blend';candidate=root/'candidate.blend'
            plan=root/'plan.json';report=root/'report.json'
            source.write_bytes(b'original');candidate.write_bytes(b'candidate')
            plan.write_text(json.dumps(dict(schema=1,object='Cord',frames=[0,1],sample_times=[0,1],
                target_length=1.,max_displacement=.01,length_tolerance=1e-6,maximum_key_step=1.)),encoding='utf-8')
            context=NS(scene=NS(objects={}))
            def opened(filepath,**_kwargs):context.scene.objects={'Cord':cord(Path(filepath)==candidate)}
            bpy=NS(app=NS(background=True),context=context,data=NS(curves=Curves()),ops=NS(wm=NS(open_mainfile=opened)))
            with patch.dict(sys.modules,{'bpy':bpy}):
                with self.assertRaisesRegex(ValueError,'verification failed'):
                    verify.run(NS(source=source,candidate=candidate,plan=plan,report=report,
                                  source_sha256=verify.sha(source),candidate_sha256=verify.sha(candidate)))
            result=json.loads(report.read_text('utf-8'))
            self.assertFalse(result['passed']);self.assertFalse(result['checks']['displacement'])
            self.assertEqual(result['original_knots'],5)
            self.assertAlmostEqual(result['maximum_control_shift'],.02)

    def test_same_verification_budget_is_available_before_writing(self):
        with self.assertRaisesRegex(ValueError,'before mutation'):
            verification_times([0,2000],range(2001),[0,2000],128)
        times=verification_times([0,.1,1],[0,1],[0,1],4)
        self.assertIn(.1,times)
        self.assertLess(len(times)*4,1000000)

    def test_native_witness_requires_two_independently_matching_resolutions(self):
        points=np.column_stack((np.linspace(0,1,4),np.zeros((4,2))))
        probe=ProbeSpline();probe.points.add(3)
        probe.calc_length=lambda resolution:{24:1.+1e-8,28:1.-1e-8,32:1.+5e-6,36:1.+6e-6,40:1.+7e-6}[resolution]
        result=native_length_witness(probe,points,1.,1e-6)
        self.assertEqual(set(result['selected_resolutions']),{24,28})
        probe.calc_length=lambda resolution:1. if resolution==24 else 1.+2e-6
        with self.assertRaisesRegex(ValueError,'agreement failed'):
            native_length_witness(probe,points,1.,1e-6)


if __name__=='__main__':unittest.main()
