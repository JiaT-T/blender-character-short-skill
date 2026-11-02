"""Synthetic public checks. No Blender, character assets or licensed motion inputs."""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

import numpy as np
from PIL import Image

SCRIPTS = Path(__file__).resolve().parents[1] / "blender-character-short/scripts"
sys.path.insert(0, str(SCRIPTS))
import blueprint_fingerprint
import gaze_plan
import hand_retime_plan
import scene_asset_inputs
import source_motion


def write_json(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


def fixture_glb(path, change=None):
    binary = struct.pack("<9f3H", 0, 0, 0, 1, 0, 0, 0, 1, 1, 0, 1, 2)
    binary += b"\0" * (-len(binary) % 4)
    data = {"asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": [0]}],
            "nodes": [{"mesh": 0}], "materials": [{"name": "Fixture matte"}],
            "buffers": [{"byteLength": len(binary)}],
            "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": 36},
                            {"buffer": 0, "byteOffset": 36, "byteLength": 6}],
            "accessors": [{"bufferView": 0, "componentType": 5126, "count": 3, "type": "VEC3",
                           "min": [0, 0, 0], "max": [1, 1, 1]},
                          {"bufferView": 1, "componentType": 5123, "count": 3, "type": "SCALAR"}],
            "meshes": [{"primitives": [{"attributes": {"POSITION": 0}, "indices": 1, "material": 0}]}]}
    if change:
        change(data)
    text = json.dumps(data, separators=(",", ":")).encode("utf-8")
    text += b" " * (-len(text) % 4)
    payload = struct.pack("<4sII", b"glTF", 2, 12 + 8 + len(text) + 8 + len(binary))
    payload += struct.pack("<II", len(text), 0x4E4F534A) + text
    payload += struct.pack("<II", len(binary), 0x004E4942) + binary
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


class SceneIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="skill-v25-input-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.asset = self.root / "fixture.glb"
        digest = fixture_glb(self.asset)
        self.entry = {"name": "Fixture", "file": self.asset.name, "sha256": digest, "height": 0.5,
                      "position": [0, 0, 0], "materials": {"Fixture matte": "matte"},
                      "purpose": "Synthetic identity check", "source": "Generated original test triangle",
                      "license": "Original synthetic test input; no external model"}
        self.story = {"set": {"materials": {"matte": {}}, "imports": [self.entry]}}
        self.path = self.root / "story.json"

    def collect(self):
        write_json(self.path, self.story)
        return scene_asset_inputs.collect_scene_asset_inputs(self.path)

    def test_relative_asset_identity_and_no_import_default(self):
        result = self.collect()
        self.assertEqual(result[0]["path"], str(self.asset.resolve()))
        self.assertEqual(result[0]["rotation"], [0, 0, 0])
        self.story["set"]["imports"] = []
        self.assertEqual(self.collect(), [])

    def test_changed_asset_is_rejected(self):
        fixture_glb(self.asset, lambda data: data.update(extras={"changed": True}))
        with self.assertRaisesRegex(ValueError, "hash differs"):
            self.collect()

    def test_animation_rig_texture_and_external_buffer_are_rejected(self):
        variants = {"animation": lambda x: x.update(animations=[{}]),
                    "rig": lambda x: x.update(skins=[{}]),
                    "texture": lambda x: x.update(textures=[{}]),
                    "external-buffer": lambda x: x["buffers"][0].update(uri="external.bin")}
        for label, change in variants.items():
            with self.subTest(label=label):
                fixture_glb(self.asset, change)
                with self.assertRaises(ValueError):
                    scene_asset_inputs.inspect_static_glb(self.asset)

    def test_invalid_palette_name_size_and_position_are_rejected(self):
        variants = {"palette": {"materials": {"Fixture matte": "missing"}},
                    "size": {"height": 0}, "position": {"position": [0, float("nan"), 0]},
                    "namespace": {"name": "x" * 33}, "field": {"unknown": True}}
        for label, values in variants.items():
            with self.subTest(label=label):
                self.story["set"]["imports"] = [dict(self.entry, **values)]
                with self.assertRaises(ValueError):
                    self.collect()
        self.story["set"]["imports"] = [self.entry, copy.deepcopy(self.entry)]
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            self.collect()

    def test_blueprint_identity_changes_with_referenced_image(self):
        image = self.root / "image.bin"
        image.write_bytes(b"original synthetic bytes")
        blueprint = self.root / "blueprint.json"
        write_json(blueprint, {"images": {"fixture": {"file": image.name}}})
        character = self.root / "character.json"
        write_json(character, {"materials": {"dorm_blueprint": str(blueprint)}})
        before = blueprint_fingerprint.collect_blueprint_inputs(character)
        image.write_bytes(b"changed synthetic bytes")
        after = blueprint_fingerprint.collect_blueprint_inputs(character)
        self.assertEqual(before["blueprint"], after["blueprint"])
        self.assertNotEqual(before["images"]["fixture"]["sha256"], after["images"]["fixture"]["sha256"])
        image.unlink()
        with self.assertRaises(FileNotFoundError):
            blueprint_fingerprint.collect_blueprint_inputs(character)


