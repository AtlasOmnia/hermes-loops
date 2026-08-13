import subprocess
from pathlib import Path

from hermes_autoresearch.config import AutoresearchConfig
from hermes_autoresearch.orchestrator import AutoresearchHarness


def _init_repo(path: Path) -> None:
    subprocess.run(["git", "-C", str(path), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "you@example.com"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "Test Runner"], check=True)
    (path / "README.md").write_text("autoresearch test repo")
    (path / "candidate_score.txt").write_text("1\n")
    subprocess.run(["git", "-C", str(path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(path), "commit", "-q", "-m", "initial"], check=True)


def _write_cmd_script(path: Path, contents: str) -> Path:
    p = path
    p.write_text(contents)
    p.chmod(0o755)
    subprocess.run(["git", "-C", str(path.parent), "add", str(p)], check=True)
    subprocess.run(["git", "-C", str(path.parent), "commit", "-q", "-m", f"add {path.name}"], check=True)
    return p


def test_keep_and_revert_paths_and_logs(tmp_path: Path):
    _init_repo(tmp_path)

    proposal = _write_cmd_script(
        tmp_path / "proposal.py",
        """import os\nfrom pathlib import Path\ntrial = int(os.environ['AR_TRIAL'])\npath = Path('candidate_score.txt')\nif trial == 1:\n    path.write_text('9\\n')\nelse:\n    path.write_text('1\\n')\n""",
    )

    evaluator = _write_cmd_script(
        tmp_path / "evaluator.py",
        """import json\nfrom pathlib import Path\nv = int(Path('candidate_score.txt').read_text().strip() or 0)\nprint(json.dumps({'score': float(v), 'accepted': True, 'reason': 'ok'}))\n""",
    )

    cfg = AutoresearchConfig(
        repo_path=str(tmp_path),
        proposal_command=["python3", str(proposal)],
        evaluator_command=["python3", str(evaluator)],
        max_trials=2,
        keep_on_improve=True,
        revert_on_no_improve=True,
        allowlist_relative_paths=["."],
        tsv_log_path="runs/experiments.tsv",
        jsonl_log_path="runs/experiments.jsonl",
        stop_after_no_improve=5,
        min_improvement=0.0,
    )

    result = AutoresearchHarness(cfg).run()

    assert result["best_score"] == 9.0
    assert len(result["trials"]) == 2
    assert result["trials"][0]["status"] == "kept"
    assert result["trials"][1]["status"] == "reverted"

    assert (tmp_path / "candidate_score.txt").read_text().strip() == "9"
    tsv = (tmp_path / "runs/experiments.tsv").read_text().strip().splitlines()
    jsonl = (tmp_path / "runs/experiments.jsonl").read_text().strip().splitlines()
    assert len(tsv) == 1 + 2
    assert len(jsonl) == 2


def test_noop_accepted_trial_does_not_attempt_empty_commit(tmp_path: Path):
    _init_repo(tmp_path)
    (tmp_path / ".gitignore").write_text("runs/\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", ".gitignore"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-q", "-m", "ignore logs"], check=True)
    proposal = _write_cmd_script(tmp_path / "proposal.py", "print('no changes')\n")
    evaluator = _write_cmd_script(
        tmp_path / "evaluator.py",
        "import json\nprint(json.dumps({'score': 1.0, 'accepted': True, 'reason': 'benchmark'}))\n",
    )
    before = subprocess.run(
        ["git", "-C", str(tmp_path), "rev-parse", "HEAD"],
        text=True,
        stdout=subprocess.PIPE,
        check=True,
    ).stdout.strip()
    cfg = AutoresearchConfig(
        repo_path=str(tmp_path),
        proposal_command=["python3", str(proposal)],
        evaluator_command=["python3", str(evaluator)],
        max_trials=1,
        allowlist_relative_paths=["."],
        tsv_log_path="runs/experiments.tsv",
        jsonl_log_path="runs/experiments.jsonl",
    )
    result = AutoresearchHarness(cfg).run()
    after = subprocess.run(
        ["git", "-C", str(tmp_path), "rev-parse", "HEAD"],
        text=True,
        stdout=subprocess.PIPE,
        check=True,
    ).stdout.strip()
    assert result["trials"][0]["status"] == "kept"
    assert before == after


def test_disallowlist_reverts(tmp_path: Path):
    _init_repo(tmp_path)
    (tmp_path / "safe").mkdir()
    (tmp_path / "safe" / "good.txt").write_text("ok")
    subprocess.run(["git", "-C", str(tmp_path), "add", "safe"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-q", "-m", "add safe area"], check=True)

    proposal = _write_cmd_script(
        tmp_path / "proposal.py",
        """from pathlib import Path\nPath('unsafe').mkdir(exist_ok=True)\nPath('unsafe', 'bad.txt').write_text('bad')\n""",
    )

    evaluator = _write_cmd_script(
        tmp_path / "evaluator.py",
        """import json\nprint(json.dumps({'score': 10, 'accepted': True, 'reason': 'ignored'}))\n""",
    )

    cfg = AutoresearchConfig(
        repo_path=str(tmp_path),
        proposal_command=["python3", str(proposal)],
        evaluator_command=["python3", str(evaluator)],
        max_trials=1,
        keep_on_improve=True,
        revert_on_no_improve=True,
        allowlist_relative_paths=["safe"],
    )

    result = AutoresearchHarness(cfg).run()

    assert result["trials"][0]["status"] == "reverted"
    assert "disallowed path changed: unsafe/bad.txt" in result["trials"][0]["reason"]
    assert not (tmp_path / "unsafe" / "bad.txt").exists()
