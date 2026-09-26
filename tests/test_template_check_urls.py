from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SYNTHESIS_CHECK_PATH = (
    ROOT / "templates" / "competitive-teardown" / "checks" / "synthesis_check.py"
)


def load_synthesis_check():
    spec = importlib.util.spec_from_file_location("synthesis_check", SYNTHESIS_CHECK_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {SYNTHESIS_CHECK_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SynthesisUrlTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.check = load_synthesis_check()

    def test_allowed_url_accepts_equivalent_variants(self) -> None:
        cases = (
            ("https://a.com/docs/", "https://a.com/docs"),
            ("https://a.com/docs?ref=x", "https://a.com/docs"),
            ("https://a.com/docs#pricing", "https://a.com/docs"),
            ("http://a.com/docs", "https://a.com/docs"),
            ("https://www.a.com/docs", "https://a.com/docs"),
            ("https://a.com/docs", "https://a.com/docs/pricing"),
        )

        for cited, allowed in cases:
            with self.subTest(cited=cited, allowed=allowed):
                self.assertTrue(self.check.allowed_url(cited, {allowed}))

    def test_allowed_url_rejects_different_host(self) -> None:
        self.assertFalse(
            self.check.allowed_url(
                "https://foreign.example/docs", {"https://a.com/docs"}
            )
        )

    def test_allowed_url_rejects_non_boundary_prefix(self) -> None:
        self.assertFalse(
            self.check.allowed_url("https://a.com/doc", {"https://a.com/docs"})
        )

    def run_check(self, synthesis_url: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            scout = directory / "scout.md"
            synthesis = directory / "synthesis.md"
            scout.write_text("Source: <https://example.com/pricing?ref=x>\n", encoding="utf-8")
            synthesis.write_text(
                "\n".join(
                    (
                        "## Decision Summary",
                        f"Evidence: <{synthesis_url}>",
                        "## Comparison Table",
                        "## Strongest Evidence",
                        "## Gaps and Could-Not-Fetch Items",
                        "## Recommended Follow-Up",
                    )
                ),
                encoding="utf-8",
            )
            return subprocess.run(
                (
                    sys.executable,
                    str(SYNTHESIS_CHECK_PATH),
                    "--report",
                    str(synthesis),
                    "--scout-reports",
                    str(scout),
                    "--min-competitors",
                    "1",
                    "--min-words",
                    "0",
                ),
                check=False,
                capture_output=True,
                text=True,
            )

    def test_main_accepts_trailing_slash_variant(self) -> None:
        result = self.run_check("https://example.com/pricing/")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_main_rejects_foreign_host_and_lists_url(self) -> None:
        foreign_url = "https://foreign.example/pricing/"
        result = self.run_check(foreign_url)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(foreign_url, result.stdout)


if __name__ == "__main__":
    unittest.main()
