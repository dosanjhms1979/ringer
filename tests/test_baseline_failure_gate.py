#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

HARDENING = ROOT / "templates/test-hardening/checks/test_hardening_check.py"
FEATURE = ROOT / "templates/repo-feature/checks/check_repo_feature.py"

MATCHING = [
    "  ✗ binds localhost",
    "× recovers thing",
    "Error: boom",
    "AssertionError: expected 1",
    "FAIL tests/a.test.ts > x",
    "FAILED tests/test_x.py::test_y",
    "not ok 3 - thing",
    "--- FAIL: TestX",
    "● Suite › case",
]
NON_MATCHING = ["Tests 3 passed", "✓ ok"]


def load(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def default_regex(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    match = re.search(r'"--failure-line-regex", default=(r"(?:[^"\\]|\\.)*")', text)
    return eval(match.group(1))


class DefaultRegexTests(unittest.TestCase):
    def test_default_regex_both_scripts(self) -> None:
        for path in (HARDENING, FEATURE):
            load(path)
            pattern = re.compile(default_regex(path))
            for line in MATCHING:
                self.assertIsNotNone(pattern.search(line), f"{path.name}: {line!r}")
                self.assertEqual(pattern.search(line).group(0), line)
            for line in NON_MATCHING:
                self.assertIsNone(pattern.search(line), f"{path.name}: {line!r}")

    def test_defaults_identical(self) -> None:
        self.assertEqual(default_regex(HARDENING), default_regex(FEATURE))


class HardeningEndToEndTests(unittest.TestCase):
    def run_check(self, baseline: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            git = lambda *a: subprocess.run(["git", *a], cwd=repo, check=True, capture_output=True)
            git("init", "-q")
            (repo / "base.txt").write_text("x\n")
            git("add", "-A")
            git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init")
            (repo / "t_new.test.js").write_text("expect(1)\nexpect(2)\n")
            (repo / "runner.sh").write_text("echo '  ✗ binds localhost'\necho 'Tests 1 failed | 2 passed'\nexit 1\n")
            return subprocess.run(
                [
                    sys.executable, str(HARDENING),
                    "--task-key", "k",
                    "--test-command", "sh runner.sh",
                    "--baseline-failures", baseline,
                    "--baseline-test-count", "1",
                    "--test-count-regex", "AUTO",
                    "--new-test-files", "t_new.test.js",
                    "--owned-test-files", "t_new.test.js,runner.sh",
                    "--forbidden-paths", "src/",
                    "--assertion-pattern", r"expect\(",
                    "--min-assertions-per-file", "1",
                    "--min-assertion-density", "0.1",
                    "--export-patch", str(Path(tmp) / "out.patch"),
                ],
                cwd=repo, text=True, capture_output=True, check=False,
            )

    def test_matching_baseline_passes(self) -> None:
        proc = self.run_check("binds localhost")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_short_baseline_rejected(self) -> None:
        proc = self.run_check("x")
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("too short", proc.stdout)

    def test_dot_baseline_rejected(self) -> None:
        proc = self.run_check(".")
        self.assertEqual(proc.returncode, 1, proc.stdout)


if __name__ == "__main__":
    unittest.main()
