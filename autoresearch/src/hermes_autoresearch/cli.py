from __future__ import annotations

from typing import Optional

from .config import AutoresearchConfig
from .orchestrator import AutoresearchHarness


def main(argv: Optional[list[str]] = None) -> int:
    cfg = AutoresearchConfig.parse_cli(argv)
    result = AutoresearchHarness(cfg).run()
    print(f"best_score={result['best_score']}")
    print(f"trials={len(result['trials'])}")
    print(f"head={result['head']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
