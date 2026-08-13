# Hermes Loops

Autonomous agent loops for [Hermes Agent](https://github.com/NousResearch/hermes-agent): small,
reviewable control loops that run against a bounded target and either improve it or leave it
unchanged.

| Loop | What it does | Writes? |
| --- | --- | --- |
| [autoresearch](autoresearch/) | Karpathy-style propose→test→keep/revert harness for repository experiments | Yes — commits/reverts in a local git repo |
| [maintenance](maintenance/) | Read-only Hermes health audit + suggestion-only improvement evaluator | No — read-only by design |
| [hermes-diagnostic-review](https://github.com/AtlasOmnia/hermes-custom-pack/blob/main/skills/hermes-diagnostic-review/SKILL.md) | LLM-driven diagnostic review for recurring mistakes and reusable improvements — a skill in hermes-custom-pack | No — read-only, suggestion-only |

The two code packages have opposite safety postures: the autoresearch harness mutates a git
repository, while the health/improvement loops never write to a Hermes installation. They install,
version, and test independently. The third pattern — diagnostic review — is LLM-driven, so it ships as
a skill in `hermes-custom-pack` rather than as code here.

## Loops

### autoresearch

Repeatedly lets an agent change a Git repository, measures whether each change improved a score,
and keeps good changes as local commits or reverts the rest. Provider- and agent-agnostic; never
pushes anywhere.

See [autoresearch/README.md](autoresearch/README.md). The general methodology is in
[docs/autoresearch-playbook.md](docs/autoresearch-playbook.md).

### maintenance

Two independent maintenance loops for a Hermes install:

- **Health loop** — bounded, read-only probes against a selected Hermes home; returns
  healthy / warning / unavailable / unknown findings.
- **Improvement loop** — accepts an explicitly supplied outcome packet, redacts it, and turns
  repeated or notable outcomes into a suggestion for human review. Never auto-applies.

See [maintenance/README.md](maintenance/README.md).

## Diagnostic review

A third loop pattern — reviewing your own sessions for recurring mistakes and turning them into
reusable improvements — is LLM-driven, so it ships as a skill rather than a code harness:

- [hermes-diagnostic-review](https://github.com/AtlasOmnia/hermes-custom-pack/blob/main/skills/hermes-diagnostic-review/SKILL.md) —
  read-only diagnostic review, suggestion-only output, human-gated promotion.

The deterministic improvement evaluator in `maintenance/` is the frozen-rubric evaluator half of the same idea.

## Install

Each package installs independently from its directory:

```bash
# autoresearch
cd autoresearch && python -m pip install .

# maintenance
cd maintenance && python -m pip install .
```

## License

MIT. See [LICENSE](LICENSE) and the per-package licenses.

---

This repository consolidates the former standalone repos `AtlasOmnia/hermes-autoresearch` and
`AtlasOmnia/hermes-health-improvement-loops` (now archived). It is an independent community
project, not affiliated with or endorsed by Nous Research.
