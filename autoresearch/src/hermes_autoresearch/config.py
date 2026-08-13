from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


@dataclass
class AutoresearchConfig:
    """Typed config for the harness."""

    repo_path: str = "."
    proposal_command: List[str] = field(default_factory=lambda: ["true"])
    evaluator_command: List[str] = field(default_factory=lambda: ["true"])
    max_trials: int = 20
    max_seconds: Optional[int] = None
    stop_after_no_improve: int = 0
    min_improvement: float = 0.0
    target_score: Optional[float] = None
    keep_on_improve: bool = True
    revert_on_no_improve: bool = True
    revert_on_failure: bool = True
    allowlist_relative_paths: List[str] = field(default_factory=lambda: ["."])
    tsv_log_path: str = "runs/experiments.tsv"
    jsonl_log_path: str = "runs/experiments.jsonl"
    command_timeout_seconds: float = 120.0
    log_command_output: bool = False
    dry_run: bool = False

    def normalized(self) -> "AutoresearchConfig":
        return AutoresearchConfig(**self.to_dict())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def load(cls, path: str) -> "AutoresearchConfig":
        data = json.loads(Path(path).read_text())
        return cls._coerce(data)

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "AutoresearchConfig":
        return cls._coerce(raw)

    @classmethod
    def _coerce(cls, payload: Dict[str, Any]) -> "AutoresearchConfig":
        normalized = dict(payload)
        if isinstance(normalized.get("proposal_command"), str):
            normalized["proposal_command"] = normalized["proposal_command"].split()
        if isinstance(normalized.get("evaluator_command"), str):
            normalized["evaluator_command"] = normalized["evaluator_command"].split()
        return cls(**normalized)

    @classmethod
    def parse_cli(cls, argv: Optional[List[str]] = None) -> "AutoresearchConfig":
        parser = argparse.ArgumentParser(description="Run a reusable autoresearch trial loop")
        parser.add_argument("--config", type=str, help="Path to JSON config")
        parser.add_argument("--repo", type=str, default=None, help="Working repository root")
        parser.add_argument("--proposal-command", nargs="+", default=None, help="Command to generate a proposal")
        parser.add_argument("--evaluator-command", nargs="+", default=None, help="Command implementing evaluator contract")
        parser.add_argument("--max-trials", type=int, default=None)
        parser.add_argument("--max-seconds", type=int, default=None)
        parser.add_argument("--target-score", type=float, default=None)
        parser.add_argument("--min-improvement", type=float, default=None)
        parser.add_argument("--no-revert-on-no-improve", action="store_true")
        parser.add_argument("--stop-after-no-improve", type=int, default=None)
        parser.add_argument("--allowlist", nargs="+", default=None)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--jsonl", type=str, default=None)
        parser.add_argument("--tsv", type=str, default=None)
        parser.add_argument("--timeout", type=float, default=None)

        args = parser.parse_args(argv)

        cfg = cls.load(args.config) if args.config else cls()

        if args.repo is not None:
            cfg.repo_path = args.repo
        if args.proposal_command is not None:
            cfg.proposal_command = args.proposal_command
        if args.evaluator_command is not None:
            cfg.evaluator_command = args.evaluator_command
        if args.max_trials is not None:
            cfg.max_trials = args.max_trials
        if args.max_seconds is not None:
            cfg.max_seconds = args.max_seconds
        if args.target_score is not None:
            cfg.target_score = args.target_score
        if args.min_improvement is not None:
            cfg.min_improvement = args.min_improvement
        if args.no_revert_on_no_improve:
            cfg.revert_on_no_improve = False
        if args.stop_after_no_improve is not None:
            cfg.stop_after_no_improve = args.stop_after_no_improve
        if args.allowlist is not None:
            cfg.allowlist_relative_paths = args.allowlist
        if args.dry_run:
            cfg.dry_run = True
        if args.jsonl is not None:
            cfg.jsonl_log_path = args.jsonl
        if args.tsv is not None:
            cfg.tsv_log_path = args.tsv
        if args.timeout is not None:
            cfg.command_timeout_seconds = args.timeout

        return cfg.normalized()
