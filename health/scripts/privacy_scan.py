from __future__ import annotations

import argparse
import re
from pathlib import Path

PATTERNS = {
    "credential-value": re.compile(
        r"(?i)(?:api[_-]?key|password|access[_-]?token)\s*[=:]\s*[\"'](?!<|>)[^\"']{12,}[\"']|(?:sk-|ghp_|xox[baprs]-)[A-Za-z0-9_-]{16,}|bearer\s+[A-Za-z0-9._-]{24,}"
    ),
    "email": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I),
    "phone": re.compile(r"(?<!\d)(?!(?:19|20)\d{2}-\d{2}-\d{2}(?!\d))(?:\+?\d[\d .()_-]{7,}\d)(?!\d)"),
    "absolute-path": re.compile(r"(?:^|[\s\"'])/(?:Users|home|Volumes)/|[A-Za-z]:[\\/]Users[\\/]")
}

# These are the public artifacts whose examples and templates are intended for
# operators to read or copy. Internal source and test fixtures are not public
# recommendations and therefore remain outside this choice-neutrality scan.
SELECTION_KEYS = re.compile(
    r"(?im)^\s*(?:[-#]?\s*)?(?:provider|model|delivery|route|host|endpoint|base[_-]?url|scheduler|transport)\s*:\s*(?P<value>[^#\n]+)"
)
SELECTION_FLAGS = re.compile(
    r"(?<!\w)--(?:provider|model|delivery|route|host|endpoint|base-url|scheduler|transport|modules|health-schedule|improvement-schedule)(?:=|\s+)(?P<value>[^\s\n]+)"
)
URL = re.compile(r"(?i)\b(?:https?|ssh|git)://[^\s<>'\"]+")
NETWORK_LITERAL = re.compile(r"(?i)(?<![\w.-])(?:localhost|127\.0\.0\.1|0\.0\.0\.0|\[::1\])(?::\d+)?(?![\w.-])")

INTERNAL_FIXTURE_ALLOWLIST = {
    "scripts/smoke.py": {"phone"},
    "tests/test_improvement.py": {"phone"},
    "tests/test_health.py": {"phone"},
    "tests/test_cron_inspector.py": {"phone", "email"},
    "tests/test_packets.py": {"phone"},
    "tests/test_recurrence.py": {"phone"},
}


def _unquote(value: str) -> str:
    return value.strip().rstrip(",;").strip().strip("`'\"")


def _is_operator_placeholder(value: str) -> bool:
    value = _unquote(value)
    lowered = value.lower()
    return (
        not value
        or value.startswith("$")
        or (value.startswith("<") and value.endswith(">"))
        or "operator-supplied" in lowered
        or "operator supplied" in lowered
        or value in {"…", "..."}
    )


def scan_public_text(text: str) -> list[str]:
    failures: list[str] = []
    for label, pattern in PATTERNS.items():
        if pattern.search(text):
            failures.append(label)
    if URL.search(text):
        failures.append("network-url")
    if NETWORK_LITERAL.search(text):
        failures.append("network-host")
    for match in SELECTION_KEYS.finditer(text):
        if not _is_operator_placeholder(match.group("value")):
            failures.append("concrete-public-choice")
            break
    for match in SELECTION_FLAGS.finditer(text):
        if not _is_operator_placeholder(match.group("value")):
            failures.append("executable-literal-choice")
            break
    return failures


def _is_public_artifact(root: Path, path: Path) -> bool:
    relative = path.relative_to(root).as_posix()
    if relative == "README.md":
        return True
    if relative.startswith("docs/") and path.suffix == ".md":
        return True
    return relative.startswith("config/") and path.suffix in {".yaml", ".yml", ".json"}


def scan_repository(root: Path) -> list[str]:
    failures: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file() or ".git" in path.parts or path.name == "privacy_scan.py":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        relative = path.relative_to(root)
        allowed = INTERNAL_FIXTURE_ALLOWLIST.get(relative.as_posix(), set())
        for label, pattern in PATTERNS.items():
            if label not in allowed and pattern.search(text):
                failures.append(f"{label}: {relative}")
        if _is_public_artifact(root, path):
            for label in scan_public_text(text):
                if label not in PATTERNS:
                    failures.append(f"{label}: {relative}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan public repository artifacts for privacy and neutrality hazards")
    parser.add_argument("root", nargs="?", default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args()
    failures = scan_repository(Path(args.root))
    if failures:
        print("PRIVACY_SCAN_FAIL")
        print("\n".join(failures))
        return 1
    print("PRIVACY_SCAN_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
