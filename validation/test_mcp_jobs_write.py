"""Own-file host writer fixtures. No Blender, service, network or real jobs."""
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'blender-character-short' / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import mcp_jobs


class MetadataWriteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.target = self.root / 'state.json'
        self.old = b'{"status":"running","marker":"old"}'
        self.target.write_bytes(self.old)
        self.new = {'status': 'uncertain', 'marker': 'new', 'values': list(range(256))}

    def tearDown(self):
        self.tmp.cleanup()

    def test_backoff_is_finite_and_below_one_second(self):
        self.assertEqual(len(mcp_jobs.METADATA_REPLACE_DELAYS) + 1, 6)
        self.assertTrue(all(0 < delay < 1 for delay in mcp_jobs.METADATA_REPLACE_DELAYS))
        self.assertLess(sum(mcp_jobs.METADATA_REPLACE_DELAYS), 1)

    @unittest.skipUnless(os.name == 'nt', 'Actual Windows held-reader fixture')
    def test_actual_reader_closes_at_retry_boundary_then_atomic_replace_succeeds(self):
        reader = self.target.open('rb')
        real_replace = os.replace
        calls, sleeps = [], []
        stderr, stdout = io.StringIO(), io.StringIO()

        def replacing(source, target):
            calls.append((Path(source), Path(target)))
            # Complete old target and complete new temp exist before every attempt.
            self.assertEqual(self.target.read_bytes(), self.old)
            self.assertEqual(json.loads(Path(source).read_text('utf-8')), self.new)
            return real_replace(source, target)

        def release(delay):
            sleeps.append(delay)
            self.assertEqual(reader.read(), self.old)
            reader.close()

        try:
            with patch('mcp_jobs.os.replace', replacing), patch('mcp_jobs.time.sleep', release), \
                    contextlib.redirect_stderr(stderr), contextlib.redirect_stdout(stdout), \
                    patch('mcp_jobs.json.dump', wraps=json.dump) as dumped:
                mcp_jobs.write(self.target, self.new)
        finally:
            reader.close()
        self.assertEqual(len(calls), 2)
        self.assertEqual(len(set(source for source, _ in calls)), 1)
        self.assertEqual({target for _, target in calls}, {self.target})
        self.assertEqual(sleeps, [mcp_jobs.METADATA_REPLACE_DELAYS[0]])
        self.assertEqual(dumped.call_count, 1)
        self.assertEqual(mcp_jobs.read(self.target), self.new)
        self.assertFalse(list(self.root.glob('state.json.tmp-*')))
        self.assertEqual(stdout.getvalue(), '')
        diagnostic = json.loads(stderr.getvalue())
        self.assertEqual((diagnostic['event'], diagnostic['attempt'], diagnostic['winerror']),
                         ('metadata_replace_retry', 1, 5))

    @unittest.skipUnless(os.name == 'nt', 'Actual Windows held-reader fixture')
    def test_actual_persistent_reader_is_bounded_failclosed_and_preserves_complete_temp(self):
        stderr = io.StringIO()
        real_replace = os.replace
        started = time.monotonic()
        with self.target.open('rb') as reader, contextlib.redirect_stderr(stderr), \
                patch('mcp_jobs.os.replace', wraps=real_replace) as replacing:
            with self.assertRaises(PermissionError) as caught:
                mcp_jobs.write(self.target, self.new)
            self.assertEqual(reader.read(), self.old)
        elapsed = time.monotonic() - started
        self.assertEqual(caught.exception.winerror, 5)
        self.assertEqual(replacing.call_count, 6)
        self.assertLess(elapsed, 1.0)
        self.assertEqual(self.target.read_bytes(), self.old)
        leftovers = list(self.root.glob('state.json.tmp-*'))
        self.assertEqual(len(leftovers), 1)
        self.assertEqual(mcp_jobs.read(leftovers[0]), self.new)
        diagnostics = [json.loads(line) for line in stderr.getvalue().splitlines()]
        self.assertEqual([row['attempt'] for row in diagnostics], list(range(1, 7)))
        self.assertEqual(diagnostics[-1]['event'], 'metadata_replace_failed')
        self.assertEqual(diagnostics[-1]['delay_seconds'], 0)

    @unittest.skipUnless(os.name == 'nt', 'Windows retry eligibility')
    def test_only_listed_windows_errors_retry_same_temp_then_succeed(self):
        for code in (5, 32, 33):
            with self.subTest(winerror=code):
                fault = PermissionError(13, 'injected transient metadata error')
                fault.winerror = code
                real_replace = os.replace
                calls = []
                def replacing(source, target):
                    calls.append((source, target))
                    if len(calls) == 1:
                        raise fault
                    return real_replace(source, target)
                with patch('mcp_jobs.os.replace', replacing), patch('mcp_jobs.time.sleep') as sleeping, \
                        contextlib.redirect_stderr(io.StringIO()):
                    mcp_jobs.write(self.target, self.new)
                self.assertEqual(calls[0], calls[1])
                sleeping.assert_called_once_with(mcp_jobs.METADATA_REPLACE_DELAYS[0])

    def test_unlisted_or_no_winerror_is_raised_without_retry(self):
        for code in (None, 87, 112):
            with self.subTest(winerror=code):
                fault = OSError(5, 'injected non-retryable replace error')
                if code is not None:
                    fault.winerror = code
                with patch('mcp_jobs.os.replace', side_effect=fault) as replacing, \
                        patch('mcp_jobs.time.sleep') as sleeping:
                    with self.assertRaises(OSError) as caught:
                        mcp_jobs.write(self.target, self.new)
                self.assertIs(caught.exception, fault)
                replacing.assert_called_once()
                sleeping.assert_not_called()
                self.assertEqual(self.target.read_bytes(), self.old)

    def test_serialization_failure_does_not_attempt_replace_or_retry(self):
        with patch('mcp_jobs.os.replace') as replacing, patch('mcp_jobs.time.sleep') as sleeping:
            with self.assertRaises(ValueError):
                mcp_jobs.write(self.target, {'invalid': float('nan')})
        replacing.assert_not_called()
        sleeping.assert_not_called()
        self.assertEqual(self.target.read_bytes(), self.old)

    def test_fsync_failure_does_not_attempt_replace_or_retry(self):
        fault = OSError(28, 'injected fsync failure')
        with patch('mcp_jobs.os.fsync', side_effect=fault), patch('mcp_jobs.os.replace') as replacing, \
                patch('mcp_jobs.time.sleep') as sleeping:
            with self.assertRaises(OSError) as caught:
                mcp_jobs.write(self.target, self.new)
        self.assertIs(caught.exception, fault)
        replacing.assert_not_called()
        sleeping.assert_not_called()
        self.assertEqual(self.target.read_bytes(), self.old)

    @unittest.skipUnless(os.name == 'nt', 'Windows retry eligibility')
    def test_stderr_failure_cannot_replace_original_persistent_error(self):
        fault = PermissionError(13, 'injected persistent replace error')
        fault.winerror = 5
        with patch('mcp_jobs.os.replace', side_effect=fault) as replacing, \
                patch('mcp_jobs.time.sleep') as sleeping, patch('mcp_jobs.sys.stderr') as stderr:
            stderr.write.side_effect = OSError('injected broken stderr')
            with self.assertRaises(PermissionError) as caught:
                mcp_jobs.write(self.target, self.new)
        self.assertIs(caught.exception, fault)
        self.assertEqual(replacing.call_count, 6)
        self.assertEqual(sleeping.call_count, 5)

    @unittest.skipUnless(os.name == 'nt', 'Windows retry eligibility')
    def test_absent_stderr_never_redirects_diagnostics_to_stdout(self):
        fault = PermissionError(13, 'injected persistent replace error')
        fault.winerror = 5
        stdout = io.StringIO()
        with patch('mcp_jobs.os.replace', side_effect=fault), patch('mcp_jobs.time.sleep'), \
                patch('mcp_jobs.sys.stderr', None), contextlib.redirect_stdout(stdout):
            with self.assertRaises(PermissionError) as caught:
                mcp_jobs.write(self.target, self.new)
        self.assertIs(caught.exception, fault)
        self.assertEqual(stdout.getvalue(), '')


if __name__ == '__main__':
    unittest.main()
