"""Host/mock tests; an optional real Blender fixture never opens/saves/renders.

Host: python -B validation/test_saved_shot_contract.py
Blender (caller launches separately):
  blender --background --factory-startup --python validation/test_saved_shot_contract.py -- --blender-fixture
"""
import copy
import json
import math
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender-character-short/scripts"))
from saved_shot_contract import validate_scene_shots


def matrix(x=0.0, rotation=False):
    return [[0.0 if rotation else 1.0, -1.0 if rotation else 0.0, 0.0, x],
            [1.0 if rotation else 0.0, 0.0 if rotation else 1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]


def plan():
    shot = {"id": "a", "beat": "discover", "camera": "wide", "framing": "full body",
            "start": 25, "end": 30, "action_start": "idle", "action_end": "idle",
            "spatial_start": {"hero": "left"}, "spatial_end": {"hero": "left"},
            "props_start": {}, "props_end": {}, "asset_ids": ["hero"]}
    second = copy.deepcopy(shot)
    second.update(id="b", camera="close", start=31, end=36)
    return {"schema": 1, "fps": 24, "fps_base": 1.0, "start": 25, "end": 36,
            "assets": {"hero": "original actor", "prop": "held prop"}, "shots": [shot, second]}


class Object:
    def __init__(self, name, kind="EMPTY", evaluated=None):
        self.name, self.type = name, kind
        self.matrix_world = matrix(999.0)  # Deliberately different from evaluated pose.
        self._evaluated = evaluated or (lambda: matrix())
        self.graphs = []

    def evaluated_get(self, graph):
        self.graphs.append(graph)
        return SimpleNamespace(matrix_world=self._evaluated())


class Graph:
    def __init__(self, scene):
        self.updates = 0
        self.scene_eval = SimpleNamespace(original=scene)

    def update(self):
        self.updates += 1


class Scene:
    def __init__(self):
        self.frame_start, self.frame_end = -24, 48
        self.frame_current, self.frame_subframe = 28, 0.375
        self.render = SimpleNamespace(fps=24, fps_base=1.0)
        self.objects = {n: Object(n, "CAMERA") for n in ("wide", "close", "saved")}
        self.camera = self.objects["saved"]
        self.timeline_markers = [self.marker(25, "wide"), self.marker(31, "close")]
        self.frame_calls = []
        # A preview range must never silently become the requested display range.
        self.use_preview_range, self.frame_preview_start, self.frame_preview_end = True, 1, 2

    def marker(self, frame, camera=None):
        return SimpleNamespace(frame=frame, camera=self.objects[camera] if camera else None,
                               name="marker-" + str(frame))

    def frame_set(self, frame, subframe=0.0):
        self.frame_current, self.frame_subframe = frame, subframe
        self.frame_calls.append((frame, subframe))
        cuts = [m for m in self.timeline_markers if m.camera and m.frame <= frame]
        if cuts:
            self.camera = max(cuts, key=lambda m: m.frame).camera


class SavedShotTests(unittest.TestCase):
    def setUp(self):
        self.scene, self.plan = Scene(), plan()
        self.graph = Graph(self.scene)

    def run_contract(self, **kwargs):
        return validate_scene_shots(self.scene, self.plan, **kwargs)

    def test_valid_preroll_exact_display_and_no_rig_count_assumption(self):
        for i in range(3):
            self.scene.objects["arm-" + str(i)] = Object("arm-" + str(i), "ARMATURE")
        original = copy.deepcopy(self.plan)
        result = self.run_contract(display_range=(25, 36))
        self.assertTrue(result["valid_scene_binding"])
        self.assertEqual(result["scene_range"], [-24, 48])
        self.assertEqual(result["display_range"], [25, 36])
        self.assertEqual(result["declaration"]["expected_cut_frames"], [31])
        self.assertFalse(result["visual_acceptance"])
        self.assertEqual(result["movement_rejection_thresholds"], None)
        self.assertEqual(len(result["plan_sha256"]), 64)
        self.assertEqual(self.plan, original)
        self.assertEqual(self.scene.frame_calls, [])

    def test_existing_schema_and_gap_validation_reused(self):
        for key, value in (("schema", 2), ("schema", True)):
            p = plan(); p[key] = value
            with self.assertRaises(ValueError): validate_scene_shots(self.scene, p)
        self.plan["shots"][1]["start"] = 32
        with self.assertRaisesRegex(ValueError, "without gaps"):
            self.run_contract()

    def test_display_and_scene_range_mismatches(self):
        for display in ((24, 36), (25, 37), (True, 36), [25], "25,36"):
            with self.subTest(display=display), self.assertRaisesRegex(ValueError, "specified inclusive display"):
                self.run_contract(display_range=display)
        for start, end in ((26, 48), (-24, 35)):
            self.scene.frame_start, self.scene.frame_end = start, end
            with self.assertRaisesRegex(ValueError, "complete display"):
                self.run_contract()

    def test_fps_and_base_checked_separately(self):
        self.scene.render.fps, self.scene.render.fps_base = 48, 2.0
        with self.assertRaisesRegex(ValueError, "fps differs"):
            self.run_contract()  # Same effective fps is insufficient.
        self.scene.render.fps = 24
        with self.assertRaisesRegex(ValueError, "fps_base differs"):
            self.run_contract()
        for value in (float("nan"), float("inf"), True):
            self.scene.render.fps_base = value
            with self.assertRaises(ValueError): self.run_contract()

    def test_fractional_fps_storage_tolerance_explicit(self):
        self.plan["fps_base"] = 1.001
        self.scene.render.fps_base = 1.0010000467300415
        result = self.run_contract()
        self.assertEqual(result["fps_base_abs_tolerance"], 1e-7)
        self.scene.render.fps_base = 1.001001
        with self.assertRaisesRegex(ValueError, "fps_base differs"):
            self.run_contract()

    def test_exact_scene_camera_lookup_and_type(self):
        self.plan["shots"][0]["camera"] = "Wide"
        with self.assertRaisesRegex(ValueError, "Exact scene object missing"):
            self.run_contract()
        self.plan = plan(); self.scene.objects["wide"].type = "EMPTY"
        with self.assertRaisesRegex(ValueError, "not a CAMERA"):
            self.run_contract()

    def test_missing_or_wrong_boundary_markers(self):
        for frame in (25, 31):
            self.scene = Scene()
            self.scene.timeline_markers = [m for m in self.scene.timeline_markers if m.frame != frame]
            with self.assertRaisesRegex(ValueError, "exact camera marker"):
                self.run_contract()
        self.scene = Scene(); self.scene.timeline_markers[1].camera = self.scene.objects["wide"]
        with self.assertRaisesRegex(ValueError, "exact camera marker"):
            self.run_contract()

    def test_same_camera_shots_still_require_boundary_marker(self):
        self.plan["shots"][1]["camera"] = "wide"
        self.scene.timeline_markers = [self.scene.marker(25, "wide")]
        with self.assertRaisesRegex(ValueError, "exact camera marker"):
            self.run_contract()
        self.scene.timeline_markers.append(self.scene.marker(31, "wide"))
        self.assertTrue(self.run_contract()["valid_scene_binding"])

    def test_duplicate_marker_and_switch_away_then_back_rejected(self):
        self.scene.timeline_markers.append(self.scene.marker(31, "close"))
        with self.assertRaisesRegex(ValueError, "Ambiguous multiple"):
            self.run_contract()
        self.scene = Scene()
        self.scene.timeline_markers += [self.scene.marker(27, "close"), self.scene.marker(28, "wide")]
        with self.assertRaisesRegex(ValueError, "Unplanned camera switch"):
            self.run_contract()

    def test_non_camera_preroll_postroll_and_redundant_markers(self):
        self.scene.timeline_markers += [self.scene.marker(26), self.scene.marker(-1, "close"),
                                        self.scene.marker(40, "wide"), self.scene.marker(29, "wide")]
        result = self.run_contract()
        self.assertEqual(result["camera_markers_outside_display_ignored"], 2)
        self.assertEqual(result["redundant_same_camera_markers"][0]["frame"], 29)

    def test_foreign_marker_camera_and_missing_active_camera_rejected(self):
        self.scene.timeline_markers[0].camera = Object("wide", "CAMERA")
        with self.assertRaisesRegex(ValueError, "outside this scene"):
            self.run_contract()
        self.scene = Scene(); self.scene.camera = None
        with self.assertRaisesRegex(ValueError, "Saved active camera"):
            self.run_contract()

    def test_bindings_validation_and_conflicting_sources(self):
        for bindings in (None, {}, {"missing-id": "wide"}, {"hero": ""}, [], {"hero": "missing-object"}):
            with self.subTest(bindings=bindings):
                if bindings is None or bindings == {}:
                    self.assertEqual(self.run_contract(object_bindings=bindings)["object_matrix_samples"], 0)
                else:
                    with self.assertRaises(ValueError): self.run_contract(object_bindings=bindings)
        self.plan["object_bindings"] = {"hero": "wide"}
        with self.assertRaisesRegex(ValueError, "conflict"):
            self.run_contract(object_bindings={"hero": "close"})

    def test_evaluated_movement_samples_and_state_restoration(self):
        self.scene.objects["actor"] = Object("actor", evaluated=lambda: matrix(self.scene.frame_current * 0.25))
        self.plan["object_bindings"] = {"hero": "actor"}
        original = (self.scene.frame_current, self.scene.frame_subframe, self.scene.camera)
        result = self.run_contract(depsgraph_getter=lambda: self.graph)
        movement = result["observed_cut_movements"][0]
        self.assertEqual(movement["frames"], [30, 31])
        self.assertEqual(movement["world_before"][0][3], 7.5)
        self.assertEqual(movement["world_after"][0][3], 7.75)
        self.assertEqual(movement["translation_distance_scene_units"], 0.25)
        self.assertEqual(self.graph.updates, 2)
        self.assertEqual(self.scene.objects["actor"].graphs, [self.graph, self.graph])
        self.assertEqual((self.scene.frame_current, self.scene.frame_subframe, self.scene.camera), original)
        self.assertEqual(self.scene.frame_calls, [(30, 0.0), (31, 0.0), (28, 0.375)])
        json.dumps(result, allow_nan=False)

    def test_rotation_and_no_motion_are_observations_without_rejection(self):
        self.scene.objects["actor"] = Object("actor", evaluated=lambda: matrix(rotation=self.scene.frame_current >= 31))
        self.scene.objects["prop"] = Object("prop")
        result = self.run_contract(object_bindings={"hero": "actor", "prop": "prop"},
                                   depsgraph_getter=lambda: self.graph)
        hero, prop = result["observed_cut_movements"]
        self.assertEqual(hero["translation_distance_scene_units"], 0.0)
        self.assertEqual(hero["max_matrix_component_change"], 1.0)
        self.assertEqual(prop["max_matrix_component_change"], 0.0)
        self.assertTrue(result["valid_scene_binding"])

    def test_sampling_exception_and_nonfinite_matrix_restore_state(self):
        def fail():
            if self.scene.frame_current == 31:
                raise RuntimeError("synthetic evaluated constraint failure")
            return matrix()
        self.scene.objects["actor"] = Object("actor", evaluated=fail)
        original = (self.scene.frame_current, self.scene.frame_subframe, self.scene.camera)
        with self.assertRaisesRegex(RuntimeError, "synthetic evaluated"):
            self.run_contract(object_bindings={"hero": "actor"}, depsgraph_getter=lambda: self.graph)
        self.assertEqual((self.scene.frame_current, self.scene.frame_subframe, self.scene.camera), original)
        self.scene.objects["actor"]._evaluated = lambda: matrix(float("nan"))
        with self.assertRaisesRegex(ValueError, "finite 4x4"):
            self.run_contract(object_bindings={"hero": "actor"}, depsgraph_getter=lambda: self.graph)
        self.assertEqual((self.scene.frame_current, self.scene.frame_subframe, self.scene.camera), original)

    def test_bad_matrix_shape_and_movement_overflow_restore_state(self):
        self.scene.objects["actor"] = Object("actor", evaluated=lambda: [[1.0]])
        original = (self.scene.frame_current, self.scene.frame_subframe, self.scene.camera)
        with self.assertRaisesRegex(ValueError, "finite 4x4"):
            self.run_contract(object_bindings={"hero": "actor"}, depsgraph_getter=lambda: self.graph)
        self.assertEqual((self.scene.frame_current, self.scene.frame_subframe, self.scene.camera), original)
        self.scene.objects["actor"]._evaluated = lambda: matrix(-1e308 if self.scene.frame_current == 30 else 1e308)
        with self.assertRaisesRegex(ValueError, "movement must be finite"):
            self.run_contract(object_bindings={"hero": "actor"}, depsgraph_getter=lambda: self.graph)
        self.assertEqual((self.scene.frame_current, self.scene.frame_subframe, self.scene.camera), original)

    def test_wrong_scene_dependency_graph_rejected_and_state_restored(self):
        self.scene.objects["actor"] = Object("actor")
        original = (self.scene.frame_current, self.scene.frame_subframe, self.scene.camera)
        foreign_graph = Graph(Scene())
        with self.assertRaisesRegex(ValueError, "must belong to the validated scene"):
            self.run_contract(object_bindings={"hero": "actor"}, depsgraph_getter=lambda: foreign_graph)
        self.assertEqual(foreign_graph.updates, 0)
        self.assertEqual((self.scene.frame_current, self.scene.frame_subframe, self.scene.camera), original)

    def test_frame_set_failure_also_restores_camera_last(self):
        self.scene.objects["actor"] = Object("actor")
        original = (self.scene.frame_current, self.scene.frame_subframe, self.scene.camera)
        frame_set = self.scene.frame_set
        def fail_at_sample(frame, subframe=0.0):
            frame_set(frame, subframe)
            if frame == 31:
                raise RuntimeError("synthetic frame evaluation failure")
        self.scene.frame_set = fail_at_sample
        with self.assertRaisesRegex(RuntimeError, "frame evaluation failure"):
            self.run_contract(object_bindings={"hero": "actor"}, depsgraph_getter=lambda: self.graph)
        self.assertEqual((self.scene.frame_current, self.scene.frame_subframe, self.scene.camera), original)

    def test_explicit_sample_budget_fails_before_scene_evaluation(self):
        base = copy.deepcopy(self.plan["shots"][0])
        self.plan["start"], self.plan["end"] = 1, 1000
        self.plan["shots"] = [dict(base, id="shot-" + str(f), start=f, end=f) for f in range(1, 1001)]
        self.scene.frame_start, self.scene.frame_end = 1, 1000
        self.scene.timeline_markers = [self.scene.marker(f, "wide") for f in range(1, 1001)]
        self.plan["assets"] = {"asset-" + str(i): "supplied object" for i in range(101)}
        self.plan["object_bindings"] = {k: "wide" for k in self.plan["assets"]}
        for shot in self.plan["shots"]:
            shot["asset_ids"] = []
        with self.assertRaisesRegex(ValueError, "100000 matrix sample budget"):
            self.run_contract()
        self.assertEqual(self.scene.frame_calls, [])

    def test_dissolve_is_bound_but_not_reported_as_a_hard_cut(self):
        self.plan["shots"][1]["transition"] = "dissolve"
        self.scene.objects["actor"] = Object("actor")
        result = self.run_contract(object_bindings={"hero": "actor"})
        self.assertEqual(result["observed_cut_movements"], [])
        self.assertEqual(result["object_matrix_samples"], 0)


def run_blender_fixture():
    """Caller-executed real depsgraph fixture; removes only its own datablocks."""
    import bpy
    scene = bpy.data.scenes.new("SavedShotContractFixture")
    created, data = [], []
    try:
        scene.frame_start, scene.frame_end = -24, 48
        scene.render.fps, scene.render.fps_base = 24, 1.0
        cameras = {}
        for name in ("wide", "close", "saved"):
            block = bpy.data.cameras.new("Fixture-" + name); data.append(block)
            obj = bpy.data.objects.new(name, block); created.append(obj); scene.collection.objects.link(obj)
            cameras[name] = obj
        # Bind exact generated names rather than assuming a factory namespace.
        p = plan()
        for shot in p["shots"]:
            shot["camera"] = cameras[shot["camera"]].name
            marker = scene.timeline_markers.new(shot["id"], frame=shot["start"])
            marker.camera = cameras["wide" if shot["id"] == "a" else "close"]
        parent = bpy.data.objects.new("Fixture-parent", None); created.append(parent); scene.collection.objects.link(parent)
        actor = bpy.data.objects.new("Fixture-actor", None); created.append(actor); scene.collection.objects.link(actor)
        actor.parent = parent; actor.location.x = 1.0
        for frame, x in ((30, 2.0), (31, 5.0)):
            parent.location.x = x; parent.keyframe_insert(data_path="location", frame=frame)
        for i in range(3):
            block = bpy.data.armatures.new("Fixture-arm-" + str(i)); data.append(block)
            obj = bpy.data.objects.new(block.name, block); created.append(obj); scene.collection.objects.link(obj)
        scene.frame_set(28, subframe=0.375); scene.camera = cameras["saved"]
        original = (scene.frame_current, scene.frame_subframe, scene.camera)
        report = validate_scene_shots(scene, p, display_range=(25, 36),
                                     object_bindings={"hero": actor.name},
                                     depsgraph_getter=lambda: scene.view_layers[0].depsgraph)
        row = report["observed_cut_movements"][0]
        assert math.isclose(row["world_before"][0][3], 3.0, abs_tol=1e-6), row
        assert math.isclose(row["world_after"][0][3], 6.0, abs_tol=1e-6), row
        assert math.isclose(row["translation_distance_scene_units"], 3.0, abs_tol=1e-6), row
        assert (scene.frame_current, scene.frame_subframe, scene.camera) == original
        print("SAVED_SHOT_BLENDER_FIXTURE", json.dumps({"passed": True, "object_matrix_samples": report["object_matrix_samples"],
                                                       "three_armatures": True, "rendered": False, "saved": False}), flush=True)
    finally:
        for obj in reversed(created):
            bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.scenes.remove(scene)
        for block in data:
            if block.users == 0:
                if isinstance(block, bpy.types.Camera): bpy.data.cameras.remove(block)
                else: bpy.data.armatures.remove(block)


if __name__ == "__main__":
    if "--blender-fixture" in sys.argv:
        run_blender_fixture()
    else:
        unittest.main()
