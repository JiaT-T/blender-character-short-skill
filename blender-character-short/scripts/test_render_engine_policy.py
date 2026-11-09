import unittest
from types import SimpleNamespace as NS
from render_engine_policy import EEVEE,CYCLES,EnginePolicyError,engine_plan,require_engine,apply_sampling


class EnginePolicyTests(unittest.TestCase):
    def test_new_scene_prefers_eevee(self):
        self.assertEqual(engine_plan(), EEVEE)

    def test_existing_eevee_preserved(self):
        self.assertEqual(engine_plan(EEVEE), EEVEE)

    def test_existing_cycles_preserved(self):
        self.assertEqual(engine_plan(CYCLES), CYCLES)

    def test_explicit_new_cycles_supported(self):
        self.assertEqual(engine_plan(requested=CYCLES), CYCLES)

    def test_existing_engine_conversion_refused(self):
        for saved,requested in [(EEVEE,CYCLES),(CYCLES,EEVEE)]:
            with self.subTest(saved=saved),self.assertRaisesRegex(EnginePolicyError,'no automatic'):
                engine_plan(saved,requested)

    def test_unknown_engine_refused(self):
        with self.assertRaises(EnginePolicyError):
            engine_plan('UNKNOWN')

    def test_eevee_sampling_does_not_touch_cycles(self):
        scene=NS(render=NS(engine=EEVEE),eevee=NS(taa_render_samples=8))
        result=apply_sampling(scene,16,True)
        self.assertEqual(scene.render.engine,EEVEE)
        self.assertEqual(scene.eevee.taa_render_samples,16)
        self.assertFalse(result['denoise'])
        self.assertTrue(result['cycles_denoise_requested_but_not_applicable'])

    def test_cycles_sampling_does_not_touch_eevee(self):
        scene=NS(render=NS(engine=CYCLES),cycles=NS(samples=1,use_denoising=False))
        result=apply_sampling(scene,4,True)
        self.assertEqual(scene.render.engine,CYCLES)
        self.assertEqual(scene.cycles.denoiser,'OPENIMAGEDENOISE')
        self.assertTrue(result['denoise'])

    def test_engine_assertion_does_not_mutate_project(self):
        scene=NS(render=NS(engine=CYCLES))
        with self.assertRaises(EnginePolicyError):
            require_engine(scene,EEVEE)
        self.assertEqual(scene.render.engine,CYCLES)


if __name__=='__main__':unittest.main()
