# Hermes Health Improvement Loops — Changelog

## 0.1.1 — Correct distinct-session recurrence detection

- Excludes the event date from the improvement fingerprint, so the same issue recurring across different days now shares one fingerprint.
- Adds a normalized session lineage identifier to packets and counts distinct sessions rather than packets, so duplicate records from one session no longer promote.
- Enforces a seven-day span plus seven-day recency before a repeated signal promotes; critical kinds still promote on any occurrence.
- Parses the timestamp from the raw record so real dates survive redaction (previously the date was redacted and always "unknown-date").
- Adds recurrence regression tests and updates the health-check matrix, privacy notes, and the privacy-scan allowlist.

## 0.1.0 — Initial public release

- Clarifies the README's bounded health-check scope with an explicit checklist and synthetic report example.
- Clarifies the README for non-technical readers while preserving the project's technical scope and safety boundaries.
- Provides two independent, portable maintenance loops: bounded read-only health auditing and suggestion-only improvement evaluation.
- Keeps installation, scheduling, provider, model, delivery, and runtime changes outside the package's authority boundary.
- Includes standard-library CI, privacy, smoke, compile, documentation, architecture, and licensing guidance.
- Adds a detailed public health-check matrix documenting the current bounded probes, supported metadata shapes, source anchors, and explicit limitations.
