#!/usr/bin/env python3
"""Validate a second-phase competitive teardown synthesis."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


URL_RE = re.compile(r"https?://[^\s)\]\"'<>]+", re.IGNORECASE)


def fail(message: str) -> None:
    print(f"FAIL: {message}")


def split_paths(value: str) -> list[Path]:
    pieces = re.split(r"[|,]", value)
    return [Path(piece.strip()) for piece in pieces if piece.strip()]


def extract_urls(text: str) -> set[str]:
    return {match.group(0).rstrip(".,;:!?)]}'\"") for match in URL_RE.finditer(text)}


def normalise_url(url: str) -> str:
    parts = urlsplit(url)
    host = parts.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return urlunsplit(("https", host, parts.path.rstrip("/"), "", ""))


def allowed_url(cited: str, allowed_set: set[str]) -> bool:
    cited_parts = urlsplit(normalise_url(cited))
    cited_path = cited_parts.path

    for allowed in allowed_set:
        allowed_parts = urlsplit(normalise_url(allowed))
        if cited_parts.netloc != allowed_parts.netloc:
            continue

        allowed_path = allowed_parts.path
        if cited_path == allowed_path:
            return True

        shorter, longer = sorted((cited_path, allowed_path), key=len)
        if longer.startswith(shorter + "/"):
            return True

    return False


def word_count(text: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", text))


HEADING_LEVELS = (2,)


def heading_pattern(level: int, text: str) -> str:
    return rf"^{'#' * level}\s+(?:\d+[.):]\s+)?{re.escape(text)}:?\s*$"


def has_heading(text: str, heading: str) -> bool:
    flags = re.IGNORECASE | re.MULTILINE
    return any(re.search(heading_pattern(level, heading), text, flags) for level in HEADING_LEVELS)


def found_headings(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if re.match(r"^#{1,6}\s+\S", line)]


def missing_section(section: str, text: str) -> str:
    found = ", ".join(found_headings(text)) or "(none)"
    return f"missing required section: {section}; found headings: {found}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True)
    parser.add_argument("--scout-reports", required=True)
    parser.add_argument("--min-competitors", type=int, default=2)
    parser.add_argument("--min-words", type=int, default=400)
    args = parser.parse_args()

    failures: list[str] = []
    report_path = Path(args.report)
    scout_paths = split_paths(args.scout_reports)

    if not report_path.is_file():
        failures.append(f"missing synthesis report: {report_path}")
    if len(scout_paths) < args.min_competitors:
        failures.append(
            f"only {len(scout_paths)} scout report path(s) supplied; expected at least {args.min_competitors}"
        )

    scout_texts: list[str] = []
    for path in scout_paths:
        if not path.is_file():
            failures.append(f"missing scout report: {path}")
            continue
        scout_texts.append(path.read_text(encoding="utf-8", errors="replace"))

    if failures:
        for item in failures:
            fail(item)
        return 1

    report = report_path.read_text(encoding="utf-8", errors="replace")
    for section in (
        "decision summary",
        "comparison table",
        "strongest evidence",
        "gaps and could-not-fetch items",
        "recommended follow-up",
    ):
        if not has_heading(report, section):
            failures.append(missing_section(f"## {section}", report))

    if word_count(report) < args.min_words:
        failures.append(f"synthesis is below minimum substance threshold of {args.min_words} words")

    allowed_urls = set().union(*(extract_urls(text) for text in scout_texts))
    report_urls = extract_urls(report)
    new_urls = sorted(url for url in report_urls if not allowed_url(url, allowed_urls))
    if new_urls:
        failures.append(
            "synthesis cites URL(s) not present in scout reports: " + ", ".join(new_urls[:10])
        )
    if not report_urls:
        failures.append("synthesis contains no source URLs from scout reports")

    if failures:
        for item in failures:
            fail(item)
        return 1

    print(
        "PASS: synthesis compares supplied scout reports and cites only URLs already present in them"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
