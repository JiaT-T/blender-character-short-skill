"""Decision and Blender-call boundary regressions; no render or hardware assumed."""
import sys
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch
import render_device_policy as policy


def adapter(name='Discrete board', integrated=False, hardware=True):
    return dict(name=name, hardware=hardware, integrated=integrated)


class Preferences:
    def __init__(self, backends):
        self.backends = backends
        self.devices = []
        self._backend = ''

    @property
    def compute_device_type(self):
        return self._backend

    @compute_device_type.setter
    def compute_device_type(self, value):
        if value not in self.backends:
            raise TypeError('unsupported backend')
        self._backend = value

    def refresh_devices(self):
        data = self.backends[self._backend]
        if isinstance(data, Exception):
            raise data
        self.devices = [NS(name=name, id=name+'-'+kind, type=kind, use=True) for name, kind in data]


class DevicePolicyTests(unittest.TestCase):
    def test_integrated_only_cpu(self):
        self.assertEqual(policy.hardware_mode([adapter('iGPU', True)]), 'CPU')

    def test_discrete_and_integrated_gpu(self):
        self.assertEqual(policy.hardware_mode([adapter(), adapter('iGPU', True)]), 'GPU')

    def test_software_does_not_prevent_integrated_only(self):
        self.assertEqual(policy.hardware_mode([adapter('software', False, False), adapter('iGPU', True)]), 'CPU')

    def test_empty_or_software_only_refused(self):
        for data in ([], [adapter('software', False, False)], None):
            with self.subTest(data=data), self.assertRaises(policy.DevicePolicyError):
                policy.hardware_mode(data)

    def test_unknown_classification_refused(self):
        for data in ([adapter(integrated=None)], [dict(name='unknown', hardware=None)], [dict(name='', hardware=True, integrated=True)]):
            with self.subTest(data=data), self.assertRaises(policy.DevicePolicyError):
                policy.hardware_mode(data)

    def test_unique_matching_required(self):
        with self.assertRaises(policy.DevicePolicyError):
            policy.matching_discrete('Discrete board', [adapter(), adapter()])

    def test_cycles_disables_cpu_and_other_boards(self):
        prefs = Preferences({'OPTIX': [('Discrete board', 'OPTIX'), ('Other board', 'OPTIX'), ('processor', 'CPU')]})
        scene = NS(cycles=NS(device='CPU'))
        result = policy.configure_cycles(scene, prefs, [adapter(), adapter('Other board')])
        self.assertEqual((scene.cycles.device, result['backend']), ('GPU', 'OPTIX'))
        self.assertEqual([d.name for d in prefs.devices if d.use], ['Discrete board'])

    def test_gpu_backend_retry_remains_gpu_only(self):
        prefs = Preferences({'OPTIX': RuntimeError('driver unavailable'), 'CUDA': [('Discrete board', 'CUDA'), ('processor', 'CPU')]})
        scene = NS(cycles=NS(device='GPU'))
        result = policy.configure_cycles(scene, prefs, [adapter()])
        self.assertEqual(result['backend'], 'CUDA')
        self.assertFalse(next(d for d in prefs.devices if d.type == 'CPU').use)

    def test_driver_failure_never_falls_back(self):
        scene = NS(cycles=NS(device='GPU'))
        with self.assertRaisesRegex(policy.DevicePolicyError, 'CPU fallback prohibited'):
            policy.configure_cycles(scene, Preferences({'OPTIX': RuntimeError('driver')}), [adapter()])
        self.assertEqual(scene.cycles.device, 'GPU')

    def test_integrated_cycles_device_cannot_substitute_for_discrete(self):
        with self.assertRaises(policy.DevicePolicyError):
            policy.configure_cycles(NS(cycles=NS(device='GPU')), Preferences({'ONEAPI': [('iGPU', 'ONEAPI')]}), [adapter(), adapter('iGPU', True)])

    def test_cpu_config_only_when_integrated_only(self):
        prefs = Preferences({})
        prefs.devices = [NS(name='iGPU', type='ONEAPI', use=True), NS(name='processor', type='CPU', use=False)]
        scene = NS(cycles=NS(device='GPU'))
        self.assertEqual(policy.configure_cycles(scene, prefs, [adapter('iGPU', True)])['mode'], 'CPU')
        self.assertEqual(scene.cycles.device, 'CPU')
        self.assertEqual([d.type for d in prefs.devices if d.use], ['CPU'])

    def test_eevee_has_no_cpu_fallback(self):
        with self.assertRaisesRegex(policy.DevicePolicyError, 'no CPU render mode'):
            policy.configure_graphics('BLENDER_EEVEE_NEXT', 'iGPU', [adapter('iGPU', True)])

    def test_eevee_active_discrete_verified(self):
        self.assertEqual(policy.configure_graphics('BLENDER_EEVEE_NEXT', 'Discrete board/PCIe/SSE2', [adapter()])['mode'], 'GPU')

    def test_eevee_wrong_or_unknown_context_refused(self):
        for renderer in ('iGPU', '', 'Discrete board fake', None):
            with self.subTest(renderer=renderer), self.assertRaises(policy.DevicePolicyError):
                policy.configure_graphics('BLENDER_EEVEE_NEXT', renderer, [adapter(), adapter('iGPU', True)])

    def test_actual_render_error_has_no_cpu_retry(self):
        prefs = Preferences({'OPTIX': [('Discrete board', 'OPTIX')]})
        scene = NS(cycles=NS(device='GPU'), render=NS(engine='CYCLES'), as_pointer=lambda: 111)
        result = policy.configure_cycles(scene, prefs, [adapter()]);result['engine']='CYCLES'
        calls = []
        def render(**kw):
            calls.append(kw)
            raise RuntimeError('GPU out of memory')
        fake_bpy = NS(context=NS(scene=scene, preferences=NS(addons={'cycles': NS(preferences=prefs)})), data=NS(filepath='test'), ops=NS(render=NS(render=render)))
        with patch.dict(sys.modules, {'bpy': fake_bpy}), patch.dict(policy._CACHE, {(111, 'test'): result}, clear=True):
            with self.assertRaisesRegex(policy.DevicePolicyError, 'no CPU retry'):
                policy.render_with_policy(write_still=True)
        self.assertEqual(len(calls), 1)
        self.assertEqual(scene.cycles.device, 'GPU')

    def test_tampered_cpu_flag_prevents_render(self):
        prefs = Preferences({'OPTIX': [('Discrete board', 'OPTIX'), ('processor', 'CPU')]})
        scene = NS(cycles=NS(device='GPU'), render=NS(engine='CYCLES'), as_pointer=lambda: 112)
        result = policy.configure_cycles(scene, prefs, [adapter()]);result['engine']='CYCLES'
        prefs.devices[-1].use = True
        fake_bpy = NS(context=NS(scene=scene, preferences=NS(addons={'cycles': NS(preferences=prefs)})), data=NS(filepath='test'))
        with patch.dict(sys.modules, {'bpy': fake_bpy}), patch.dict(policy._CACHE, {(112, 'test'): result}, clear=True):
            with self.assertRaisesRegex(policy.DevicePolicyError, 'configuration changed'):
                policy.render_with_policy()

    def test_cancelled_render_is_failure(self):
        prefs = Preferences({'OPTIX': [('Discrete board', 'OPTIX')]})
        scene = NS(cycles=NS(device='GPU'), render=NS(engine='CYCLES'), as_pointer=lambda: 113)
        result = policy.configure_cycles(scene, prefs, [adapter()]);result['engine']='CYCLES'
        fake_bpy = NS(context=NS(scene=scene, preferences=NS(addons={'cycles': NS(preferences=prefs)})), data=NS(filepath='test'), ops=NS(render=NS(render=lambda **kw: {'CANCELLED'})))
        with patch.dict(sys.modules, {'bpy': fake_bpy}), patch.dict(policy._CACHE, {(113, 'test'): result}, clear=True):
            with self.assertRaisesRegex(policy.DevicePolicyError, 'no CPU retry'):
                policy.render_with_policy()


if __name__ == '__main__':
    unittest.main()
