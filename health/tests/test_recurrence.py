from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hermes_health_loops.improvement import evaluate_packets
from hermes_health_loops.packets import normalize_outcome


def _outcome(kind: str, day: str, result: str, session: str | None = None) -> dict[str, object]:
    raw: dict[str, object] = {
        "kind": kind,
        "timestamp": f"{day}T00:00:00Z",
        "result": result,
    }
    if session is not None:
        raw["session"] = session
    return raw


class RecurrenceTests(unittest.TestCase):
    def test_fingerprint_is_date_independent(self) -> None:
        a = normalize_outcome(_outcome("warning", "2026-01-01", "retry", "s1"))
        b = normalize_outcome(_outcome("warning", "2026-01-03", "retry", "s2"))
        self.assertEqual(a["fingerprint"], b["fingerprint"])
        self.assertNotEqual(a["day"], b["day"])
        self.assertEqual(a["session"], "s1")
        self.assertEqual(b["session"], "s2")

    def test_duplicate_same_session_do_not_promote(self) -> None:
        packets = [normalize_outcome(_outcome("warning", "2026-01-01", "retry", "s1")) for _ in range(3)]
        result = evaluate_packets(packets, now=datetime(2026, 1, 2, tzinfo=timezone.utc))
        self.assertEqual(result["proposals"], [])

    def test_three_distinct_sessions_within_window_promote(self) -> None:
        packets = [normalize_outcome(_outcome("warning", f"2026-01-0{i}", "retry", f"s{i}")) for i in range(1, 4)]
        result = evaluate_packets(packets, now=datetime(2026, 1, 4, tzinfo=timezone.utc))
        self.assertEqual(len(result["proposals"]), 1)
        self.assertEqual(result["proposals"][0]["count"], 3)

    def test_three_distinct_sessions_over_span_do_not_promote(self) -> None:
        days = ["2026-01-01", "2026-01-05", "2026-01-10"]
        packets = [normalize_outcome(_outcome("warning", d, "retry", f"s{i}")) for i, d in enumerate(days, 1)]
        result = evaluate_packets(packets, now=datetime(2026, 1, 11, tzinfo=timezone.utc))
        self.assertEqual(result["proposals"], [])

    def test_stale_recurrence_does_not_promote(self) -> None:
        packets = [normalize_outcome(_outcome("warning", f"2026-01-0{i}", "retry", f"s{i}")) for i in range(1, 4)]
        result = evaluate_packets(packets, now=datetime(2026, 1, 20, tzinfo=timezone.utc))
        self.assertEqual(result["proposals"], [])

    def test_critical_single_occurrence_promotes(self) -> None:
        packets = [normalize_outcome(_outcome("critical", "2026-01-01", "data loss", "s1"))]
        result = evaluate_packets(packets, now=datetime(2026, 1, 2, tzinfo=timezone.utc))
        self.assertEqual(len(result["proposals"]), 1)

    def test_missing_session_does_not_promote(self) -> None:
        packets = [normalize_outcome(_outcome("warning", "2026-01-01", "retry")) for _ in range(3)]
        result = evaluate_packets(packets, now=datetime(2026, 1, 2, tzinfo=timezone.utc))
        self.assertEqual(result["proposals"], [])


if __name__ == "__main__":
    unittest.main()
