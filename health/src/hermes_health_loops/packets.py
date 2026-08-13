"""Portable, redacted outcome packets and frozen proposal lifecycle."""
from __future__ import annotations

from datetime import timezone
from typing import Any, Mapping

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


def _fail(message: str) -> None:
    raise PacketValidationError(message)


def _kind(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail("outcome kind is required")
    return value.strip().lower()[:48]


def normalize_outcome(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Redact first, then validate and normalize an explicit source record."""
    if not isinstance(raw, Mapping):
        _fail("outcome must be an object")
    safe = redact(dict(raw))
    kind = _kind(safe.get("kind", safe.get("outcome", "")))
    timestamp = safe.get("timestamp", safe.get("created_at"))
    parsed = parse_time(timestamp)
    day = parsed.astimezone(timezone.utc).strftime("%Y-%m-%d") if parsed else "unknown-date"
    result = safe.get("result", safe.get("status", "unspecified"))
    if not isinstance(result, str):
        result = str(result)
    signal = {"kind": kind, "day": day, "result": result[:80]}
    signal = redact(signal)
    return {"schema": SCHEMA, "kind": kind, "day": day, "fingerprint": stable_fingerprint(signal), "signal": signal}


def validate_packet(packet: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(packet, Mapping):
        _fail("packet must be an object")
    safe = redact(dict(packet))
    if safe.get("schema") != SCHEMA:
        _fail("unsupported packet schema")
    if not isinstance(safe.get("kind"), str) or not isinstance(safe.get("day"), str) or not isinstance(safe.get("fingerprint"), str) or not isinstance(safe.get("signal"), Mapping):
        _fail("packet shape is invalid")
    return {"schema": SCHEMA, "kind": safe["kind"][:48], "day": safe["day"][:16], "fingerprint": safe["fingerprint"][:64], "signal": redact(dict(safe["signal"]))}


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
