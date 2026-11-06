"""Native Blender saved-input regressions; no third-party model or motion needed."""
from pathlib import Path
import hashlib
import json
import tempfile
import unittest
import bpy
import numpy as np
from mathutils import Matrix
from import_existing_controller_action import main


class ExistingControllerInputTests(unittest.TestCase):
    def setUp(self):
        base = Path(tempfile.gettempdir()).resolve()
        self.temp = tempfile.TemporaryDirectory(prefix='controller-input-', dir=base)
        self.root = Path(self.temp.name).resolve()
        if not self.root.is_relative_to(base):
            raise ValueError('Own temporary fixture must stay inside the intended temporary root')
        for obj in list(bpy.data.objects):
            if obj.name.startswith('InputGuardFixture'):
                bpy.data.objects.remove(obj, do_unlink=True)

    def tearDown(self):
        base = Path(tempfile.gettempdir()).resolve()
        if not self.root.is_relative_to(base):
            raise ValueError('Refuse cleanup outside own temporary root')
        self.temp.cleanup()

    def armature(self, name):
        data = bpy.data.armatures.new(name)
        obj = bpy.data.objects.new(name, data)
        bpy.context.scene.collection.objects.link(obj)
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode='EDIT')
        bone = data.edit_bones.new('Root')
        bone.head, bone.tail = (0, 0, 0), (0, 1, 0)
        bpy.ops.object.mode_set(mode='OBJECT')
        return obj

    def fixture(self, case):
        rig = self.armature('InputGuardFixtureRig')
        model = self.armature('InputGuardFixtureModel')
        constraint = model.pose.bones['Root'].constraints.new('COPY_ROTATION')
        constraint.target, constraint.subtarget = rig, 'Root'
        constraint.owner_space = constraint.target_space = 'WORLD'
        if case != 'unweighted':
            data = bpy.data.meshes.new('InputGuardFixtureMesh')
            data.from_pydata([(0, 0, 0), (.1, 0, 0), (0, 0, .1)], [], [(0, 1, 2)])
            mesh = bpy.data.objects.new('InputGuardFixtureMesh', data)
            bpy.context.scene.collection.objects.link(mesh)
            group = mesh.vertex_groups.new(name='Root')
            group.add([0, 1, 2], 1., 'REPLACE')
            mesh.modifiers.new('Original weighted model', 'ARMATURE').object = model
        if case == 'model-action':
            model.pose.bones['Root'].keyframe_insert(data_path='location', frame=1)
        source = self.root / 'source.blend'
        bpy.ops.wm.save_as_mainfile(filepath=str(source))
        sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
        goals = self.root / 'goals.npz'
        np.savez(goals, frames=np.arange(1, 3), names=np.asarray(['Root']),
                 worlds=np.asarray([[np.eye(4)], [np.asarray(Matrix.Rotation(.1, 4, 'Z'))]]))
        cfg = {'schema': 1, 'source_sha256': sha(source), 'goals_sha256': sha(goals),
               'controller_object': rig.name, 'model_armature': rig.name if case == 'alias' else model.name,
               'mapping': [{'model_bone': 'Root', 'controller_bone': 'Root', 'control': 'Root',
                            'helper': 'Root', 'preserve_local_translation_scale': True}],
               'fk_switches': [], 'fps': 30, 'frames': 2,
               'maximum_position_difference_m': .001, 'maximum_orientation_difference_degrees': 1.}
        plan = self.root / 'plan.json'
        plan.write_text(json.dumps(cfg), 'utf-8')
        output, report = self.root / 'new.blend', self.root / 'report.json'
        arguments = ['--source', str(source), '--plan', str(plan), '--goals', str(goals),
                     '--output', str(output), '--report', str(report)]
        return source, cfg, output, report, arguments

    def reject(self, case, message):
        source, cfg, output, report, arguments = self.fixture(case)
        with self.assertRaisesRegex(ValueError, message):
            main(arguments)
        self.assertFalse(output.exists())
        self.assertFalse(report.exists())
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), cfg['source_sha256'])

    def test_same_controller_and_model_are_refused(self):
        self.reject('alias', 'existing rigs')

    def test_unweighted_model_is_refused(self):
        self.reject('unweighted', 'positive-weight skin')

    def test_original_model_action_is_preserved_by_refusal(self):
        self.reject('model-action', 'controller/model actions')

    def test_real_distinct_weighted_target_can_import(self):
        source, cfg, output, report, arguments = self.fixture('valid')
        main(arguments)
        proof = json.loads(report.read_text('utf-8'))
        self.assertTrue(output.is_file())
        self.assertEqual(proof['frames'], 2)
        self.assertLess(proof['maximum_differences']['orientation_degrees'], .001)
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), cfg['source_sha256'])


if __name__ == '__main__':
    unittest.main()
