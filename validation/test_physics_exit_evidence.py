"""CPU fault injection: a written cache report cannot overrule a failed exit.

Popen is replaced locally. Synthetic files are not Blender projects or caches.
"""
from pathlib import Path
from hashlib import sha256
from unittest.mock import patch
import json
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'blender-character-short/scripts'))
import short_project
digest=lambda p:sha256(Path(p).read_bytes()).hexdigest()


class PhysicsExitEvidence(unittest.TestCase):
    def fixture(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name).resolve()
        source = root / "source.blend"
        source.write_bytes(b"CPU-only synthetic source, not a Blender file")
        source_hash = digest(source)
        (root / "plan.json").write_text(json.dumps({"source_sha256": source_hash}), encoding="utf-8")
        project = {
            "runtime": {"blender": sys.executable, "blender_version": [4, 5, 15], "addons": {}, "threads": 1},
            "reports": "native-receipts", "execution_lock": "cpu-only-unused.lock",
            "physics": {"source": {"path": "source.blend", "sha256": source_hash}, "plan": "plan.json", "output": "new.blend", "report": "bake.json", "verify_report": "verify.json"},
        }
        return root, project, source_hash

    def process_factory(self, calls, codes):
        class SyntheticCompletedProcess:
            pid = -1  # Explicit sentinel: no OS process was created.

            def __init__(self, command, **unused):
                mode = command[command.index("--mode") + 1]
                source = Path(command[command.index("--source") + 1])
                report = Path(command[command.index("--report") + 1])
                calls.append(mode)
                if mode == "bake":
                    output = Path(command[command.index("--output") + 1])
                    output.write_bytes(b"CPU-only synthetic cache, not a Blender cache")
                    data = {"cache_baked": True, "output_sha256": digest(output), "source_sha256": digest(source)}
                elif mode == "verify":
                    data = {"cache_baked": True, "fresh_process_reopen_verified": True, "source_sha256": digest(source)}
                else:
                    raise AssertionError(mode)
                report.write_text(json.dumps(data), encoding="utf-8")
                self.code = codes[mode]

            def wait(self, timeout):
                return self.code

        return SyntheticCompletedProcess

    def jobs(self, root):
        return {r["stage"]: r for p in (root / "native-receipts").glob("*.job.json") for r in [json.loads(p.read_text("utf-8"))]}

    def test_bake_report_written_but_failed_exit_stops_before_fresh_reader(self):
        root, project, source_hash = self.fixture()
        calls = []
        with patch.object(short_project.subprocess, "Popen", self.process_factory(calls, {"bake": 37, "verify": 0})):
            with self.assertRaisesRegex(RuntimeError, r"physics-bake failed \(37\)"):
                short_project.physics(project, root)
        self.assertEqual(calls, ["bake"])
        self.assertTrue(json.loads((root / "bake.json").read_text())["cache_baked"])
        self.assertFalse((root / "verify.json").exists())
        self.assertEqual(self.jobs(root)["physics-bake"]["returncode"], 37)
        self.assertEqual(self.jobs(root)["physics-bake"]["status"], "failed_no_automatic_retry")
        self.assertEqual(digest(root / "source.blend"), source_hash)

    def test_fresh_report_written_but_failed_exit_is_separate_failure(self):
        root, project, source_hash = self.fixture()
        calls = []
        with patch.object(short_project.subprocess, "Popen", self.process_factory(calls, {"bake": 0, "verify": 41})):
            with self.assertRaisesRegex(RuntimeError, r"physics-fresh-verify failed \(41\)"):
                short_project.physics(project, root)
        self.assertEqual(calls, ["bake", "verify"])
        jobs = self.jobs(root)
        self.assertEqual((jobs["physics-bake"]["status"], jobs["physics-bake"]["returncode"]), ("completed", 0))
        self.assertEqual((jobs["physics-fresh-verify"]["status"], jobs["physics-fresh-verify"]["returncode"]), ("failed_no_automatic_retry", 41))
        self.assertTrue(json.loads((root / "verify.json").read_text())["fresh_process_reopen_verified"])
        self.assertEqual(digest(root / "source.blend"), source_hash)

    def test_two_zero_exits_have_two_separate_completed_receipts(self):
        root, project, source_hash = self.fixture()
        calls = []
        with patch.object(short_project.subprocess, "Popen", self.process_factory(calls, {"bake": 0, "verify": 0})):
            result = short_project.physics(project, root)
        self.assertEqual(result, root / "verify.json")
        self.assertEqual(calls, ["bake", "verify"])
        jobs = self.jobs(root)
        self.assertEqual(set(jobs), {"physics-bake", "physics-fresh-verify"})
        self.assertTrue(all(row["returncode"] == 0 and row["status"] == "completed" for row in jobs.values()))
        self.assertEqual(digest(root / "source.blend"), source_hash)

    def test_failed_bake_outputs_are_preserved_and_not_replayed(self):
        root, project, _ = self.fixture()
        calls = []
        with patch.object(short_project.subprocess, "Popen", self.process_factory(calls, {"bake": 37, "verify": 0})):
            with self.assertRaises(RuntimeError):
                short_project.physics(project, root)
            before = {p.name: digest(p) for p in (root / "new.blend", root / "bake.json")}
            with self.assertRaisesRegex(ValueError, "New distinct physics outputs required"):
                short_project.physics(project, root)
            self.assertEqual(before, {p.name: digest(p) for p in (root / "new.blend", root / "bake.json")})
        self.assertEqual(calls, ["bake"])


if __name__=='__main__':unittest.main()
