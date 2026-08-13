from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hermes_maintenance_loops.scheduler import ManifestValidationError, render_manifest

PACKAGE = "hermes-maintenance-loops"


def default_runtime_dir() -> Path:
    if os.environ.get("XDG_STATE_HOME"):
        return Path(os.environ["XDG_STATE_HOME"]) / PACKAGE
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", Path.home())) / PACKAGE
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / PACKAGE
    return Path.home() / ".local" / "state" / PACKAGE


def parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render or apply a safe package manifest")
    parser.add_argument("--modules", required=True)
    parser.add_argument("--health-schedule")
    parser.add_argument("--improvement-schedule")
    parser.add_argument("--provider", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--delivery", required=True)
    parser.add_argument("--hermes-home", required=True)
    parser.add_argument("--runtime-dir", default=str(default_runtime_dir()))
    parser.add_argument("--review-acknowledged", action="store_true")
    parser.add_argument("--apply", action="store_true")
    return parser


def request_from_args(args: argparse.Namespace) -> dict[str, object]:
    modules = [item.strip() for item in args.modules.split(",") if item.strip()]
    return {"schema": "install-manifest.v2", "modules": modules, "schedules": {"health": args.health_schedule, "improvement": args.improvement_schedule}, "provider": args.provider, "model": args.model, "delivery": args.delivery, "hermes_home": args.hermes_home, "runtime_dir": args.runtime_dir, "review_acknowledged": args.review_acknowledged}


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        manifest = render_manifest(request_from_args(args))
    except ManifestValidationError as error:
        print(f"INVALID MANIFEST: {error}", file=sys.stderr)
        return 2
    print(json.dumps(manifest, indent=2, sort_keys=True))
    if not args.apply:
        print("DRY-RUN: no files or Hermes jobs changed")
        return 0
    root = Path(args.runtime_dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    target = root / "install-manifest.json"
    if target.exists():
        target.replace(root / "install-manifest.previous.json")
    target.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"APPLIED MANIFEST ONLY: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
