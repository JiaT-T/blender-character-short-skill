import copy
import math
import unittest
from existing_controller_plan import validate_plan, shortest_quaternion_angle_degrees as angle


class ExistingControllerPlanTests(unittest.TestCase):
    def setUp(self):
        self.plan = {'schema': 1, 'source_sha256': 'a' * 64,
                     'controller_object': 'ExistingRig', 'model_armature': 'OriginalModel',
                     'mesh_object': 'WeightedSkin', 'existing_controller_bones': 42,
                     'pairs': [{'model_bone': 'Arm', 'controller_bone': 'ORG-arm'}],
                     'maximum_baseline_skin_difference_m': 1e-5}

    def test_explicit_mapping_accepted(self):
        self.assertEqual(validate_plan(self.plan), self.plan)

    def test_rejects_unreviewed_or_unbounded_plan(self):
        variants = [{'schema': True}, {'source_sha256': 'not-a-digest'}, {'existing_controller_bones': True},
                    {'existing_controller_bones': 4096}, {'mesh_object': ''},
                    {'controller_object': 'OriginalModel'}, {'pairs': []},
                    {'maximum_baseline_skin_difference_m': float('nan')},
                    {'maximum_baseline_skin_difference_m': .01},
                    {'maximum_baseline_skin_difference_m': True}, {'unexpected': 'field'}]
        for changes in variants:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                validate_plan(dict(self.plan, **changes))

    def test_rejects_duplicate_mapping(self):
        for field in ('model_bone', 'controller_bone'):
            plan = copy.deepcopy(self.plan)
            row = {'model_bone': 'Other', 'controller_bone': 'ORG-other'}
            row[field] = plan['pairs'][0][field]
            plan['pairs'].append(row)
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_plan(plan)

    def test_rejects_names_that_blender_would_truncate(self):
        plan = copy.deepcopy(self.plan)
        plan['pairs'][0]['model_bone'] = '長' * 20
        with self.assertRaises(ValueError):
            validate_plan(plan)

    def test_antipodal_quaternion_is_same_orientation(self):
        self.assertAlmostEqual(angle((1, 0, 0, 0), (-1, 0, 0, 0)), 0)

    def test_wraparound_uses_shortest_orientation(self):
        half = math.radians(359.08 / 2)
        self.assertAlmostEqual(angle((1, 0, 0, 0), (math.cos(half), 0, math.sin(half), 0)), .92, places=9)

    def test_quaternion_scale_does_not_overflow(self):
        self.assertAlmostEqual(angle((1e308, 0, 0, 0), (0, 1e308, 0, 0)), 180)

    def test_invalid_quaternion_is_not_a_passing_measurement(self):
        for invalid in ((0, 0, 0, 0), (1, 0, 0), (1, math.inf, 0, 0), (True, 0, 0, 0)):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                angle(invalid, (1, 0, 0, 0))


if __name__ == '__main__':
    unittest.main()
