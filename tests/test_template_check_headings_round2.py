from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parents[1]
CHECKS = {
    "synthesis": ROOT / "templates" / "competitive-teardown" / "checks" / "synthesis_check.py",
    "teardown": ROOT / "templates" / "competitive-teardown" / "checks" / "teardown_check.py",
    "pipeline": ROOT / "templates" / "data-pipeline" / "checks" / "pipeline_check.py",
    "doc": ROOT / "templates" / "doc-swarm" / "checks" / "doc_check.py",
    "listing": ROOT / "templates" / "launch-kit" / "checks" / "check_listing.py",
}

SYNTHESIS_TITLES = (
    "Decision Summary",
    "Comparison Table",
    "Strongest Evidence",
    "Gaps and Could-Not-Fetch Items",
    "Recommended Follow-Up",
)
TEARDOWN_TITLES = ("Target", "Source Log", "Angle Findings", "Extracted Numbers")
PIPELINE_TITLES = (
    "Verdict",
    "Row Counts",
    "Schema",
    "Empty Value Scan",
    "Spot Invariants",
    "Rejects",
    "Assumptions",
)
NUMBERED_PREFIXES = ("1. ", "2) ", "3: ", "4. ", "5) ", "6: ", "7. ")


def load_check(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"template_check_round2_{name}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_main(module: ModuleType, argv: list[str]) -> tuple[int, str]:
    stdout = io.StringIO()
    old_argv = sys.argv
    try:
        sys.argv = argv
        with contextlib.redirect_stdout(stdout):
            code = module.main()
    finally:
        sys.argv = old_argv
    return code, stdout.getvalue()


def heading_lines(titles: tuple[str, ...], numbered: bool, rename: str | None = None) -> list[str]:
    lines: list[str] = []
    for index, title in enumerate(titles):
        shown = rename if index == 0 and rename else title
        if numbered:
            colon = ":" if index == len(titles) - 1 else ""
            lines.append(f"## {NUMBERED_PREFIXES[index]}{shown}{colon}")
        else:
            lines.append(f"## {shown}")
    return lines


def synthesis_markdown(numbered: bool, rename: str | None = None) -> str:
    parts: list[str] = []
    for heading in heading_lines(SYNTHESIS_TITLES, numbered, rename):
        parts.append(heading)
        parts.append("")
        parts.append("Evidence from https://example.com/pricing supports this section.")
        parts.append("")
    return "\n".join(parts)


# teardown_check's URL regex only accepts this shape; keep the fixture on it.
TEARDOWN_URL = "https://a\"'<>]"


def teardown_markdown(numbered: bool, rename: str | None = None) -> str:
    parts: list[str] = []
    for heading in heading_lines(TEARDOWN_TITLES, numbered, rename):
        parts.append(heading)
        parts.append("")
        parts.append(f"Fetched {TEARDOWN_URL} and recorded 42 users.")
        parts.append("")
    return "\n".join(parts)


def pipeline_markdown(numbered: bool, rename: str | None = None) -> str:
    parts: list[str] = []
    for heading in heading_lines(PIPELINE_TITLES, numbered, rename):
        parts.append(heading)
        parts.append("")
        parts.append("Row count 1. Reject count 0.")
        parts.append("")
    return "\n".join(parts)


def doc_markdown(overview: str, numbered: bool) -> str:
    if numbered:
        overview_heading = f"## 1. {overview}"
        details_heading = "## 2) Details:"
    else:
        overview_heading = f"## {overview}"
        details_heading = "## Details"
    return "\n".join(
        (
            overview_heading,
            "",
            "This overview explains the documented surface.",
            "",
            details_heading,
            "",
            "Call `RingerHeadingToken` from the source tree.",
            "",
            "```python",
            'print("ok")',
            "```",
            "",
        )
    )


def listing_markdown(about_heading: str) -> str:
    products: list[str] = []
    for name in ("Alpha", "Beta", "Gamma"):
        products.append(
            "\n".join(
                (
                    f"## PRODUCT {name}",
                    "",
                    f"TITLE: {name} storefront item",
                    "",
                    f"A factual description of the {name} item.",
                    "",
                    "- first bullet assumption",
                    "- second bullet TBD",
                    "- third bullet draft",
                    "",
                )
            )
        )
    filler = " ".join(f"word{index}" for index in range(260))
    about = "\n".join(
        (
            about_heading,
            "",
            "Honest maker copy. coming soon placeholder to be measured.",
            filler,
            "",
        )
    )
    return "\n".join(products) + "\n" + about


class TemplateCheckHeadingRound2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.checks = {name: load_check(name, path) for name, path in CHECKS.items()}

    def assert_pass(self, code: int, output: str) -> None:
        self.assertEqual(code, 0, output)

    def assert_missing_lists_found(self, code: int, output: str, missing: str, found: list[str]) -> None:
        self.assertNotEqual(code, 0, output)
        self.assertIn(missing, output)
        self.assertIn("found headings:", output)
        for heading in found:
            self.assertIn(heading, output)

    def test_synthesis_numbered_headings_pass(self) -> None:
        code, output = self.run_synthesis(synthesis_markdown(numbered=True))
        self.assert_pass(code, output)

    def test_synthesis_unnumbered_headings_pass(self) -> None:
        code, output = self.run_synthesis(synthesis_markdown(numbered=False))
        self.assert_pass(code, output)

    def test_synthesis_renamed_heading_lists_found(self) -> None:
        headings = heading_lines(SYNTHESIS_TITLES, numbered=True, rename="Executive Summary")
        code, output = self.run_synthesis(synthesis_markdown(numbered=True, rename="Executive Summary"))
        self.assert_missing_lists_found(code, output, "decision summary", headings)
        self.assertNotIn("cites URL", output)
        self.assertNotIn("minimum substance", output)

    def test_teardown_numbered_headings_pass(self) -> None:
        code, output = self.run_teardown(teardown_markdown(numbered=True))
        self.assert_pass(code, output)

    def test_teardown_unnumbered_headings_pass(self) -> None:
        code, output = self.run_teardown(teardown_markdown(numbered=False))
        self.assert_pass(code, output)

    def test_teardown_renamed_heading_lists_found(self) -> None:
        headings = heading_lines(TEARDOWN_TITLES, numbered=True, rename="Subject")
        code, output = self.run_teardown(teardown_markdown(numbered=True, rename="Subject"))
        self.assert_missing_lists_found(code, output, "## Target", headings)
        self.assertNotIn("outside the allowlist", output)
        self.assertNotIn("fetch status", output)

    def test_pipeline_numbered_headings_pass(self) -> None:
        code, output = self.run_pipeline(pipeline_markdown(numbered=True))
        self.assert_pass(code, output)

    def test_pipeline_unnumbered_headings_pass(self) -> None:
        code, output = self.run_pipeline(pipeline_markdown(numbered=False))
        self.assert_pass(code, output)

    def test_pipeline_renamed_heading_lists_found(self) -> None:
        headings = heading_lines(PIPELINE_TITLES, numbered=True, rename="Outcome")
        code, output = self.run_pipeline(pipeline_markdown(numbered=True, rename="Outcome"))
        self.assert_missing_lists_found(code, output, "## verdict", headings)
        self.assertNotIn("does not mention", output)
        self.assertNotIn("invariant failed", output)

    def test_doc_numbered_headings_pass(self) -> None:
        code, output = self.run_doc(doc_markdown("Overview", numbered=True))
        self.assert_pass(code, output)

    def test_doc_unnumbered_headings_pass(self) -> None:
        code, output = self.run_doc(doc_markdown("Overview", numbered=False))
        self.assert_pass(code, output)

    def test_doc_renamed_heading_lists_found(self) -> None:
        code, output = self.run_doc(doc_markdown("Introduction", numbered=True))
        self.assert_missing_lists_found(
            code,
            output,
            "missing required section: Overview",
            ["## 1. Introduction", "## 2) Details:"],
        )
        self.assertNotIn("passed doc validation", output)

    def test_listing_numbered_headings_pass(self) -> None:
        code, output = self.run_listing(listing_markdown("## 1. About the Maker:"))
        self.assert_pass(code, output)

    def test_listing_unnumbered_headings_pass(self) -> None:
        code, output = self.run_listing(listing_markdown("## About the Maker"))
        self.assert_pass(code, output)

    def test_listing_renamed_heading_lists_found(self) -> None:
        code, output = self.run_listing(listing_markdown("## 4. Company Background"))
        self.assert_missing_lists_found(
            code,
            output,
            "missing ABOUT section",
            [
                "## PRODUCT Alpha",
                "## PRODUCT Beta",
                "## PRODUCT Gamma",
                "## 4. Company Background",
            ],
        )
        self.assertNotIn("words (need", output)
        self.assertNotIn("PRODUCT sections", output)

    def run_synthesis(self, report: str) -> tuple[int, str]:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            scout = directory / "scout.md"
            synthesis = directory / "synthesis.md"
            scout.write_text("Source https://example.com/pricing\n", encoding="utf-8")
            synthesis.write_text(report, encoding="utf-8")
            return run_main(
                self.checks["synthesis"],
                [
                    "synthesis_check.py",
                    "--report",
                    str(synthesis),
                    "--scout-reports",
                    str(scout),
                    "--min-competitors",
                    "1",
                    "--min-words",
                    "1",
                ],
            )

    def run_teardown(self, report: str) -> tuple[int, str]:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            report_path = directory / "report.md"
            allowlist = directory / "allowlist.txt"
            report_path.write_text(report, encoding="utf-8")
            allowlist.write_text(TEARDOWN_URL + "\n", encoding="utf-8")
            return run_main(
                self.checks["teardown"],
                [
                    "teardown_check.py",
                    "--report",
                    str(report_path),
                    "--allowlist",
                    str(allowlist),
                    "--min-words",
                    "1",
                    "--min-citations",
                    "1",
                    "--min-numbers",
                    "1",
                ],
            )

    def run_pipeline(self, report: str) -> tuple[int, str]:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            report_path = directory / "report.md"
            data_path = directory / "rows.json"
            report_path.write_text(report, encoding="utf-8")
            data_path.write_text(json.dumps([{"id": "row-1"}]), encoding="utf-8")
            return run_main(
                self.checks["pipeline"],
                [
                    "pipeline_check.py",
                    "report",
                    "--stage",
                    "transform",
                    "--report",
                    str(report_path),
                    "--data-file",
                    str(data_path),
                    "--min-rows",
                    "1",
                ],
            )

    def run_doc(self, markdown: str) -> tuple[int, str]:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            source = directory / "source"
            example_cwd = directory / "cwd"
            source.mkdir()
            example_cwd.mkdir()
            (source / "widget.py").write_text("RingerHeadingToken = 1\n", encoding="utf-8")
            doc_path = directory / "guide.md"
            doc_path.write_text(markdown, encoding="utf-8")
            return run_main(
                self.checks["doc"],
                [
                    "doc_check.py",
                    "--doc-path",
                    str(doc_path),
                    "--source-root",
                    str(source),
                    "--required-sections",
                    "Overview;Details",
                    "--min-words",
                    "1",
                    "--min-section-words",
                    "1",
                    "--symbol-section",
                    "Details",
                    "--runnable-language",
                    "python",
                    "--example-runner",
                    "python3 '{file}'",
                    "--example-cwd",
                    str(example_cwd),
                ],
            )

    def run_listing(self, markdown: str) -> tuple[int, str]:
        with tempfile.TemporaryDirectory() as temporary:
            listing = Path(temporary) / "listing-copy.md"
            listing.write_text(markdown, encoding="utf-8")
            return run_main(
                self.checks["listing"],
                ["check_listing.py", "--file", str(listing)],
            )


if __name__ == "__main__":
    unittest.main()
