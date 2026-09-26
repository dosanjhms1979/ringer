#!/usr/bin/env python3
"""Attempt annotations: void orchestrator-caused attempts without touching runs.jsonl."""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import ringer  # noqa: E402
from ringer import (  # noqa: E402
    AppConfig,
    ArtifactConfig,
    EvalConfig,
    aggregate_model_log_rows,
    aggregate_model_scoreboard_rows,
    apply_annotations,
    eval_annotations_path,
    load_annotations,
    read_model_log_rows,
    run_annotate_command,
    run_models_command,
)

MODEL = "openrouter/z-ai/glm-5.2"
OTHER_MODEL = "openrouter/other/model"
REASON = "check regex could not match honest output; orchestrator defect"


def attempt(
    *,
    run_id: str,
    task_key: str,
    verdict: str,
    retry: bool,
    logged_at: str,
    model: str = MODEL,
    task_type: str = "code-feature",
) -> dict[str, object]:
    return {
        "run_id": run_id,
        "task_key": task_key,
        "worker_engine": "opencode",
        "model": model,
        "task_type": task_type,
        "verdict": verdict,
        "retry": retry,
        "worker_tokens": 1000,
        "duration_ms": 100,
        "orchestrator": "tester",
        "logged_at": logged_at,
    }


def fixture_rows() -> list[dict[str, object]]:
    return [
        # task A: attempt 1 FAIL (defective check), attempt 2 PASS
        attempt(run_id="run-1", task_key="alpha", verdict="FAIL", retry=False, logged_at="2026-09-01T10:00:00+00:00"),
        attempt(run_id="run-1", task_key="alpha", verdict="PASS", retry=True, logged_at="2026-09-01T10:05:00+00:00"),
        # task B: first-try PASS
        attempt(run_id="run-1", task_key="beta", verdict="PASS", retry=False, logged_at="2026-09-01T10:10:00+00:00"),
        # task C: FAIL then FAIL (quota wall on both) — the whole task is void-able
        attempt(run_id="run-2", task_key="gamma", verdict="FAIL", retry=False, logged_at="2026-09-02T09:00:00+00:00"),
        attempt(run_id="run-2", task_key="gamma", verdict="FAIL", retry=True, logged_at="2026-09-02T09:05:00+00:00"),
        # task D: another model, untouched control
        attempt(run_id="run-3", task_key="delta", verdict="PASS", retry=False, logged_at="2026-09-03T09:00:00+00:00", model=OTHER_MODEL),
    ]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class AnnotationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.old_env = os.environ.copy()
        self.addCleanup(self.restore_env)
        # Keep every implicit path (HOME, RINGER_HOME, identity env) inside the temp dir.
        os.environ["HOME"] = str(self.root / "home")
        os.environ["RINGER_HOME"] = str(self.root / "ringer-home")
        os.environ.pop("FLEET_IDENTITY", None)
        os.environ.pop("RINGER_IDENTITY", None)
        self.state_dir = self.root / "state"
        self.state_dir.mkdir()
        self.log_path = self.state_dir / "runs.jsonl"
        self.log_path.write_text(
            "".join(json.dumps(row) + "\n" for row in fixture_rows()), encoding="utf-8"
        )
        self.log_digest = sha256(self.log_path)
        self.registry_path = self.root / "registry.json"
        self.registry_path.write_text(json.dumps({"engines": {}, "models": {}}), encoding="utf-8")
        self.notes_path = self.root / "MODEL-NOTES.md"
        self.notes_path.write_text("# notes\n", encoding="utf-8")
        self.catalog_path = self.root / "catalog.json"
        self.config = AppConfig(
            path=None,
            identity_default="unit-tester",
            state_dir=self.state_dir,
            dashboard_port_base=8787,
            hud_port=8700,
            hud_app_path=None,
            allow_full_access=False,
            eval=EvalConfig(backend="jsonl", jsonl_path=self.log_path),
            engines={},
            artifact=ArtifactConfig(
                enabled=True,
                out_template=str(self.root / "live.html"),
                report_template=str(self.root / "report.html"),
                index_out=self.root / "index.html",
            ),
        )
        self.annotations_path = eval_annotations_path(self.config)

    def restore_env(self) -> None:
        os.environ.clear()
        os.environ.update(self.old_env)

    def annotate_args(self, **overrides: object) -> argparse.Namespace:
        values: dict[str, object] = {
            "run_id": None,
            "task": None,
            "attempt": None,
            "kind": None,
            "reason": None,
            "identity": None,
            "list": False,
            "json": False,
            "remove": None,
            "log": None,
            "annotations_file": None,
        }
        values.update(overrides)
        return argparse.Namespace(**values)

    def models_args(self, **overrides: object) -> argparse.Namespace:
        values: dict[str, object] = {
            "log": self.log_path,
            "db": self.root / "unused.db",
            "task_type": None,
            "model": None,
            "engine": None,
            "since": None,
            "explore": False,
            "catalog_file": self.catalog_path,
            "notes_file": self.notes_path,
            "registry": self.registry_path,
            "html": None,
            "open": False,
            "json": False,
        }
        values.update(overrides)
        return argparse.Namespace(**values)

    def run_annotate(self, **overrides: object) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = run_annotate_command(self.config, self.annotate_args(**overrides))
        return code, out.getvalue(), err.getvalue()

    def models_json(self) -> list[dict[str, object]]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(0, run_models_command(self.config, self.models_args(json=True)))
        return json.loads(out.getvalue())

    def group(self, groups: list[dict[str, object]], model: str = MODEL) -> dict[str, object]:
        return next(item for item in groups if item["model"] == model)

    def assert_log_untouched(self) -> None:
        self.assertEqual(self.log_digest, sha256(self.log_path), "runs.jsonl bytes changed")

    # (a) append + list ----------------------------------------------------
    def test_annotate_appends_well_formed_row_and_list_shows_it(self) -> None:
        self.assertEqual((self.state_dir / "annotations.jsonl").resolve(), self.annotations_path)
        code, out, err = self.run_annotate(
            run_id="run-1", task="alpha", attempt=1, kind="check_defect", reason=REASON, identity="kiran"
        )
        self.assertEqual(0, code, err)
        self.assertIn("voided run-1/alpha#1 as check_defect", out)
        lines = self.annotations_path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(1, len(lines))
        row = json.loads(lines[0])
        self.assertEqual(
            {"run_id", "task_key", "attempt", "kind", "reason", "annotated_by", "annotated_at"},
            set(row),
        )
        self.assertEqual("run-1", row["run_id"])
        self.assertEqual("alpha", row["task_key"])
        self.assertEqual(1, row["attempt"])
        self.assertEqual("check_defect", row["kind"])
        self.assertEqual(REASON, row["reason"])
        self.assertEqual("kiran", row["annotated_by"])
        self.assertRegex(row["annotated_at"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+00:00$")

        code, out, _err = self.run_annotate(list=True)
        self.assertEqual(0, code)
        self.assertIn("run-1/alpha#1", out)
        self.assertIn("check_defect", out)
        self.assertIn(REASON, out)

        code, out, _err = self.run_annotate(list=True, json=True, run_id="run-1")
        self.assertEqual(0, code)
        listed = json.loads(out)
        self.assertEqual(1, len(listed))
        self.assertEqual("alpha", listed[0]["task_key"])
        code, out, _err = self.run_annotate(list=True, json=True, run_id="run-9")
        self.assertEqual([], json.loads(out))
        self.assert_log_untouched()

    def test_identity_falls_back_to_config_default(self) -> None:
        code, _out, err = self.run_annotate(
            run_id="run-1", task="alpha", attempt=1, kind="quota", reason=REASON
        )
        self.assertEqual(0, code, err)
        row = json.loads(self.annotations_path.read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual("unit-tester", row["annotated_by"])

    # (b) refusals -----------------------------------------------------------
    def test_short_reason_is_refused(self) -> None:
        code, _out, err = self.run_annotate(
            run_id="run-1", task="alpha", attempt=1, kind="check_defect", reason="too short"
        )
        self.assertNotEqual(0, code)
        self.assertIn("at least 20 characters", err)
        self.assertFalse(self.annotations_path.exists())
        # Whitespace padding does not count.
        code, _out, err = self.run_annotate(
            run_id="run-1", task="alpha", attempt=1, kind="check_defect", reason="short" + " " * 30
        )
        self.assertNotEqual(0, code)
        self.assertFalse(self.annotations_path.exists())
        self.assert_log_untouched()

    def test_unknown_target_is_refused(self) -> None:
        code, _out, err = self.run_annotate(
            run_id="run-404", task="alpha", kind="check_defect", reason=REASON
        )
        self.assertEqual(1, code)
        self.assertIn("run_id 'run-404' is not in", err)
        code, _out, err = self.run_annotate(
            run_id="run-1", task="nope", kind="check_defect", reason=REASON
        )
        self.assertEqual(1, code)
        self.assertIn("task 'nope' is not in run 'run-1'", err)
        code, _out, err = self.run_annotate(
            run_id="run-1", task="alpha", attempt=3, kind="check_defect", reason=REASON
        )
        self.assertEqual(1, code)
        self.assertIn("has 2 attempt(s); attempt 3 does not exist", err)
        code, _out, err = self.run_annotate(run_id="run-1", task="alpha", kind="check_defect")
        self.assertEqual(2, code)
        self.assertIn("--reason", err)
        self.assertFalse(self.annotations_path.exists())
        self.assert_log_untouched()

    # (c) first-try flips after voiding attempt 1 -----------------------------
    def test_voiding_attempt_one_promotes_retry_to_first_try(self) -> None:
        rows, _skipped = read_model_log_rows(self.log_path)
        before_groups = self.group(aggregate_model_log_rows(rows))
        before_rollup = self.group(aggregate_model_scoreboard_rows(rows))
        # alpha (first FAIL), beta (first PASS), gamma (first FAIL): 1/3 first-try.
        self.assertEqual(3, before_groups["tasks"])
        self.assertAlmostEqual(1 / 3, before_groups["first_try_pass_rate"])
        self.assertAlmostEqual(1 / 3, before_rollup["first_try_pass_rate"])
        self.assertEqual(0, before_groups["voided_attempts"])
        self.assertEqual(5, before_groups["attempts"])

        code, _out, err = self.run_annotate(
            run_id="run-1", task="alpha", attempt=1, kind="check_defect", reason=REASON
        )
        self.assertEqual(0, code, err)
        annotations = load_annotations(self.annotations_path)
        self.assertEqual(1, len(annotations))

        survivors, voided = apply_annotations(rows, annotations)
        self.assertEqual(1, len(voided))
        self.assertEqual("FAIL", voided[0]["verdict"])
        alpha = [row for row in survivors if row["task_key"] == "alpha"]
        self.assertEqual(1, len(alpha))
        self.assertIs(False, alpha[0]["retry"], "earliest survivor must become the first try")
        # Input rows are never mutated.
        self.assertIs(True, rows[1]["retry"])

        after_groups = self.group(aggregate_model_log_rows(rows, annotations=annotations))
        after_rollup = self.group(aggregate_model_scoreboard_rows(rows, annotations=annotations))
        self.assertEqual(3, after_groups["tasks"])
        self.assertAlmostEqual(2 / 3, after_groups["first_try_pass_rate"])
        self.assertAlmostEqual(2 / 3, after_rollup["first_try_pass_rate"])
        self.assertEqual(4, after_groups["attempts"])
        self.assertEqual(1, after_groups["voided_attempts"])
        self.assertEqual(1, after_rollup["voided_attempts"])
        self.assertEqual(1, after_rollup["task_types"][0]["voided_attempts"])
        self.assertEqual("proven", after_rollup["tier"])
        self.assertEqual("probation", before_rollup["tier"])
        # Control model is untouched.
        control = self.group(aggregate_model_scoreboard_rows(rows, annotations=annotations), OTHER_MODEL)
        self.assertEqual(0, control["voided_attempts"])
        self.assertEqual(1, control["tasks"])
        self.assert_log_untouched()

    # (d) fully voided task contributes nothing -------------------------------
    def test_task_with_every_attempt_voided_is_excluded(self) -> None:
        rows, _skipped = read_model_log_rows(self.log_path)
        code, _out, err = self.run_annotate(
            run_id="run-2", task="gamma", kind="quota", reason="HTTP 429 quota wall on both attempts, harness never ran the model"
        )
        self.assertEqual(0, code, err)
        annotations = load_annotations(self.annotations_path)
        self.assertIsNone(annotations[0]["attempt"])
        after = self.group(aggregate_model_log_rows(rows, annotations=annotations))
        self.assertEqual(2, after["tasks"])
        self.assertEqual(3, after["attempts"])
        self.assertEqual(2, after["voided_attempts"])
        self.assertAlmostEqual(1 / 2, after["first_try_pass_rate"])
        rollup = self.group(aggregate_model_scoreboard_rows(rows, annotations=annotations))
        self.assertEqual(2, rollup["tasks"])
        self.assertEqual(2, rollup["voided_attempts"])
        self.assert_log_untouched()

    # (e) retract -----------------------------------------------------------
    def test_remove_appends_retract_and_restores_counts(self) -> None:
        rows, _skipped = read_model_log_rows(self.log_path)
        self.assertEqual(0, self.run_annotate(run_id="run-1", task="alpha", attempt=1, kind="check_defect", reason=REASON)[0])
        self.assertEqual(0, self.run_annotate(run_id="run-2", task="gamma", kind="quota", reason=REASON)[0])
        self.assertEqual(2, len(load_annotations(self.annotations_path)))

        code, out, err = self.run_annotate(remove=["run-1", "alpha"], attempt=1)
        self.assertEqual(0, code, err)
        self.assertIn("retracted 1 annotation(s)", out)
        lines = self.annotations_path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(3, len(lines), "append-only: retract is a new row, nothing rewritten")
        retract = json.loads(lines[-1])
        self.assertEqual("retract", retract["kind"])
        self.assertEqual("run-1", retract["run_id"])
        self.assertEqual(1, retract["attempt"])

        active = load_annotations(self.annotations_path)
        self.assertEqual(["gamma"], [row["task_key"] for row in active])
        after = self.group(aggregate_model_log_rows(rows, annotations=active))
        self.assertAlmostEqual(1 / 2, after["first_try_pass_rate"])  # alpha FAIL, beta PASS
        self.assertEqual(2, after["voided_attempts"])

        # Retracting something that is not annotated is refused, nothing appended.
        code, _out, err = self.run_annotate(remove=["run-1", "beta"])
        self.assertEqual(1, code)
        self.assertIn("nothing to retract", err)
        self.assertEqual(3, len(self.annotations_path.read_text(encoding="utf-8").splitlines()))

        # A task-wide retract cancels a task-wide annotation.
        self.assertEqual(0, self.run_annotate(remove=["run-2", "gamma"])[0])
        self.assertEqual([], load_annotations(self.annotations_path))
        self.assert_log_untouched()

    # (f) surfaces ------------------------------------------------------------
    def test_voided_attempts_in_models_json_and_html(self) -> None:
        before = self.group(self.models_json())
        self.assertIn("voided_attempts", before)
        self.assertEqual(0, before["voided_attempts"])
        self.assertEqual(0, self.run_annotate(run_id="run-1", task="alpha", attempt=1, kind="harness", reason=REASON)[0])
        after = self.group(self.models_json())
        self.assertEqual(1, after["voided_attempts"])
        self.assertAlmostEqual(2 / 3, after["first_try_pass_rate"])

        html_path = self.root / "scoreboard.html"
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(0, run_models_command(self.config, self.models_args(html=str(html_path))))
        html = html_path.read_text(encoding="utf-8")
        self.assertIn("Voided", html)
        self.assertIn('class="num voided-cell">1<', html)
        self.assertIn("1 attempt(s) excluded from tiers", html)

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(0, run_models_command(self.config, self.models_args()))
        text = out.getvalue()
        self.assertIn("Voided", text)
        self.assertIn("Voided: 1 attempt(s) excluded from tiers", text)
        self.assert_log_untouched()

    def test_hud_payload_applies_annotations_beside_log(self) -> None:
        self.assertEqual(0, self.run_annotate(run_id="run-1", task="alpha", attempt=1, kind="check_defect", reason=REASON)[0])
        payload = ringer.build_models_api_payload(
            log_path=self.log_path,
            default_log_path=self.root / "elsewhere.jsonl",
            registry_path=self.registry_path,
            notes_path=self.notes_path,
            catalog_path=self.catalog_path,
        )
        self.assertIn("Voided", payload["columns"])
        self.assertEqual(1, self.group(payload["rollup"])["voided_attempts"])

    # (g) runs.jsonl never changes; no annotations => no-op ------------------
    def test_no_annotations_is_a_no_op_and_log_is_never_written(self) -> None:
        rows, _skipped = read_model_log_rows(self.log_path)
        survivors, voided = apply_annotations(rows, load_annotations(self.annotations_path))
        self.assertEqual(rows, survivors)
        self.assertEqual([], voided)
        self.assertEqual(aggregate_model_log_rows(rows), aggregate_model_log_rows(rows, annotations=[]))
        self.assert_log_untouched()

    def test_cli_help_mentions_reason(self) -> None:
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit) as raised:
            ringer.build_parser().parse_args(["annotate", "--help"])
        self.assertEqual(0, raised.exception.code)
        self.assertIn("--reason", out.getvalue())
        self.assertIn("--kind {check_defect,quota,harness}", out.getvalue())


if __name__ == "__main__":
    unittest.main()
