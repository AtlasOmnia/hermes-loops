from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
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
        dates = [parsed for p in group if p["day"] != "unknown-date" if (parsed := parse_time(p["day"])) is not None]
        newest = max(dates, default=None)
        decision = evaluate_kind(kind, len(group), newest, current)
        if decision in {"critical-signal", "repeat-signal"} or (decision == "watch-signal" and len(group) >= REPEAT_COUNT):
            proposals.append({"fingerprint": fingerprint, "classification": decision, "count": len(group), "window_days": WINDOW_DAYS, "suggestion_only": True, "approved": False, "applied": False, "lifecycle": "suggested", "action": "human review required"})
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
