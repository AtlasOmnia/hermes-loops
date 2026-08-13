#!/usr/bin/env python3
"""Assemble one bounded trial prompt and invoke a configurable agent safely."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import List, NoReturn


def fail(message: str) -> NoReturn:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(2)


def required_env(name: str) -> str:
    value = os.environ.get(name, "")
    if not value.strip():
        fail(f"{name} is required and must not be empty")
    return value


def parse_agent_command(raw: str) -> List[str]:
    try:
        command = json.loads(raw)
    except json.JSONDecodeError as exc:
        fail(f"AGENT_COMMAND_JSON must be valid JSON: {exc.msg}")
    if not isinstance(command, list) or not command:
        fail("AGENT_COMMAND_JSON must be a nonempty JSON array of strings")
    if not all(isinstance(part, str) and part for part in command):
        fail("AGENT_COMMAND_JSON must contain only nonempty strings")
    return command


def main() -> int:
    if len(sys.argv) != 2 or not sys.argv[1].strip():
        fail("a nonempty objective argument is required")
    objective = sys.argv[1].strip()

    trial = required_env("AR_TRIAL")
    repo_path = required_env("AR_REPO_PATH")
    allowed_paths = required_env("TRIAL_ALLOWED_PATHS")
    previous_score = os.environ.get("AR_PREVIOUS_SCORE", "").strip() or "none"
    command = parse_agent_command(required_env("AGENT_COMMAND_JSON"))

    default_contract = Path(__file__).resolve().parents[1] / "contracts" / "trial_contract.md"
    contract_path = Path(os.environ.get("CONTRACT_FILE", str(default_contract))).expanduser()
    if not contract_path.is_file():
        fail(f"contract file not found: {contract_path}")

    repo_root = Path(repo_path).expanduser().resolve()
    if not repo_root.is_dir():
        fail(f"AR_REPO_PATH is not a directory: {repo_root}")

    contract = contract_path.read_text(encoding="utf-8").rstrip()
    prompt = f"""{contract}

## Current trial

Objective: {objective}
Trial number: {trial}
Repository root: {repo_root}
Previous best score: {previous_score}

Allowed paths for this trial (must mirror the harness configuration):
{allowed_paths.rstrip()}

Apply only this hypothesis now. Leave the resulting changes uncommitted for the evaluator.
"""

    try:
        completed = subprocess.run(command + [prompt], cwd=str(repo_root), check=False)
    except FileNotFoundError:
        print(f"ERROR: agent executable not found: {command[0]}", file=sys.stderr)
        return 127
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
