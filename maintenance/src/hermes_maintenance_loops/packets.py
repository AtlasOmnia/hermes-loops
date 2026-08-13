"""Portable, redacted outcome packets and frozen proposal lifecycle."""
from __future__ import annotations

from datetime import timezone
from typing import Any, Mapping, NoReturn

from .redact import redact, stable_fingerprint
from .rubric import parse_time

SCHEMA = "outcome-packet.v1"
LIFECYCLE_STATES = ("draft", "watch", "suggested", "human-approved", "experiment", "keep", "revert")
LIFECYCLE_TRANSITIONS = {
    "draft": frozenset({"watch", "suggested"}),
    "watch": frozenset({"suggested"}),
    "suggested": frozenset({"human-approved"}),
    "human-approved": frozenset({"experiment"}),
    "experiment": frozenset({"keep", "revert"}),
    "keep": frozenset(),
    "revert": frozenset(),
}


class PacketValidationError(ValueError):
    """A safe validation error that never includes caller data."""


def _fail(message: str) -> NoReturn:
    raise PacketValidationError(message)


_SESSION_KEYS = ("session", "session_id", "source_id", "lineage", "lineage_id", "source")


def _session(value: Any) -> str:
    """Normalize a session/lineage identifier. An identifier, not a secret."""
    if value is None or not isinstance(value, str) or not value.strip():
        return "unspecified"
    return value.strip().lower()[:64]


def _kind(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail("outcome kind is required")
    return value.strip().lower()[:48]


def normalize_outcome(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and normalize an explicit source record; content is redacted, while the timestamp and session lineage are read from the raw input."""
    if not isinstance(raw, Mapping):
        _fail("outcome must be an object")
    session = _session(next((raw.get(k) for k in _SESSION_KEYS if raw.get(k)), None))
    timestamp = raw.get("timestamp", raw.get("created_at"))
    parsed = parse_time(timestamp)
    day = parsed.astimezone(timezone.utc).strftime("%Y-%m-%d") if parsed else "unknown-date"
    safe = redact(dict(raw))
    kind = _kind(safe.get("kind", safe.get("outcome", "")))
    result = safe.get("result", safe.get("status", "unspecified"))
    if not isinstance(result, str):
        result = str(result)
    signal = {"kind": kind, "result": result[:80]}
    signal = redact(signal)
    return {"schema": SCHEMA, "kind": kind, "day": day, "session": session, "fingerprint": stable_fingerprint(signal), "signal": signal}


def validate_packet(packet: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(packet, Mapping):
        _fail("packet must be an object")
    if packet.get("schema") != SCHEMA:
        _fail("unsupported packet schema")
    kind = packet.get("kind")
    day = packet.get("day")
    fingerprint = packet.get("fingerprint")
    signal = packet.get("signal")
    if not isinstance(kind, str) or not isinstance(day, str) or not isinstance(fingerprint, str) or not isinstance(signal, Mapping):
        _fail("packet shape is invalid")
    return {"schema": SCHEMA, "kind": redact(kind)[:48], "day": day[:16], "session": _session(packet.get("session", "unspecified")), "fingerprint": fingerprint[:64], "signal": redact(signal)}


def transition_lifecycle(current: str, target: str, *, actor: str = "runtime") -> str:
    """Apply only source-defined transitions; runtime cannot approve or apply."""
    if current not in LIFECYCLE_STATES or target not in LIFECYCLE_STATES:
        _fail("unknown lifecycle state")
    if target not in LIFECYCLE_TRANSITIONS[current]:
        _fail("lifecycle transition is not permitted")
    if actor == "runtime" and target in {"human-approved", "experiment", "keep", "revert"}:
        _fail("runtime cannot approve, apply, keep, or revert proposals")
    if target in {"human-approved", "experiment", "keep", "revert"} and actor != "human":
        _fail("human acknowledgement is required for this lifecycle state")
    return target


def runtime_transition(current: str, target: str) -> str:
    return transition_lifecycle(current, target, actor="runtime")
