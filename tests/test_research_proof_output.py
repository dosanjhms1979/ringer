"""Hermetic coverage for research-with-proof success-marker matching."""

from __future__ import annotations

import importlib.util
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECK_PATH = ROOT / "templates" / "research-with-proof" / "checks" / "research-with-proof.py"

PROOF_DOC = """# Executable Proof

## Claim
Coloured proof output still contains the success marker.

## How To Run
python -c "print('marker')"

## What It Proves
The marker is visible after ANSI stripping.

## Limits
Fixture only.
"""


def load_check():
    spec = importlib.util.spec_from_file_location("research_with_proof_check", CHECK_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {CHECK_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CHECK = load_check()


def command(source: str) -> str:
    return shlex.join([sys.executable, "-c", source])


class ResearchProofOutputTests(unittest.TestCase):
    def run_proof(self, source: str, marker: str = "PROOF OK") -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            proof_doc = root / "proof.md"
            artifact = root / "artifact.txt"
            proof_doc.write_text(PROOF_DOC, encoding="utf-8")
            artifact.write_text("artifact\n", encoding="utf-8")
            return subprocess.run(
                [
                    sys.executable,
                    CHECK.__file__,
                    "proof",
                    "--proof-doc",
                    str(proof_doc),
                    "--artifact",
                    str(artifact),
                    "--proof-command",
                    command(source),
                    "--success-marker",
                    marker,
                ],
                text=True,
                capture_output=True,
                timeout=30,
            )

    def test_ansi_between_marker_words_passes(self) -> None:
        result = self.run_proof(r"print('PROOF\x1b[32m OK\x1b[0m')")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASS", result.stdout)

    def test_missing_marker_shows_marker_and_searched_output(self) -> None:
        result = self.run_proof("print('nothing here')")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("PROOF OK", result.stdout)
        self.assertIn("nothing here", result.stdout)


if __name__ == "__main__":
    unittest.main()
