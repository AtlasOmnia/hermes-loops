"""Hermes autoresearch harness.

Provides a reusable loop that proposes changes through a configurable command,
Evaluates them through a configurable evaluator contract, and applies keep/revert
controls with Git-backed state.
"""

from .config import AutoresearchConfig
from .orchestrator import TrialResult, run_autoresearch

__all__ = ["AutoresearchConfig", "TrialResult", "run_autoresearch"]
