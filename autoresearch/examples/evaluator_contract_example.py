#!/usr/bin/env python3
import os
from pathlib import Path
import json

repo = Path(os.environ.get("AR_REPO_PATH", "."))
score_file = repo / "candidate_score.txt"
value = int(score_file.read_text().strip() or 0)

# Contract: always emit JSON with score and accepted.
result = {
    "score": float(value),
    "accepted": value >= 0,
    "reason": f"value={value}",
    "metrics": {
        "value": value,
        "trial": int(os.environ.get("AR_TRIAL", 0)),
    },
}
print(json.dumps(result))
