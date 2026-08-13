from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import datetime, timezone
import time
from pathlib import Path
from typing import Any

from .cron_inspector import inspect_cron
from .paths import discover_hermes_home

MAX_FILES = 80
MAX_BYTES = 64 * 1024
SESSION_MAX_AGE_DAYS = 30
STORAGE_WARN_RATIO = 0.90


def _finding(check: str, status: str, detail: str, **extra: Any) -> dict[str, Any]:
    result = {"check": check, "status": status, "detail": detail}
    result.update(extra)
    return result


def _bounded_files(root: Path, suffixes: tuple[str, ...]) -> list[Path]:
    if not root.is_dir():
        return []
    found: list[Path] = []
    try:
        for path in sorted(root.iterdir()):
            if path.is_file() and (not suffixes or path.suffix.lower() in suffixes):
                found.append(path)
            if len(found) >= MAX_FILES:
                break
    except OSError:
        return []
    return found


def _read_json(path: Path) -> Any:
    try:
        if path.stat().st_size > MAX_BYTES:
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None


def _check_core(home: Path) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for rel, optional in (("config.yaml", False), ("state.db", False), ("sessions", True), ("logs", True), ("skills", True), ("cron", True)):
        exists = (home / rel).exists()
        checks.append(_finding("core:" + rel, "available" if exists else ("unavailable" if optional else "warning"), "discoverable" if exists else "not discoverable", optional=optional))
    return checks


def _check_sessions(home: Path, now: float) -> dict[str, Any]:
    root = home / "sessions"
    if not root.is_dir():
        return _finding("sessions:age", "unavailable", "optional session surface unavailable", optional=True)
    files = _bounded_files(root, (".jsonl", ".json", ".db"))
    ages = []
    for path in files:
        try:
            ages.append(max(0, int((now - path.stat().st_mtime) / 86400)))
        except OSError:
            continue
    if not ages:
        return _finding("sessions:age", "available", "no bounded session files found", count=0)
    stale = sum(age > SESSION_MAX_AGE_DAYS for age in ages)
    return _finding("sessions:age", "warning" if stale else "healthy", "bounded metadata age sample", count=len(ages), stale_count=stale, max_age_days=max(ages), threshold_days=SESSION_MAX_AGE_DAYS)


def _check_storage(home: Path) -> dict[str, Any]:
    try:
        usage = os.statvfs(home)
        ratio = 1 - (usage.f_bavail / usage.f_blocks) if usage.f_blocks else 0.0
        return _finding("storage:filesystem", "warning" if ratio >= STORAGE_WARN_RATIO else "healthy", "filesystem capacity signal", used_ratio=round(ratio, 4), warning_ratio=STORAGE_WARN_RATIO)
    except OSError:
        return _finding("storage:filesystem", "unavailable", "filesystem capacity unavailable", optional=True)


def _check_cron(home: Path, now: float | None = None) -> list[dict[str, Any]]:
    inspected = inspect_cron(home, now=(None if now is None else datetime.fromtimestamp(now, timezone.utc)))
    return inspected["findings"]


def _check_stalls(home: Path) -> dict[str, Any]:
    log_root = home / "logs"
    if not log_root.is_dir():
        return _finding("tools:stall-candidates", "unavailable", "optional log surface unavailable", optional=True)
    tool_calls = 0
    errors = 0
    repeated = 0
    for path in _bounded_files(log_root, (".log", ".txt", ".jsonl")):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")[:MAX_BYTES]
        except OSError:
            continue
        tool_calls += len(re.findall(r"tool[_ -]?call|tool_use", text, re.I))
        errors += len(re.findall(r"error|timeout|stuck|stall", text, re.I))
        repeated += len(re.findall(r"(tool[_ -]?call|timeout).*(?:\\n|$).*\\1", text, re.I))
    candidate = errors >= 3 and tool_calls >= 3
    return _finding("tools:stall-candidates", "warning" if candidate else "healthy", "bounded log signal; candidate is not proof", tool_calls=tool_calls, error_signals=errors, repeated_signals=repeated, candidate= candidate)


def _check_sqlite(home: Path) -> dict[str, Any]:
    path = home / "state.db"
    if not path.exists():
        return _finding("state:sqlite", "unavailable", "optional state database unavailable", optional=True)
    uri = f"file:{path.as_posix()}?mode=ro"
    try:
        with sqlite3.connect(uri, uri=True, timeout=1) as connection:
            row = connection.execute("SELECT 1").fetchone()
        return _finding("state:sqlite", "healthy" if row == (1,) else "warning", "read-only probe completed")
    except (sqlite3.Error, OSError):
        return _finding("state:sqlite", "warning", "read-only probe failed")


def audit_home(home: str | Path, *, now: float | None = None) -> dict[str, Any]:
    root = Path(home).expanduser()
    timestamp = time.time() if now is None else now
    findings: list[dict[str, Any]] = []
    if not root.exists():
        return {"schema": "health.v1", "status": "unavailable", "home": "hermes_home", "findings": [_finding("home", "unavailable", "Hermes home is not discoverable")]}
    findings.extend(_check_core(root))
    findings.append(_check_sessions(root, timestamp))
    findings.append(_check_storage(root))
    findings.extend(_check_cron(root, timestamp))
    findings.append(_check_stalls(root))
    findings.append(_check_sqlite(root))
    statuses = {item["status"] for item in findings}
    overall = "warning" if "warning" in statuses else ("unknown" if "unknown" in statuses else ("healthy" if "healthy" in statuses or "available" in statuses else "unavailable"))
    return {"schema": "health.v1", "status": overall, "home": "hermes_home", "findings": findings}


def audit_discovered_home(explicit: str | None = None, *, now: float | None = None) -> dict[str, Any]:
    return audit_home(discover_hermes_home(explicit), now=now)
