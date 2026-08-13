from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hermes_health_loops.improvement import collect_packets, evaluate_packets, write_runtime_artifacts
from hermes_health_loops.redact import redact
from hermes_health_loops.rubric import REPEAT_COUNT, WINDOW_DAYS


class ImprovementTests(unittest.TestCase):
    def test_redaction_and_compact_packets(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "fixture.json"
            source.write_text(json.dumps([{"kind": "warning", "timestamp": "2026-01-01T00:00:00Z", "result": "token-abcdefghijklmnopqrstuvwxyz0123456789", "api_key": "do-not-retain"}]), encoding="utf-8")
            packets = collect_packets([source])
            payload = json.dumps(packets)
            self.assertNotIn("do-not-retain", payload)
            self.assertNotIn("abcdefghijklmnopqrstuvwxyz", payload)
            self.assertEqual(set(packets[0]), {"schema", "kind", "day", "fingerprint", "signal"})
            self.assertEqual(redact({"password": "secret"})["password"], "[redacted]")

    def test_frozen_thresholds_do_not_promote_two_repeats(self) -> None:
        self.assertEqual(REPEAT_COUNT, 3)
        self.assertEqual(WINDOW_DAYS, 7)
        packets = [{"schema": "outcome-packet.v1", "kind": "warning", "day": "2026-01-01", "fingerprint": "same", "signal": {}} for _ in range(2)]
        result = evaluate_packets(packets, now=datetime(2026, 1, 2, tzinfo=timezone.utc))
        self.assertEqual(result["proposals"], [])

    def test_repeated_signal_is_suggestion_only_and_external(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "fixture.json"
            source.write_text(json.dumps([{"kind": "warning", "timestamp": f"2026-01-0{i}T00:00:00Z", "result": "same"} for i in range(1, 4)]), encoding="utf-8")
            packets = collect_packets([source])
            result = evaluate_packets(packets, now=datetime(2026, 1, 4, tzinfo=timezone.utc))
            self.assertEqual(len(result["proposals"]), 1)
            proposal = result["proposals"][0]
            self.assertTrue(proposal["suggestion_only"])
            self.assertFalse(proposal["approved"])
            self.assertFalse(proposal["applied"])
            paths = write_runtime_artifacts(result, packets, Path(temp) / "runtime")
            self.assertTrue(Path(paths["ledger"]).exists())
            self.assertTrue(Path(paths["proposals"]).exists())


if __name__ == "__main__":
    unittest.main()
