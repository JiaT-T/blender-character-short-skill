import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender-character-short/scripts"))
from production_workflow import evaluate

class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        for name in ("character.pmx", "scene.blend", "evidence.json"):
            (self.base/name).write_text("fixture", encoding="utf-8")
        self.brief = {"schema":1, "inputs":{"character_mmd":"character.pmx", "scene":"scene.blend"}, "prompt":"Who finds a ribbon in a garden"}
    def test_defaults_and_no_license_gate(self):
        r=evaluate(self.brief,self.base)
        self.assertEqual(r["status"],"ready_for_agent")
        self.assertEqual(r["new_video_settings"],{"width":1280,"height":720,"fps":24})
        self.assertEqual(r["original_prompt"],self.brief["prompt"])
    def test_required(self):
        self.brief["inputs"]={};self.brief["prompt"]=""
        self.assertEqual(len(evaluate(self.brief,self.base)["missing"]),3)
    def test_explicit_exception(self):
        self.brief["inputs"]={};self.brief["user_exceptions"]={"character_mmd":"Find a model", "scene":"Find a scene"}
        self.assertEqual(evaluate(self.brief,self.base)["missing"],[])
    def test_blank_exception(self):
        self.brief["user_exceptions"]={"scene":" "}
        with self.assertRaises(ValueError):evaluate(self.brief,self.base)
    def test_saved_mmd_declaration(self):
        self.brief["inputs"]["character_mmd"]="scene.blend"
        self.assertTrue(evaluate(self.brief,self.base)["missing"])
        self.brief["inputs"]["saved_mmd_skeleton"]=True
        self.assertFalse(evaluate(self.brief,self.base)["missing"])
    def test_fallback_is_not_blocker_or_application(self):
        self.brief["missing_textures"]=[{"material":"coat","kind":"normal"},{"material":"face","kind":"base_color"}]
        r=evaluate(self.brief,self.base)
        self.assertFalse(r["missing"])
        self.assertFalse(r["fallback_plan"][0]["applied"])
        self.assertIn("Cannot reliably",r["fallback_plan"][1]["limitation"])
    def test_login_pause(self):
        self.brief["motion_search"]={"status":"login_required"}
        r=evaluate(self.brief,self.base)
        self.assertEqual(r["status"],"awaiting_login_authorization")
        self.assertEqual(r["independent_work_allowed"],["static_look_on_copies"])
    def test_conflict(self):
        self.brief["intent"]={"conflicts":["Conflicting ending"]}
        self.assertEqual(evaluate(self.brief,self.base)["status"],"needs_clarification")
    def test_evidence_required(self):
        self.brief["completed"]=["intake"]
        with self.assertRaises(ValueError):evaluate(self.brief,self.base)
        self.brief["evidence"]={"intake":["evidence.json"]}
        self.assertEqual(evaluate(self.brief,self.base)["next_stage"],"intent")
    def test_order(self):
        self.brief["completed"]=["storyboard"];self.brief["evidence"]={"storyboard":["evidence.json"]}
        with self.assertRaises(ValueError):evaluate(self.brief,self.base)
    def test_pending_search_no_completion(self):
        self.brief["completed"]=["intake","intent","look_and_motion"]
        self.brief["evidence"]={s:["evidence.json"] for s in self.brief["completed"]}
        with self.assertRaises(ValueError):evaluate(self.brief,self.base)
    def test_cli_route_without_runtime_and_no_overwrite(self):
        (self.base/"brief.json").write_text(json.dumps(self.brief),encoding="utf-8")
        (self.base/"project.json").write_text(json.dumps({"schema":1,"id":"workflow","workflow_brief":"brief.json","workflow_report":"report.json"}),encoding="utf-8")
        entry=Path(__file__).resolve().parents[1]/"blender-character-short/scripts/short_project.py"
        cmd=[sys.executable,"-B",str(entry),"workflow","--project",str(self.base/"project.json")]
        r=subprocess.run(cmd,capture_output=True)
        self.assertEqual(r.returncode,0,r.stderr)
        original=(self.base/"report.json").read_bytes()
        self.assertNotEqual(subprocess.run(cmd,capture_output=True).returncode,0)
        self.assertEqual(original,(self.base/"report.json").read_bytes())

if __name__ == "__main__":unittest.main()
