"""Hermetic regression coverage for the test-hardening baseline gate."""

import importlib.util
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SCRIPT = ROOT / "templates/test-hardening/checks/test_hardening_check.py"
SPEC = importlib.util.spec_from_file_location("test_hardening_check", SCRIPT)
CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK)


class TestHardeningBaselineTests(unittest.TestCase):
    def run_check(self, baseline=None, *, count=1, failure="\x1b[31mFAIL old_test\x1b[0m", regex=None):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo = root / "repo"
            repo.mkdir()
            env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
            env.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull})

            def git(*args):
                subprocess.run(["git", *args], cwd=repo, env=env, check=True, capture_output=True)

            git("init")
            test_file = repo / "test_example.py"
            test_file.write_text("assert True\n", encoding="utf-8")
            git("add", "test_example.py")
            git("-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                "-c", "commit.gpgsign=false", "commit", "-m", "fixture")
            test_file.write_text("assert True\nassert 1 == 1\n", encoding="utf-8")
            command = shlex.join([sys.executable, "-c", f"print('Tests  2 passed'); print({failure!r}); raise SystemExit(1)"])
            args = [
                sys.executable, str(SCRIPT), "--task-key", "baseline-test",
                "--test-command", command, "--baseline-test-count", str(count),
                "--test-count-regex", "AUTO", "--new-test-files", "test_example.py",
                "--owned-test-files", "test_example.py", "--forbidden-paths", "src",
                "--assertion-pattern", r"\bassert\b", "--min-assertions-per-file", "1",
                "--min-assertion-density", "0.1", "--export-patch", str(root / "result.patch"),
            ]
            if baseline is not None:
                args.extend(["--baseline-failures", baseline])
            if regex is not None:
                args.extend(["--failure-line-regex", regex])
            return subprocess.run(args, cwd=repo, env=env, capture_output=True, text=True, check=False)

    def test_matching_baseline_passes_with_increased_count(self):
        result = self.run_check("old_test")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("OK: tests failed only on baseline failures (1 lines matched baseline)", result.stdout)
        self.assertIn("OK: test count increased from 1 to 2", result.stdout)

    def test_new_failure_is_rejected(self):
        result = self.run_check("different_test")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("NEW failures", result.stdout)
        self.assertIn("FAIL old_test", result.stdout)

    def test_no_baseline_is_rejected(self):
        result = self.run_check()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("no --baseline-failures", result.stdout)

    def test_baseline_does_not_bypass_count_increase(self):
        result = self.run_check("old_test", count=2)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("test count did not increase", result.stdout)

    def test_missing_failure_lines_is_rejected_with_output(self):
        result = self.run_check("old_test", failure="old_test crashed")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("no extractable failure lines", result.stdout)
        self.assertIn("old_test crashed", result.stdout)

    def test_comma_and_newline_baselines(self):
        result = self.run_check("other_test, old_test\nsecond_test", failure="FAIL old_test\nFAIL second_test")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("2 lines matched baseline", result.stdout)

    def test_custom_failure_regex(self):
        result = self.run_check("old_test", failure="BROKEN old_test", regex=r"(?m)^BROKEN .*$")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_invalid_failure_regex_is_rejected(self):
        result = self.run_check("old_test", regex="[")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("--failure-line-regex is not valid regex", result.stdout)


if __name__ == "__main__":
    unittest.main()
