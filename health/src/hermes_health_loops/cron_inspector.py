"""Bounded, read-only, version-tolerant inspection of explicit cron fixtures."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .redact import redact, stable_fingerprint

MAX_FILES = 12
MAX_BYTES = 128 * 1024
MAX_ROWS = 200
JSON_NAMES = ("jobs.json", "jobs.v1.json", "jobs.v2.json")
SQLITE_NAMES = ("executions.db", "executions.v1.db", "executions.v2.db", "history.db")
TERMINAL_FAILURES = frozenset({"failed", "failure", "error", "timeout", "cancelled", "blocked"})
JOB_ID_ALIASES = ("job_id", "id", "jobId", "job")
JOB_ID_SENTINELS = frozenset({"", "unknown", "unavailable", "none", "null", "n/a", "na"})


def _finding(check: str, status: str, detail: str, **extra: Any) -> dict[str, Any]:
    result = {"check": check, "status": status, "detail": detail}
    result.update(extra)
    return result


def _time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _job_label(job: Mapping[str, Any], index: int) -> str:
    safe = redact(dict(job))
    return f"job-{stable_fingerprint({'index': index, 'job': safe})[:8]}"


def _stable_job_identity(value: Mapping[str, Any]) -> str | None:
    """Return one unambiguous, non-sentinel identity from supported aliases."""
    candidates: set[str] = set()
    for alias in JOB_ID_ALIASES:
        candidate = value.get(alias)
        if isinstance(candidate, (str, int)) and not isinstance(candidate, bool):
            normalized = str(candidate).strip()
            if normalized.lower() not in JOB_ID_SENTINELS:
                candidates.add(normalized)
    if len(candidates) != 1:
        return None
    return candidates.pop()


def _read_json(path: Path) -> tuple[list[dict[str, Any]], str | None]:
    try:
        if path.stat().st_size > MAX_BYTES:
            return [], "bounded file size exceeded"
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return [], "metadata is malformed or unreadable"
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, dict) and isinstance(raw.get("jobs"), list):
        items = raw["jobs"]
    elif isinstance(raw, dict) and isinstance(raw.get("items"), list):
        items = raw["items"]
    else:
        return [], "metadata schema is unknown"
    jobs = [dict(item) for item in items[:MAX_ROWS] if isinstance(item, dict)]
    if len(jobs) != min(len(items), MAX_ROWS):
        return jobs, "metadata contains non-object job rows"
    return jobs, None


def _read_executions(path: Path) -> tuple[list[dict[str, Any]], str | None]:
    uri = f"file:{path.as_posix()}?mode=ro"
    try:
        with sqlite3.connect(uri, uri=True, timeout=1) as connection:
            tables = [row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
            table = next((name for name in ("executions", "job_executions", "runs", "history") if name in tables), None)
            if table is None:
                return [], "execution schema is unknown"
            columns = [row[1] for row in connection.execute(f'PRAGMA table_info("{table}")').fetchall()]
            if not columns:
                return [], "execution schema is unknown"
            quoted = ", ".join('"' + col.replace('"', '""') + '"' for col in columns)
            rows = connection.execute(f'SELECT {quoted} FROM "{table}" LIMIT {MAX_ROWS}').fetchall()
    except (sqlite3.Error, OSError):
        return [], "execution database is unavailable or unreadable"
    return [dict(zip(columns, row)) for row in rows], None


def _canonical_job(raw: dict[str, Any], index: int) -> dict[str, Any]:
    delivery = raw.get("delivery", raw.get("delivery_status"))
    artifact = raw.get("artifact", raw.get("artifact_status"))
    execution = raw.get("last_status", raw.get("status", raw.get("last_result")))
    enabled = not bool(raw.get("paused", raw.get("disabled", False)))
    if "enabled" in raw:
        enabled = bool(raw["enabled"])
    return {
        "label": _job_label(raw, index),
        "_job_identity": _stable_job_identity(raw),
        "enabled": enabled,
        "schedule": raw.get("schedule", raw.get("cron", raw.get("interval"))),
        "next_run_at": raw.get("next_run_at", raw.get("nextRunAt", raw.get("due_at"))),
        "last_run_at": raw.get("last_run_at", raw.get("lastRunAt", raw.get("completed_at"))),
        "execution": str(execution).lower() if execution is not None else "unknown",
        "delivery": delivery,
        "artifact": artifact,
        "config_status": str(raw.get("config_status", raw.get("configuration", "ok"))).lower(),
        "raw": redact(raw),
    }


def classify_job(job: dict[str, Any], executions: list[dict[str, Any]] | None = None, *, now: datetime | None = None) -> list[str]:
    current = now or datetime.now(timezone.utc)
    if not job.get("enabled", False):
        return []
    categories: list[str] = []
    config = job.get("config_status", "ok")
    if config in {"drift", "blocked", "invalid", "missing", "error", "failed"} or job.get("raw", {}).get("script_missing") is True:
        categories.append("pre-dispatch")
    status = str(job.get("execution", "unknown")).lower()
    if status in TERMINAL_FAILURES or status in {"unknown", ""}:
        categories.append("execution")
    artifact = job.get("artifact")
    if artifact is True or str(artifact).lower() in {"failed", "failure", "error", "missing"} or (isinstance(artifact, dict) and str(artifact.get("status", "")).lower() in {"failed", "error"}):
        categories.append("side-effect")
    delivery = job.get("delivery")
    if str(delivery).lower() in {"failed", "failure", "error", "undelivered"} or (isinstance(delivery, dict) and str(delivery.get("status", "")).lower() in {"failed", "error"}):
        categories.append("delivery")
    due = _time(job.get("next_run_at"))
    if due is not None and due < current and job.get("schedule"):
        categories.append("overdue")
    identity = job.get("_job_identity")
    failures = [
        item for item in (executions or [])
        if identity is not None
        and _stable_job_identity(item) == identity
        and str(item.get("status", item.get("result", ""))).lower() in TERMINAL_FAILURES
    ]
    if len(failures) >= 2:
        categories.append("repeated-failure")
    return categories


def inspect_cron(home: str | Path, *, now: datetime | None = None) -> dict[str, Any]:
    root = Path(home).expanduser()
    base = root / "cron"
    json_path = next((base / name for name in JSON_NAMES if (base / name).is_file()), None)
    if json_path is None:
        json_path = next((root / name for name in JSON_NAMES if (root / name).is_file()), None)
    db_path = next((base / name for name in SQLITE_NAMES if (base / name).is_file()), None)
    if db_path is None:
        db_path = next((root / name for name in SQLITE_NAMES if (root / name).is_file()), None)
    findings: list[dict[str, Any]] = []
    if json_path is None:
        jobs, json_error = [], None
    else:
        jobs, json_error = _read_json(json_path)
    if json_path is None:
        findings.append(_finding("cron:jobs", "unavailable", "cron job metadata unavailable", optional=True))
    elif json_error:
        findings.append(_finding("cron:jobs", "unknown", json_error, source="explicit-cron-fixture"))
    else:
        findings.append(_finding("cron:jobs", "available", "bounded job metadata read", count=len(jobs), source="explicit-cron-fixture"))
    executions, db_error = ([], "execution metadata unavailable") if db_path is None else _read_executions(db_path)
    if db_error:
        findings.append(_finding("cron:executions", "unavailable" if db_path is None else "unknown", db_error, optional=db_path is None))
    else:
        findings.append(_finding("cron:executions", "available", "read-only bounded execution metadata read", count=len(executions)))
    canonical = [_canonical_job(item, index) for index, item in enumerate(jobs)]
    for job in canonical:
        for category in classify_job(job, executions, now=now):
            findings.append(_finding(f"cron:{category}", "warning", f"enabled job classified as {category}", job=job["label"]))
    statuses = {item["status"] for item in findings}
    overall = "warning" if "warning" in statuses else ("unknown" if "unknown" in statuses else ("available" if "available" in statuses else "unavailable"))
    return {"schema": "cron-inspection.v1", "status": overall, "findings": findings, "jobs": [{k: v for k, v in job.items() if k not in {"raw", "_job_identity"}} for job in canonical], "execution_count": len(executions)}
