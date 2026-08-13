from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .config import AutoresearchConfig


@dataclass
class EvaluationResult:
    trial: int
    score: Optional[float]
    accepted: bool
    reason: str = ""
    metrics: Dict[str, Any] = None
    elapsed_ms: int = 0
    raw_output: str = ""
    error: str = ""

    def __post_init__(self) -> None:
        if self.metrics is None:
            self.metrics = {}


@dataclass
class TrialResult:
    trial: int
    status: str
    decision: str
    proposal_ok: bool
    evaluator_ok: bool
    before: str
    after: str
    score: Optional[float]
    best_score: Optional[float]
    reason: str
    changed_paths: List[str]
    elapsed_ms: int
    output: str = ""


class AutoresearchError(RuntimeError):
    pass


class AutoresearchHarness:
    def __init__(self, cfg: AutoresearchConfig):
        self.cfg = cfg.normalized()
        self.repo_root = Path(self.cfg.repo_path).resolve()
        self.start_time = 0.0
        self.tsv_path = self.repo_root / self.cfg.tsv_log_path
        self.jsonl_path = self.repo_root / self.cfg.jsonl_log_path

    def run(self) -> Dict[str, Any]:
        self.start_time = time.monotonic()
        self._ensure_ready()

        self.tsv_path.parent.mkdir(parents=True, exist_ok=True)
        self.jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.tsv_path.exists():
            self.tsv_path.write_text("trial\tstatus\tdecision\tscore\tbest_score\treason\telapsed_ms\tchanged_paths\n")
        if not self.jsonl_path.exists():
            self.jsonl_path.write_text("")

        results: List[TrialResult] = []
        best_score: Optional[float] = None
        no_improve_count = 0

        for trial in range(1, self.cfg.max_trials + 1):
            self._check_budget()
            before = self._git_head()
            baseline_untracked = self._untracked_paths()
            trial_start = time.monotonic()

            proposal_ok, proposal_out = self._run_command(
                self.cfg.proposal_command,
                {
                    "AR_TRIAL": str(trial),
                    "AR_PHASE": "proposal",
                    "AR_REPO_PATH": str(self.repo_root),
                    "AR_PREVIOUS_SCORE": str(best_score if best_score is not None else ""),
                },
            )

            if not proposal_ok:
                if self.cfg.revert_on_failure:
                    self._revert_to(before, baseline_untracked)
                changed = self._git_changed_paths()
                no_improve_count += 1
                result = self._record(
                    trial=trial,
                    status="failed",
                    decision="proposal_failed",
                    proposal_ok=False,
                    evaluator_ok=False,
                    before=before,
                    after=self._git_head(),
                    score=None,
                    best_score=best_score,
                    reason=proposal_out.strip() or "proposal command returned non-zero status",
                    changed_paths=changed,
                    started_at=trial_start,
                    output=proposal_out,
                )
                results.append(result)
                if self._stop_due_to_no_improve(no_improve_count):
                    break
                continue

            changed_paths = self._git_changed_paths()
            allowlist_ok, allowlist_error = self._check_allowlist(
                [p for p in changed_paths if not self._is_log_path(p)]
            )
            if not allowlist_ok:
                if self.cfg.revert_on_failure:
                    self._revert_to(before, baseline_untracked)
                no_improve_count += 1
                result = self._record(
                    trial=trial,
                    status="reverted",
                    decision="disallowed_path",
                    proposal_ok=True,
                    evaluator_ok=False,
                    before=before,
                    after=self._git_head(),
                    score=None,
                    best_score=best_score,
                    reason=allowlist_error,
                    changed_paths=changed_paths,
                    started_at=trial_start,
                    output=allowlist_error,
                )
                results.append(result)
                if self._stop_due_to_no_improve(no_improve_count):
                    break
                continue

            eval_ok, eval_result = self._evaluate(trial)
            if not eval_ok:
                if self.cfg.revert_on_failure:
                    self._revert_to(before, baseline_untracked)
                no_improve_count += 1
                result = self._record(
                    trial=trial,
                    status="reverted",
                    decision="eval_failed",
                    proposal_ok=True,
                    evaluator_ok=False,
                    before=before,
                    after=self._git_head(),
                    score=eval_result.score,
                    best_score=best_score,
                    reason=eval_result.error or eval_result.reason,
                    changed_paths=changed_paths,
                    started_at=trial_start,
                    output=eval_result.raw_output,
                )
                results.append(result)
                if self._stop_due_to_no_improve(no_improve_count):
                    break
                continue

            score = eval_result.score
            improved = best_score is None
            if best_score is not None and score is not None:
                improved = score >= (best_score + self.cfg.min_improvement)

            should_keep = eval_result.accepted and (not self.cfg.keep_on_improve or improved)

            if should_keep:
                status = "kept"
                decision = "accepted"
                result = self._record(
                    trial=trial,
                    status=status,
                    decision=decision,
                    proposal_ok=True,
                    evaluator_ok=True,
                    before=before,
                    after=self._git_head(),
                    score=score,
                    best_score=best_score,
                    reason=eval_result.reason,
                    changed_paths=changed_paths,
                    started_at=trial_start,
                    output=eval_result.raw_output,
                )
                if not self.cfg.dry_run:
                    self._commit(f"autoresearch: accept trial {trial} score={score}")
                    result.after = self._git_head()
                no_improve_count = 0
                if score is not None:
                    best_score = score if best_score is None else max(best_score, score)
                results.append(result)
            else:
                if self.cfg.revert_on_no_improve:
                    self._revert_to(before, baseline_untracked)
                no_improve_count += 1
                status = "reverted" if self.cfg.revert_on_no_improve else "evaluated_no_commit"
                decision = "no_improve"

                result = self._record(
                    trial=trial,
                    status=status,
                    decision=decision,
                    proposal_ok=True,
                    evaluator_ok=True,
                    before=before,
                    after=self._git_head(),
                    score=score,
                    best_score=best_score,
                    reason=eval_result.reason,
                    changed_paths=changed_paths,
                    started_at=trial_start,
                    output=eval_result.raw_output,
                )
                results.append(result)

            if self.cfg.target_score is not None and best_score is not None and best_score >= self.cfg.target_score:
                break
            if self._stop_due_to_no_improve(no_improve_count):
                break

        return {
            "repo_path": str(self.repo_root),
            "trials": [r.__dict__ for r in results],
            "best_score": best_score,
            "head": self._git_head(),
            "elapsed_ms": int((time.monotonic() - self.start_time) * 1000),
        }

    def _stop_due_to_no_improve(self, no_improve_count: int) -> bool:
        return self.cfg.stop_after_no_improve > 0 and no_improve_count >= self.cfg.stop_after_no_improve

    def _check_budget(self) -> None:
        if self.cfg.max_seconds is None:
            return
        elapsed = time.monotonic() - self.start_time
        if elapsed > self.cfg.max_seconds:
            raise AutoresearchError(f"Budget exceeded: {self.cfg.max_seconds}s")

    def _ensure_ready(self) -> None:
        if not self.repo_root.exists():
            raise AutoresearchError(f"repo_path does not exist: {self.repo_root}")

        check = subprocess.run(
            ["git", "-C", str(self.repo_root), "rev-parse", "--is-inside-work-tree"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if check.returncode != 0:
            raise AutoresearchError(f"Not a git repository: {self.repo_root}")

        if not self.cfg.dry_run:
            status = subprocess.run(
                ["git", "-C", str(self.repo_root), "status", "--porcelain"],
                text=True,
                stdout=subprocess.PIPE,
                check=True,
            )
            if status.stdout.strip():
                raise AutoresearchError("Repository must be clean before running the harness")

    def _git_head(self) -> str:
        return (
            subprocess.run(
                ["git", "-C", str(self.repo_root), "rev-parse", "--short", "HEAD"],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            ).stdout.strip()
            or "EMPTY"
        )

    def _run_command(self, command: List[str], extra_env: Dict[str, str]) -> Tuple[bool, str]:
        if self.cfg.dry_run:
            return True, ""
        env = os.environ.copy()
        env.update(extra_env)
        try:
            result = subprocess.run(
                command,
                cwd=self.repo_root,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=self.cfg.command_timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return False, "command timed out"
        except Exception as exc:
            return False, str(exc)

        out = result.stdout + ("\n" + result.stderr if result.stderr else "")
        if result.returncode != 0:
            return False, out.strip() or "command failed"
        return True, out if self.cfg.log_command_output else ""

    def _evaluate(self, trial: int) -> Tuple[bool, EvaluationResult]:
        if self.cfg.dry_run:
            return True, EvaluationResult(
                trial=trial,
                score=0.0,
                accepted=True,
                reason="dry-run",
                elapsed_ms=0,
                raw_output='{"score": 0.0, "accepted": true}',
            )

        cmd = list(self.cfg.evaluator_command)
        env = os.environ.copy()
        env.update({
            "AR_TRIAL": str(trial),
            "AR_PHASE": "evaluate",
            "AR_REPO_PATH": str(self.repo_root),
        })
        started = time.monotonic()

        try:
            result = subprocess.run(
                cmd,
                cwd=self.repo_root,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=self.cfg.command_timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return (
                False,
                EvaluationResult(
                    trial=trial,
                    score=None,
                    accepted=False,
                    reason="evaluator timeout",
                    error="evaluator timeout",
                    elapsed_ms=int((time.monotonic() - started) * 1000),
                ),
            )
        except Exception as exc:
            return (
                False,
                EvaluationResult(
                    trial=trial,
                    score=None,
                    accepted=False,
                    reason=str(exc),
                    error=str(exc),
                    elapsed_ms=int((time.monotonic() - started) * 1000),
                ),
            )

        elapsed_ms = int((time.monotonic() - started) * 1000)
        output = result.stdout.strip()
        if result.returncode != 0:
            return (
                False,
                EvaluationResult(
                    trial=trial,
                    score=None,
                    accepted=False,
                    reason=(result.stderr or "evaluator command failed"),
                    error=result.stderr or "",
                    elapsed_ms=elapsed_ms,
                    raw_output=output,
                ),
            )

        parsed = self._parse_eval_output(output)
        if parsed is None:
            return (
                False,
                EvaluationResult(
                    trial=trial,
                    score=None,
                    accepted=False,
                    reason="invalid evaluator output",
                    error="expected JSON object in stdout",
                    elapsed_ms=elapsed_ms,
                    raw_output=output,
                ),
            )

        if "score" not in parsed:
            return (
                False,
                EvaluationResult(
                    trial=trial,
                    score=None,
                    accepted=False,
                    reason="missing score",
                    error="evaluator JSON missing 'score'",
                    elapsed_ms=elapsed_ms,
                    raw_output=output,
                ),
            )

        try:
            score = float(parsed["score"])
        except (TypeError, ValueError):
            return (
                False,
                EvaluationResult(
                    trial=trial,
                    score=None,
                    accepted=False,
                    reason="score must be numeric",
                    error="invalid score type",
                    elapsed_ms=elapsed_ms,
                    raw_output=output,
                ),
            )

        return (
            True,
            EvaluationResult(
                trial=trial,
                score=score,
                accepted=bool(parsed.get("accepted", True)),
                reason=str(parsed.get("reason", "")),
                metrics=parsed.get("metrics", {}) if isinstance(parsed.get("metrics", {}), dict) else {},
                elapsed_ms=elapsed_ms,
                raw_output=output,
            ),
        )

    def _parse_eval_output(self, raw: str) -> Optional[Dict[str, Any]]:
        if not raw:
            return None
        for line in raw.splitlines()[::-1]:
            line = line.strip()
            if not line:
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                return value
        return None

    def _status_paths(self) -> List[str]:
        result = subprocess.run(
            ["git", "-C", str(self.repo_root), "status", "--porcelain", "--untracked-files=all"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )

        paths: List[str] = []
        for line in result.stdout.splitlines():
            if len(line) < 4:
                continue
            path = line[3:].strip()
            if not path:
                continue
            if "->" in path:
                path = path.split("->")[-1].strip()
            paths.append(path)

        return sorted(set(paths))

    def _untracked_paths(self) -> List[str]:
        result = subprocess.run(
            ["git", "-C", str(self.repo_root), "status", "--porcelain", "--untracked-files=all"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        paths: List[str] = []
        for line in result.stdout.splitlines():
            if len(line) < 3:
                continue
            if line[0] == "?" and line[1] == "?":
                paths.append(line[3:].strip())
        return sorted(set(paths))

    def _git_changed_paths(self) -> List[str]:
        result: List[str] = []
        for p in self._status_paths():
            result.append(p)
        return sorted(set(result))

    def _is_log_path(self, rel_path: str) -> bool:
        for candidate in [self.cfg.tsv_log_path, self.cfg.jsonl_log_path]:
            if rel_path == candidate:
                return True
            try:
                candidate_path = Path(candidate)
                rel_parent = Path(rel_path)
                rel_parent.relative_to(candidate_path)
                return True
            except ValueError:
                pass
        return False

    def _is_within_allowlist(self, rel_path: str) -> bool:
        full = (self.repo_root / rel_path).resolve()
        for allowed in self.cfg.allowlist_relative_paths:
            allowed_root = (self.repo_root / allowed).resolve()
            try:
                full.relative_to(allowed_root)
                return True
            except ValueError:
                continue
        return False

    def _check_allowlist(self, paths: List[str]) -> Tuple[bool, str]:
        for path in paths:
            if not self._is_within_allowlist(path):
                return False, f"disallowed path changed: {path}"
        return True, ""

    def _revert_to(self, commit: str, protected_untracked: List[str]) -> None:
        if self.cfg.dry_run:
            return
        subprocess.run(["git", "-C", str(self.repo_root), "reset", "--hard", commit], check=True)

        protected_set = set(protected_untracked)
        # Keep configured log files for complete trial-level visibility.
        for path in self._untracked_paths():
            if path in protected_set or self._is_log_path(path):
                continue
            target = self.repo_root / path
            if target.is_dir():
                shutil.rmtree(target, ignore_errors=True)
            elif target.exists():
                target.unlink()

    def _commit(self, message: str) -> None:
        subprocess.run(["git", "-C", str(self.repo_root), "add", "-A"], check=True)
        staged = subprocess.run(
            ["git", "-C", str(self.repo_root), "diff", "--cached", "--quiet"],
            check=False,
        )
        if staged.returncode == 0:
            return
        subprocess.run(["git", "-C", str(self.repo_root), "commit", "-m", message], check=True)

    def _record(
        self,
        trial: int,
        status: str,
        decision: str,
        proposal_ok: bool,
        evaluator_ok: bool,
        before: str,
        after: str,
        score: Optional[float],
        best_score: Optional[float],
        reason: str,
        changed_paths: List[str],
        started_at: float,
        output: str = "",
    ) -> TrialResult:
        elapsed_ms = int((time.monotonic() - started_at) * 1000)
        result = TrialResult(
            trial=trial,
            status=status,
            decision=decision,
            proposal_ok=proposal_ok,
            evaluator_ok=evaluator_ok,
            before=before,
            after=after,
            score=score,
            best_score=best_score,
            reason=reason,
            changed_paths=changed_paths,
            elapsed_ms=elapsed_ms,
            output=output,
        )

        tsv_row = [
            str(trial),
            status,
            decision,
            "" if score is None else f"{score:.6f}",
            "" if best_score is None else f"{best_score:.6f}",
            reason.replace("\t", " ").replace("\n", " ").replace("\r", " "),
            str(elapsed_ms),
            ";".join(changed_paths),
        ]

        with self.tsv_path.open("a", encoding="utf-8") as tsv:
            tsv.write("\t".join(tsv_row) + "\n")
        with self.jsonl_path.open("a", encoding="utf-8") as jsonl:
            jsonl.write(json.dumps(result.__dict__, sort_keys=True) + "\n")

        return result


# Backward-compatible helper

def run_autoresearch(cfg: Any) -> Dict[str, Any]:
    if isinstance(cfg, dict):
        cfg = AutoresearchConfig.from_dict(cfg)
    return AutoresearchHarness(cfg).run()
