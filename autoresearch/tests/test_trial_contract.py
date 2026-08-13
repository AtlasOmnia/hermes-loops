"""Tests for the public trial contract and safe proposal wrapper."""

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts" / "trial_contract.md"
WRAPPER_PATH = ROOT / "examples" / "proposal_wrapper_example.py"
README_PATH = ROOT / "README.md"


@pytest.fixture
def contract_text() -> str:
    return CONTRACT_PATH.read_text(encoding="utf-8")


def test_contract_contains_required_trial_rules(contract_text: str):
    required = {
        "one hypothesis": r"one\s+hypothesi",
        "allowlisted scope": r"allowlist|allowed paths",
        "no commit": r"no.*commit|do.?not.*commit",
        "no push": r"no.*push|do.?not.*push",
        "evaluator owns decision": r"evaluator.*(decide|review|accept|keep)",
        "nonzero blocked exit": r"non.?zero",
        "no second hypothesis": r"no.*second",
    }
    for label, pattern in required.items():
        assert re.search(pattern, contract_text, re.IGNORECASE | re.DOTALL), label


def test_contract_is_provider_agnostic(contract_text: str):
    forbidden = [
        r"\bopenai\b",
        r"\banthropic\b",
        r"\bclaude\b",
        r"\bgpt-\d",
        r"127\.0\.0\.1",
        r"/Users/[^/]+/",
        r"sk-[A-Za-z0-9]{20,}",
    ]
    for pattern in forbidden:
        assert not re.search(pattern, contract_text, re.IGNORECASE), pattern


def _make_agent(tmp_path: Path) -> Tuple[Path, Path]:
    capture = tmp_path / "captured.json"
    agent = tmp_path / "agent.py"
    agent.write_text(
        """import json, pathlib, sys
capture = pathlib.Path(sys.argv[1])
capture.write_text(json.dumps({"argv": sys.argv[2:], "prompt": sys.argv[-1]}))
raise SystemExit(int(sys.argv[2]) if len(sys.argv) > 3 and sys.argv[2].isdigit() else 0)
""",
        encoding="utf-8",
    )
    return agent, capture


def _run_wrapper(
    tmp_path: Path,
    objective: Optional[str] = "Improve one measured behavior",
    *,
    allowed_paths: Optional[str] = "src/\ntests/",
    command_json: Optional[str] = None,
    previous_score: str = "12.5",
) -> Tuple[subprocess.CompletedProcess, Path]:
    agent, capture = _make_agent(tmp_path)
    env = os.environ.copy()
    env.update(
        {
            "AR_TRIAL": "3",
            "AR_REPO_PATH": str(tmp_path),
            "AR_PREVIOUS_SCORE": previous_score,
            "TRIAL_ALLOWED_PATHS": allowed_paths if allowed_paths is not None else "",
            "AGENT_COMMAND_JSON": command_json
            or json.dumps([sys.executable, str(agent), str(capture)]),
            "CONTRACT_FILE": str(CONTRACT_PATH),
        }
    )
    argv = [sys.executable, str(WRAPPER_PATH)]
    if objective is not None:
        argv.append(objective)
    return subprocess.run(argv, env=env, capture_output=True, text=True), capture


def test_wrapper_assembles_prompt_and_invokes_agent_without_shell(tmp_path: Path):
    result, capture = _run_wrapper(tmp_path)
    assert result.returncode == 0, result.stderr
    payload = json.loads(capture.read_text(encoding="utf-8"))
    prompt = payload["prompt"]
    assert payload["argv"] == [prompt]
    assert "Improve one measured behavior" in prompt
    assert "Trial number: 3" in prompt
    assert f"Repository root: {tmp_path}" in prompt
    assert "Previous best score: 12.5" in prompt
    assert "src/" in prompt and "tests/" in prompt
    assert "Trial Contract" in prompt


def test_wrapper_treats_metacharacters_as_prompt_data(tmp_path: Path):
    marker = tmp_path / "must-not-exist"
    objective = f"Measure $(touch {marker}); then inspect `whoami` and $HOME"
    result, capture = _run_wrapper(tmp_path, objective)
    assert result.returncode == 0, result.stderr
    assert not marker.exists()
    assert objective in json.loads(capture.read_text(encoding="utf-8"))["prompt"]


@pytest.mark.parametrize("objective", [None, "", "   "])
def test_wrapper_requires_nonempty_objective(tmp_path: Path, objective: Optional[str]):
    result, _ = _run_wrapper(tmp_path, objective)
    assert result.returncode == 2
    assert "objective" in result.stderr.lower()


def test_wrapper_requires_explicit_allowed_paths(tmp_path: Path):
    result, _ = _run_wrapper(tmp_path, allowed_paths=None)
    assert result.returncode == 2
    assert "TRIAL_ALLOWED_PATHS" in result.stderr


@pytest.mark.parametrize(
    "command_json",
    ["not-json", "{}", "[]", '["ok", 3]'],
)
def test_wrapper_rejects_invalid_agent_command_json(tmp_path: Path, command_json: str):
    result, _ = _run_wrapper(tmp_path, command_json=command_json)
    assert result.returncode == 2
    assert "AGENT_COMMAND_JSON" in result.stderr


def test_wrapper_propagates_agent_exit_code(tmp_path: Path):
    agent, capture = _make_agent(tmp_path)
    command = json.dumps([sys.executable, str(agent), str(capture), "7"])
    result, _ = _run_wrapper(tmp_path, command_json=command)
    assert result.returncode == 7


def test_readme_documents_working_hermes_example_and_scope_input():
    content = README_PATH.read_text(encoding="utf-8")
    assert "AGENT_COMMAND_JSON" in content
    assert "TRIAL_ALLOWED_PATHS" in content
    assert "hermes" in content and "chat" in content and "-q" in content
    assert "hermes agent --prompt-file" not in content
    assert "proposal_wrapper_example.py" in content
