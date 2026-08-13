# Health loop check matrix

This document describes the operational health loop as it exists in the current source. It is a bounded, read-only inspection of one operator-selected Hermes home. It does not write to that home, its source files, or its databases. The health loop reports signals and limitations; it does not prove that a source file is a valid production Hermes schema.

The supported shapes below are version-tolerant best effort. An unfamiliar or malformed shape is reported as unknown where the source can identify that condition, not silently treated as healthy.

## Selected home and status semantics

- `paths.py:discover_hermes_home()` resolves the selected home from an explicit argument first, then the `HERMES_HOME` environment value, then the process user's default Hermes-home location. `health.py:audit_discovered_home()` passes that result to `audit_home()`.
- `health.py:audit_home()` records the home as the abstract label `hermes_home` in its result. It does not expose the selected filesystem path in the public result.
- Missing or undiscoverable homes return overall `unavailable` without attempting source creation or repair.
- Overall health aggregation in `health.py:audit_home()` is ordered: `warning` status outranks `unknown`; `unknown` status outranks `healthy` or `available`; `unavailable` is used only when none of the stronger statuses is present. Therefore, `unknown` never means healthy.
- Cron-local aggregation in `cron_inspector.py:inspect_cron()` follows the same warning, unknown, available, unavailable ordering. A cron finding with status `available` is evidence that a bounded read completed, not a claim that every job is healthy.

## Core surface discovery

`health.py:_check_core()` checks these immediate entries at the selected home:

| Surface | Required? | Missing result | Meaning |
|---|---:|---|---|
| `config.yaml` | Yes | `warning` | Core configuration was not discoverable. |
| `state.db` | Yes | `warning` from core discovery | Core state database was not discoverable. The separate SQLite probe also reports the probe as unavailable when the file is absent. |
| `sessions/` | No | `unavailable` | Optional session surface is not available. |
| `logs/` | No | `unavailable` | Optional log surface is not available. |
| `skills/` | No | `unavailable` | Optional skills surface is not available. |
| `cron/` | No | `unavailable` in the cron findings | Optional cron surface is not available. |

Presence means the entry is discoverable; it does not validate the contents. Core discovery itself does not write, parse, or repair any of these surfaces.

## Session metadata check

Source anchors: `health.py:_bounded_files()` and `health.py:_check_sessions()`.

- The loop inspects only immediate directory entries below `sessions/`; it does not recurse.
- It keeps files whose lower-cased suffix is `.jsonl`, `.json`, or `.db`, in sorted directory order, up to `MAX_FILES = 80`.
- It reads metadata only: each selected file's modification time is sampled with `stat()`. It does not open or parse a transcript, JSON document, or SQLite database, and it does not inspect session contents.
- Age is calculated in whole days from the supplied/current time. A file is stale only when `age > SESSION_MAX_AGE_DAYS`, with `SESSION_MAX_AGE_DAYS = 30`; exactly 30 days is not counted stale.
- The finding reports the bounded sample count, stale count, maximum observed age, and `threshold_days`. It is `warning` when at least one sampled file is stale, otherwise `healthy` when the surface exists, including an empty sample.

## Filesystem capacity check

Source anchor: `health.py:_check_storage()`.

- `os.statvfs()` is called on the selected home, so the signal describes the filesystem containing that home rather than a separately selected mount.
- Used capacity is calculated as `1 - (f_bavail / f_blocks)` when `f_blocks` is nonzero.
- `STORAGE_WARN_RATIO = 0.90`; used capacity greater than or equal to 0.90 produces `warning`, and a lower ratio produces `healthy`.
- If the capacity probe raises an operating-system error, the finding is `unavailable` and optional. The probe does not change filesystem state.

## State database probe

Source anchor: `health.py:_check_sqlite()`.

- The selected home's `state.db` is opened through a SQLite URI with `mode=ro` and `uri=True`.
- The only SQL operation is `SELECT 1`.
- A successful row `(1,)` produces `healthy`. An unexpected result produces `warning`.
- SQLite or operating-system failure produces `warning` with a read-only probe failure detail. A missing file produces `unavailable` for this probe, while the required core-discovery check separately contributes its missing-file `warning`.
- No schema discovery, application query, transaction, write, migration, or repair is performed.

## Log signal check

Source anchors: `health.py:_bounded_files()` and `health.py:_check_stalls()`.

- The optional `logs/` directory is not recursive. The loop samples up to `MAX_FILES = 80` immediate files with suffix `.log`, `.txt`, or `.jsonl`.
- Each selected file is read as UTF-8 with replacement for undecodable bytes, and the scan is limited to `MAX_BYTES = 64 * 1024` bytes per file.
- Case-insensitive counters use these source patterns:
  - `tool[_ -]?call` and `tool_use` contribute to `tool_calls`.
  - `error`, `timeout`, `stuck`, and `stall` contribute to `error_signals`.
  - A separate `repeated_signals` counter is returned as additional bounded text evidence; it does not change the candidate threshold by itself.
- The loop emits a `warning` candidate when `error_signals >= 3` **and** `tool_calls >= 3`. The finding explicitly says this is a bounded log signal and that the candidate is not proof of a stall or failure.
- If the log surface is absent, the finding is `unavailable`; no log file is created.

## Cron metadata and execution checks

