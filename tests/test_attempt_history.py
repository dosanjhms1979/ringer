from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ringer import build_failure_context


ROOT = Path(__file__).resolve().parents[1]


class FailureContextTests(unittest.TestCase):
    def test_check_precedes_long_worker_tail(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "worker.log"
            log.write_text("worker noise " * 1000 + "final worker line", encoding="utf-8")
            check = "FAIL: distinct check diagnostic"
            context = build_failure_context(log, check)
            self.assertTrue(context.startswith("CHECK OUTPUT:\n" + check))
            self.assertIn(check, context[:400])
            self.assertLess(context.index(check), context.index("WORKER LOG TAIL:"))
            self.assertTrue(context.endswith("final worker line"))
            self.assertEqual(6000, len(context))

    def test_oversized_check_keeps_its_last_6000_characters(self) -> None:
        check = "discard this prefix" + "diagnostic" * 700
        self.assertEqual(check[-6000:], build_failure_context(Path("missing-worker.log"), check))

    def test_empty_check(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            context = build_failure_context(Path(directory) / "missing.log", "")
            self.assertIsInstance(context, str)
            self.assertTrue(context.startswith("CHECK OUTPUT:"))
            self.assertLessEqual(len(context), 6000)

    def test_check_near_cap_is_preserved(self) -> None:
        for size in (5970, 5990, 6000):
            with self.subTest(size=size):
                check = "x" * size
                context = build_failure_context(Path("missing-worker.log"), check)
                self.assertIn(check, context)
                self.assertLessEqual(len(context), 6000)


class AttemptHistoryTests(unittest.TestCase):
    def test_two_failed_attempts_keep_distinct_check_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state_dir = root / "state"
            config = root / "config.toml"
            quote = lambda value: json.dumps(str(value))
            config.write_text("\n".join([
                f"state_dir = {quote(state_dir)}",
                "[eval]", 'backend = "jsonl"',
                f"jsonl_path = {quote(root / 'runs.jsonl')}",
                "[artifact]", "enabled = false",
                "[engines.mock]", f"bin = {quote(sys.executable)}",
                f"args_template = [{quote(ROOT / 'engines' / 'mock_worker.py')}, \"{{spec}}\"]",
                "sandbox_args = []", "full_access_args = []",
            ]), encoding="utf-8")
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({
                "run_name": "attempt-history-test",
                "workdir": str(root / "work"),
                "max_parallel": 1,
                "worktrees": False,
                "tasks": [{
                    "key": "retry-task", "engine": "mock",
                    "spec": "MOCK_FAIL", "max_attempts": 2,
                    "check": (
                        "if test -f checked-once; then echo FAIL: second attempt; "
                        "else touch checked-once; echo FAIL: first attempt; fi; exit 1"
                    ),
                }],
            }), encoding="utf-8")
            env = os.environ.copy()
            for variable, subdir in (("HOME", "home"), ("RINGER_HOME", "ringer-home"),
                                     ("XDG_CONFIG_HOME", "xdg-config")):
                path = root / subdir
                path.mkdir()
                env[variable] = str(path)
            result = subprocess.run([
                sys.executable, str(ROOT / "ringer.py"), "run", str(manifest),
                "--config", str(config), "--no-dashboard", "--identity", "history-test",
            ], cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(1, result.returncode, result.stdout + result.stderr)
            states = list((state_dir / "runs").glob("*.json"))
            self.assertEqual(1, len(states))
            task = json.loads(states[0].read_text(encoding="utf-8"))["tasks"][0]
            expected = [
                # The tail keeps the check's real line breaks (no whitespace
                # collapsing) and records whether the worker itself timed out.
                {"attempt": attempt, "check_returncode": 1, "check_timed_out": False,
                 "check_output_tail": f"FAIL: {name} attempt\n", "worker_timed_out": False}
                for attempt, name in ((1, "first"), (2, "second"))
            ]
            self.assertEqual(expected, task["attempt_history"])
            for key in ("check_returncode", "check_timed_out", "check_output_tail"):
                self.assertEqual(expected[-1][key], task[key])


if __name__ == "__main__":
    unittest.main()
