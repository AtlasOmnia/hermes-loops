# Architecture

The package contains two independently executable lanes and one optional presentation step. The lanes do not share inputs, permissions, runtime state, or failure handling.

## Health lane

`health.py` and `cron_inspector.py` provide bounded, read-only inspection seams. The health command accepts a selected home through an explicit argument, an environment value, or the process user's default home. It performs metadata checks, bounded JSON reads, bounded log scans, and a read-only SQLite probe. Missing optional surfaces are unavailable rather than fatal.

The detailed source-grounded matrix is in [Health check matrix](health-check-matrix.md).

Health results use concise statuses including `available`, `unavailable`, `unknown`, `warning`, and `healthy`. Unsupported or malformed cron metadata remains `unknown`. Repeated-failure findings require matching, unambiguous, non-sentinel identities in the bounded data.

## Improvement lane

`collect_packets()` accepts only explicitly supplied source paths or fixture JSON. It does not recursively search a home. The source is loaded read-only, normalized to a compact outcome shape, and redacted before validation, fingerprinting, persistence, or error reporting. `evaluate_packets()` applies frozen constants in `rubric.py` and can emit a suggestion proposal only. Runtime artifacts are JSONL files in a caller-selected external directory.

## Optional report

`report.py` can assemble already-produced lane results for display. It performs no collection, evaluation, approval, application, or scheduling. A combined report is therefore a view of outputs, not a new authority boundary.

## Installation boundary

The installer validates explicit operator-supplied inputs, defaults to dry-run, and renders review material without selecting values or invoking a Hermes command. Apply writes only package-owned manifests in an external runtime directory. Uninstall and rollback target only validated package-owned manifests.

## Explicit non-boundaries

Neither executable lane writes to Hermes configuration, scheduling, provider, model, route, host, or delivery state. The package does not make those selections and does not require them to run its health or improvement logic.
