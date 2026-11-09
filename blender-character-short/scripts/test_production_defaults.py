import unittest
from production_defaults import new_video_settings,saved_render_dimensions
from production_contract import fps_value

class DefaultSettingsTests(unittest.TestCase):
    def test_new_video_defaults(self):
        self.assertEqual(new_video_settings(),{'width':1280,'height':720,'fps':24})
    def test_explicit_current_high_spec_is_preserved(self):
        overrides={'width':1920,'height':1080,'fps':30};copy=dict(overrides)
        self.assertEqual(new_video_settings(overrides),copy);self.assertEqual(overrides,copy)
    def test_saved_dimensions_have_720_default(self):
        self.assertEqual(saved_render_dimensions({}),(1280,720))
        self.assertEqual(saved_render_dimensions({'width':1920,'height':1080}),(1920,1080))
    def test_saved_fps_is_not_retimed(self):
        job={'fps':30000/1001};saved_render_dimensions(job)
        self.assertAlmostEqual(job['fps'],fps_value(30,1.001),places=5)
    def test_bad_new_video_rate_is_rejected(self):
        for value in [0,-1,True,24.5]:
            with self.subTest(value=value),self.assertRaises(ValueError):new_video_settings({'fps':value})

if __name__=='__main__':unittest.main()
