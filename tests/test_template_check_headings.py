from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parents[1]
CHECKS = {
    "bakeoff": ROOT / "templates" / "bakeoff" / "checks" / "bakeoff.py",
    "focus_group": ROOT / "templates" / "focus-group" / "checks" / "focus-group.py",
    "fix_swarm": ROOT / "templates" / "fix-swarm" / "checks" / "fix-swarm.py",
    "research_with_proof": ROOT / "templates" / "research-with-proof" / "checks" / "research-with-proof.py",
    "review_swarm": ROOT / "templates" / "review-swarm" / "checks" / "review-swarm.py",
}


def load_check(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"template_check_{name}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TemplateCheckHeadingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.checks = {name: load_check(name, path) for name, path in CHECKS.items()}

    def test_level_two_heading_variants(self) -> None:
        accepted = ("## 1. Summary", "## 2) Summary", "## Summary:", "## Summary")
        rejected = ("## Summaries", "### Summary")

        for name, check in self.checks.items():
            with self.subTest(check=name):
                for heading in accepted:
                    self.assertTrue(check.has_heading(heading, "Summary"), heading)
                for heading in rejected:
                    self.assertFalse(check.has_heading(heading, "Summary"), heading)

    def test_all_numeric_prefix_separators(self) -> None:
        for name, check in self.checks.items():
            for heading in ("## 3. Summary", "## 3) Summary", "## 3: Summary"):
                with self.subTest(check=name, heading=heading):
                    self.assertTrue(check.has_heading(heading, "Summary"))

    def test_title_pattern_accepts_numbering_and_colon_but_stays_strict(self) -> None:
        for name, check in self.checks.items():
            pattern = check.heading_pattern(1, "Report")
            for heading in ("# 1. Report", "# Report:", "# Report"):
                with self.subTest(check=name, heading=heading):
                    self.assertRegex(heading, pattern)
            for heading in ("# Reports", "## Report"):
                with self.subTest(check=name, heading=heading):
                    self.assertNotRegex(heading, pattern)

    def test_review_section_extracts_numbered_heading_body(self) -> None:
        check = self.checks["review_swarm"]
        text = "## 1. Summary:\nBody under numbered heading.\n\n## 2) Findings\nNo findings\n"
        self.assertEqual(check.section(text, "Summary"), "Body under numbered heading.")


if __name__ == "__main__":
    unittest.main()