Source anchors: `cron_inspector.py:inspect_cron()`, `_read_json()`, `_read_executions()`, `_canonical_job()`, and `classify_job()`.

### Discovery locations and supported names

The inspector checks the `cron/` directory first, then the selected home itself. It accepts the first existing file in source order from these exact name lists:

- Job metadata: `JSON_NAMES = ("jobs.json", "jobs.v1.json", "jobs.v2.json")`.
- Execution history: `SQLITE_NAMES = ("executions.db", "executions.v1.db", "executions.v2.db", "history.db")`.

The optional `MAX_FILES = 12` constant in `cron_inspector.py` is retained as a module bound, but discovery selects named files rather than walking an arbitrary directory. Absence is `unavailable`; it is not an error and does not create a substitute file.

### Job JSON

- The selected job file must be at most `MAX_BYTES = 128 * 1024` bytes.
- Supported top-level shapes are a list, an object containing a `jobs` list, or an object containing an `items` list. These are supported shapes, not a claim about a production Hermes schema.
- At most `MAX_ROWS = 200` object rows are considered. Non-object rows in the bounded input make the metadata result `unknown`; malformed JSON, unreadable content, an oversized file, and an unrecognized shape also produce `unknown`.
- A successfully read file produces an `available` `cron:jobs` finding with the bounded count. It does not execute, modify, or validate the job payload beyond the supported shape checks.

### Execution SQLite

- The selected execution database is opened read-only through a SQLite URI with `mode=ro`.
- The inspector recognizes the first table, in source order, named `executions`, `job_executions`, `runs`, or `history`.
- It reads the table's reported columns and at most `MAX_ROWS = 200` rows. No write transaction or migration is attempted.
- Missing database is `unavailable`. A database that cannot be opened, has no supported table, or has an unknown table shape is `unknown` when a file was found. A successful bounded read is `available`.

### Enabled-job classifications

`cron_inspector.py:classify_job()` evaluates only jobs whose canonical `enabled` value is true. The canonicalizer accepts the source's supported aliases for status, schedule, delivery, artifact, enabled/paused/disabled, and next-run fields. An enabled job can receive one or more of these warnings:

- `pre-dispatch`: configuration status is one of `drift`, `blocked`, `invalid`, `missing`, `error`, or `failed`, or the redacted raw job has `script_missing: true`.
- `execution`: execution status is a terminal failure in `TERMINAL_FAILURES = {"failed", "failure", "error", "timeout", "cancelled", "blocked"}`, or execution status is missing/empty/`unknown`.
- `side-effect`: the artifact status is true, or is `failed`, `failure`, `error`, or `missing`, including the supported nested status shape.
- `delivery`: delivery status is `failed`, `failure`, `error`, or `undelivered`, including the supported nested status shape.
- `overdue`: `next_run_at` parses as a time earlier than the inspection time and the job has a schedule value. Equal-to-now is not overdue.
- `repeated-failure`: at least two execution rows have a terminal failure status and the same unambiguous, non-sentinel job identity as the enabled job.

For `repeated-failure`, supported identity aliases are `JOB_ID_ALIASES = ("job_id", "id", "jobId", "job")`. The identity is usable only when exactly one distinct non-sentinel value remains after normalization. `JOB_ID_SENTINELS = {"", "unknown", "unavailable", "none", "null", "n/a", "na"}` are excluded. Missing identity, conflicting supported aliases, sentinel identity, an unrelated identity, or fewer than two terminal failure rows does **not** trigger `repeated-failure`.

These are classifications of bounded metadata, not proof that a job actually ran, failed, delivered, or changed an external side effect. The inspector emits warnings only; it does not retry, disable, repair, schedule, or deliver anything.

## Separate improvement loop

The improvement lane is not an operational health check. Its explicitly supplied packet flow is:

1. `improvement.py:_load_source()` accepts a caller-supplied JSON source bounded by `MAX_SOURCE_BYTES = 128 * 1024` and keeps at most `MAX_PACKETS = 200` packet objects. `collect_packets()` accepts explicit source paths only; it does not crawl a home or parse transcripts.
2. `packets.py:normalize_outcome()` redacts each supplied record before validation and normalization. Fingerprints are computed from the redacted signal. Validation errors are fixed safe messages without caller data, and `write_runtime_artifacts()` validates/redacts again before appending external runtime artifacts.
3. `rubric.py` freezes the current defaults: `CRITICAL_KINDS = {"critical", "incident", "data-loss"}`, `WATCH_KINDS = {"warning", "degraded", "timeout", "stall"}`, `REPEAT_COUNT = 3`, and `WINDOW_DAYS = 7`.
4. `improvement.py:evaluate_packets()` can emit suggestion records for critical kinds, repeated watch signals, or a non-critical repeated signal meeting the frozen count/window rule. Results are suggestion-only and require human review; they are not approvals or applied changes.

This lane has no crawling, approval, application, scheduling, or automatic promotion behavior. Its packet source, redaction, evaluation, and runtime artifacts remain separate from the operational health lane.

## Boundary summary

The operational health loop reads bounded metadata/content from one selected home and opens supported SQLite files read-only. It does not write to the home or choose provider, model, route, host, delivery, or schedule values, and it does not claim that detected files are valid production Hermes schema. Unknown and unavailable states remain visible so missing or unsupported data is not mistaken for health.
