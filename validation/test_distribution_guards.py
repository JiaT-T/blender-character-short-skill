"""Keep public SDK UUID exceptions narrow without allowing private identifiers."""
import unittest,uuid
from validate_distribution import validate_text_privacy,PUBLIC_DXCORE_GUIDS

class PrivacyChecks(unittest.TestCase):
    def test_known_guid_allowed_only_in_declared_file(self):
        for value in PUBLIC_DXCORE_GUIDS:
            validate_text_privacy('blender-character-short/scripts/render_device_policy.py',repr(value))
            with self.assertRaises(AssertionError):validate_text_privacy('README.md',value)
    def test_unknown_uuid_still_rejected_in_device_source(self):
        with self.assertRaises(AssertionError):
            validate_text_privacy('blender-character-short/scripts/render_device_policy.py',str(uuid.UUID(int=7)))
    def test_matrix_operator_is_not_an_email(self):
        validate_text_privacy('fixture.py','value=model.matrix'+'@'+'bone.matrix\n')
    def test_email_literal_is_rejected(self):
        with self.assertRaises(AssertionError):validate_text_privacy('fixture.py',repr('person'+'@'+'example.invalid'))
    def test_arbitrary_windows_workspace_is_rejected(self):
        for separator in (chr(92),'/'):
            path='Z:'+separator+'StudioWork'+separator+'shot.blend'
            with self.subTest(separator=separator),self.assertRaises(AssertionError):
                validate_text_privacy('fixture.md',path)
    def test_escaped_windows_paths_are_rejected(self):
        import json
        path='Z:'+chr(92)+'StudioWork'+chr(92)+'shot.blend'
        for representation in (json.dumps({'source':path}),repr(path)):
            with self.subTest(representation=representation),self.assertRaises(AssertionError):
                validate_text_privacy('fixture.json',representation)
    def test_extended_windows_drive_path_is_rejected(self):
        path=chr(92)*2+'?'+chr(92)+'Z:'+chr(92)+'StudioWork'+chr(92)+'shot.blend'
        with self.assertRaises(AssertionError):validate_text_privacy('fixture.md',path)
    def test_urls_and_relative_asset_paths_remain_allowed(self):
        for value in ('https://example.invalid/files/shot','relative/projects/shot.blend','<INPUT_PROJECT>'):
            with self.subTest(value=value):validate_text_privacy('fixture.md',value)

if __name__=='__main__':unittest.main()
