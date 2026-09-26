"""Citation gate must follow the evidence label as it was written."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
CHECK_PATH = ROOT / "templates" / "review-swarm" / "checks" / "review-swarm.py"


def load_review_swarm_check():
    spec = importlib.util.spec_from_file_location("review_swarm_check", CHECK_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {CHECK_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def report_text(evidence_line: str) -> str:
    return "\n".join(
        [
            "# Review Report",
            "",
            "## Summary",
            "Lowercase evidence labels still need a file:line citation.",
            "",
            "## Findings",
            "### Finding: lowercase evidence label",
            evidence_line,
            "Impact: a report with no path can pass the citation gate",
            "Fix: match the evidence label case-insensitively",
            "Priority: P2",
            "Confidence: medium",
            "",
            "## Clean",
            "Heading structure was reviewed.",
            "",
            "## Assumptions",
            "The fixture report is the whole input.",
            "",
        ]
    )


class ReviewSwarmEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.check = load_review_swarm_check()

    def run_check(self, evidence_line: str) -> subprocess.CompletedProcess[str]:
        script = self.check.__file__
        if script is None:
            raise RuntimeError("loaded review-swarm check has no file path")
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "report.md"
            report.write_text(report_text(evidence_line), encoding="utf-8")
            return subprocess.run(
                [sys.executable, script, "--report", str(report), "--surface", "auth-routes"],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )

    def test_lowercase_evidence_without_citation_fails_and_quotes_label(self) -> None:
        result = self.run_check("evidence: described behavior without a location")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("cite file:line", result.stdout)
        self.assertIn("'evidence:'", result.stdout)

    def test_lowercase_evidence_with_citation_passes(self) -> None:
        result = self.run_check("evidence: ringer.py:12")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASS [review_contract]", result.stdout)


if __name__ == "__main__":
    unittest.main()
