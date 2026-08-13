from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hermes_maintenance_loops.scheduler import ManifestValidationError, validate_owned_manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Remove package-owned external manifests")
    parser.add_argument("--runtime-dir", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--rollback", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    root = Path(args.runtime_dir).expanduser().resolve()
    current = root / "install-manifest.json"
    previous = root / "install-manifest.previous.json"
    if args.rollback:
        if not previous.exists():
            print("UNAVAILABLE: previous package manifest")
            return 0
        try:
            validate_owned_manifest(previous, root)
            if current.exists():
                validate_owned_manifest(current, root)
        except ManifestValidationError as error:
            print(f"REFUSED: {error}", file=sys.stderr)
            return 2
        if args.apply and not args.dry_run:
            if current.exists():
                current.unlink()
            previous.replace(current)
            print(f"ROLLED BACK: {current}")
        else:
            print(f"DRY-RUN ROLLBACK: {previous} -> {current}")
        return 0
    for target in (current, previous):
        if not target.exists():
            print("UNAVAILABLE: package manifest")
            continue
        try:
            validate_owned_manifest(target, root)
        except ManifestValidationError as error:
            print(f"REFUSED: {error}", file=sys.stderr)
            return 2
        if args.apply and not args.dry_run:
            target.unlink()
            print(f"REMOVED: {target}")
        else:
            print(f"DRY-RUN REMOVE: {target}")
    if not args.apply or args.dry_run:
        print("DRY-RUN: no files changed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
