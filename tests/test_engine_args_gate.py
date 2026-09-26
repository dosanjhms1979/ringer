#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import shutil
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ringer import (  # noqa: E402
    AppConfig,
    ArtifactConfig,
    EngineConfig,
    EvalConfig,
    Manifest,
    RingerRunner,
    engine_args_full_access_error,
    lint_manifest,
)


LONG_SPEC = (
    "Create the requested artifact in the current working directory, keep the change scoped, "
    "and make the check command able to explain any failure clearly."
)

GOOD_CHECK = (
    "test -s output.txt && grep -q 'ready' output.txt || "
    "{ echo 'FAIL: output.txt missing or does not contain ready'; exit 1; }"
)

BYPASS = "--dangerously-bypass-approvals-and-sandbox"


def gated_engine(bin_path: str = "codex") -> EngineConfig:
    return EngineConfig(
        name="codex",
        bin=bin_path,
        args_template=("exec", "{access_args}", "{engine_args}", "{spec}"),
        full_access_args=(BYPASS,),
        sandbox_args=("--sandbox", "workspace-write"),
        token_regex=None,
    )


class EngineArgsGateTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def config(self, *, allow_full_access: bool, engine: EngineConfig) -> AppConfig:
        return AppConfig(
            path=None,
            identity_default=None,
            state_dir=self.root / "state",
            dashboard_port_base=8787,
            hud_port=8700,
            hud_app_path=None,
            allow_full_access=allow_full_access,
            eval=EvalConfig(backend="jsonl", jsonl_path=self.root / "eval.jsonl"),
            engines={"codex": engine},
            artifact=ArtifactConfig(
                enabled=False,
                out_template=str(self.root / "live.html"),
                report_template=str(self.root / "report.html"),
                index_out=self.root / "index.html",
            ),
        )

    def manifest(self, *, engine_args: list[str], full_access: bool = False) -> Manifest:
        return Manifest.from_obj(
            {
                "run_name": "engine-args-gate",
                "workdir": str(self.root / "work"),
                "tasks": [
                    {
                        "key": "a",
                        "engine": "codex",
                        "spec": LONG_SPEC,
                        "check": GOOD_CHECK,
                        "expect_files": ["output.txt"],
                        "verified": "output exists with expected content",
                        "engine_args": engine_args,
                        "full_access": full_access,
                    }
                ],
            }
        )

    def run_worker(self, manifest: Manifest, config: AppConfig):
        runner = RingerRunner(manifest, config=config, identity="tester", dashboard_enabled=False)
        runtime = runner.runtimes[0]
        runtime.taskdir.mkdir(parents=True, exist_ok=True)
        runtime.log_path.parent.mkdir(parents=True, exist_ok=True)
        result = asyncio.run(runner._run_worker(runtime, runtime.task.spec, 1))
        return runtime, result

    def test_engine_full_access_token_is_refused_when_not_allowed(self) -> None:
        manifest = self.manifest(engine_args=[BYPASS])
        config = self.config(allow_full_access=False, engine=gated_engine())
        runtime, result = self.run_worker(manifest, config)
        self.assertIsNotNone(result.error)
        self.assertIn(BYPASS, result.error)
        self.assertIn("allow_full_access", result.error)
        self.assertFalse(runtime.last_worker_command)

    def test_denylist_prefix_is_refused_even_with_task_full_access(self) -> None:
        # Task asks for full access but the config does not allow it.
        manifest = self.manifest(engine_args=["--yolo"], full_access=True)
        task = manifest.tasks[0]
        error = engine_args_full_access_error(task, gated_engine(), allow_full_access=False)
        self.assertIsNotNone(error)
        self.assertIn("--yolo", error)
        # Denylist applies even for an engine that is not in the config.
        task = replace(task, full_access=False)
        self.assertIsNotNone(engine_args_full_access_error(task, None, allow_full_access=True))

    def test_sandbox_args_and_ordinary_flags_pass(self) -> None:
        manifest = self.manifest(engine_args=["-c", "model_reasoning_effort=high", "--sandbox"])
        error = engine_args_full_access_error(
            manifest.tasks[0], gated_engine(), allow_full_access=False
        )
        self.assertIsNone(error)

    def test_engine_full_access_token_passes_when_task_and_config_allow(self) -> None:
        true_bin = shutil.which("true")
        if true_bin is None:
            self.skipTest("no 'true' binary on PATH")
        manifest = self.manifest(engine_args=[BYPASS], full_access=True)
        config = self.config(allow_full_access=True, engine=gated_engine(true_bin))
        runtime, result = self.run_worker(manifest, config)
        self.assertIsNone(result.error)
        self.assertIn(BYPASS, runtime.last_worker_command)

    def test_lint_reports_engine_args_full_access(self) -> None:
        manifest = self.manifest(engine_args=[BYPASS])
        findings = lint_manifest(manifest, allow_noncanonical_route=True)
        self.assertTrue(
            any("engine_args_full_access" in finding and BYPASS in finding for finding in findings),
            findings,
        )
        config = self.config(allow_full_access=False, engine=gated_engine())
        findings = lint_manifest(manifest, config=config, allow_noncanonical_route=True)
        self.assertTrue(any("engine_args_full_access" in finding for finding in findings), findings)

    def test_lint_is_quiet_without_full_access_tokens(self) -> None:
        manifest = self.manifest(engine_args=["-c", "model_reasoning_effort=high"])
        findings = lint_manifest(manifest, allow_noncanonical_route=True)
        self.assertFalse(any("engine_args_full_access" in finding for finding in findings), findings)


if __name__ == "__main__":
    unittest.main()
