from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class InstallerTests(unittest.TestCase):
    def test_dry_run_writes_nothing_and_requires_explicit_choices(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            runtime = Path(temp) / "runtime"
            command = [sys.executable, "scripts/install.py", "--modules", "health", "--health-schedule", "weekly", "--provider", "explicit", "--model", "explicit", "--delivery", "none", "--hermes-home", "explicit-home", "--review-acknowledged", "--runtime-dir", str(runtime)]
            completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("DRY-RUN", completed.stdout)
            self.assertFalse(runtime.exists())

            missing = subprocess.run(command[:-3], cwd=ROOT, text=True, capture_output=True)
            self.assertNotEqual(missing.returncode, 0)

    def test_apply_and_uninstall_only_package_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            runtime = Path(temp) / "runtime"
            command = [sys.executable, "scripts/install.py", "--modules", "health", "--health-schedule", "weekly", "--provider", "explicit", "--model", "explicit", "--delivery", "none", "--hermes-home", "explicit-home", "--review-acknowledged", "--runtime-dir", str(runtime), "--apply"]
            completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            manifest = runtime / "install-manifest.json"
            self.assertTrue(manifest.exists())
            self.assertEqual(json.loads(manifest.read_text())["apply_policy"], "manifest-only; never create Hermes jobs automatically")
            removed = subprocess.run([sys.executable, "scripts/uninstall.py", "--runtime-dir", str(runtime), "--apply"], cwd=ROOT, text=True, capture_output=True)
            self.assertEqual(removed.returncode, 0, removed.stderr)
            self.assertFalse(manifest.exists())


if __name__ == "__main__":
    unittest.main()
