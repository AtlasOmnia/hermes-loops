from __future__ import annotations

import os
from pathlib import Path


def discover_hermes_home(explicit: str | None = None) -> Path:
    """Resolve a Hermes home without inspecting or creating it."""
    value = explicit or os.environ.get("HERMES_HOME")
    return Path(value).expanduser() if value else Path.home() / ".hermes"


def default_runtime_dir() -> Path:
    """Return external package state, never a repository directory."""
    root = os.environ.get("XDG_STATE_HOME")
    if root:
        return Path(root) / "hermes-health-improvement-loops"
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "hermes-health-improvement-loops"
    if os.uname().sysname == "Darwin":
        return Path.home() / "Library" / "Application Support" / "hermes-health-improvement-loops"
    return Path.home() / ".local" / "state" / "hermes-health-improvement-loops"


def relative_label(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return "external"