class MotionAndPlanTests(unittest.TestCase):
    def test_component_delta_decode_and_hierarchy(self):
        document = {"version": 1, "packing": {"times": [0, 1], "valueDigits": 2},
                    "tracks": [{"node": 1, "property": "position", "deltas": [0, 100, 0, 200, 0, 300]}]}
        tracks = source_motion.decode_clip(document)
        np.testing.assert_array_equal(tracks[0]["values"], [[0, 0, 0], [1, 2, 3]])
        skeleton = {"nodes": [{"translation": [10, 0, 0], "children": [1]}, {}]}
        worlds = source_motion.node_worlds(skeleton, tracks, time=1)
        np.testing.assert_array_equal(worlds[1, :3, 3], [11, 2, 3])

    def test_quaternion_decode_and_halfway_rotation(self):
        packing = {"times": [0, 1], "rotationBits": 16}
        raw = {"node": 0, "property": "quaternion", "deltas": [0, 0, 0, 0, 0, 32767],
               "dropped": [{"at": 0, "component": 3}]}
        times, values = source_motion.decode_track(raw, packing)
        track = {"times": times, "values": values, "property": "quaternion"}
        matrix = source_motion.quaternion_matrix(source_motion.sample_track(track, 0.5))
        np.testing.assert_allclose(matrix @ [1, 0, 0], [np.sqrt(0.5), np.sqrt(0.5), 0], atol=1e-6)

    def test_invalid_motion_and_cyclic_hierarchy_are_rejected(self):
        with self.assertRaises(ValueError):
            source_motion.decode_track({"property": "position", "value": [0, float("nan"), 0]}, None)
        with self.assertRaisesRegex(ValueError, "cycle"):
            source_motion.node_worlds({"nodes": [{"children": [1]}, {"children": [0]}]})
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            source_motion.decode_clip({"version": 1, "tracks": [{"node": 0, "property": "position", "value": [0, 0, 0]}] * 2})

    def test_gaze_return_endpoints_and_overlap_guards(self):
        plan = {"ranges": [{"start": 1, "end": 4, "object": "Target"}],
                "returns": [{"start": 5, "end": 8, "easing": "smoothstep"}]}
        targets, returns = gaze_plan.parse_plan(plan, 1, 12, {"Target"})
        self.assertEqual(set(targets), {1, 2, 3, 4})
        weights = [gaze_plan.return_weight(frame, returns[0]) for frame in range(4, 9)]
        self.assertEqual((weights[0], weights[-1]), (0, 1))
        self.assertEqual(weights, sorted(weights))
        with self.assertRaises(ValueError):
            gaze_plan.parse_plan(plan, 1, 12, {"Wrong target"})
        plan["ranges"].append({"start": 7, "end": 9, "object": "Target"})
        with self.assertRaisesRegex(ValueError, "overlaps"):
            gaze_plan.parse_plan(plan, 1, 12, {"Target"})

    def test_retime_protects_contact_and_preserves_endpoints(self):
        plan = {"side": "left", "source_frames": [11, 15], "output_frames": [11, 19], "timing": "smoothstep"}
        source, output = hand_retime_plan.validate_plan(plan, 1, 24, contact_end=10)
        times = [hand_retime_plan.source_time(f, source, output, plan["timing"]) for f in range(11, 20)]
        self.assertEqual((times[0], times[-1]), (11, 15))
        self.assertEqual(times, sorted(times))
        with self.assertRaisesRegex(ValueError, "after"):
            hand_retime_plan.validate_plan(plan, 1, 24, contact_end=11)


