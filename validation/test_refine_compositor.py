"""Host-side parameter tests; native topology and render checks are separate."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'blender-character-short' / 'scripts'))
from refine_compositor import normalized_config


class CompositorParameters(unittest.TestCase):
    def test_defaults(self):
        cfg = normalized_config()
        self.assertEqual(cfg['gain'], .025)
        self.assertTrue(cfg['coverage'])
        self.assertEqual((cfg['device'], cfg['precision']), ('GPU', 'FULL'))

    def test_restore_values(self):
        cfg = normalized_config(dict(coverage=False, gain=.035, device='CPU', precision='AUTO'))
        self.assertFalse(cfg['coverage'])
        self.assertEqual(cfg['gain'], .035)

    def test_unknown_option(self):
        with self.assertRaises(ValueError): normalized_config({'render': True})

    def test_nonfinite_or_out_of_range(self):
        for value in (float('nan'), float('inf'), -1, 1.1, True, '0.1'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalized_config({'gain': value})

    def test_coverage_is_boolean(self):
        with self.assertRaises(ValueError): normalized_config({'coverage': 1})

    def test_gain_selectors(self):
        for value in ([], ['a', 'b'], ['a', 'a', 'b'], ['a', 'b', {}], 'abc'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalized_config({'gain_nodes': value})

    def test_selector_overlap(self):
        with self.assertRaises(ValueError):
            normalized_config({'premultiply_node': 'same', 'glare_node': 'same'})

    def test_execution_settings(self):
        for cfg in ({'device': 'AUTO'}, {'precision': 'HALF'}):
            with self.subTest(cfg=cfg), self.assertRaises(ValueError): normalized_config(cfg)

    def test_prefix(self):
        for value in ('', ' ', 'x' * 41, None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalized_config({'prefix': value})


if __name__ == '__main__':
    unittest.main()
