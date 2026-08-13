# Autoresearch Loops Playbook

A Karpathy-style autoresearch loop gives an agent a concrete environment, a frozen
evaluator, and a scalar metric, then lets it iterate autonomously via
propose→test→keep/revert cycles. Use it for bounded problems with clear metrics:
config tuning, infra hardening, skill improvement, and post-update safety checks.

This playbook is the general methodology. The `autoresearch/` directory in this
monorepo is the reusable harness that runs the loop.

## Core principles (from Karpathy's talks)

1. **Context engineering** — what you put in the context window is your real
   design surface. Tight, structured `AGENTS.md`/skills beat clever prompt phrasing.
2. **The autoresearch loop** — the agent edits code or config, runs a short
   experiment, checks the metric, keeps or reverts, and repeats. The human sets
   direction and constraints only; the agent does the grind.
3. **Jagged intelligence** — models are strong but brittle. Design for partial
   reliability, not perfection. Verify after external actions; break big tasks
   into small scopes with clear success criteria.
4. **World models** — maintain concise canonical reference docs so agents behave
   like they understand the environment, and improve those docs via feedback loops.
5. **Files over apps** — small focused tools orchestrated by the agent beat
   monolithic "do everything" prompts. Prefer scripted loops for recurring checks.

## How to set up a loop

1. **Define the target** — a concrete, bounded scope only (a repo, a directory, a
   config subset).
2. **Define the metric** — scalar and unambiguous. Test pass/fail count, lint
   error count, startup latency, or a config-alignment check (0 mismatches = good).
3. **Define constraints** — what the agent may change, and what it must never
   touch without explicit human approval.
4. **Implement the loop** — the real pattern is a continuous loop that runs until
   stopped, not discrete scheduled runs. The human picks the start time; the loop
   iterates autonomously without pausing to ask "should I continue?". Cron is for
   bounded windows only (for example "run 2am-6am"), and even then the loop runs
   continuously inside the window.
   Each iteration: propose a small patch, run the evaluator, keep if the metric
   improves or holds with no regressions, otherwise revert.
5. **Logging** — log only concise summaries of accepted changes and metrics.

## Launching repository improvement loops

1. Honor the explicitly named worker profile; do not silently substitute another.
2. Inspect live Git state first. Start from a clean tree unless the prompt
   identifies pre-existing changes to preserve.
3. Create a dedicated local branch for the experiment series. Keep accepted
   iterations as small local commits; never push, tag, publish, or release unless
   separately authorized.
4. Keep controller prompts and loop logs in a local artifact directory (for
   example `.hermes/`), excluded through `.git/info/exclude`. Do not edit the
   shared `.gitignore` to hide one operator's artifacts.
5. Treat "about five minutes" as a timebox for one hypothesis, not a fixed sleep.
   One problem, one acceptance condition, test, patch, evaluate, KEEP or REVERT.
6. Freeze the evaluator before the first edit; rerun the same gate for every
   accepted change.
7. Process liveness and exit code are not completion evidence. Verify real tool
   activity, a substantive loop log, commits/diffs, and evaluator output.
8. Keep controller artifacts out of commits, and finish or revert the active
   experiment before closeout.
9. Do not assume one invocation runs forever just because the prompt says "loop
   forever." If it completes one experiment and exits, put repetition in an
   external controller that constrains each invocation to one hypothesis.

## Publishing a reusable harness (trial-contract packaging)

When publishing a harness that can invoke arbitrary agents:

- Put portable proposal-agent rules in a public template such as
  `contracts/trial_contract.md`, not in the root `AGENTS.md`.
- Require exactly one hypothesis per trial, explicit allowed paths, no staging or
  commit/push by the proposal agent, uncommitted changes left for the evaluator,
  a nonzero exit when blocked, and no second hypothesis in the same trial.
- Invoke configurable agent commands without a shell. Prefer a JSON argv prefix,
  validate it as a nonempty string array, append the prompt as the final argument,
  and call `subprocess.run(..., shell=False)`. Propagate the child exit code.
- Require a nonempty objective and allowed-path input; treat objectives with
  spaces, backticks, `$()`, semicolons, or env-var syntax as inert prompt data.
- Verify every documented CLI invocation against live command help before
  publishing.
- Use TDD for the wrapper: prompt assembly, exact argv behavior, missing
  objective/scope, malformed command JSON, shell-metacharacter inertness, child
  exit-code propagation, and README examples.

## Pitfalls

- `max_trials` applies to one harness invocation, not the whole campaign.
  Re-running appends another block to the same logs unless the controller uses a
  fresh run directory or run ID.
- Do not put agent prompt bodies inside double-quoted shell assignments — command
  substitution can execute backticked tokens. Store prompts in files and pass
  them through a safe argv/Python wrapper.
- Verify comparison semantics before choosing `min_improvement`. If zero allows
  equality, equal-score trials can be accepted despite a "must improve" contract.
  Use a positive threshold and add a fixture proving equal scores revert.
- A keyword-presence evaluator proves tokens exist, not that behavior improved.
  Pair static checks with meaningful tests and real measurements, and label any
  checklist score honestly.
- Do not let loops touch critical procedures (payroll submission, safety
  policies) without human approval gates.
- Loops are for bounded problems with clear metrics, not open-ended creative
  tasks.
- Watch for overfitting to local metrics, for example improving a test count by
  removing meaningful tests.
- Do not call an evaluation-only trial a failure merely because it produced no
  Git diff. Accepted no-op trials should log metrics without attempting an empty
  commit.
- A perfect frozen-corpus score is not sufficient adoption evidence. Probe
  nearby counterexamples outside the target cases before adopting a change.
