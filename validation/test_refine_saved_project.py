import hashlib, json, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"blender-character-short/scripts"))
from refine_saved_project import validate_plan

class PlanTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.base=Path(self.tmp.name)
        (self.base/"source.blend").write_bytes(b"test source")
        self.plan={"schema":1,"source":{"path":"source.blend","sha256":hashlib.sha256(b"test source").hexdigest()},"output":"out.blend","backup":"backup.blend","report":"report.json","compositor":{"gain":.025}}
    def test_valid(self): self.assertEqual(validate_plan(self.plan,self.base)[0]["bytes"],11)
    def test_source_hash(self):
        self.plan["source"]["sha256"]="0"*64
        with self.assertRaises(ValueError):validate_plan(self.plan,self.base)
    def test_no_overwrite(self):
        (self.base/"out.blend").write_bytes(b"old")
        with self.assertRaises(FileExistsError):validate_plan(self.plan,self.base)
    def test_no_source_alias(self):
        self.plan["output"]="source.blend"
        with self.assertRaises(ValueError):validate_plan(self.plan,self.base)
    def test_distinct_paths(self):
        self.plan["backup"]=self.plan["output"]
        with self.assertRaises(ValueError):validate_plan(self.plan,self.base)
    def test_unknown_field(self):
        self.plan["ignore_protection"]=True
        with self.assertRaises(ValueError):validate_plan(self.plan,self.base)
    def test_operation_required(self):
        self.plan.pop("compositor")
        with self.assertRaises(ValueError):validate_plan(self.plan,self.base)
    def test_bad_samples(self):
        for x in [True,0,4097,1.5,float("nan")]:
            self.plan["samples"]=x
            with self.assertRaises(ValueError):validate_plan(self.plan,self.base)
    def test_blend_extension(self):
        self.plan["backup"]="backup.txt"
        with self.assertRaises(ValueError):validate_plan(self.plan,self.base)
class DispatchTests(unittest.TestCase):
    def test_refine_uses_existing_runtime_and_plan(self):
        from unittest.mock import patch
        from production_contract import digest, sha
        import short_project
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve(); (root/"blender").write_bytes(b"fixture binary")
            runtime={"blender":"blender","blender_version":"fixture","threads":1}
            (root/"reports").mkdir()
            (root/"reports/runtime.json").write_text(json.dumps({"accepted":True,"runtime_spec_sha256":digest(runtime),"binary_sha256":sha(root/"blender")}))
            project={"schema":1,"id":"fixture","runtime":runtime,"reports":"reports","refine_plan":"plan.json"}
            (root/"project.json").write_text(json.dumps(project))
            with patch.object(sys,"argv",["short_project.py","refine","--project",str(root/"project.json")]), patch.object(short_project,"run_native") as native:
                short_project.main()
                native.assert_called_once_with(project,root,"refine_saved_project.py",["--plan",root/"plan.json"],"refine-saved-project")
if __name__=="__main__":unittest.main()
