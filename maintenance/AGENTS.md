# Repository scope and execution contract

## Purpose

This repository packages two independently runnable, shareable Hermes maintenance loops:

1. A deterministic, read-only operational health audit.
2. A suggestion-only engineering improvement evaluator.

The optional report command may combine their outputs, but it must not merge their inputs, permissions, runtime state, or failure handling.

## Scope lock

Allowed work:

- Portable collectors, evaluators, reports, installers, documentation, fixtures, privacy checks, and tests contained in this repository.
- Synthetic or explicitly supplied test data.
- Package-owned runtime manifests and redacted runtime artifacts at a caller-selected location.

Forbidden work:

- Reading or copying credentials, authentication files, private memories, raw transcripts, personal profiles, or live delivery identifiers into this repository.
- Mutating a live Hermes home, cron store, configuration, sessions, memories, skills, source checkout, gateway, or provider/model routing.
- Automatically approving or applying an improvement proposal.
- Silently choosing a provider, model, schedule, delivery target, or Hermes profile.
- Publishing or adding a network remote without explicit owner authorization.

Newly discovered work outside this contract is deferred unless it blocks a stated acceptance criterion.

## Engineering rules

- Resolve homes through explicit arguments or environment variables; never commit machine-specific absolute paths.
- Open inspected SQLite databases read-only.
- Bound file counts, byte counts, and time windows.
- Treat missing optional Hermes surfaces as unavailable, not fatal.
- Keep health and improvement pipelines executable and testable independently.
- Keep the evaluation rubric frozen at runtime. Rubric changes require source review and tests.
- Default installation behavior is dry-run. Applied installation may write only package-owned manifests unless a separately reviewed integration explicitly adds more authority.
- One writer per checkout. Verify branch, HEAD, clean/dirty state, and incumbent writer before editing.

## Required verification

Before committing a material change, run:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 scripts/privacy_scan.py
python3 scripts/smoke.py
python3 -m compileall -q src scripts tests
git diff --check
```

A release candidate additionally requires an independent read-only privacy and package review, an extracted-artifact rescan, and explicit approval before any public remote or publication step.
