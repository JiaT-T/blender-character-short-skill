"""Fault-injection fixtures only: no Blender, service, network or real workers."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'blender-character-short' / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import mcp_jobs
from mcp_jobs import Jobs, input_snapshot, read, write


class ExitedChild:
    pid = 424242
    returncode = 0

    def wait(self):
        return self.returncode

    def poll(self):
        return self.returncode


class JobsReliabilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.scripts = self.root / 'skill' / 'scripts'
        self.scripts.mkdir(parents=True)
        shutil.copy2(SCRIPTS / 'mcp_jobs.py', self.scripts / 'mcp_jobs.py')
        (self.scripts / 'short_project.py').write_text('# fixture only\n', encoding='utf-8')
        self.project = self.root / 'project.json'
        write(self.project, {'schema': 1})
        self.config = self.root / 'config.json'
        write(self.config, {'schema': 1, 'state_dir': str(self.root / 'jobs'),
                            'project_roots': [str(self.root)]})
        self.jobs = Jobs(self.config, self.scripts)
        self.guard = self.project.with_name(self.project.name + '.mcp-owner.json')
        self.job_id = 'job-' + hashlib.sha256(b'fixture').hexdigest()[:32]
        self.folder = self.jobs.store / self.job_id

    def tearDown(self):
        self.tmp.cleanup()

    def submit(self, **kwargs):
        return self.jobs.submit(self.project, kwargs.pop('stage', 'workflow'), 'fixture', **kwargs)

    def queued(self, **kwargs):
        with patch('mcp_jobs.subprocess.Popen', return_value=ExitedChild()) as spawn:
            state = self.submit(**kwargs)
        self.assertEqual(spawn.call_count, 1)
        self.assertEqual(state['status'], 'queued')
        return state

    def test_snapshot_hash_and_lock_come_from_same_project_bytes(self):
        old = {'schema': 1, 'execution_lock': 'old.lock'}
        write(self.project, old)
        raw = self.project.read_bytes()
        original = Path.read_bytes

        def changing(path):
            value = original(path)
            if path == self.project:
                write(self.project, {'schema': 1, 'execution_lock': 'new.lock'})
            return value

        with patch.object(Path, 'read_bytes', changing):
            data, bound = input_snapshot(self.project)
        self.assertEqual(data, old)
        self.assertEqual(bound[str(self.project)], hashlib.sha256(raw).hexdigest())
        self.assertNotEqual(bound[str(self.project)], mcp_jobs.sha(self.project))

    def test_project_change_during_submission_refused_before_reservation(self):
        original = mcp_jobs.input_snapshot

        def changing(path):
            snapshot = original(path)
            write(self.project, {'schema': 1, 'execution_lock': 'different.lock'})
            return snapshot

        with patch('mcp_jobs.input_snapshot', changing), patch('mcp_jobs.subprocess.Popen') as spawn:
            with self.assertRaisesRegex(ValueError, 'changed while submitting'):
                self.submit()
        spawn.assert_not_called()
        self.assertFalse(self.guard.exists())
        self.assertFalse(self.folder.exists())

    def test_plan_change_during_submission_refused_before_reservation(self):
        plan = self.root / 'brief.json'
        write(plan, {'version': 1})
        write(self.project, {'schema': 1, 'workflow_brief': plan.name})
        original = mcp_jobs.input_snapshot

        def changing(path):
            snapshot = original(path)
            write(plan, {'version': 2})
            return snapshot

        with patch('mcp_jobs.input_snapshot', changing), patch('mcp_jobs.subprocess.Popen') as spawn:
            with self.assertRaisesRegex(ValueError, 'changed while submitting'):
                self.submit()
        spawn.assert_not_called()
        self.assertFalse(self.guard.exists())

    def metadata_failure(self, name):
        def failing(path, data):
            if Path(path).name == name:
                raise OSError('fixture metadata failure')
            write(path, data)

        with patch('mcp_jobs.write', failing), patch('mcp_jobs.subprocess.Popen') as spawn:
            with self.assertRaisesRegex(OSError, 'fixture metadata failure'):
                self.submit()
        spawn.assert_not_called()
        self.assertFalse(self.folder.exists())
        self.assertFalse(self.guard.exists())
        self.assertFalse(list(self.jobs.store.glob('.prepare-*')))
        self.queued()

    def test_request_write_failure_does_not_publish_partial_job(self):
        self.metadata_failure('request.json')

    def test_state_write_failure_does_not_publish_partial_job(self):
        self.metadata_failure('state.json')

    def interrupted_prelaunch(self, point):
        def failing(path, data):
            if ((point == 'guard' and Path(path) == self.guard) or
                    (point == 'queued' and Path(path).name == 'state.json' and data['status'] == 'queued')):
                raise OSError('fixture prelaunch failure')
            write(path, data)

        with patch('mcp_jobs.write', failing), patch('mcp_jobs.subprocess.Popen') as spawn:
            with self.assertRaisesRegex(OSError, 'fixture prelaunch failure'):
                self.submit()
        spawn.assert_not_called()
        self.assertEqual(read(self.folder / 'state.json')['status'], 'prepared')
        return self.jobs

    def test_interruption_before_guard_recovers_failed_without_replay(self):
        self.interrupted_prelaunch('guard')
        with patch('mcp_jobs.subprocess.Popen') as spawn:
            state = self.submit()
        spawn.assert_not_called()
        self.assertEqual(state['status'], 'failed')
        self.assertEqual(state['submission_phase'], 'not_launched')
        self.assertFalse(self.guard.exists())

    def test_interruption_before_queued_recovers_own_reservation_only(self):
        self.interrupted_prelaunch('queued')
        self.assertTrue(self.guard.exists())
        with patch('mcp_jobs.subprocess.Popen') as spawn:
            state = self.submit()
        spawn.assert_not_called()
        self.assertEqual(state['status'], 'failed')
        self.assertFalse(state['reservation_retained'])

    def test_stale_prepared_receipt_remains_known_prelaunch(self):
        self.interrupted_prelaunch('queued')
        state = read(self.folder / 'state.json')
        state['heartbeat'] = 0
        write(self.folder / 'state.json', state)
        status = self.jobs.status(self.job_id)
        self.assertEqual(status['status'], 'prepared')
        self.assertTrue(status['reservation_retained'])
        with patch('mcp_jobs.subprocess.Popen') as spawn:
            recovered = self.submit()
        spawn.assert_not_called()
        self.assertEqual(recovered['status'], 'failed')
        self.assertFalse(self.guard.exists())

    def test_prepared_recovery_retains_foreign_reservation(self):
        self.interrupted_prelaunch('queued')
        foreign = {'job_id': 'someone-else', 'identity': 'different', 'store': 'other'}
        write(self.guard, foreign)
        with patch('mcp_jobs.subprocess.Popen') as spawn:
            with self.assertRaisesRegex(RuntimeError, 'Reservation differs'):
                self.submit()
        spawn.assert_not_called()
        self.assertEqual(read(self.guard), foreign)
        self.assertEqual(read(self.folder / 'state.json')['status'], 'prepared')

    def test_prelaunch_cleanup_failure_can_be_reconciled_without_replay(self):
        self.interrupted_prelaunch('queued')
        original = Path.unlink

        def failing(path, *args, **kwargs):
            if path == self.guard:
                raise OSError('fixture guard cleanup failure')
            return original(path, *args, **kwargs)

        with patch.object(Path, 'unlink', failing):
            with self.assertRaisesRegex(OSError, 'fixture guard cleanup failure'):
                self.submit()
        self.assertEqual(read(self.folder / 'state.json')['submission_phase'], 'not_launched')
        self.assertTrue(self.jobs.status(self.job_id)['reservation_retained'])
        with patch('mcp_jobs.subprocess.Popen') as spawn:
            state = self.submit()
        spawn.assert_not_called()
        self.assertEqual(state['status'], 'failed')
        self.assertFalse(self.guard.exists())

    def test_os_spawn_failure_is_terminal_and_same_key_never_replays(self):
        with patch('mcp_jobs.subprocess.Popen', side_effect=OSError('fixture spawn refusal')):
            with self.assertRaisesRegex(OSError, 'fixture spawn refusal'):
                self.submit()
        with patch('mcp_jobs.subprocess.Popen') as spawn:
            state = self.submit()
        spawn.assert_not_called()
        self.assertEqual(state['status'], 'failed')
        self.assertEqual(state['submission_phase'], 'not_launched')
        self.assertFalse(self.guard.exists())

    def test_missing_durable_spawn_failure_receipt_retains_uncertainty(self):
        def failing(path, data):
            if Path(path).name == 'state.json' and data['status'] == 'failed':
                raise OSError('fixture failed receipt unavailable')
            write(path, data)

        with patch('mcp_jobs.subprocess.Popen', side_effect=OSError('fixture spawn refusal')), patch('mcp_jobs.write', failing):
            with self.assertRaisesRegex(OSError, 'fixture failed receipt unavailable'):
                self.submit()
        state = read(self.folder / 'state.json')
        state['heartbeat'] = 0
        write(self.folder / 'state.json', state)
        with patch('mcp_jobs.subprocess.Popen') as spawn:
            state = self.submit()
        spawn.assert_not_called()
        self.assertEqual(state['status'], 'uncertain')
        self.assertTrue(self.guard.exists())

    def test_cancelled_incomplete_final_budget_batch_is_cancelled(self):
        write(self.project, {'schema': 1, 'render': {'output': 'frames'}})
        self.queued(stage='render', complete=True, max_batches=1)

        def finished(*args, **kwargs):
            frames = self.root / 'frames'
            frames.mkdir()
            write(frames / 'progress.json', {'complete': False})
            self.jobs.cancel(self.job_id)
            return ExitedChild()

        with patch('mcp_jobs.subprocess.Popen', finished):
            state = self.jobs.worker(self.job_id)
        self.assertEqual(state['status'], 'cancelled')
        self.assertEqual(state['batches_finished'], 1)
        self.assertFalse(state['render_complete'])
        self.assertFalse(self.guard.exists())

    def test_cancel_during_completed_final_batch_preserves_completion(self):
        write(self.project, {'schema': 1, 'render': {'output': 'frames'}})
        self.queued(stage='render', complete=True, max_batches=1)

        def finished(*args, **kwargs):
            frames = self.root / 'frames'
            frames.mkdir()
            write(frames / 'progress.json', {'complete': True})
            self.jobs.cancel(self.job_id)
            return ExitedChild()

        with patch('mcp_jobs.subprocess.Popen', finished):
            state = self.jobs.worker(self.job_id)
        self.assertEqual(state['status'], 'completed')
        self.assertTrue(state['render_complete'])
        self.assertFalse(self.guard.exists())

    def test_cancel_of_uncertain_job_retains_reservation_and_no_replay(self):
        self.queued()
        state = read(self.folder / 'state.json')
        state['heartbeat'] = 0
        write(self.folder / 'state.json', state)
        self.assertEqual(self.jobs.cancel(self.job_id)['status'], 'uncertain')
        with patch('mcp_jobs.subprocess.Popen') as spawn:
            repeated = self.submit()
            with self.assertRaisesRegex(RuntimeError, 'Project reserved'):
                self.jobs.submit(self.project, 'workflow', 'other-request')
        spawn.assert_not_called()
        self.assertTrue(repeated['cancel_requested'])
        self.assertTrue(repeated['reservation_retained'])

    @unittest.skipUnless(mcp_jobs.os.name == 'nt', 'Windows publication failure classification')
    def test_exhausted_heartbeat_replace_keeps_uncertain_reservation_without_replay(self):
        self.queued()
        fault = PermissionError(13, 'injected heartbeat replace failure')
        fault.winerror = 5
        real_replace = mcp_jobs.os.replace
        failed_temps = []

        def replacing(source, target):
            if Path(target) == self.folder / 'state.json':
                state = read(source)
                if state['status'] == 'running' and state.get('child_pid'):
                    failed_temps.append(Path(source))
                    raise fault
            return real_replace(source, target)

        class LiveChild:
            pid = 424243
            def poll(self):
                return None

        with patch('mcp_jobs.subprocess.Popen', return_value=LiveChild()) as spawn, \
                patch('mcp_jobs.os.replace', replacing), patch('mcp_jobs.time.sleep'), \
                patch('mcp_jobs.sys.stderr'):
            state = self.jobs.worker(self.job_id)
        self.assertEqual(state['status'], 'uncertain')
        self.assertTrue(self.jobs.status(self.job_id)['reservation_retained'])
        self.assertTrue(self.guard.exists())
        self.assertEqual(spawn.call_count, 1)
        self.assertEqual(len(failed_temps), 6)
        self.assertEqual(len(set(failed_temps)), 1)
        self.assertTrue(failed_temps[0].exists())
        with patch('mcp_jobs.subprocess.Popen') as spawn:
            repeated = self.submit()
        spawn.assert_not_called()
        self.assertEqual(repeated['status'], 'uncertain')
        self.assertTrue(repeated['reservation_retained'])

    def test_terminal_leftover_reservation_is_reported_and_retained(self):
        self.queued()
        state = read(self.folder / 'state.json')
        state.update(status='completed')
        write(self.folder / 'state.json', state)
        with patch('mcp_jobs.subprocess.Popen') as spawn:
            state = self.submit()
        spawn.assert_not_called()
        self.assertEqual(state['status'], 'completed')
        self.assertTrue(state['reservation_retained'])
        self.assertTrue(self.guard.exists())

    def test_legacy_partial_metadata_is_uncertain_and_never_replayed(self):
        self.folder.mkdir()
        with patch('mcp_jobs.subprocess.Popen') as spawn:
            with self.assertRaisesRegex(RuntimeError, 'Incomplete job metadata'):
                self.submit()
        spawn.assert_not_called()
        state = self.jobs.status(self.job_id)
        self.assertEqual(state['status'], 'uncertain')
        self.assertTrue(state['reservation_inspection_required'])

    def test_invalid_legacy_state_shape_is_uncertain_and_never_replayed(self):
        self.queued()
        write(self.folder / 'state.json', {})
        with patch('mcp_jobs.subprocess.Popen') as spawn:
            with self.assertRaisesRegex(RuntimeError, 'Incomplete job metadata'):
                self.submit()
        spawn.assert_not_called()
        self.assertEqual(self.jobs.status(self.job_id)['status'], 'uncertain')
        self.assertTrue(self.guard.exists())


if __name__ == '__main__':
    unittest.main()
