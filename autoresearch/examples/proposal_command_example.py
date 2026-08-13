#!/usr/bin/env python3
import os
from pathlib import Path

repo = Path(os.environ.get("AR_REPO_PATH", "."))
trial = int(os.environ.get("AR_TRIAL", "1"))
value_file = repo / "candidate_score.txt"
# Demo proposal policy: first trial writes 10, then alternates to 5 and 3.
base = int(value_file.read_text().strip() or 0) if value_file.exists() else 0
next_value = [10, 5, 3, 5, 8][(trial - 1) % 5] if base == 0 else max(0, base - 1)
value_file.write_text(f"{next_value}\n")
