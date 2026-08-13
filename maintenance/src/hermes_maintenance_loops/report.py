from __future__ import annotations

from typing import Any


def unified_report(health: dict[str, Any] | None = None, improvement: dict[str, Any] | None = None) -> dict[str, Any]:
    """Assemble independent reports without collecting or mutating either source."""
    result: dict[str, Any] = {"schema": "report.v1", "modules": {}}
    if health is not None:
        result["modules"]["health"] = health
    if improvement is not None:
        result["modules"]["improvement"] = improvement
    return result
