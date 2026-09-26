from __future__ import annotations

import asyncio
import os
import shlex
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ringer


class VerifierOutputFidelityTests(unittest.TestCase):
    def test_timeout_preserves_diagnostic(self):
        command = shlex.join([sys.executable, '-u', '-c',
                              "import time; print('DIAG: which assertion broke'); time.sleep(30)"])
        with tempfile.TemporaryDirectory() as tmp, patch.object(ringer, 'CHECK_TIMEOUT_S', 1):
            _, timed_out, output = asyncio.run(ringer.Verifier._run_check(command, Path(tmp)))
        self.assertTrue(timed_out)
        self.assertIn('DIAG: which assertion broke', output)
        self.assertIn('[ringer.py] check timed out after 1s', output)

    def test_retry_context_preserves_late_assertion(self):
        command = shlex.join([sys.executable, '-c',
                              "print('x' * 3000); print('ASSERT FAILED: the real reason'); raise SystemExit(1)"])
        with tempfile.TemporaryDirectory() as tmp:
            task = ringer.TaskSpec(key='diag', spec='Verify output', check=command)
            result = asyncio.run(ringer.Verifier().verify(task, Path(tmp)))
            context = ringer.build_failure_context(Path(tmp) / 'worker.log', result.raw_output_tail)
        self.assertFalse(result.ok)
        self.assertEqual(len(result.raw_output_excerpt), 2000)
        self.assertIn('ASSERT FAILED: the real reason', context)

    def test_long_context_preserves_timeout_banner(self):
        banner = '[ringer.py] check timed out after 1s\n'
        with tempfile.TemporaryDirectory() as tmp:
            context = ringer.build_failure_context(Path(tmp) / 'worker.log', 'x' * 10000 + '\n' + banner)
        self.assertLessEqual(len(context), 6000)
        self.assertTrue(context.endswith(banner))

    def test_verified_artifact_passes_after_worker_timeout(self):
        worker = ringer.WorkerResult(returncode=-15, timed_out=True, tokens=None)
        for ok, expected in ((True, 'PASS'), (False, 'TIMEOUT')):
            with self.subTest(ok=ok):
                verify = ringer.VerifyResult(ok, 0 if ok else 1, False, '')
                self.assertEqual(ringer.verdict_for(worker, verify), expected)

    def test_passing_timeout_records_worker_state_without_retry(self):
        from tests import test_ringer as cli_tests

        harness = cli_tests.RingerCliTests()
        harness.setUp()
        self.addCleanup(harness.tearDown)
        manifest = harness.write_manifest('valid-timeout', harness.manifest(
            'valid-timeout', {
                'key': 'valid', 'engine': 'spec_shell',
                'spec': 'printf done > out.txt; sleep 30',
                'expect_files': ['out.txt'], 'timeout_s': 1,
                'check': 'test "$(cat out.txt)" = done',
            }))
        with patch.dict(os.environ, {'RINGER_HOME': str(harness.root / 'ringer-home')}):
            result = harness.run_ringer(manifest)
        self.assertEqual(result.returncode, 0, result.stdout)
        rows = harness.read_rows()
        self.assertEqual([row['verdict'] for row in rows], ['PASS'])
        self.assertIn('worker_timed_out=true', rows[0]['notes'])
        task = harness.read_final_state()['tasks'][0]
        self.assertTrue(task['worker_timed_out'])
        self.assertTrue(task['attempt_history'][0]['worker_timed_out'])

    def test_attempt_history_preserves_multiline_tail(self):
        from tests import test_ringer as cli_tests

        harness = cli_tests.RingerCliTests()
        harness.setUp()
        self.addCleanup(harness.tearDown)
        check = shlex.join([sys.executable, '-c',
                           "print('x' * 7000); print('ASSERT FAILED: first\\nsecond'); raise SystemExit(1)"])
        manifest = harness.write_manifest('tail-history', harness.manifest(
            'tail-history', {
                'key': 'tail', 'engine': 'write_done', 'spec': 'Write done.',
                'check': check,
            }))
        with patch.dict(os.environ, {'RINGER_HOME': str(harness.root / 'ringer-home')}):
            result = harness.run_ringer(manifest)
        self.assertEqual(result.returncode, 1, result.stdout)
        task = harness.read_final_state()['tasks'][0]
        self.assertIn('ASSERT FAILED: first\nsecond', task['check_output_tail'])
        for attempt in task['attempt_history']:
            self.assertIn('ASSERT FAILED: first\nsecond', attempt['check_output_tail'])
        self.assertIn('Previous attempt failed', harness.read_rows()[1]['spec'])

    def test_error_and_check_timeout_keep_precedence(self):
        verify = ringer.VerifyResult(True, None, True, '')
        worker = ringer.WorkerResult(None, True, None)
        self.assertEqual(ringer.verdict_for(worker, verify), 'TIMEOUT')
        worker = ringer.WorkerResult(None, True, None, error='spawn failed')
        self.assertEqual(ringer.verdict_for(worker, verify), 'ERROR')


if __name__ == '__main__':
    unittest.main()
