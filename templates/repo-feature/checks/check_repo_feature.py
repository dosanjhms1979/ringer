#!/usr/bin/env python3
"""Validate a sandboxed repo edit with build/tests, content checks, and git status allowlist."""

from __future__ import annotations

import argparse
import os
import pathlib
import re
import subprocess
import sys


def strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07]*\x07", "", text)


def split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def path_allowed(path: str, allowed: list[str]) -> bool:
    normalized = path.strip().rstrip("/")
    for raw in allowed:
        candidate = raw.strip().rstrip("/")
        if not candidate:
            continue
        if normalized == candidate or normalized.startswith(candidate + "/"):
            return True
        if candidate.startswith(normalized + "/"):
            return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--owned", required=True, help="Comma-separated repo paths the worker may change")
    parser.add_argument("--allowed-status", default="", help="Additional comma-separated paths allowed in git status")
    parser.add_argument("--required-paths", default="", help="Comma-separated repo paths that must exist")
    parser.add_argument("--required-text", default="", help="Comma-separated text snippets that must appear somewhere in owned files")
    parser.add_argument("--build-command", required=True)
    parser.add_argument("--baseline-failures", default="", help="Comma-or-newline separated substrings of known baseline failures")
    parser.add_argument("--failure-line-regex", default=r"(?m)^[ \t]*(?:[✗×●]|FAIL(?:ED)?\b|ERROR\b|E[ \t]|not ok\b|\d+\)[ \t]|--- FAIL|\w*(?:Error|Exception):|.* › ).*$", help="Regex extracting failure lines from build/test output")
    parser.add_argument("--notes", default="notes.md")
    args = parser.parse_args()

    repo = pathlib.Path(args.repo)
    fails: list[str] = []
    if not repo.exists():
        print(f"FAIL: repo path does not exist: {repo}")
        return 1
    if not (repo / ".git").exists():
        print(f"FAIL: repo path is not a git checkout: {repo}")
        return 1

    notes = pathlib.Path(args.notes)
    if not notes.exists() or notes.stat().st_size == 0:
        fails.append(f"scratch notes file missing or empty: {notes}")

    required_paths = split_csv(args.required_paths)
    for rel in required_paths:
        if not (repo / rel).exists():
            fails.append(f"required repo path missing: {rel}")

    owned = split_csv(args.owned)
    allowed = owned + split_csv(args.allowed_status)
    if not owned:
        fails.append("no owned paths supplied to validator")

    required_text = split_csv(args.required_text)
    if required_text:
        haystack_parts: list[str] = []
        for rel in owned:
            path = repo / rel
            if path.is_file():
                haystack_parts.append(path.read_text(encoding="utf-8", errors="replace"))
            elif path.is_dir():
                for child in path.rglob("*"):
                    if child.is_file() and child.stat().st_size < 1_000_000:
                        haystack_parts.append(child.read_text(encoding="utf-8", errors="replace"))
        haystack = "\n".join(haystack_parts)
        for snippet in required_text:
            if snippet not in haystack:
                fails.append(f"required text not found in owned files: {snippet!r}")

    print(f"running build/test command in {repo}: {args.build_command}")
    proc = subprocess.run(
        args.build_command, cwd=repo, shell=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True, timeout=1800,
        env={**os.environ, "NO_COLOR": "1", "FORCE_COLOR": "0", "TERM": "dumb"},
    )
    output = strip_ansi(proc.stdout)
    if proc.returncode != 0:
        baseline = split_csv(args.baseline_failures.replace("\n", ","))
        if not baseline:
            print("FAIL: build/test command failed")
            print(output[-7000:])
            return 1
        short = [item for item in baseline if len(item) < 6]
        if short:
            for item in short:
                print(f"FAIL: --baseline-failures entry {item!r} is too short (minimum 6 characters); it would whitelist unrelated failures")
            return 1
        try:
            pattern = re.compile(args.failure_line_regex)
        except re.error as exc:
            print(f"FAIL: --failure-line-regex is not valid regex: {exc}")
            print(output[-7000:])
            return 1
        failure_lines = [match.group(0) for match in pattern.finditer(output) if match.group(0).strip()]
        if not failure_lines:
            print("FAIL: build/test command failed with no extractable failure lines")
            print(output[-7000:])
            return 1
        new_failures = [line for line in failure_lines if not any(item in line for item in baseline)]
        if new_failures:
            print("FAIL: build/test command failed with NEW failures:")
            for line in new_failures[:20]:
                print(line)
            return 1
        if len(failure_lines) >= 3:
            broad = [item for item in baseline if len(item) < 20 and all(item in line for line in failure_lines)]
            if broad:
                print(f"FAIL: baseline entry {broad[0]!r} matches every failure line — too broad")
                return 1
        print(f"OK: build failed only on baseline failures ({len(failure_lines)} lines matched baseline)")
    print(output[-3000:])

    status = subprocess.run(["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True, timeout=60)
    if status.returncode != 0:
        print("FAIL: git status failed")
        print(status.stderr)
        return 1
    for line in status.stdout.splitlines():
        if not line:
            continue
        rel = line[3:].strip()
        if not path_allowed(rel, allowed):
            fails.append(f"unexpected repo change outside owned/allowed paths: {line}")

    if fails:
        print("FAIL:")
        for fail in fails:
            print(f" - {fail}")
        return 1
    print("PASS: notes exist, content assertions passed, build/tests passed or matched baseline, and git status is allowlisted")
    return 0


if __name__ == "__main__":
    sys.exit(main())
