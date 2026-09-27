#!/usr/bin/env python3
"""Template substitutions must not alter text inserted from a task spec."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ringer import EngineConfig, build_worker_command  # noqa: E402


def command_for(args_template: tuple[str, ...], spec: str, model: str = "gpt-x") -> list[str]:
    engine = EngineConfig(
        name="test",
        bin="worker",
        args_template=args_template,
        full_access_args=(),
        sandbox_args=(),
        model_default="m0",
    )
    return build_worker_command(
        engine, taskdir=Path("/t"), spec=spec, full_access=False, model=model
    )


class WorkerCommandPlaceholderTests(unittest.TestCase):
    def test_model_name_in_spec_stays_verbatim(self) -> None:
        spec = "set {model} in args_template"
        self.assertEqual(["worker", spec], command_for(("{spec}",), spec))

    def test_placeholders_in_spec_stay_verbatim(self) -> None:
        spec = "document {taskdir}, {spec}, and {model}"
        self.assertEqual(["worker", spec], command_for(("{spec}",), spec))

    def test_taskdir_expands_inside_template_item(self) -> None:
        self.assertEqual(
            ["worker", "--dir=/t", "brief"],
            command_for(("--dir={taskdir}", "{spec}"), "brief"),
        )

    def test_model_tokens_expand_in_template_item(self) -> None:
        self.assertEqual(
            ["worker", "gpt-x", "-mgpt-x"],
            command_for(("{model}", "-m{model}"), "brief"),
        )
        self.assertEqual(
            ["worker", "m0", "-mm0"],
            command_for(("{model}", "-m{model}"), "brief", model=""),
        )

    def test_engine_args_placeholder_in_spec_stays_verbatim(self) -> None:
        spec = "keep {engine_args} literal"
        self.assertEqual(["worker", spec], command_for(("{spec}",), spec))

    def test_unknown_braces_pass_through(self) -> None:
        self.assertEqual(
            ["worker", "{other}", "brief"],
            command_for(("{other}", "{spec}"), "brief"),
        )


if __name__ == "__main__":
    unittest.main()
