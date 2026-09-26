"""Seatbelt profile checks for engines/opencode-sandboxed.sh.

Extracts the SBPL heredoc from the wrapper script (without running opencode)
and exercises it with sandbox-exec against temp dirs. macOS only.
"""
import os
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

SCRIPT = os.path.join(ROOT, "engines", "opencode-sandboxed.sh")
SANDBOX_EXEC = "/usr/bin/sandbox-exec"


def extract_profile():
    with open(SCRIPT, encoding="utf-8") as f:
        text = f.read()
    m = re.search(r"<<'SBEOF'\n(.*?)\nSBEOF\n", text, re.S)
    if not m:
        raise AssertionError("SBEOF heredoc not found in opencode-sandboxed.sh")
    return m.group(1) + "\n"


@unittest.skipUnless(os.access(SANDBOX_EXEC, os.X_OK), "sandbox-exec not available")
class OpenCodeSandboxProfileTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = os.path.realpath(self.tmp.name)
        self.dirs = {}
        for name, rel in (
            ("TASKDIR", "task"),
            ("SCRATCH", "scratch"),
            ("OC_CONFIG", "config/opencode"),
            ("OC_SHARE", "share/opencode"),
            ("OC_STATE", "state/opencode"),
        ):
            path = os.path.join(self.root, rel)
            os.makedirs(path)
            self.dirs[name] = path
        for sub in ("plugins", "commands"):
            os.makedirs(os.path.join(self.dirs["OC_SHARE"], sub))
        self.profile = os.path.join(self.root, "profile.sb")
        with open(self.profile, "w", encoding="utf-8") as f:
            f.write(extract_profile())

    def run_sandboxed(self, *argv):
        cmd = [SANDBOX_EXEC]
        for k, v in self.dirs.items():
            cmd += ["-D", f"{k}={v}"]
        cmd += ["-f", self.profile, *argv]
        return subprocess.run(cmd, capture_output=True, text=True, timeout=30)

    def require_sandbox_apply(self):
        # When the test itself already runs inside a Seatbelt sandbox (e.g. a
        # Claude Code Bash tool), nesting is refused with EPERM at apply time.
        # Skip rather than let every "denied" assertion pass vacuously.
        r = self.run_sandboxed("/usr/bin/true")
        if "sandbox_apply" in r.stderr:
            self.skipTest("sandbox-exec cannot apply a profile here (nested sandbox)")
        self.assertEqual(r.returncode, 0, f"profile failed to load:\n{r.stderr}")

    def touch(self, path):
        return self.run_sandboxed("/bin/sh", "-c", f"touch '{path}'")

    def assert_writable(self, path):
        self.require_sandbox_apply()
        r = self.touch(path)
        self.assertEqual(r.returncode, 0, f"expected write to succeed: {path}\n{r.stderr}")
        self.assertTrue(os.path.exists(path))

    def assert_denied(self, path):
        self.require_sandbox_apply()
        r = self.touch(path)
        self.assertNotEqual(r.returncode, 0, f"expected write to be denied: {path}")
        self.assertFalse(os.path.exists(path))

    def test_profile_compiles(self):
        # Runs even under a nested sandbox: SBPL parse/bind errors (exit 65)
        # surface before sandbox_apply, so a broken heredoc is caught here.
        r = self.run_sandboxed("/usr/bin/true")
        self.assertNotEqual(r.returncode, 65, f"profile does not compile:\n{r.stderr}")
        for marker in ("syntax error", "unbound variable"):
            self.assertNotIn(marker, r.stderr)

    def test_profile_denies_config_after_allows(self):
        # Static guard: OC_CONFIG must not be in the allow list, and the deny
        # block for config/plugins/commands must come after the allow block
        # (Seatbelt applies the last matching rule).
        prof = extract_profile()
        allow = re.search(r"\(allow file-write\*(.*?)\)\n", prof, re.S).group(1)
        self.assertNotIn("OC_CONFIG", allow)
        deny_at = prof.index('(deny file-write*\n  (subpath (param "OC_CONFIG"))')
        self.assertGreater(deny_at, prof.index("(allow file-write*"))
        self.assertIn('(string-append (param "OC_SHARE") "/plugins")', prof)
        self.assertIn('(string-append (param "OC_SHARE") "/commands")', prof)

    def test_task_dir_writable(self):
        self.assert_writable(os.path.join(self.dirs["TASKDIR"], "out.txt"))

    def test_scratch_writable(self):
        self.assert_writable(os.path.join(self.dirs["SCRATCH"], "tmp.txt"))

    def test_state_writable(self):
        self.assert_writable(os.path.join(self.dirs["OC_STATE"], "session.json"))

    def test_share_root_writable(self):
        # auth refresh / session storage live here and must keep working
        self.assert_writable(os.path.join(self.dirs["OC_SHARE"], "auth.json"))

    def test_config_dir_denied(self):
        self.assert_denied(os.path.join(self.dirs["OC_CONFIG"], "opencode.json"))

    def test_config_plugin_denied(self):
        os.makedirs(os.path.join(self.dirs["OC_CONFIG"], "plugins"))
        self.assert_denied(os.path.join(self.dirs["OC_CONFIG"], "plugins", "evil.js"))

    def test_share_plugins_denied(self):
        self.assert_denied(os.path.join(self.dirs["OC_SHARE"], "plugins", "evil.js"))

    def test_share_commands_denied(self):
        self.assert_denied(os.path.join(self.dirs["OC_SHARE"], "commands", "evil.md"))

    def test_outside_denied(self):
        self.assert_denied(os.path.join(self.root, "outside.txt"))


if __name__ == "__main__":
    unittest.main()
