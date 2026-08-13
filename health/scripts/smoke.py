from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
sys.path.insert(0, str(ROOT / "src"))

from hermes_health_loops.scheduler import render_manifest


def main() -> int:
    proposal = render_manifest({
        "modules": ["health"], "schedules": {"health": "weekly"},
        "provider": "explicit", "model": "explicit", "delivery": "none",
        "hermes_home": "selected-home", "runtime_dir": "/tmp/runtime",
        "review_acknowledged": True,
    })["commands"][0]
    assert "hermes cron create weekly 'Before manually running this proposal" in proposal
    assert "--deliver none" in proposal
    assert "--prompt" not in proposal and "--delivery" not in proposal and "--hermes-home" not in proposal
    assert "selected-home" not in proposal
    with tempfile.TemporaryDirectory() as temp:
        home = Path(temp) / "hermes-home"
        home.mkdir()
        (home / "config.yaml").write_text("safe: true\n", encoding="utf-8")
        (home / "sessions").mkdir()
        (home / "logs").mkdir()
        (home / "logs" / "audit.log").write_text("tool_call ok\n", encoding="utf-8")
        sqlite3.connect(home / "state.db").close()
        fixture = Path(temp) / "outcomes.json"
        fixture.write_text(json.dumps([{"kind": "warning", "timestamp": "2026-01-01T00:00:00Z", "result": "retry"}]), encoding="utf-8")
        runtime = Path(temp) / "runtime"
        for command in [
            [sys.executable, "-m", "hermes_health_loops.cli", "health", "--hermes-home", str(home)],
            [sys.executable, "-m", "hermes_health_loops.cli", "improvement", "--source", str(fixture), "--runtime-dir", str(runtime)],
            [sys.executable, "scripts/install.py", "--modules", "health", "--health-schedule", "weekly", "--provider", "explicit", "--model", "explicit", "--delivery", "none", "--hermes-home", "explicit-home", "--review-acknowledged"],
        ]:
            completed = subprocess.run(command, cwd=ROOT, env=ENV, text=True, capture_output=True)
            print("$", " ".join(command))
            print(completed.stdout.strip())
            if completed.returncode != 0:
                print(completed.stderr)
                return completed.returncode
    print("SMOKE_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
