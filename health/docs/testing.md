# Test and verification commands

Run from the repository root:

```text
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 scripts/privacy_scan.py
python3 scripts/smoke.py
python3 -m compileall -q src scripts tests
git diff --check
```

The package has no third-party runtime dependency. The smoke script creates and removes its synthetic Hermes home and improvement fixture in a temporary directory.

The unit suite checks read-only behavior, explicit improvement-source boundaries, redaction and rubric behavior, contained package manifests, optional reporting, documentation claims, and privacy-scan rules. Scheduler tests assert the native positional-prompt cron shape and reject unsupported flags. Cron fixtures cover matching identities, unrelated execution rows, missing identities, sentinel identities, and conflicting aliases so failures cannot bleed between jobs or be inferred from ambiguous values.

The privacy scan also checks public documentation and configuration for concrete provider, model, delivery, route, host, scheduler, and transport selections, executable examples that assign literal option values, URLs, and network hosts. Internal code and test fixtures remain available for benign deterministic testing.

The CI workflow runs the same standard-library gates on supported repository events. It uses no external credentials and does not upload security or scan artifacts.
