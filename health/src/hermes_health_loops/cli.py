from __future__ import annotations

import argparse
import json
from pathlib import Path

from .health import audit_discovered_home
from .improvement import collect_packets, evaluate_packets, write_runtime_artifacts
from .paths import default_runtime_dir
from .report import unified_report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hermes-health-loops")
    sub = parser.add_subparsers(dest="command", required=True)
    health = sub.add_parser("health")
    health.add_argument("--hermes-home")
    improvement = sub.add_parser("improvement")
    improvement.add_argument("--source", action="append", required=True)
    improvement.add_argument("--runtime-dir", default=str(default_runtime_dir()))
    report = sub.add_parser("report")
    report.add_argument("--hermes-home")
    report.add_argument("--source", action="append")
    report.add_argument("--runtime-dir", default=str(default_runtime_dir()))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "health":
        output = audit_discovered_home(args.hermes_home)
    elif args.command == "improvement":
        packets = collect_packets(args.source)
        output = evaluate_packets(packets)
        output["runtime"] = write_runtime_artifacts(output, packets, args.runtime_dir)
    else:
        health = audit_discovered_home(args.hermes_home)
        improvement = None
        if args.source:
            packets = collect_packets(args.source)
            improvement = evaluate_packets(packets)
            improvement["runtime"] = write_runtime_artifacts(improvement, packets, args.runtime_dir)
        output = unified_report(health, improvement)
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
