"""Hermetic regression coverage for template check output and baseline gates."""

import importlib.util
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def load_check(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'templates' / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


hardening = load_check('test_hardening_check', 'test-hardening/checks/test_hardening_check.py')
feature = load_check('check_repo_feature', 'repo-feature/checks/check_repo_feature.py')
VITEST = 'Tests\x1b[22m\x1b[1m\x1b[32m 3 passed\x1b[39m\x1b[22m\x1b[2m (3)\x1b[22m'


def command(source):
    return shlex.join([sys.executable, '-c', source])


class OutputHygieneTests(unittest.TestCase):
    def test_vitest_count_and_ansi_helpers(self):
        for module in (hardening, feature):
            with self.subTest(module=module.__name__):
                self.assertEqual(module.strip_ansi(VITEST), 'Tests 3 passed (3)')
                self.assertEqual(module.strip_ansi('\x1b]0;title\x07\x1b[?25lhello'), 'hello')
        self.assertEqual(hardening.parse_test_count(VITEST, 'AUTO'), 3)
        self.assertEqual(hardening.parse_test_count(VITEST, r'Tests\s+(\d+)'), 3)

    def test_run_tests_strips_before_return_and_preserves_environment(self):
        source = (
            "import os; "
            "assert os.environ['NO_COLOR'] == '1'; "
            "assert os.environ['FORCE_COLOR'] == '0'; "
            "assert os.environ['TERM'] == 'dumb'; "
            "assert os.environ['HYGIENE_SENTINEL'] == 'kept'; "
            f'print({VITEST!r})'
        )
        with patch.dict(os.environ, {'HYGIENE_SENTINEL': 'kept', 'FORCE_COLOR': '1'}):
            ok, output = hardening.run_tests(command(source))
        self.assertTrue(ok)
        self.assertNotIn('\x1b', output)
        self.assertEqual(hardening.parse_test_count(output, 'AUTO'), 3)

    def run_feature(self, output, *flags, exit_code=1):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory) / 'repo'
            repo.mkdir()
            subprocess.run(['git', 'init', '-q', str(repo)], check=True, capture_output=True)
            notes = Path(directory) / 'notes.md'
            notes.write_text('Verification notes\n', encoding='utf-8')
            source = (
                "import os, sys; "
                "assert os.environ['NO_COLOR'] == '1'; "
                "assert os.environ['FORCE_COLOR'] == '0'; "
                "assert os.environ['TERM'] == 'dumb'; "
                "assert os.environ['HYGIENE_SENTINEL'] == 'kept'; "
                f'print({output!r}, file=sys.stderr); sys.exit({exit_code})'
            )
            return subprocess.run(
                [sys.executable, str(Path(feature.__file__)), '--repo', str(repo),
                 '--owned', 'src', '--notes', str(notes), '--build-command', command(source), *flags],
                cwd=directory, text=True, capture_output=True, timeout=30,
                env={**os.environ, 'HYGIENE_SENTINEL': 'kept', 'FORCE_COLOR': '1'},
            )

    def test_baseline_failure_passes(self):
        result = self.run_feature('\x1b[31mFAIL tests/net.test.ts > binds localhost\x1b[0m',
                                  '--baseline-failures', 'binds localhost')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('OK: build failed only on baseline failures (1 lines matched baseline)', result.stdout)
        self.assertNotIn('\x1b', result.stdout)

    def test_new_failure_fails(self):
        result = self.run_feature('FAIL tests/new.test.ts > new thing', '--baseline-failures', 'binds localhost')
        self.assertEqual(result.returncode, 1)
        self.assertIn('NEW failures', result.stdout)
        self.assertIn('FAIL tests/new.test.ts > new thing', result.stdout)

    def test_without_baseline_failure_still_fails(self):
        result = self.run_feature('FAIL tests/net.test.ts > binds localhost')
        self.assertEqual(result.returncode, 1)
        self.assertIn('FAIL: build/test command failed', result.stdout)

    def test_mystery_failure_never_passes(self):
        result = self.run_feature('unrecognized crash', '--baseline-failures', 'unrecognized')
        self.assertEqual(result.returncode, 1)
        self.assertIn('no extractable failure lines', result.stdout)
        self.assertIn('unrecognized crash', result.stdout)

    def test_multiple_baseline_separators_and_custom_regex(self):
        # Baseline entries must be >= 6 chars (too-short entries whitelist unrelated failures).
        result = self.run_feature('broken: alpha-one\nbroken: beta-two\nbroken: gamma-three',
                                  '--baseline-failures', 'alpha-one,beta-two\ngamma-three',
                                  '--failure-line-regex', r'(?m)^broken:.*$')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('3 lines matched baseline', result.stdout)

    def test_mixed_failures_report_only_new_lines_up_to_twenty(self):
        output = 'FAIL known-red\n' + '\n'.join(f'FAIL new-{i}' for i in range(25))
        result = self.run_feature(output, '--baseline-failures', 'known-red')
        self.assertEqual(result.returncode, 1)
        reported = result.stdout.split('NEW failures:\n', 1)[1].splitlines()
        self.assertEqual(reported, [f'FAIL new-{i}' for i in range(20)])

    def test_invalid_regex_fails_cleanly(self):
        result = self.run_feature('FAIL known-red', '--baseline-failures', 'known-red', '--failure-line-regex', '[')
        self.assertEqual(result.returncode, 1)
        self.assertIn('not valid regex', result.stdout)
        self.assertNotIn('Traceback', result.stderr)

    def test_successful_build_output_is_clean(self):
        result = self.run_feature('\x1b[32mall passed\x1b[0m', exit_code=0)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn('\x1b', result.stdout)
        self.assertIn('all passed', result.stdout)


if __name__ == '__main__':
    unittest.main()
