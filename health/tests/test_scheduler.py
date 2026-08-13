from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hermes_health_loops.scheduler import ManifestValidationError, render_manifest


class SchedulerTests(unittest.TestCase):
    def request(self, runtime: str) -> dict[str, object]:
        return {
            "schema": "install-manifest.v2", "modules": ["health", "improvement"],
            "schedules": {"health": "weekly schedule", "improvement": "daily schedule"},
            "provider": "explicit provider", "model": "explicit model", "delivery": "reviewed delivery",
            "hermes_home": "explicit home", "runtime_dir": runtime, "review_acknowledged": True,
        }

    def test_invalid_manifest_is_rejected(self) -> None:
        request = self.request("/tmp/runtime")
        request["review_acknowledged"] = False
        with self.assertRaises(ManifestValidationError):
            render_manifest(request)

    def test_reviewed_manifest_quotes_values_and_is_non_executing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            manifest = render_manifest(self.request(temp + "/space runtime"))
            text = json.dumps(manifest)
            self.assertEqual(manifest["schema"], "install-manifest.v2")
            self.assertIn("REVIEW ONLY — NOT EXECUTED", "\n".join(manifest["commands"]))
            self.assertIn("'weekly schedule'", manifest["commands"][0])
            proposal = manifest["commands"][0]
            self.assertIn("Before manually running this proposal, establish the selected Hermes context from the manifest.", proposal)
            self.assertNotIn("--prompt", proposal)
            self.assertNotIn("--hermes-home", proposal)
            self.assertNotIn("--delivery", proposal)
            self.assertIn("hermes cron create 'weekly schedule' '", proposal)
            self.assertIn("' --provider 'explicit provider' --model 'explicit model' --deliver 'reviewed delivery'", proposal)
            self.assertEqual(manifest["hermes_home"], "explicit home")
            self.assertFalse((Path(temp) / "space runtime").exists())

    def test_script_dry_run_does_not_create_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            runtime = Path(temp) / "runtime"
            completed = subprocess.run([sys.executable, "scripts/install.py", "--modules", "health", "--health-schedule", "weekly", "--provider", "provider", "--model", "model", "--delivery", "none", "--hermes-home", "home", "--review-acknowledged", "--runtime-dir", str(runtime)], cwd=ROOT, text=True, capture_output=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertFalse(runtime.exists())


if __name__ == "__main__":
    unittest.main()
