from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hermes_maintenance_loops.health import audit_home
from hermes_maintenance_loops.improvement import collect_packets, evaluate_packets
from hermes_maintenance_loops.report import unified_report
from scripts.privacy_scan import scan_public_text


class SafetyTests(unittest.TestCase):
    def test_health_does_not_mutate_source_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            (home / "config.yaml").write_text("safe: true\n", encoding="utf-8")
            before = sorted(str(path.relative_to(home)) for path in home.rglob("*"))
            audit_home(home)
            after = sorted(str(path.relative_to(home)) for path in home.rglob("*"))
            self.assertEqual(before, after)

    def test_unified_reporting_is_optional_and_separate(self) -> None:
        result = unified_report(health={"schema": "health.v1"})
        self.assertEqual(set(result["modules"]), {"health"})
        self.assertNotIn("improvement", result["modules"])

    def test_source_allowlist_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            missing = Path(temp) / "missing.json"
            with self.assertRaises(FileNotFoundError):
                collect_packets([missing])

    def test_improvement_collection_does_not_mutate_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "fixture.json"
            source.write_text(json.dumps([{"kind": "warning", "result": "stable"}]), encoding="utf-8")
            before = source.read_bytes()
            packets = collect_packets([source])
            evaluate = evaluate_packets(packets)
            self.assertIsNotNone(evaluate)
            self.assertEqual(source.read_bytes(), before)

    def test_privacy_scan_rejects_public_choices_hosts_urls_and_literal_flags(self) -> None:
        self.assertIn("concrete-public-choice", scan_public_text("provider: chosen-provider\n"))
        self.assertIn("executable-literal-choice", scan_public_text("tool --delivery chosen-delivery\n"))
        self.assertIn("network-url", scan_public_text("See https://example.invalid/reference\n"))
        self.assertIn("network-host", scan_public_text("Connect to localhost:1234\n"))
        self.assertEqual(scan_public_text("provider: <operator-supplied provider>\n"), [])

    def test_fresh_runtime_manifest_rollback_uninstall_is_contained_and_never_runs_hermes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runtime = root / "package-runtime"
            marker = root / "hermes-invoked"
            fake_bin = root / "bin"
            fake_bin.mkdir()
            (fake_bin / "hermes").write_text(
                f"#!/bin/sh\nprintf invoked > {marker!s}\nexit 99\n", encoding="utf-8"
            )
            (fake_bin / "hermes").chmod(0o755)
            env = {**os.environ, "PATH": str(fake_bin) + os.pathsep + os.environ.get("PATH", "")}
            def snapshot() -> dict[str, bytes]:
                return {
                    str(path.relative_to(root)): path.read_bytes()
                    for path in root.rglob("*") if path.is_file()
                }

            before = snapshot()
            changed: set[str] = set()

            def record_changes() -> None:
                after = snapshot()
                changed.update(
                    name for name in set(before) | set(after)
                    if before.get(name) != after.get(name)
                )
                before.clear()
                before.update(after)

            base = [
                sys.executable, "scripts/install.py", "--modules", "health",
                "--health-schedule", "operator-schedule", "--provider", "operator-provider",
                "--model", "operator-model", "--delivery", "operator-delivery",
                "--hermes-home", "operator-context", "--review-acknowledged",
                "--runtime-dir", str(runtime), "--apply",
            ]
            first = subprocess.run(base, cwd=ROOT, env=env, text=True, capture_output=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            record_changes()
            first_manifest = runtime / "install-manifest.json"
            self.assertTrue(first_manifest.is_file())
            second = subprocess.run(base, cwd=ROOT, env=env, text=True, capture_output=True)
            self.assertEqual(second.returncode, 0, second.stderr)
            record_changes()
            previous = runtime / "install-manifest.previous.json"
            self.assertTrue(previous.is_file())
            rollback = subprocess.run(
                [sys.executable, "scripts/uninstall.py", "--runtime-dir", str(runtime), "--rollback", "--apply"],
                cwd=ROOT, env=env, text=True, capture_output=True,
            )
            self.assertEqual(rollback.returncode, 0, rollback.stderr)
            record_changes()
            uninstall = subprocess.run(
                [sys.executable, "scripts/uninstall.py", "--runtime-dir", str(runtime), "--apply"],
                cwd=ROOT, env=env, text=True, capture_output=True,
            )
            self.assertEqual(uninstall.returncode, 0, uninstall.stderr)
            record_changes()
            self.assertFalse(marker.exists())
            self.assertTrue(changed)
            self.assertTrue(all(Path(name).parts[0] == runtime.name for name in changed))
            self.assertEqual(set(snapshot()), {"bin/hermes"})
            self.assertFalse((runtime / "install-manifest.json").exists())
            self.assertFalse((runtime / "install-manifest.previous.json").exists())


if __name__ == "__main__":
    unittest.main()
