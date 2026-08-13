# Hermes Loops

Autonomous agent loops for [Hermes Agent](https://github.com/NousResearch/hermes-agent): small,
reviewable control loops that run against a bounded target and either improve it or leave it
unchanged.

| Package | What it does | Writes? |
| --- | --- | --- |
| [autoresearch](autoresearch/) | Karpathy-style propose→test→keep/revert harness for repository experiments | Yes — commits/reverts in a local git repo |
| [health](health/) | Read-only Hermes health audit + suggestion-only improvement evaluator | No — read-only by design |

The two loops are separate packages because they have opposite safety postures. The autoresearch
harness mutates a git repository; the health/improvement loops never write to a Hermes
installation. They install, version, and test independently.

## Loops

### autoresearch

Repeatedly lets an agent change a Git repository, measures whether each change improved a score,
and keeps good changes as local commits or reverts the rest. Provider- and agent-agnostic; never
pushes anywhere.

See [autoresearch/README.md](autoresearch/README.md). The general methodology is in
[docs/autoresearch-playbook.md](docs/autoresearch-playbook.md).

### health

Two independent maintenance loops for a Hermes install:

- **Health loop** — bounded, read-only probes against a selected Hermes home; returns
  healthy / warning / unavailable / unknown findings.
- **Improvement loop** — accepts an explicitly supplied outcome packet, redacts it, and turns
  repeated or notable outcomes into a suggestion for human review. Never auto-applies.

See [health/README.md](health/README.md).

## Install

Each package installs independently from its directory:

```bash
# autoresearch
cd autoresearch && python -m pip install .

# health
cd health && python -m pip install .
```

## License

MIT. See [LICENSE](LICENSE) and the per-package licenses.

---

This repository consolidates the former standalone repos `AtlasOmnia/hermes-autoresearch` and
`AtlasOmnia/hermes-health-improvement-loops` (now archived). It is an independent community
project, not affiliated with or endorsed by Nous Research.