class PostResumeTests(unittest.TestCase):
    def test_synthetic_budget_resume_corruption_and_changed_config(self):
        with tempfile.TemporaryDirectory(prefix="skill-v25-post-") as folder:
            root = Path(folder)
            raw = root / "raw"
            raw.mkdir()
            write_json(raw / "render-job.json", {"kind": "original synthetic test"})
            for frame in range(1, 4):
                rgba = np.ones((6, 8, 4), dtype=np.float32)
                rgba[..., :3] = [frame / 10, 0.25, 0.5]
                np.savez(raw / f"frame_{frame:04d}.npz", rgba=rgba, weight=np.zeros((6, 8, 1), np.float32))
            config = root / "post.json"
            profile = {"target_precision": "float16", "threshold": [1, 1], "level_sizes": [4],
                       "level_kernels": ["identity"], "kernels": {"identity": [{"offset_normalized_uv": 0, "weight": 1}]},
                       "coefficients": [1], "blend": [1, 0], "curve": [1, 1], "use_lut": False}
            write_json(config, profile)
            lut = root / "synthetic-lut.png"
            Image.fromarray(np.zeros((2, 4, 3), dtype=np.uint8)).save(lut)

            def run(output, budget=None, expected=0):
                command = [sys.executable, "-B", str(SCRIPTS / "post_sequence.py"), "--raw", str(raw),
                           "--output", str(output), "--config", str(config), "--lut", str(lut), "--end", "3"]
                if budget is not None:
                    command.extend(["--max-new-seconds", str(budget)])
                env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1")
                proc = subprocess.run(command, env=env, capture_output=True, timeout=30)
                self.assertEqual(proc.returncode, expected, proc.stderr.decode("utf-8", errors="replace")[-1000:])
                return json.loads((output / "post-progress.json").read_text("utf-8")) if expected == 0 else None

            full, bounded = root / "full", root / "bounded"
            completed = run(full)
            states = [run(bounded, 1e-9) for _ in range(3)]
            self.assertEqual([s["status"] for s in states], ["budget-paused", "budget-paused", "complete"])
            self.assertEqual(len({s["job_sha256"] for s in states}), 1)
            for frame in range(1, 4):
                name = f"frame_{frame:04d}.png"
                self.assertEqual((full / name).read_bytes(), (bounded / name).read_bytes())
            protected = (bounded / "frame_0001.png").read_bytes()
            (bounded / "frame_0002.png").write_bytes(b"corrupt")
            recovered = run(bounded)
            self.assertEqual(recovered["status"], "complete")
            self.assertEqual((bounded / "frame_0001.png").read_bytes(), protected)
            self.assertEqual((bounded / "frame_0002.png").read_bytes(), (full / "frame_0002.png").read_bytes())
            self.assertEqual(completed["status"], "complete")
            invalid = root / "invalid"
            run(invalid, "nan", expected=2)
            self.assertFalse(invalid.exists())
            before = (bounded / "frame_0001.png").read_bytes()
            profile["curve"] = [2, 1]
            write_json(config, profile)
            run(bounded, expected=1)
            self.assertEqual((bounded / "frame_0001.png").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
