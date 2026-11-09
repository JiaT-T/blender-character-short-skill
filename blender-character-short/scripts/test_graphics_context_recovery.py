import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock
from render_device_policy import graphics_identity,configure_graphics,DevicePolicyError

MESSAGE='GPU functions for drawing are not available in background mode'
DGPU={'name':'NVIDIA GeForce RTX 5060','hardware':True,'integrated':False}


class ContextRecoveryTests(unittest.TestCase):
    def call(self,values,adapters=None,background=True,initializer=None):
        gpu=NS(platform=NS(renderer_get=Mock(side_effect=values)))
        init=initializer or Mock(return_value={'renderer':DGPU['name'],'backend':'VULKAN'})
        result=graphics_identity(NS(app=NS(background=background)),gpu,adapters or [DGPU],init)
        return result,init

    def test_initialized_context_does_not_probe(self):
        (renderer,proof),init=self.call([DGPU['name']])
        self.assertEqual(renderer,DGPU['name']);self.assertIsNone(proof);init.assert_not_called()

    def test_supported_lazy_initialization_requeries_actual_context(self):
        (renderer,proof),init=self.call([SystemError(MESSAGE),DGPU['name']])
        self.assertEqual(renderer,proof['renderer']);init.assert_called_once()

    def test_software_result_after_initialization_refused(self):
        with self.assertRaises(DevicePolicyError):
            self.call([SystemError(MESSAGE),'Microsoft Basic Render Driver'])

    def test_integrated_only_does_not_initialize(self):
        init=Mock()
        with self.assertRaises(DevicePolicyError):
            self.call([SystemError(MESSAGE)],[dict(DGPU,integrated=True)],initializer=init)
        init.assert_not_called()

    def test_multiple_hardware_boards_not_recovered_by_assumption(self):
        init=Mock()
        with self.assertRaises(DevicePolicyError):
            self.call([SystemError(MESSAGE)],[DGPU,dict(DGPU,name='another board')],initializer=init)
        init.assert_not_called()

    def test_foreground_error_does_not_launch_or_recover(self):
        init=Mock()
        with self.assertRaises(DevicePolicyError):self.call([SystemError(MESSAGE)],background=False,initializer=init)
        init.assert_not_called()

    def test_unrelated_error_is_not_swallowed(self):
        init=Mock()
        with self.assertRaises(DevicePolicyError):self.call([RuntimeError('driver lost')],initializer=init)
        init.assert_not_called()

    def test_initializer_failure_propagates(self):
        init=Mock(side_effect=RuntimeError('context failed'))
        with self.assertRaisesRegex(DevicePolicyError,'context initialization'):
            self.call([SystemError(MESSAGE)],initializer=init)
        init.assert_called_once()

    def test_differing_probe_identity_is_rejected(self):
        with self.assertRaises(DevicePolicyError):
            self.call([SystemError(MESSAGE),DGPU['name']],initializer=Mock(return_value={'renderer':'other'}))


if __name__=='__main__':unittest.main()
