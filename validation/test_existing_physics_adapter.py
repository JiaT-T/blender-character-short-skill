"""Mocked Blender contracts, not a bake/reopen or physical-quality test.

The fixture uses the actor/stage and population shape observed in
reports/physics-assembly06.json, without reading or modifying any .blend.
"""
import copy
from contextlib import contextmanager
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch


SCRIPT = Path(__file__).resolve().parents[1] / 'blender-character-short/scripts/cache_existing_physics.py'
IDENTITY = [[1., 0., 0., 0.], [0., 1., 0., 0.], [0., 0., 1., 0.], [0., 0., 0., 1.]]


@contextmanager
def fixture_directory():
    # Use the writable checkout rather than a redirected Windows sandbox TEMP.
    parent = Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory(prefix='physics-fixture-', dir=parent) as directory:
        target = Path(directory).resolve()
        if target.parent != parent:
            raise ValueError('Fixture cleanup must stay inside validation directory')
        yield target


class Named(list):
    def get(self, name):
        return next((o for o in self if o.name == name), None)


class Object:
    def __init__(self, name, *, kind='EMPTY', mmd_type='NONE', parent=None):
        self.name, self.type, self.mmd_type, self.parent = name, kind, mmd_type, parent
        self.children_recursive = []
        self.mmd_root = NS(is_built=False)
        self.rigid_body = None
        self.rigid_body_constraint = None
        self.matrix_world = copy.deepcopy(IDENTITY)
        self.constraints = []
        self.selected = False

    def select_set(self, value):
        self.selected = value


def fixture(*, baked=True, frames=(1, 2)):
    actor = Object('actor ROOT', mmd_type='ROOT')
    actor.mmd_root.is_built = True
    stage = Object('EXT Gothic house root', mmd_type='ROOT')
    rig = Object('current controller', kind='ARMATURE')
    native = Object('current native', kind='ARMATURE', parent=actor)
    stage_arm = Object('one-bone stage', kind='ARMATURE', parent=stage)
    for obj, count in ((rig, 773), (native, 1191), (stage_arm, 1)):
        bones = Named(NS(name='bone-' + str(i), matrix=copy.deepcopy(IDENTITY), constraints=[])
                      for i in range(count))
        obj.data, obj.pose = NS(bones=bones), NS(bones=bones)
    native.pose.bones[0].constraints = [NS(name='MMR_copy', type='COPY_TRANSFORMS',
        target=rig, subtarget=rig.pose.bones[0].name, influence=1., mute=False)]
    bodies = [Object('rigid-' + str(i), kind='MESH', mmd_type='RIGID_BODY', parent=actor)
              for i in range(933)]
    for obj in bodies:
        obj.rigid_body = NS(type='ACTIVE')
    joints = [Object('joint-' + str(i), mmd_type='JOINT', parent=actor) for i in range(1615)]
    for index, obj in enumerate(joints):
        obj.rigid_body_constraint = NS(object1=bodies[index % 933], object2=bodies[(index + 1) % 933])
    floor = Object('reviewed passive floor', kind='MESH')
    floor.rigid_body = NS(type='PASSIVE')
    actor.children_recursive = [native, *bodies, *joints]
    stage.children_recursive = [stage_arm]
    # Put the scene ROOT first to catch order-dependent selection.
    objects = Named([stage, stage_arm, rig, actor, native, *bodies, *joints, floor])
    all_constraints = [*joints, *(Object('generated-' + str(i)) for i in range(16748 - len(joints)))]
    cache = NS(is_baked=baked, is_baking=False, use_disk_cache=False, use_external=False,
               is_outdated=True, is_frame_skip=False, frame_start=frames[0], frame_end=frames[1])
    world = NS(collection=NS(objects=[], all_objects=[*bodies, floor]),
        constraints=NS(objects=[], all_objects=all_constraints), point_cache=cache,
        enabled=True, time_scale=1., substeps_per_frame=6, solver_iterations=10)
    scene = NS(objects=objects, rigidbody_world=world, frame_start=25, frame_end=360,
               frame_current=25, render=NS(fps=24, fps_base=1.))
    def set_frame(frame):
        scene.frame_current = frame
    scene.frame_set = Mock(side_effect=set_frame)
    model = NS(find_root_object=lambda obj: actor if obj == native else None,
               find_armature_object=lambda obj: native if obj == actor else None)
    cfg = {'schema': 1, 'source_sha256': '0' * 64, 'module': 'mmd_tools',
           'addon_version': '4.5.14', 'instructions_url': 'https://mmd-blender.fandom.com/wiki/MMD_Tools/Manual',
           'controller_object': rig.name, 'model_armature': native.name,
           'controller_bones': 773, 'rigid_bodies': 933, 'frames': list(frames),
           'mmd_root': actor.name,
           'physics_population': {'joints': 1615, 'world_bodies': 934,
                                  'world_constraints': 16748, 'passive_bodies': [floor.name]}}
    open_file, save_file, bake, enable = Mock(), Mock(), Mock(), Mock()
    stub = NS(app=NS(background=True), data=NS(actions=[]),
        context=NS(scene=scene, preferences=NS(addons={'mmd_tools': True}),
                   view_layer=NS(update=Mock(), objects=NS(active=None))),
        ops=NS(wm=NS(open_mainfile=open_file, save_as_mainfile=save_file),
               object=NS(select_all=Mock()), mmd_tools=NS(ptcache_rigid_body_bake=bake),
               preferences=NS(addon_enable=enable)))
    def runtime_enable(module):
        stub.context.preferences.addons[module] = True
        return {'FINISHED'}
    enable.side_effect = runtime_enable
    return NS(actor=actor, stage=stage, rig=rig, native=native, stage_arm=stage_arm,
              bodies=bodies, joints=joints, floor=floor, world=world, cache=cache,
              scene=scene, model=model, cfg=cfg, bpy=stub, open=open_file, save=save_file, bake=bake,
              enable=enable, installed_version='4.5.14')


