# Security Policy

## Supported versions

Security fixes are applied to the latest release and the `main` branch.

## Reporting a vulnerability

Please use GitHub's private vulnerability reporting feature from the
repository's **Security** tab. Do not open a public issue for a vulnerability
that could put users or their data at risk.

Include the affected version, reproduction steps, likely impact, and any
suggested remediation. You should receive an acknowledgement within seven
days.

## Execution model

Hermes Autoresearch runs operator-configured proposal and evaluator commands
with the permissions of the current user. Configurations, commands, target
repositories, and generated code must therefore be treated as trusted input.
The path allowlist detects repository changes after a command runs; it is not
an operating-system sandbox and cannot prevent network access or writes
outside the target repository.