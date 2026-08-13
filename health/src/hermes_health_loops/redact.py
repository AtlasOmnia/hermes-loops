from __future__ import annotations

import hashlib
import json
import re
from typing import Any

_SECRET_KEY = re.compile(r"(secret|token|password|credential|api[_-]?key|auth|cookie|phone|email)", re.I)
_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
_PHONE = re.compile(r"(?<!\d)(?:\+?\d[\d .()_-]{7,}\d)(?!\d)")
_PATH = re.compile(r"(?<!\w)(?:/[^\s]+|[A-Za-z]:[\\/][^\s]+)")
_URL = re.compile(r"https?://[^\s]+", re.I)
_OPAQUE = re.compile(r"\b[A-Za-z0-9_-]{32,}\b")


def _clean_text(value: str) -> str:
    value = _EMAIL.sub("[redacted-email]", value)
    value = _PHONE.sub("[redacted-phone]", value)
    value = _URL.sub("[redacted-url]", value)
    value = _PATH.sub("[redacted-path]", value)
    value = _OPAQUE.sub("[redacted-token]", value)
    return value[:240]


def redact(value: Any, key: str = "") -> Any:
    if _SECRET_KEY.search(key):
        return "[redacted]"
    if isinstance(value, dict):
        return {str(k)[:80]: redact(v, str(k)) for k, v in list(value.items())[:40]}
    if isinstance(value, list):
        return [redact(v, key) for v in value[:40]]
    if isinstance(value, str):
        return _clean_text(value)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return _clean_text(str(value))


def stable_fingerprint(value: Any) -> str:
    payload = json.dumps(redact(value), sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()[:16]
