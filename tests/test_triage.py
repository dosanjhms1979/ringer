from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from ringer import (RingerRunner, TriageConfig, WorkerResult, VerifyResult,
                    load_triage_config, parse_triage_answer)

ROOT = Path(__file__).resolve().parents[1]
ANSWER = {"cause": {"type": "choice", "choice": "check", "confidence": 0.91,
                    "probabilities": {"model": 0.02, "spec": 0.03, "check": 0.91, "harness": 0.04}}}


@contextlib.contextmanager
def stub(status=200, payload=None, delay=0):
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            requests.append((json.loads(self.rfile.read(int(self.headers["Content-Length"]))),
                             dict(self.headers)))
            time.sleep(delay)
            self.send_response(status)
            self.end_headers()
            with contextlib.suppress(BrokenPipeError):
                self.wfile.write(json.dumps(ANSWER if payload is None else payload).encode())

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/triage", requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


class TriageTests(unittest.TestCase):
    def run_task(self, endpoint, *, enabled=True, key=True, hold=False, attempts=2, timeout=2):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state_dir = root / "state"
            config = root / "config.toml"
            quote = lambda value: json.dumps(str(value))
            config.write_text("\n".join([
                f"state_dir = {quote(state_dir)}",
                "[update]", "auto = false",
                "[eval]", 'backend = "jsonl"',
                f"jsonl_path = {quote(root / 'runs.jsonl')}",
                "[artifact]", "enabled = false",
                "[triage]", f"enabled = {str(enabled).lower()}",
                f"endpoint = {quote(endpoint)}",
                'api_key_env = "RINGER_TEST_TRIAGE_KEY"',
                f"timeout_s = {timeout}",
                'hold_retry_on = ["check"]' if hold else "hold_retry_on = []",
                "[engines.mock]", f"bin = {quote(sys.executable)}",
                f"args_template = [{quote(ROOT / 'engines' / 'mock_worker.py')}, \"{{spec}}\"]",
                "sandbox_args = []", "full_access_args = []",
            ]), encoding="utf-8")
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({
                "run_name": "triage-test", "workdir": str(root / "work"),
                "max_parallel": 1, "worktrees": False,
                "tasks": [{"key": "retry-task", "engine": "mock",
                           "spec": "MOCK_FAIL", "max_attempts": attempts,
                           "check": "echo FAIL: diagnostic; exit 1"}],
            }), encoding="utf-8")
            env = os.environ.copy()
            env["NO_PROXY"] = env["no_proxy"] = "127.0.0.1"
            env.pop("RINGER_TEST_TRIAGE_KEY", None)
            if key:
                env["RINGER_TEST_TRIAGE_KEY"] = "test-secret"
            for variable, subdir in (("HOME", "home"), ("RINGER_HOME", "ringer-home"),
                                     ("XDG_CONFIG_HOME", "xdg-config")):
                path = root / subdir
                path.mkdir()
                env[variable] = str(path)
            result = subprocess.run([
                sys.executable, str(ROOT / "ringer.py"), "run", str(manifest),
                "--config", str(config), "--no-dashboard", "--identity", "triage-test",
            ], cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(1, result.returncode, result.stdout + result.stderr)
            states = list((state_dir / "runs").glob("*.json"))
            self.assertEqual(1, len(states))
            state = json.loads(states[0].read_text())
            log = state_dir / "triage.jsonl"
            rows = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
            return state["tasks"][0], rows, result.stdout, (root / "runs.jsonl").read_text()

    def test_disabled(self):
        self.assertFalse(TriageConfig().enabled)
        with stub() as (endpoint, requests):
            task, rows, _, _ = self.run_task(endpoint, enabled=False)
            self.assertEqual([], requests)
        self.assertEqual(2, len(task["attempt_history"]))
        self.assertTrue(all("triage" not in row for row in task["attempt_history"]))
        self.assertEqual([], rows)

    def test_advisory_answer_and_request(self):
        with stub() as (endpoint, requests):
            task, rows, stdout, logs = self.run_task(endpoint, attempts=3)
        self.assertEqual(3, len(task["attempt_history"]))
        self.assertEqual(1, len(requests))
        body, headers = requests[0]
        self.assertEqual("jev-latest", body["model"])
        self.assertEqual("Bearer test-secret", headers["Authorization"])
        self.assertEqual("application/json", headers["Content-Type"])
        self.assertEqual({"task_key", "engine", "model", "task_type", "spec", "check_command",
                          "check_output", "check_returncode", "check_timed_out",
                          "worker_returncode", "worker_timed_out", "worker_log_tail", "worker_notes"},
                         set(body["state"]))
        self.assertEqual("choice", body["questions"]["cause"]["type"])
        self.assertEqual({"model", "spec", "check", "harness"},
                         set(body["questions"]["cause"]["criteria"]))
        triage = task["attempt_history"][0]["triage"]
        self.assertEqual("check", triage["choice"])
        self.assertEqual(ANSWER["cause"]["probabilities"], triage["probabilities"])
        self.assertEqual(1, len(rows))
        self.assertEqual(triage, rows[0]["triage"])
        self.assertTrue(rows[0]["run_id"])
        self.assertEqual("retry-task", rows[0]["task_key"])
        self.assertEqual(1, rows[0]["attempt"])
        self.assertIn("cause=check (0.91) — retrying", stdout)
        self.assertIn("triage=check", logs)

    def test_http_error(self):
        with stub(status=500) as (endpoint, requests):
            task, _, _, _ = self.run_task(endpoint)
        self.assertEqual(1, len(requests))
        self.assertEqual(2, len(task["attempt_history"]))
        self.assertEqual({"error": "HTTPError"}, task["attempt_history"][0]["triage"])

    def test_missing_key(self):
        with stub() as (endpoint, requests):
            task, _, _, _ = self.run_task(endpoint, key=False)
            self.assertEqual([], requests)
        self.assertEqual(2, len(task["attempt_history"]))
        self.assertEqual({"error": "missing environment variable RINGER_TEST_TRIAGE_KEY"},
                         task["attempt_history"][0]["triage"])

    def test_hold(self):
        with stub(payload={"answers": ANSWER}) as (endpoint, requests):
            task, _, stdout, _ = self.run_task(endpoint, hold=True)
        self.assertEqual(1, len(task["attempt_history"]))
        self.assertTrue(task["attempt_history"][0]["retry_held"])
        self.assertEqual("fail", task["status"])
        self.assertIn("retry HELD", stdout)

    def test_invalid_answer_does_not_hold(self):
        with stub(payload={"cause": {"choice": "check"}}) as (endpoint, requests):
            task, _, _, _ = self.run_task(endpoint, hold=True)
        self.assertEqual(2, len(task["attempt_history"]))
        self.assertEqual({"error"}, set(task["attempt_history"][0]["triage"]))

    def test_timeout_does_not_hold(self):
        with stub(delay=0.3) as (endpoint, requests):
            task, _, _, _ = self.run_task(endpoint, hold=True, timeout=0.05)
        self.assertEqual(2, len(task["attempt_history"]))
        self.assertIn("error", task["attempt_history"][0]["triage"])

    def test_config_garbage(self):
        state_dir = Path("/tmp/triage-test-state")
        defaults = load_triage_config(None, state_dir)
        self.assertFalse(defaults.enabled)
        self.assertEqual(state_dir / "triage.jsonl", defaults.log_path)
        for raw in (None, [], 3, "bad", {"enabled": "yes"}, {"timeout_s": "bad"},
                    {"timeout_s": float("nan")}, {"endpoint": []}, {"log_path": {}},
                    {"hold_retry_on": "check"}):
            with self.subTest(raw=raw):
                self.assertEqual(defaults, load_triage_config(raw, state_dir))
        cfg = load_triage_config({"enabled": True, "hold_retry_on": ["check", "unknown", {}, "harness"]},
                                 state_dir)
        self.assertTrue(cfg.enabled)
        self.assertEqual(("check", "harness"), cfg.hold_retry_on)

    def test_hook_with_mock_transport(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "fix-summary.md").write_text("worker notes")
            (root / "worker.log").write_text("worker output")
            runtime = SimpleNamespace(
                task=SimpleNamespace(key="unit-task", engine="mock", task_type="code",
                                     spec="task spec", check="exit 1"),
                taskdir=root, log_path=root / "worker.log",
                last_worker_command=[], attempt_history=[{"attempt": 1}],
            )
            scheduler = object.__new__(RingerRunner)
            scheduler.config = SimpleNamespace(
                triage=TriageConfig(log_path=root / "triage.jsonl", hold_retry_on=("check",)),
                engines={},
            )
            scheduler.lock = threading.Lock()
            scheduler.run_id = "unit-run"
            worker = WorkerResult(1, False, None, reported_model="worker-model")
            verify = VerifyResult(False, 1, False, "check failed", raw_output_tail="check failed")
            with patch.dict(os.environ, {"TYPESAFE_API_KEY": "unit-secret"}), patch(
                "ringer.urllib.request.urlopen", return_value=io.BytesIO(json.dumps(ANSWER).encode())
            ) as transport:
                scheduler._triage_attempt(runtime, verify, worker, 1)
            request = transport.call_args.args[0]
            body = json.loads(request.data)
            self.assertEqual("worker notes", body["state"]["worker_notes"])
            self.assertEqual("worker output", body["state"]["worker_log_tail"])
            self.assertEqual("worker-model", body["state"]["model"])
            self.assertEqual("Bearer unit-secret", request.get_header("Authorization"))
            self.assertEqual(20.0, transport.call_args.kwargs["timeout"])
            self.assertTrue(runtime.attempt_history[0]["retry_held"])
            row = json.loads((root / "triage.jsonl").read_text())
            self.assertEqual(runtime.attempt_history[0]["triage"], row["triage"])

    def test_parse_nested_answer(self):
        self.assertEqual("check", parse_triage_answer({"answers": ANSWER})["choice"])


if __name__ == "__main__":
    unittest.main()
