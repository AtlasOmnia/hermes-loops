from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hermes_maintenance_loops.packets import PacketValidationError, normalize_outcome, runtime_transition, transition_lifecycle
from hermes_maintenance_loops.improvement import collect_packets, evaluate_packets, write_runtime_artifacts


class PacketTests(unittest.TestCase):
    def test_redacts_before_fingerprint_and_runtime_persistence(self) -> None:
        raw = {"kind": "warning", "timestamp": "2026-01-01T00:00:00Z", "result": "secret-token-abcdefghijklmnopqrstuvwxyz0123456789", "password": "private-value"}
        packet = normalize_outcome(raw)
        self.assertNotIn("private-value", json.dumps(packet))
        self.assertNotIn("abcdefghijklmnopqrstuvwxyz", packet["fingerprint"])
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "source.json"
            source.write_text(json.dumps([raw]), encoding="utf-8")
            packets = collect_packets([source])
            result = evaluate_packets(packets)
            paths = write_runtime_artifacts(result, packets, Path(temp) / "runtime")
            persisted = Path(paths["ledger"]).read_text(encoding="utf-8")
            self.assertNotIn("private-value", persisted)

    def test_redact_preserves_iso_dates_and_redacts_phones(self) -> None:
        from hermes_maintenance_loops.redact import redact
        self.assertEqual(redact({"timestamp": "2026-01-01T00:00:00Z"})["timestamp"], "2026-01-01T00:00:00Z")
        self.assertEqual(redact("+1 (555) 123-4567"), "[redacted-phone]")

    def test_malformed_packet_error_does_not_echo_input(self) -> None:
        raw = {"schema": "bad", "secret": "do-not-echo"}
        with self.assertRaises(PacketValidationError) as caught:
            from hermes_maintenance_loops.packets import validate_packet
            validate_packet(raw)
        self.assertNotIn("do-not-echo", str(caught.exception))

    def test_runtime_cannot_approve_or_apply_lifecycle(self) -> None:
        with self.assertRaises(PacketValidationError):
            runtime_transition("suggested", "human-approved")
        with self.assertRaises(PacketValidationError):
            runtime_transition("human-approved", "experiment")
        self.assertEqual(transition_lifecycle("suggested", "human-approved", actor="human"), "human-approved")
        self.assertEqual(transition_lifecycle("human-approved", "experiment", actor="human"), "experiment")
        with self.assertRaises(PacketValidationError):
            transition_lifecycle("draft", "keep", actor="human")


if __name__ == "__main__":
    unittest.main()