def load_adapter(stub):
    spec = importlib.util.spec_from_file_location('fixture_existing_physics_adapter', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {'bpy': stub}):
        spec.loader.exec_module(module)
    return module


class ExistingPhysicsAdapter(unittest.TestCase):
    def setUp(self):
        self.fx = fixture()
        self.adapter = load_adapter(self.fx.bpy)

    def selected(self, cfg=None):
        f = self.fx
        return self.adapter.select_actor_root(f.scene, cfg or f.cfg, f.rig, f.native, f.model)

    def test_isolated_background_style_sibling_import_and_pre_fix_control(self):
        # A new -I interpreter, unrelated cwd and no test mock for scene_integrity
        # reproduce Blender --python lacking the producer's script directory.
        check = r'''
from pathlib import Path
from types import ModuleType, SimpleNamespace as NS
import json, sys
path = Path(sys.argv[1]).resolve()
assert str(path.parent) not in sys.path
bpy = ModuleType('bpy')
bpy.data = NS(actions=[])
sys.modules['bpy'] = bpy
source = path.read_text(encoding='utf-8')
if sys.argv[2] == 'pre_fix_control':
    source = source.replace('sys.path.insert(0, str(Path(__file__).resolve().parent))', '')
scope = {'__file__': str(path), '__name__': 'isolated_cache_import_fixture'}
exec(compile(source, str(path), 'exec'), scope)
rig = NS(name='fixture rig', parent=None, animation_data=None, constraints=[], pose=NS(bones=[]))
arm = NS(name='fixture native', parent=None, animation_data=None, constraints=[], pose=NS(bones=[]))
try:
    result = scope['protected_state'](NS(objects=[]), rig, arm, [])
except ModuleNotFoundError as exc:
    if sys.argv[2] != 'pre_fix_control' or exc.name != 'scene_integrity':
        raise
    print(json.dumps({'expected_pre_fix_failure': exc.name}))
else:
    assert sys.argv[2] == 'fixed'
    sibling = Path(sys.modules['scene_integrity'].__file__).resolve()
    assert sibling == path.with_name('scene_integrity.py')
    assert len(result) == 5 and all(len(v) == 64 for v in result.values())
    print(json.dumps({'real_sibling_imported': str(sibling), 'protected_state_keys': sorted(result)}))
'''
        with fixture_directory() as unrelated:
            for mode in ('fixed', 'pre_fix_control'):
                with self.subTest(mode=mode):
                    result = subprocess.run([sys.executable, '-I', '-B', '-c', check, str(SCRIPT), mode],
                        cwd=unrelated, capture_output=True, text=True, timeout=20)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    evidence = json.loads(result.stdout)
                    self.assertIn('real_sibling_imported' if mode == 'fixed' else 'expected_pre_fix_failure', evidence)

    def population(self):
        f = self.fx
        return self.adapter.check_population(f.scene, f.world, f.actor, f.cfg)

    def test_two_roots_resolve_actor_with_explicit_name_and_association(self):
        self.assertIs(self.selected(), self.fx.actor)
        cfg = copy.deepcopy(self.fx.cfg)
        del cfg['mmd_root']
        self.assertIs(self.selected(cfg), self.fx.actor)

    def test_explicit_scene_root_is_rejected(self):
        self.fx.cfg['mmd_root'] = self.fx.stage.name
        with self.assertRaisesRegex(ValueError, 'not the declared original'):
            self.selected()

    def test_missing_or_nested_native_root_is_rejected(self):
        self.fx.native.parent = None
        with self.assertRaisesRegex(ValueError, 'exactly one'):
            self.selected()
        self.fx.native.parent = self.fx.actor
        self.fx.actor.parent = self.fx.stage
        with self.assertRaisesRegex(ValueError, 'exactly one'):
            self.selected()

    def test_addon_native_disagreement_is_rejected(self):
        self.fx.model.find_armature_object = lambda root: self.fx.stage_arm
        with self.assertRaisesRegex(ValueError, 'ambiguous'):
            self.selected()

    def test_wrong_controller_root_or_binding_is_rejected(self):
        self.fx.rig.parent = self.fx.stage
        with self.assertRaisesRegex(ValueError, 'different or ambiguous'):
            self.selected()
        self.fx.rig.parent = None
        self.fx.native.pose.bones[0].constraints[0].target = self.fx.stage_arm
        with self.assertRaisesRegex(ValueError, 'MMR binding'):
            self.selected()

    def test_missing_controller_relation_is_rejected(self):
        self.fx.native.pose.bones[0].constraints.clear()
        with self.assertRaisesRegex(ValueError, 'actual native/controller'):
            self.selected()

    def test_real_population_shape_and_recursive_collections_pass(self):
        bodies, summary = self.population()
        self.assertEqual(len(bodies), 934)
        self.assertEqual(summary['actor_rigid_bodies'], 933)
        self.assertEqual(summary['original_joints'], 1615)
        self.assertEqual(summary['world_constraints'], 16748)
        self.assertEqual(summary['scene_mmd_roots'], ['EXT Gothic house root', 'actor ROOT'])

    def test_undeclared_floor_and_active_extra_are_rejected(self):
        declaration = self.fx.cfg.pop('physics_population')
        with self.assertRaisesRegex(ValueError, 'additional passive bodies'):
            self.population()
        self.fx.cfg['physics_population'] = declaration
        self.fx.floor.rigid_body.type = 'ACTIVE'
        with self.assertRaisesRegex(ValueError, 'independent passive'):
            self.population()

    def test_scene_body_or_bad_original_joint_is_rejected(self):
        self.fx.bodies[0].parent = self.fx.stage
        with self.assertRaisesRegex(ValueError, 'declared actor ROOT'):
            self.population()
        self.fx.bodies[0].parent = self.fx.actor
        self.fx.joints[0].rigid_body_constraint.object2 = self.fx.floor
        with self.assertRaisesRegex(ValueError, 'joint endpoints'):
            self.population()

    def test_exact_world_constraint_population_is_enforced(self):
        self.fx.world.constraints.all_objects.pop()
        with self.assertRaisesRegex(ValueError, 'exact reviewed'):
            self.population()

    def test_outdated_is_diagnostic_skip_is_failure(self):
        self.adapter.check_cache(self.fx.cache, [1, 2], baked=True)
        self.assertTrue(self.adapter.cache_state(self.fx.cache)['is_outdated'])
        self.fx.cache.is_frame_skip = True
        with self.assertRaisesRegex(ValueError, 'skipped frames'):
            self.adapter.check_cache(self.fx.cache, [1, 2], baked=True)

    def test_incomplete_or_external_cache_is_rejected(self):
        for field in ('is_baking', 'use_external', 'use_disk_cache'):
            with self.subTest(field=field):
                self.fx.cache.__dict__[field] = True
                with self.assertRaisesRegex(ValueError, 'embedded'):
                    self.adapter.check_cache(self.fx.cache, [1, 2], baked=True)
                self.fx.cache.__dict__[field] = False
        self.fx.cache.is_baked = False
        with self.assertRaisesRegex(ValueError, 'baked cache'):
            self.adapter.check_cache(self.fx.cache, [1, 2], baked=True)

    def test_plan_strictness_and_legacy_population(self):
        self.adapter.validate_plan(self.fx.cfg)
        for mutation in ({'unknown': 1}, {'controller_bones': True}, {'mmd_root': ''},
                         {'physics_population': None}, {'source_sha256': 'unbound'},
                         {'module': 'unrelated_addon'}, {'module': 'bl_ext..mmd_tools'},
                         {'addon_version': 'unreviewed'}):
            with self.subTest(mutation=mutation):
                cfg = {**self.fx.cfg, **mutation}
                with self.assertRaises(ValueError):
                    self.adapter.validate_plan(cfg)
        del self.fx.cfg['physics_population']
        del self.fx.cfg['mmd_root']
        self.adapter.validate_plan(self.fx.cfg)
        self.fx.world.collection.all_objects.remove(self.fx.floor)
        self.assertEqual(self.population()[1]['world_bodies'], 933)

    def test_stored_asset_guard_covers_meshes_rests_actions_and_physics(self):
        f = self.fx
        skin = Object('stored skin', kind='MESH', parent=f.native)
        skin.data, skin.vertex_groups, skin.modifiers = NS(fixture_value='base geometry/UV/weights/shape'), [], []
        f.scene.objects.append(skin)
        action = NS(name='authored action', fixture_value='original keyframes')
        f.bpy.data.actions.append(action)
        serializers = NS(_action=lambda a: a.fixture_value, _animation=lambda o: 'unchanged animation links',
            _armature=lambda a: {'bones': len(a.bones), 'rest': getattr(a, 'fixture_value', 'original rest')},
            _mesh=lambda m: m.fixture_value, _rna=lambda o: getattr(o, 'fixture_value', 'unchanged settings'))
        with patch.dict(sys.modules, {'scene_integrity': serializers}):
            before = self.adapter.protected_state(f.scene, f.rig, f.native, [*f.bodies, f.floor])
            # Simulation changes are permitted; stored data changes are detected.
            f.bodies[0].matrix_world[0][3] = 10.
            self.assertEqual(before, self.adapter.protected_state(f.scene, f.rig, f.native, [*f.bodies, f.floor]))
            for owner, key in ((skin.data, 'meshes_weights_uv_shape_keys'), (f.native.data, 'armature_rest'),
                               (action, 'actions'), (f.floor.rigid_body, 'physics_settings')):
                with self.subTest(key=key):
                    original = getattr(owner, 'fixture_value', None)
                    owner.fixture_value = 'unexpected change'
                    after = self.adapter.protected_state(f.scene, f.rig, f.native, [*f.bodies, f.floor])
                    self.assertNotEqual(before[key], after[key])
                    if original is None:
                        del owner.fixture_value
                    else:
                        owner.fixture_value = original

    def invoke(self, directory, mode='verify', protect=None, *, output_name='new.blend'):
        f = self.fx
        source, plan, report = (directory / name for name in ('source.blend', 'plan.json', 'report.json'))
        source.write_bytes(b'not-a-blend: mock fixture only')
        cfg = {**f.cfg, 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest()}
        plan.write_text(json.dumps(cfg), encoding='utf-8')
        argv = ['--mode', mode, '--source', str(source), '--plan', str(plan), '--report', str(report)]
        if mode == 'bake':
            argv += ['--output', str(directory / output_name)]
        def imports(name):
            return NS(MMD_TOOLS_VERSION=f.installed_version) if name == 'mmd_tools' else NS(FnModel=f.model)
        def save(filepath):
            Path(filepath).write_bytes(b'new mocked baked project')
            return {'FINISHED'}
        def bake():
            self.assertIs(f.bpy.context.view_layer.objects.active, f.actor)
            self.assertTrue(f.actor.selected)
            f.cache.is_baked = True
            return {'FINISHED'}
        f.save.side_effect, f.bake.side_effect = save, bake
        if protect is None:
            protect = Mock(return_value={'fixture_stored_assets': 'unchanged'})
        with patch.object(self.adapter.importlib, 'import_module', side_effect=imports), \
             patch.object(self.adapter, 'protected_state', protect):
            self.adapter.main(argv)
        return source, report

    def test_full_mock_verify_reopens_once_and_never_saves_or_bakes(self):
        with fixture_directory() as td:
            source, report = self.invoke(Path(td))
            result = json.loads(report.read_text(encoding='utf-8'))
            self.assertTrue(result['fresh_process_reopen_verified'])
            self.assertTrue(result['all_integer_native_matrices_finite'])
            self.assertEqual(result['diagnostic_cache_flags']['outdated_frames'], [1, 2])
            self.assertEqual(result['physics_population']['world_bodies'], 934)
            self.assertEqual(source.read_bytes(), b'not-a-blend: mock fixture only')
        self.fx.open.assert_called_once()
        self.fx.save.assert_not_called()
        self.fx.bake.assert_not_called()
        self.fx.enable.assert_not_called()
        self.assertEqual(self.fx.scene.frame_current, 25)

    def test_missing_process_addon_is_activated_without_persisting_preferences(self):
        self.fx.bpy.context.preferences.addons.clear()
        with fixture_directory() as td:
            _, report = self.invoke(Path(td))
            result = json.loads(report.read_text(encoding='utf-8'))
            self.assertTrue(result['runtime_only_activation'])
            self.assertFalse(result['preferences_saved'])
        self.fx.enable.assert_called_once_with(module='mmd_tools')
        self.fx.save.assert_not_called()

    def test_wrong_installed_version_is_refused_before_activation_or_open(self):
        self.fx.bpy.context.preferences.addons.clear()
        self.fx.installed_version = '4.5.13'
        with fixture_directory() as td:
            with self.assertRaisesRegex(ValueError, 'version required before runtime activation'):
                self.invoke(Path(td))
        self.fx.enable.assert_not_called()
        self.fx.open.assert_not_called()

    def test_failed_runtime_activation_is_refused_before_open(self):
        self.fx.bpy.context.preferences.addons.clear()
        self.fx.enable.side_effect = lambda module: {'CANCELLED'}
        with fixture_directory() as td:
            with self.assertRaisesRegex(ValueError, 'activation did not finish'):
                self.invoke(Path(td))
        self.fx.open.assert_not_called()

    def test_full_mock_bake_selects_actor_and_preserves_original(self):
        self.fx.cache.is_baked = False
        with fixture_directory() as td:
            source, report = self.invoke(Path(td), 'bake')
            result = json.loads(report.read_text(encoding='utf-8'))
            self.assertFalse(result['fresh_process_reopen_verified'])
            self.assertTrue(result['stored_assets_actions_and_rig_unchanged'])
            self.assertEqual(source.read_bytes(), b'not-a-blend: mock fixture only')
            self.assertTrue((Path(td) / 'new.blend').is_file())
        self.fx.bake.assert_called_once()
        self.assertEqual(self.fx.save.call_count, 2)
        self.fx.open.assert_called_once()

    def test_already_baked_input_refused_before_bake_save_or_frame_evaluation(self):
        with fixture_directory() as td:
            with self.assertRaisesRegex(ValueError, 'Already baked'):
                self.invoke(Path(td), 'bake')
            self.assertFalse((Path(td) / 'new.blend').exists())
        self.fx.save.assert_not_called()
        self.fx.bake.assert_not_called()
        self.fx.scene.frame_set.assert_not_called()

    def test_native_nonfinite_transform_and_stored_asset_change_fail(self):
        self.fx.native.pose.bones[1].matrix[0][0] = float('nan')
        with fixture_directory() as td:
            with self.assertRaisesRegex(ValueError, 'Nonfinite'):
                self.invoke(Path(td))
            self.assertFalse((Path(td) / 'report.json').exists())
        self.fx.native.pose.bones[1].matrix[0][0] = 1.
        with fixture_directory() as td:
            with self.assertRaisesRegex(ValueError, 'Stored mesh assets'):
                self.invoke(Path(td), protect=Mock(side_effect=[{'assets': 'before'}, {'assets': 'changed'}]))
        self.fx.save.assert_not_called()

    def test_output_report_alias_is_rejected_before_scene_open(self):
        with fixture_directory() as td:
            with self.assertRaisesRegex(ValueError, 'Distinct'):
                self.invoke(Path(td), 'bake', output_name='report.json')
        self.fx.open.assert_not_called()
        self.fx.save.assert_not_called()


if __name__ == '__main__':
    unittest.main()
