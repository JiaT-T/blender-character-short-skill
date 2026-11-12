import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
SCRIPTS = Path(__file__).resolve().parents[1] / "blender-character-short/scripts"
sys.path.insert(0, str(SCRIPTS))
from scene_lighting_candidates import generate
from refine_scene import validate_config

class LightingCandidatesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source.blend"
        self.source.write_bytes(b"synthetic fixture, not a Blender scene")
        self.cfg = {"schema": 1, "source": {"path": "source.blend", "sha256": hashlib.sha256(self.source.read_bytes()).hexdigest()}, "objects": ["Wall", "Floor"], "collection": "StageOnly", "protected_objects": ["Character"], "target": {"center": [0, 0, 1], "dimensions": [2, 3, 2]}}
    def test_candidates_compatible_and_no_mutation(self):
        before = copy.deepcopy(self.cfg)
        result = generate(self.cfg, self.root)
        self.assertEqual(before, self.cfg)
        self.assertTrue(result["review_only"])
        self.assertFalse(result["applied"])
        self.assertEqual(len(result["candidates"]), 3)
        self.assertEqual(hashlib.sha256(self.source.read_bytes()).hexdigest(), before["source"]["sha256"])
        for candidate in result["candidates"]:
            self.assertFalse(candidate["reviewed"])
            validate_config(candidate["scene_patch"])
            self.assertEqual(candidate["scene_patch"]["lights"], [])
            self.assertEqual(candidate["scene_patch"]["materials"], [])
        with self.assertRaises(ValueError): validate_config(result)
    def test_source_hash(self):
        self.source.write_bytes(b"changed")
        with self.assertRaises(ValueError): generate(self.cfg, self.root)
    def test_scope_excludes_character(self):
        self.cfg["objects"].append("Character")
        with self.assertRaises(ValueError): generate(self.cfg, self.root)
    def test_explicit_scope(self):
        for key in ("objects", "protected_objects"):
            cfg = copy.deepcopy(self.cfg); cfg[key] = []
            with self.assertRaises(ValueError): generate(cfg, self.root)
    def test_finite(self):
        for bad in (float("nan"), float("inf"), True, -1):
            cfg=copy.deepcopy(self.cfg); cfg["target"]["dimensions"][0]=bad
            with self.assertRaises(ValueError): generate(cfg, self.root)
    def test_zero_direction(self):
        self.cfg["forward"]=[0,0,0]
        with self.assertRaises(ValueError): generate(self.cfg, self.root)
        self.cfg["forward"]=[0,0,1]
        with self.assertRaises(ValueError): generate(self.cfg, self.root)
    def test_scale(self):
        a=generate(self.cfg,self.root)["candidates"][0]["scene_patch"]["add_lights"][0]
        self.cfg["target"]["dimensions"]=[4,6,4]
        b=generate(self.cfg,self.root)["candidates"][0]["scene_patch"]["add_lights"][0]
        self.assertAlmostEqual(b["energy"],4*a["energy"])
        self.assertAlmostEqual(b["size"],2*a["size"])
    def test_orientation(self):
        a=generate(self.cfg,self.root)["candidates"][0]["scene_patch"]["add_lights"][0]
        self.cfg["forward"]=[0,1,0]
        b=generate(self.cfg,self.root)["candidates"][0]["scene_patch"]["add_lights"][0]
        self.assertAlmostEqual(a["location"][0],-b["location"][0])
        self.assertAlmostEqual(a["location"][1],-b["location"][1])
    def test_unknown_intent(self):
        self.cfg["material_intent"]="arbitrary"
        with self.assertRaises(ValueError): generate(self.cfg,self.root)
    def test_extremes_compatible(self):
        self.cfg["target"]["dimensions"]=[50,50,50];self.cfg["base_energy"]=400
        for row in generate(self.cfg,self.root)["candidates"]: validate_config(row["scene_patch"])
    def test_default_energy_scale_boundaries(self):
        for dimension in (.01,50):
            cfg=copy.deepcopy(self.cfg);cfg["target"]["dimensions"]=[dimension]*3
            for row in generate(cfg,self.root)["candidates"]:
                validate_config(row["scene_patch"])
                for light in row["scene_patch"]["add_lights"]:
                    self.assertLessEqual(light["energy"],1e6)
                    self.assertGreaterEqual(light["size"],.000001)
    def test_idempotent(self):
        self.assertEqual(generate(self.cfg,self.root),generate(self.cfg,self.root))
    def test_cli_no_overwrite(self):
        req=self.root/"request.json"; report=self.root/"report.json"
        req.write_text(json.dumps(self.cfg),encoding="utf-8")
        cmd=[sys.executable,"-B",str(SCRIPTS/"scene_lighting_candidates.py"),"--request",str(req),"--report",str(report)]
        r=subprocess.run(cmd,capture_output=True)
        self.assertEqual(r.returncode,0,r.stderr)
        before=report.read_bytes()
        self.assertNotEqual(subprocess.run(cmd,capture_output=True).returncode,0)
        self.assertEqual(report.read_bytes(),before)

if __name__ == "__main__": unittest.main()
