"""Mock native addon bootstrap; no Blender, preferences, install or network."""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'blender-character-short' / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import runtime_addons as addons
import short_project


class RuntimeAddonsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.enabled = {}
        self.enable = Mock(side_effect=self.activate)
        self.save = Mock()
        self.bpy = SimpleNamespace(
            app=SimpleNamespace(background=True, version=(4, 5, 15)),
            context=SimpleNamespace(preferences=SimpleNamespace(addons=self.enabled)),
            ops=SimpleNamespace(preferences=SimpleNamespace(addon_enable=self.enable, save_userpref=self.save)))
        self.modules = {}
        self.import_mock = Mock(side_effect=self.import_module)
        self.importer = patch.object(addons, 'importlib', SimpleNamespace(import_module=self.import_mock))
        self.importer.start()

    def tearDown(self):
        self.save.assert_not_called()
        self.importer.stop()
        self.tmp.cleanup()

    def activate(self, module):
        self.enabled[module] = object()
        return {'FINISHED'}

    def import_module(self, name):
        if name not in self.modules:
            raise ModuleNotFoundError('fixture addon unavailable: ' + name)
        return self.modules[name]

    def module(self, name='mmd_tools', version=(4, 5, 14), manifest=None, legacy=None):
        folder = self.root / name.replace('.', '_')
        folder.mkdir(exist_ok=True)
        path = folder / '__init__.py'
        path.write_text('# installed addon fixture\n', encoding='utf-8')
        module = SimpleNamespace(__file__=str(path))
        if version is not None:
            module.bl_info = {'version': version}
        manifest_path = folder / 'blender_manifest.toml'
        manifest_path.unlink(missing_ok=True)
        if manifest is not None:
            manifest_path.write_text('version = ' + json.dumps(manifest) + '\n', encoding='utf-8')
        if legacy is not None:
            module.MMD_TOOLS_VERSION = legacy
        self.modules[name] = module
        return module

    def runtime(self, declared=None):
        return {'blender_version': [4, 5, 15], 'addons': {'mmd_tools': [4, 5, 14]} if declared is None else declared}

    def test_correct_installed_version_enables_in_current_process(self):
        self.module(legacy='4.5.14')
        result = addons.initialize(self.runtime(), self.bpy)
        self.enable.assert_called_once_with(module='mmd_tools')
        self.assertTrue(result['process_only'])
        self.assertFalse(result['preferences_saved'])
        self.assertTrue(result['addons']['mmd_tools']['enabled_now'])

    def test_already_enabled_and_repeated_initialization_are_idempotent(self):
        self.module()
        addons.initialize(self.runtime(), self.bpy)
        result = addons.initialize(self.runtime(), self.bpy)
        self.enable.assert_called_once()
        self.assertFalse(result['addons']['mmd_tools']['enabled_now'])

    def test_manifest_extension_and_legacy_version_agree(self):
        name = 'bl_ext.blender_org.mmd_tools'
        self.module(name, version=None, manifest='4.5.14', legacy='4.5.14')
        result = addons.initialize(self.runtime({name: [4, 5, 14]}), self.bpy)
        self.assertEqual(result['addons'][name]['version'], [4, 5, 14])
        self.enable.assert_called_once_with(module=name)

    def test_mikumiku_rig_fixed_nested_bl_info_is_supported(self):
        self.module('MikuMikuRig', version=None)
        self.modules['MikuMikuRig.addons.MikuMikuRig'] = SimpleNamespace(bl_info={'version': (0, 6, 0)})
        result = addons.initialize(self.runtime({'MikuMikuRig': [0, 6, 0]}), self.bpy)
        self.assertEqual(result['addons']['MikuMikuRig']['version'], [0, 6, 0])
        self.assertEqual({c.args[0] for c in self.import_mock.call_args_list},
                         {'MikuMikuRig', 'MikuMikuRig.addons.MikuMikuRig'})

    def test_missing_installed_addon_fails_before_enable(self):
        with self.assertRaisesRegex(ValueError, 'unavailable'):
            addons.initialize(self.runtime(), self.bpy)
        self.enable.assert_not_called()

    def test_imported_object_without_installed_file_fails_before_enable(self):
        module = self.module()
        module.__file__ = str(self.root / 'not-installed.py')
        with self.assertRaisesRegex(ValueError, 'module file missing'):
            addons.initialize(self.runtime(), self.bpy)
        self.enable.assert_not_called()

    def test_wrong_installed_version_fails_before_any_enable(self):
        self.module()
        self.module('MikuMikuRig', version=(0, 5, 0))
        with self.assertRaisesRegex(ValueError, 'version differs'):
            addons.initialize(self.runtime({'mmd_tools': [4, 5, 14], 'MikuMikuRig': [0, 6, 0]}), self.bpy)
        self.enable.assert_not_called()

    def test_unknown_module_and_code_like_names_are_never_imported(self):
        for name in ('os', 'bl_ext.repo.extra.mmd_tools', 'bl_ext.repo.mmd_tools.payload',
                     "mmd_tools; __import__('os')", 'bl_ext.repo-name.mmd_tools'):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'Unsupported'):
                addons.initialize(self.runtime({name: [4, 5, 14]}), self.bpy)
        self.import_mock.assert_not_called()
        self.enable.assert_not_called()

    def test_non_mapping_and_invalid_versions_fail_before_import(self):
        cases = [[], None, 'mmd_tools', {'mmd_tools': '4.5.14'},
                 {'mmd_tools': [4, True, 14]}, {'mmd_tools': [4, 5]}, {'mmd_tools': [4, -1, 14]}]
        for declared in cases:
            with self.subTest(declared=declared), self.assertRaises(ValueError):
                addons.initialize({'blender_version': [4, 5, 15], 'addons': declared}, self.bpy)
        self.import_mock.assert_not_called()
        self.enable.assert_not_called()

    def test_duplicate_mmd_aliases_fail_before_import(self):
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            addons.initialize(self.runtime({'mmd_tools': [4, 5, 14], 'bl_ext.repo.mmd_tools': [4, 5, 14]}), self.bpy)
        self.import_mock.assert_not_called()
        self.enable.assert_not_called()

    def test_duplicate_nested_project_keys_fail_before_native_launch(self):
        samples = [
            '{"schema":1,"runtime":{"addons":{"mmd_tools":[4,5,14],"mmd_tools":[4,5,13]}}}',
            '{"schema":1,"runtime":{"addons":{},"addons":{"mmd_tools":[4,5,14]}}}',
            '{"schema":1,"runtime":{"blender_version":[4,5,15],"blender_version":[4,5,14],"addons":{}}}'
        ]
        project = self.root / 'duplicate.json'
        for raw in samples:
            project.write_text(raw, encoding='utf-8')
            with self.subTest(raw=raw), patch.object(sys, 'argv', ['short_project.py', 'doctor', '--project', str(project)]), patch('short_project.run_native') as native:
                with self.assertRaisesRegex(ValueError, 'Duplicate'):
                    short_project.main()
                native.assert_not_called()
        self.import_mock.assert_not_called()
        self.enable.assert_not_called()

    def test_duplicate_bootstrap_payload_fails_before_bpy_or_import(self):
        raw = '{"blender_version":[4,5,15],"addons":{"mmd_tools":[4,5,14],"mmd_tools":[4,5,14]}}'
        with patch.dict('os.environ', {addons.ENVIRONMENT_KEY: raw}), self.assertRaisesRegex(ValueError, 'Duplicate'):
            addons.main()
        self.import_mock.assert_not_called()
        self.enable.assert_not_called()

    def test_missing_and_inconsistent_installed_metadata_fail_before_enable(self):
        for case in ('missing', 'manifest_conflict', 'legacy_conflict'):
            with self.subTest(case=case):
                self.module(version=None if case == 'missing' else (4, 5, 14),
                            manifest='4.5.13' if case == 'manifest_conflict' else None,
                            legacy='4.5.13' if case == 'legacy_conflict' else None)
                with self.assertRaises(ValueError):
                    addons.initialize(self.runtime(), self.bpy)
        self.enable.assert_not_called()

    def test_cancelled_activation_does_not_claim_enabled(self):
        self.module()
        self.enable.side_effect = None
        self.enable.return_value = {'CANCELLED'}
        with self.assertRaisesRegex(ValueError, 'did not finish'):
            addons.initialize(self.runtime(), self.bpy)
        self.assertFalse(self.enabled)

    def test_finished_activation_without_enabled_state_fails(self):
        self.module()
        self.enable.side_effect = None
        self.enable.return_value = {'FINISHED'}
        with self.assertRaisesRegex(ValueError, 'not enabled'):
            addons.initialize(self.runtime(), self.bpy)

    def test_changed_version_during_activation_fails(self):
        module = self.module()

        def changing(name=None, **kwargs):
            result = self.activate(kwargs.get('module', name))
            module.bl_info['version'] = (4, 5, 13)
            return result

        self.enable.side_effect = changing
        with self.assertRaisesRegex(ValueError, 'not enabled'):
            addons.initialize(self.runtime(), self.bpy)

    def test_wrong_blender_or_foreground_context_fails_before_import(self):
        self.bpy.app.background = False
        with self.assertRaisesRegex(ValueError, 'background'):
            addons.initialize(self.runtime(), self.bpy)
        self.bpy.app.background = True
        self.bpy.app.version = (4, 5, 14)
        with self.assertRaisesRegex(ValueError, 'Blender version differs'):
            addons.initialize(self.runtime(), self.bpy)
        self.import_mock.assert_not_called()
        self.enable.assert_not_called()

    def test_empty_declaration_does_not_enable_extra_plugins(self):
        result = addons.initialize(self.runtime({}), self.bpy)
        self.assertEqual(result['addons'], {})
        self.import_mock.assert_not_called()
        self.enable.assert_not_called()

    def project(self):
        binary = self.root / 'Blender fixture.exe'
        binary.write_bytes(b'not executable; mock only')
        return {'schema': 1, 'runtime': dict(self.runtime(), blender=binary.name, threads=1),
                'reports': 'reports', 'execution_lock': 'fixture.lock'}

    def test_native_command_bootstraps_fixed_script_before_stage(self):
        project = self.project()
        child = SimpleNamespace(pid=1234, wait=Mock(return_value=0))
        with patch('short_project.subprocess.Popen', return_value=child) as spawn:
            short_project.run_native(project, self.root, 'runtime_probe.py', ['--project', 'reviewed.json'], 'fixture')
        call = spawn.call_args
        wrapper = call.args[0]
        bootstrap = str(SCRIPTS / 'runtime_addons.py')
        stage = str(SCRIPTS / 'runtime_probe.py')
        self.assertLess(wrapper.index(bootstrap), wrapper.index(stage))
        self.assertEqual(wrapper[wrapper.index(bootstrap) - 1], '--python')
        self.assertEqual(wrapper[wrapper.index('--python-exit-code') + 1], '1')
        self.assertNotIn('shell', call.kwargs)
        self.assertEqual(json.loads(call.kwargs['env'][addons.ENVIRONMENT_KEY]), self.runtime())
        self.import_mock.assert_not_called()
        self.enable.assert_not_called()

    def test_native_command_rejects_unknown_declaration_before_spawn(self):
        project = self.project()
        project['runtime']['addons'] = {'os': [1, 0, 0]}
        with patch('short_project.subprocess.Popen') as spawn, self.assertRaisesRegex(ValueError, 'Unsupported'):
            short_project.run_native(project, self.root, 'runtime_probe.py', [], 'fixture')
        spawn.assert_not_called()

    def test_existing_runtime_doctor_identity_gate_is_retained(self):
        project = self.project()
        reports = self.root / project['reports']
        reports.mkdir()
        (reports / 'runtime.json').write_text(json.dumps({'accepted': True, 'runtime_spec_sha256': 'wrong'}))
        path = self.root / 'project.json'
        path.write_text(json.dumps(project))
        with patch.object(sys, 'argv', ['short_project.py', 'tests', '--project', str(path)]), patch('short_project.run_native') as native:
            with self.assertRaisesRegex(ValueError, 'Run doctor'):
                short_project.main()
        native.assert_not_called()


if __name__ == '__main__':
    unittest.main()
