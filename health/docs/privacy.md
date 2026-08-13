# Privacy

This package is designed for shareable source distribution without embedding live runtime data.

## Never commit

- Live job files, SQLite state, transcripts, logs, credentials, or authentication files.
- Names, organizations, cities, profile names, absolute local paths, chat identifiers, or personal data.
- Provider, model, delivery, route, host, scheduler, or transport selections.
- Raw session packets or unredacted improvement data.

## Read-only source rules

Health uses metadata and bounded content probes. SQLite opens with a read-only URI, so the health lane cannot perform schema migration or a write transaction. Improvement accepts only explicit allowlisted files supplied by the caller and never recursively searches a home.

## Redaction limitations

Redaction removes common secret-like key values, email addresses, phone-like numbers, absolute POSIX and Windows paths, URLs, and long opaque tokens. Packet retention is limited to event kind, outcome, timestamp bucket, a bounded session lineage identifier, and a deterministic redacted fingerprint. Redaction is not a guarantee against every possible personal-data format; review fixtures before sharing.

## Runtime state

Ledger, suggestion, and installation-manifest files default to an external state location and are not repository artifacts. Use a disposable directory for tests. The privacy scan checks repository text for likely credential, personal-data, path, network, and concrete-choice hazards.
