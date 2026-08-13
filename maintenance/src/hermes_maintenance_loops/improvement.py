from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from .packets import normalize_outcome, validate_packet
from .redact import redact
from .rubric import CRITICAL_KINDS, REPEAT_COUNT, WINDOW_DAYS, evaluate_kind, parse_time

MAX_SOURCE_BYTES = 128 * 1024
MAX_PACKETS = 200


def _load_source(path: Path) -> list[dict[str, Any]]:
    try:
        if path.stat().st_size > MAX_SOURCE_BYTES:
            raise ValueError("source exceeds bounded packet size")
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise FileNotFoundError("explicit improvement source unavailable") from None
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise ValueError("explicit improvement source is malformed or unreadable") from None
    if isinstance(raw, dict):
        raw = raw.get("outcomes", raw.get("packets", [raw]))
    if not isinstance(raw, list):
        raise ValueError("explicit improvement source shape is invalid")
    return [item for item in raw[:MAX_PACKETS] if isinstance(item, dict)]


def collect_packets(sources: Iterable[str | Path]) -> list[dict[str, Any]]:
    paths = [Path(source).expanduser() for source in sources]
    packets: list[dict[str, Any]] = []
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError("explicit improvement source unavailable")
        packets.extend(normalize_outcome(item) for item in _load_source(path))
    return packets[:MAX_PACKETS]


def evaluate_packets(packets: list[dict[str, Any]], *, now: datetime | None = None) -> dict[str, Any]:
    current = now or datetime.now(timezone.utc)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for packet in packets:
        safe_packet = validate_packet(packet)
        grouped[safe_packet["fingerprint"]].append(safe_packet)
    proposals: list[dict[str, Any]] = []
    counts = Counter(packet["kind"] for packet in packets)
    for fingerprint, group in sorted(grouped.items()):
        kind = group[0]["kind"]
        session_days: dict[str, str] = {}
        for packet in group:
            session = packet.get("session", "unspecified")
            day = packet["day"]
            if session not in session_days:
                session_days[session] = day
            elif day != "unknown-date" and (session_days[session] == "unknown-date" or day < session_days[session]):
                session_days[session] = day
        distinct = len(session_days)
        parsed_days = [d for d in (parse_time(day) for day in session_days.values()) if d is not None]
        newest = max(parsed_days, default=None)
        oldest = min(parsed_days, default=None)
        span_ok = newest is not None and oldest is not None and (newest - oldest) <= timedelta(days=WINDOW_DAYS)
        decision = evaluate_kind(kind, distinct, newest, current)
        if decision == "critical-signal" or (decision == "repeat-signal" and span_ok):
            proposals.append({"fingerprint": fingerprint, "classification": decision, "count": distinct, "window_days": WINDOW_DAYS, "suggestion_only": True, "approved": False, "applied": False, "lifecycle": "suggested", "action": "human review required"})
    return {"schema": "improvement.v1", "packet_count": len(packets), "kind_counts": dict(sorted(counts.items())), "proposals": proposals, "policy": {"suggestion_only": True, "approval": "never automatic", "application": "never automatic", "repeat_count": REPEAT_COUNT, "window_days": WINDOW_DAYS, "critical_kinds": sorted(CRITICAL_KINDS)}}


def write_runtime_artifacts(result: dict[str, Any], packets: list[dict[str, Any]], runtime_dir: str | Path) -> dict[str, str]:
    root = Path(runtime_dir).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    ledger = root / "redacted-ledger.jsonl"
    proposals = root / "suggestion-proposals.jsonl"
    with ledger.open("a", encoding="utf-8") as handle:
        for packet in packets:
            handle.write(json.dumps(redact(validate_packet(packet)), sort_keys=True) + "\n")
    with proposals.open("a", encoding="utf-8") as handle:
        for proposal in result["proposals"]:
            handle.write(json.dumps(redact(proposal), sort_keys=True) + "\n")
    return {"ledger": str(ledger), "proposals": str(proposals)}
