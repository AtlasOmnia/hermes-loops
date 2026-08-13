"""Pure reviewed-manifest renderer for optional Hermes scheduling.

This module is intentionally incapable of invoking Hermes, starting a process,
using the network, or writing a Hermes home.  It only validates explicit input
and renders command proposals for a human to review.
"""
from __future__ import annotations

import json
import shlex
from pathlib import Path
from typing import Any, Mapping

SCHEMA = "install-manifest.v2"
PACKAGE = "hermes-health-improvement-loops"
PACKAGE_OWNER = "hermes-health-improvement-loops"
MODULES = frozenset({"health", "improvement"})


class ManifestValidationError(ValueError):
    """Raised for a malformed or incomplete reviewed scheduling request."""


def _explicit(label: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ManifestValidationError(f"{label} must be explicit")
    value = value.strip()
    if value.startswith("<") and value.endswith(">"):
        raise ManifestValidationError(f"{label} must be an explicit value")
    return value


def validate_request(request: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(request, Mapping):
        raise ManifestValidationError("manifest request must be an object")
    if request.get("schema") not in {None, SCHEMA}:
        raise ManifestValidationError("unsupported manifest schema")
    raw_modules = request.get("modules")
    if not isinstance(raw_modules, (list, tuple)) or not raw_modules:
        raise ManifestValidationError("modules must explicitly select health and/or improvement")
    modules: list[str] = []
    for module in raw_modules:
        if not isinstance(module, str) or module not in MODULES or module in modules:
            raise ManifestValidationError("modules contains an invalid or duplicate selection")
        modules.append(module)
    schedules_raw = request.get("schedules")
    if not isinstance(schedules_raw, Mapping):
        raise ManifestValidationError("schedules must be explicit")
    schedules: dict[str, str] = {}
    for module in modules:
        schedules[module] = _explicit(f"{module} schedule", schedules_raw.get(module))
    provider = _explicit("provider", request.get("provider"))
    model = _explicit("model", request.get("model"))
    delivery = _explicit("delivery", request.get("delivery"))
    hermes_home = _explicit("hermes_home", request.get("hermes_home"))
    acknowledgement = request.get("review_acknowledged")
    if acknowledgement is not True:
        raise ManifestValidationError("review acknowledgement must be explicit")
    runtime_dir = _explicit("runtime_dir", request.get("runtime_dir"))
    return {
        "schema": SCHEMA,
        "package": PACKAGE,
        "ownership": PACKAGE_OWNER,
        "modules": modules,
        "schedules": schedules,
        "provider": provider,
        "model": model,
        "delivery": delivery,
        "hermes_home": hermes_home,
        "runtime_dir": str(Path(runtime_dir).expanduser()),
        "review_acknowledged": True,
    }


def _quoted(value: str) -> str:
    return shlex.quote(value)


def render_command_proposals(manifest: Mapping[str, Any]) -> list[str]:
    """Render exact, non-executed native Hermes cron proposals."""
    validated = validate_request(manifest)
    proposals: list[str] = []
    for module in validated["modules"]:
        schedule = validated["schedules"][module]
        prompt = (
            "Before manually running this proposal, establish the selected Hermes "
            "context from the manifest. "
            f"Run hermes-health-improvement-loops {module}; emit a redacted result only."
        )
        command = " ".join(
            [
                "hermes cron create",
                _quoted(schedule),
                _quoted(prompt),
                "--provider", _quoted(validated["provider"]),
                "--model", _quoted(validated["model"]),
                "--deliver", _quoted(validated["delivery"]),
            ]
        )
        proposals.append(f"REVIEW ONLY — NOT EXECUTED: {command}")
    return proposals


def render_manifest(request: Mapping[str, Any]) -> dict[str, Any]:
    validated = validate_request(request)
    proposals = render_command_proposals(validated)
    return {
        **validated,
        "commands": proposals,
        "command_execution": "never by this package",
        "apply_policy": "manifest-only; never create Hermes jobs automatically",
    }


def manifest_json(request: Mapping[str, Any]) -> str:
    return json.dumps(render_manifest(request), indent=2, sort_keys=True) + "\n"


def validate_owned_manifest(path: str | Path, runtime_dir: str | Path) -> dict[str, Any]:
    """Validate package ownership before uninstall or rollback."""
    target = Path(path).expanduser().resolve()
    root = Path(runtime_dir).expanduser().resolve()
    if target.parent != root or target.name not in {"install-manifest.json", "install-manifest.previous.json"}:
        raise ManifestValidationError("manifest is outside the selected package runtime directory")
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise ManifestValidationError("manifest is unreadable") from None
    if not isinstance(data, dict) or data.get("schema") != SCHEMA or data.get("package") != PACKAGE or data.get("ownership") != PACKAGE_OWNER:
        raise ManifestValidationError("manifest ownership or version is invalid")
    if Path(str(data.get("runtime_dir", ""))).expanduser().resolve() != root:
        raise ManifestValidationError("manifest runtime ownership is invalid")
    return data
