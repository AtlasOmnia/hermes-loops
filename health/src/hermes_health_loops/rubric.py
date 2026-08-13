"""Frozen, suggestion-only evaluation constants. Do not tune at runtime."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

WINDOW_DAYS = 7
REPEAT_COUNT = 3
CRITICAL_KINDS = frozenset({"critical", "incident", "data-loss"})
WATCH_KINDS = frozenset({"warning", "degraded", "timeout", "stall"})


def parse_time(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.replace(tzinfo=parsed.tzinfo or timezone.utc)
    except ValueError:
        return None


def evaluate_kind(kind: str, count: int, newest: datetime | None, now: datetime) -> str:
    if kind in CRITICAL_KINDS:
        return "critical-signal"
    if count >= REPEAT_COUNT and newest and now - newest <= timedelta(days=WINDOW_DAYS):
        return "repeat-signal"
    if kind in WATCH_KINDS:
        return "watch-signal"
    return "insufficient-signal"
