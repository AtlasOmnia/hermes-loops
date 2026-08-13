from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hermes_maintenance_loops.cron_inspector import inspect_cron
from hermes_maintenance_loops.health import audit_home


class CronInspectorTests(unittest.TestCase):
    def test_json_classifies_all_enabled_failure_categories_and_redacts_job(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cron = root / "cron"
            cron.mkdir()
            (cron / "jobs.v2.json").write_text(json.dumps({"items": [{
                "name": "private@example.invalid", "enabled": True, "schedule": "daily",
                "next_run_at": "2026-01-01T00:00:00Z", "status": "failed",
                "config_status": "drift", "artifact_status": "failed", "delivery_status": "failed"
            }]}), encoding="utf-8")
            result = inspect_cron(root, now=datetime(2026, 1, 2, tzinfo=timezone.utc))
            checks = {item["check"] for item in result["findings"]}
            for expected in {"cron:pre-dispatch", "cron:execution", "cron:side-effect", "cron:delivery", "cron:overdue"}:
                self.assertIn(expected, checks)
            self.assertNotIn("private@example.invalid", json.dumps(result))

    def test_unknown_json_and_sqlite_are_not_healthy(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cron = root / "cron"
            cron.mkdir()
            (cron / "jobs.json").write_text(json.dumps({"unexpected": True}), encoding="utf-8")
            connection = sqlite3.connect(cron / "executions.v2.db")
            connection.execute("create table unrelated (value text)")
            connection.commit()
            connection.close()
            result = inspect_cron(root)
            self.assertEqual(result["status"], "unknown")
            self.assertTrue(any(item["status"] == "unknown" for item in result["findings"]))

    def test_repeated_failure_requires_matching_stable_job_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cron = root / "cron"
            cron.mkdir()
            (cron / "jobs.json").write_text(json.dumps([{"id": "job-a", "enabled": True, "status": "ok"}]), encoding="utf-8")
            connection = sqlite3.connect(cron / "executions.db")
            connection.execute("create table executions (job_id text, status text)")
            connection.executemany("insert into executions values (?, ?)", [("job-a", "failed"), ("job-a", "error")])
            connection.commit()
            connection.close()
            result = inspect_cron(root)
            self.assertTrue(any(item["check"] == "cron:repeated-failure" for item in result["findings"]))

    def test_unrelated_job_failures_do_not_taint_classified_job(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cron = root / "cron"
            cron.mkdir()
            (cron / "jobs.json").write_text(json.dumps([{"jobId": "job-a", "enabled": True, "status": "ok"}]), encoding="utf-8")
            connection = sqlite3.connect(cron / "executions.db")
            connection.execute("create table executions (jobId text, status text)")
            connection.executemany("insert into executions values (?, ?)", [("job-b", "failed"), ("job-b", "error")])
            connection.commit()
            connection.close()
            result = inspect_cron(root)
            self.assertFalse(any(item["check"] == "cron:repeated-failure" for item in result["findings"]))

    def test_missing_job_identity_does_not_emit_repeated_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cron = root / "cron"
            cron.mkdir()
            (cron / "jobs.json").write_text(json.dumps([{"enabled": True, "status": "ok"}]), encoding="utf-8")
            connection = sqlite3.connect(cron / "executions.db")
            connection.execute("create table executions (status text)")
            connection.executemany("insert into executions values (?)", [("failed",), ("error",)])
            connection.commit()
            connection.close()
            result = inspect_cron(root)
            self.assertFalse(any(item["check"] == "cron:repeated-failure" for item in result["findings"]))

    def test_sentinel_job_identity_does_not_emit_repeated_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cron = root / "cron"
            cron.mkdir()
            (cron / "jobs.json").write_text(json.dumps([{"id": "unknown", "enabled": True, "status": "ok"}]), encoding="utf-8")
            connection = sqlite3.connect(cron / "executions.db")
            connection.execute("create table executions (job_id text, status text)")
            connection.executemany("insert into executions values (?, ?)", [("unknown", "failed"), ("unknown", "error")])
            connection.commit()
            connection.close()
            result = inspect_cron(root)
            self.assertFalse(any(item["check"] == "cron:repeated-failure" for item in result["findings"]))

    def test_conflicting_supported_job_id_aliases_do_not_emit_repeated_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cron = root / "cron"
            cron.mkdir()
            (cron / "jobs.json").write_text(json.dumps([{
                "id": "job-a", "jobId": "job-b", "enabled": True, "status": "ok",
            }]), encoding="utf-8")
            connection = sqlite3.connect(cron / "executions.db")
            connection.execute("create table executions (job_id text, status text)")
            connection.executemany("insert into executions values (?, ?)", [("job-a", "failed"), ("job-a", "error")])
            connection.commit()
            connection.close()
            result = inspect_cron(root)
            self.assertFalse(any(item["check"] == "cron:repeated-failure" for item in result["findings"]))

    def test_health_includes_structured_cron_findings_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "config.yaml").write_text("safe: true\n", encoding="utf-8")
            (root / "cron").mkdir()
            (root / "cron" / "jobs.json").write_text(json.dumps([{"enabled": True, "status": "unknown"}]), encoding="utf-8")
            before = sorted(path.relative_to(root).as_posix() for path in root.rglob("*"))
            result = audit_home(root, now=2_000_000_000)
            after = sorted(path.relative_to(root).as_posix() for path in root.rglob("*"))
            self.assertEqual(before, after)
            self.assertTrue(any(item["check"] == "cron:execution" for item in result["findings"]))


if __name__ == "__main__":
    unittest.main()
