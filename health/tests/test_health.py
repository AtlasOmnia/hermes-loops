from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from hermes_health_loops.health import audit_home
from hermes_health_loops.paths import discover_hermes_home


class HealthTests(unittest.TestCase):
    def test_healthy_synthetic_home(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            (home / "config.yaml").write_text("safe: true\n", encoding="utf-8")
            (home / "sessions").mkdir()
            (home / "logs").mkdir()
            (home / "skills").mkdir()
            (home / "cron").mkdir()
            (home / "cron" / "jobs.json").write_text(json.dumps({"jobs": [{"name": "fixture", "status": "ok"}]}), encoding="utf-8")
            (home / "logs" / "agent.log").write_text("tool_call completed\n", encoding="utf-8")
            sqlite3.connect(home / "state.db").close()
            result = audit_home(home, now=2_000_000_000)
            self.assertIn(result["status"], {"healthy", "warning"})
            self.assertTrue(any(item["check"] == "state:sqlite" and item["status"] == "healthy" for item in result["findings"]))

    def test_unhealthy_and_missing_optional_surfaces_are_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            (home / "config.yaml").write_text("safe: true\n", encoding="utf-8")
            (home / "logs").mkdir()
            (home / "logs" / "agent.log").write_text("tool_call timeout error\n" * 8, encoding="utf-8")
            result = audit_home(home, now=2_000_000_000)
            checks = {item["check"]: item for item in result["findings"]}
            self.assertEqual(checks["sessions:age"]["status"], "unavailable")
            self.assertEqual(checks["cron:jobs"]["status"], "unavailable")
            self.assertEqual(checks["tools:stall-candidates"]["status"], "warning")

    def test_discovery_precedence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            explicit = Path(temp) / "explicit"
            env = Path(temp) / "env"
            os.environ["HERMES_HOME"] = str(env)
            try:
                self.assertEqual(discover_hermes_home(str(explicit)), explicit)
                self.assertEqual(discover_hermes_home(), env)
            finally:
                os.environ.pop("HERMES_HOME", None)


if __name__ == "__main__":
    unittest.main()
