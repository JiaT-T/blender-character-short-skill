import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender-character-short/scripts"))
import mcp_setup as setup

class SetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
    def test_relative_rejected(self):
        with self.assertRaises(ValueError): setup.absolute("relative")
    def test_install_plan_no_changes(self):
        p = self.base / "env"
        result = setup.install(p)
        self.assertEqual(result["status"], "planned")
        self.assertFalse(p.exists())
        self.assertIn("mcp==1.30.0", result["command"])
        self.assertIn("numpy==2.5.4", result["command"])
    def test_existing_unowned_rejected(self):
        with self.assertRaises(ValueError): setup.install(self.base, True)
    def test_marker_conflict(self):
        p=self.base/'env';p.mkdir();(p/setup.OWNER).write_text('{}')
        with self.assertRaises(ValueError):setup.install(p,True)
    def test_inspect_missing(self):
        self.assertEqual(setup.inspect_environment(self.base/'missing')['status'],'missing')
    def test_version_probe(self):
        env=self.base/'env';python=setup.python_at(env);python.parent.mkdir(parents=True);python.write_text('')
        response=subprocess.CompletedProcess([],0,json.dumps(setup.PACKAGES),'')
        with patch.object(setup,'run',return_value=response):self.assertEqual(setup.inspect_environment(env)['status'],'ready')
        bad=dict(setup.PACKAGES,mcp='0')
        with patch.object(setup,'run',return_value=subprocess.CompletedProcess([],0,json.dumps(bad),'')):
            self.assertEqual(setup.inspect_environment(env)['status'],'version_mismatch')
    def test_configuration_plan(self):
        result=setup.configuration(self.base/'env',self.base/'cfg.json',self.base/'state',[str(self.base)],self.base/'client.json')
        self.assertEqual(result['status'],'planned');self.assertFalse((self.base/'cfg.json').exists())
    def test_configuration_conflict_preserved(self):
        cfg=self.base/'cfg.json';cfg.write_text('{"keep":1}')
        with self.assertRaises(ValueError):setup.configuration(self.base/'env',cfg,self.base/'state',[str(self.base)],self.base/'client.json',True)
        self.assertEqual(cfg.read_text(),'{"keep":1}');self.assertFalse((self.base/'client.json').exists())
    def test_configuration_root_refused(self):
        with self.assertRaises(ValueError):setup.configuration(self.base/'env',self.base/'cfg.json',self.base/'state',[self.base.anchor],self.base/'client.json')
    def test_write_idempotent(self):
        p=self.base/'new.json';self.assertTrue(setup.write_new_or_same(p,{'a':1}));self.assertFalse(setup.write_new_or_same(p,{'a':1}))
        with self.assertRaises(ValueError):setup.write_new_or_same(p,{'a':2})
    def test_bridge_stage_hashed_no_overwrite(self):
        src=self.base/'source.py';src.write_text('VALUE=1\n');sha=hashlib.sha256(src.read_bytes()).hexdigest()
        dest=self.base/'addons'
        self.assertEqual(setup.stage_bridge(src,sha,dest,True)['status'],'staged')
        self.assertEqual(setup.stage_bridge(src,sha,dest,True)['status'],'staged')
        (dest/'blender_mcp.py').write_text('VALUE=2')
        with self.assertRaises(ValueError):setup.stage_bridge(src,sha,dest,True)
    def test_bridge_bad_hash(self):
        src=self.base/'source.py';src.write_text('VALUE=1')
        with self.assertRaises(ValueError):setup.stage_bridge(src,'0'*64,self.base/'addons',True)
        self.assertFalse((self.base/'addons').exists())
    def test_bridge_install_requires_owner(self):
        with self.assertRaises(ValueError):setup.install_bridge_package(self.base)
    def test_bridge_health_failure_does_not_restart(self):
        with patch('socket.create_connection',side_effect=ConnectionRefusedError('fixture')):
            result=setup.bridge_health()
        self.assertFalse(result['verified_protocol']);self.assertFalse(result['automatic_restart'])
    def test_cli_help(self):
        r=subprocess.run([sys.executable,str(Path(setup.__file__)),'--help'],capture_output=True,text=True)
        self.assertEqual(r.returncode,0);self.assertIn('bridge-launch',r.stdout)

    def test_health_invalid_configuration_not_ready(self):
        cfg=self.base/'cfg.json';cfg.write_text(json.dumps({'schema':2,'project_roots':[str(self.base)]}))
        with patch.object(setup,'inspect_environment',return_value={'status':'ready'}):
            result=setup.health(self.base/'env',cfg)
        self.assertEqual(result['status'],'invalid_configuration')
    def test_health_check_failure_not_ready(self):
        cfg=self.base/'cfg.json';cfg.write_text(json.dumps({'schema':1,'project_roots':[str(self.base)]}))
        with patch.object(setup,'inspect_environment',return_value={'status':'ready'}), patch.object(setup,'run',side_effect=subprocess.CalledProcessError(1,['fixture'])):
            result=setup.health(self.base/'env',cfg)
        self.assertIn(result['status'],('service_check_failed','invalid_configuration'))
    def test_state_inside_skill_refused(self):
        with self.assertRaises(ValueError):setup.configuration(self.base/'env',self.base/'cfg.json',setup.SCRIPTS/'state',[str(self.base)],self.base/'client.json')
    def test_optional_bridge_snippet(self):
        expected={'command':'fixture','args':[],'env':{'BLENDER_HOST':'127.0.0.1','BLENDER_PORT':'9876'}}
        with patch.object(setup,'bridge_client',return_value=expected):
            r=setup.configuration(self.base/'env',self.base/'cfg.json',self.base/'state',[str(self.base)],self.base/'client.json',with_bridge=True)
        self.assertEqual(r['client_snippet']['mcpServers']['blender-mcp'],expected)
    def test_codex_only_add_absent(self):
        exe=self.base/('codex.exe' if setup.os.name=='nt' else 'codex');exe.write_text('')
        launcher=self.base/'python.exe';launcher.write_text('')
        cfg=self.base/'client.json';cfg.write_text(json.dumps({'mcpServers':{'blender-short-jobs':{'command':str(launcher),'args':['service.py']}}}))
        with patch.object(setup,'run',return_value=subprocess.CompletedProcess([],0,'[]','')) as mocked:
            r=setup.register_codex(exe,cfg)
        self.assertEqual(mocked.call_count,1);self.assertEqual(len(r['commands']),1);self.assertFalse(r['connected'])
    def test_codex_refuses_existing_different(self):
        exe=self.base/('codex.exe' if setup.os.name=='nt' else 'codex');exe.write_text('')
        launcher=self.base/'python.exe';launcher.write_text('')
        cfg=self.base/'client.json';cfg.write_text(json.dumps({'mcpServers':{'blender-mcp':{'command':str(launcher),'args':[]}}}))
        rows=[{'name':'blender-mcp','transport':{'type':'stdio','command':'other','args':[]}}]
        with patch.object(setup,'run',return_value=subprocess.CompletedProcess([],0,json.dumps(rows),'')) as mocked:
            with self.assertRaises(ValueError):setup.register_codex(exe,cfg,True)
        self.assertEqual(mocked.call_count,1)
if __name__=='__main__':unittest.main()


