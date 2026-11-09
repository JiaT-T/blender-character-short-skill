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

if __name__=='__main__':unittest.main()
