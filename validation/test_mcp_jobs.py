"""CPU-only process tests; no Blender, network or live service changes."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'blender-character-short' / 'scripts'
sys.path.insert(0, str(SCRIPTS))
from mcp_jobs import Jobs, read, write, mutex, sha

STUB = '''import argparse,json,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('stage');p.add_argument('--project');a=p.parse_args()
f=Path(a.project);d=json.loads(f.read_text());out=f.parent/'calls.txt'
with out.open('a') as h:h.write(a.stage+'\\n')
time.sleep(d.get('sleep',0))
if a.stage=='render':
    dst=f.parent/d['render']['output'];dst.mkdir(exist_ok=True)
    n=len(out.read_text().splitlines())
    (dst/'progress.json').write_text(json.dumps({'complete':n>=d.get('batches',2)}))
print('STUB_STAGE_FINISHED',flush=True)
raise SystemExit(d.get('exit_code',0))
'''


class JobsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.scripts=self.root/'skill'/'scripts';self.scripts.mkdir(parents=True)
        shutil.copy2(SCRIPTS/'mcp_jobs.py',self.scripts/'mcp_jobs.py')
        (self.scripts/'short_project.py').write_text(STUB,encoding='utf-8')
        self.project=self.root/'project.json';write(self.project,{'schema':1})
        self.config=self.root/'config.json'
        write(self.config,{'schema':1,'state_dir':str(self.root/'jobs'),'project_roots':[str(self.root)]})
        self.jobs=Jobs(self.config,self.scripts)
        self.ids=[]

    def tearDown(self):
        for job in self.ids:
            deadline=time.time()+10
            while self.jobs.status(job)['status'] not in ('completed','failed','cancelled','uncertain') and time.time()<deadline:
                time.sleep(.05)
        for attempt in range(40):
            try:
                self.tmp.cleanup();break
            except PermissionError:
                time.sleep(.05)
        else:self.fail('Worker did not close its test logs')

    def submit(self,stage='workflow',key='case',**kwargs):
        state=self.jobs.submit(self.project,stage,key,**kwargs);self.ids.append(state['job_id']);return state['job_id']

    def done(self,job):
        deadline=time.time()+10
        while time.time()<deadline:
            state=self.jobs.status(job)
            if state['status'] in ('completed','failed','cancelled','uncertain'):return state
            time.sleep(.05)
        self.fail('Job timed out')

    def test_complete_persisted_duplicate(self):
        job=self.submit();self.assertEqual(self.done(job)['status'],'completed')
        second=Jobs(self.config,self.scripts)
        self.assertEqual(second.submit(self.project,'workflow','case')['job_id'],job)
        self.assertEqual((self.root/'calls.txt').read_text().splitlines(),['workflow'])
        self.assertFalse(second.result(job)['result']['visual_acceptance'])
        self.assertIn('STUB_STAGE_FINISHED',second.logs(job)['text'])

    def test_same_key_changed_input_rejected(self):
        job=self.submit();self.done(job);write(self.project,{'schema':1,'extra':True})
        with self.assertRaisesRegex(ValueError,'already bound'):self.jobs.submit(self.project,'workflow','case')

    def test_project_reservation_across_stores(self):
        write(self.project,{'schema':1,'sleep':.8});job=self.submit()
        other=self.root/'other-config.json';write(other,dict(read(self.config),state_dir=str(self.root/'other-jobs')))
        with self.assertRaises((RuntimeError,OSError)):
            Jobs(other,self.scripts).submit(self.project,'workflow','other')
        self.assertEqual(self.done(job)['status'],'completed')

    def test_render_batches(self):
        write(self.project,{'schema':1,'render':{'output':'frames'},'batches':3})
        job=self.submit('render',complete=True)
        state=self.done(job);self.assertEqual(state['status'],'completed');self.assertEqual(state['batches_finished'],3)
        self.assertTrue(state['render_complete'])

    def test_cancel_waits_current_batch(self):
        write(self.project,{'schema':1,'render':{'output':'frames'},'batches':20,'sleep':.5})
        job=self.submit('render',complete=True)
        deadline=time.time()+5
        while not (self.root/'calls.txt').exists() and time.time()<deadline:time.sleep(.02)
        response=self.jobs.cancel(job);self.assertIn('no process is killed',response['message'])
        self.assertEqual(self.done(job)['status'],'cancelled')
        self.assertEqual(len((self.root/'calls.txt').read_text().splitlines()),1)

    def test_budget_no_false_completion(self):
        write(self.project,{'schema':1,'render':{'output':'frames'},'batches':20})
        job=self.submit('render',complete=True,max_batches=1)
        state=self.done(job);self.assertEqual(state['status'],'failed');self.assertFalse(state['render_complete'])

    def test_stage_failure_not_retried(self):
        write(self.project,{'schema':1,'exit_code':1});job=self.submit()
        state=self.done(job);self.assertEqual(state['status'],'uncertain');self.assertTrue(self.project.with_name(self.project.name+'.mcp-owner.json').exists())
        self.assertEqual(self.jobs.submit(self.project,'workflow','case')['job_id'],job)
        self.assertEqual(len((self.root/'calls.txt').read_text().splitlines()),1)

    def test_input_and_stage_boundaries(self):
        with self.assertRaises(ValueError):self.jobs.submit(self.project,'shell','abc')
        with self.assertRaises(ValueError):self.jobs.submit(self.project,'workflow','../bad')
        with self.assertRaises(ValueError):self.jobs.logs('../bad')
        with self.assertRaises(ValueError):self.jobs.submit(self.project,'workflow','x',complete=True)
        with self.assertRaises(ValueError):self.jobs.submit(self.project,'render','x',max_batches=0)
        cfg=self.root/'limited.json';d=self.root/'allowed';d.mkdir()
        write(cfg,dict(read(self.config),project_roots=[str(d)]))
        with self.assertRaisesRegex(ValueError,'configured'):Jobs(cfg,self.scripts).submit(self.project,'workflow','x')

    def test_changed_producer_before_worker_fails_closed(self):
        with patch('mcp_jobs.subprocess.Popen') as spawn:
            spawn.return_value.pid=1
            job=self.submit()
        (self.scripts/'short_project.py').write_text(STUB+'\n# changed\n')
        result=self.jobs.worker(job)
        self.assertEqual(result['status'],'failed');self.assertFalse((self.root/'calls.txt').exists())

    def test_stale_is_uncertain_not_restarted(self):
        with patch('mcp_jobs.subprocess.Popen') as spawn:
            spawn.return_value.pid=1;job=self.submit()
        file=self.jobs.directory(job)/'state.json';state=read(file);state['heartbeat']=0;write(file,state)
        self.assertEqual(self.jobs.status(job)['status'],'uncertain')
        self.assertTrue(self.project.with_name(self.project.name+'.mcp-owner.json').exists())
        with self.assertRaises((RuntimeError,OSError)):self.jobs.submit(self.project,'workflow','retry')
        # No actual worker was started by the mock.
        state['status']='failed';write(file,state)

    def test_post_spawn_metadata_failure_retains_reservation(self):
        def failing(path,data):
            if Path(path).name=='launch.json':raise OSError('metadata unavailable')
            write(path,data)
        with patch('mcp_jobs.subprocess.Popen') as spawn, patch('mcp_jobs.write',side_effect=failing):
            spawn.return_value.pid=1;job=self.submit()
        self.assertEqual(self.jobs.status(job)['status'],'queued')
        self.assertTrue(self.project.with_name(self.project.name+'.mcp-owner.json').exists())
        state=read(self.jobs.directory(job)/'state.json');state['status']='failed';write(self.jobs.directory(job)/'state.json',state)

    def test_repeated_worker_does_not_change_terminal_state(self):
        job=self.submit();before=self.done(job)
        result=self.jobs.worker(job)
        self.assertTrue(result['duplicate_worker_refused'])
        self.assertEqual(self.jobs.status(job),before)
        self.assertEqual(len((self.root/'calls.txt').read_text().splitlines()),1)

    def test_missing_plan_rejected(self):
        write(self.project,{'schema':1,'refine_plan':'missing.json'})
        with self.assertRaisesRegex(ValueError,'missing'):self.submit('refine')

    def test_shared_execution_lock_different_project(self):
        write(self.project,{'schema':1,'execution_lock':'shared.lock','sleep':.5});job=self.submit()
        other=self.root/'other.json';write(other,{'schema':1,'execution_lock':'shared.lock'})
        with self.assertRaises((RuntimeError,OSError)):self.jobs.submit(other,'workflow','other')
        self.assertEqual(self.done(job)['status'],'completed')

    def test_os_lock_excludes_second_writer(self):
        lock=self.root/'lock'
        with mutex(lock):
            with self.assertRaises(OSError):
                with mutex(lock):pass


if __name__=='__main__':unittest.main()
