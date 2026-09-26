from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECK_PATH = ROOT / "templates" / "probe" / "checks" / "probe_check.py"


def load_check():
    spec = importlib.util.spec_from_file_location("probe_check_modes", CHECK_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {CHECK_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


probe_check = load_check()


class ProbeCheckModeTests(unittest.TestCase):
    def test_api_accepts_markdown_headings(self) -> None:
        transcript = "## Observed Behavior\nAPI returned the expected marker.\n\n## Verdict\nPass.\n"
        failures: list[str] = []

        probe_check.validate_api(transcript, "HTTP_STATUS: 200\nEXPECTED_MARKER", failures)

        self.assertEqual(failures, [])

    def test_api_still_accepts_colon_labels(self) -> None:
        transcript = "OBSERVED BEHAVIOR: API returned the expected marker.\n\nVERDICT: Pass.\n"
        failures: list[str] = []

        probe_check.validate_api(transcript, "HTTP_STATUS: 200\nEXPECTED_MARKER", failures)

        self.assertEqual(failures, [])

    def test_section_headings_allow_level_number_case_and_trailing_colon(self) -> None:
        transcript = "### 2. vErDiCt:\nPass.\n"

        self.assertEqual(probe_check.has_section(transcript, "Verdict"), "Pass.")

    def test_api_missing_sections_names_both_accepted_forms(self) -> None:
        failures: list[str] = []

        probe_check.validate_api("No structured findings.\n", "HTTP_STATUS: 200", failures)

        self.assertIn(
            'missing Observed Behavior — write a "## Observed Behavior" heading or a '
            '"OBSERVED BEHAVIOR:" label',
            failures,
        )
        self.assertIn(
            'missing Verdict — write a "## Verdict" heading or a "VERDICT:" label',
            failures,
        )

    def test_postmortem_accepts_markdown_headings(self) -> None:
        transcript = """\
## Failure Observed
The worker failed validation.
## Evidence
The checker reported the missing section.
## Likely Cause
The documented format was not recognized.
## Next Check
Run the focused tests.
## Verdict
The checker needs to accept headings.
"""
        failures: list[str] = []

        probe_check.validate_postmortem(transcript, failures)

        self.assertEqual(failures, [])

    def test_postmortem_still_accepts_colon_labels(self) -> None:
        transcript = """\
FAILURE OBSERVED:
The worker failed validation.
EVIDENCE:
The checker reported the missing section.
LIKELY CAUSE:
The documented format was not recognized.
NEXT CHECK:
Run the focused tests.
VERDICT:
The checker needs to accept headings.
"""
        failures: list[str] = []

        probe_check.validate_postmortem(transcript, failures)

        self.assertEqual(failures, [])

    def test_postmortem_missing_sections_names_both_accepted_forms(self) -> None:
        failures: list[str] = []

        probe_check.validate_postmortem("No structured findings.\n", failures)

        expected_names = (
            "Failure Observed",
            "Evidence",
            "Likely Cause",
            "Next Check",
            "Verdict",
        )
        self.assertEqual(len(failures), len(expected_names))
        for name in expected_names:
            with self.subTest(name=name):
                self.assertIn(
                    f'missing {name} — write a "## {name}" heading or a '
                    f'"{name.upper()}:" label',
                    failures,
                )


if __name__ == "__main__":
    unittest.main()
