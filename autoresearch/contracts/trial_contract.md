# Trial Contract

You are running inside a single trial of an autoresearch loop. Follow this contract
exactly. The evaluator decides whether to keep or revert your changes — you do not.

## Rules (non-negotiable)

1. **One hypothesis only.** Propose exactly one focused change per trial. Do not pursue
   a second hypothesis, even if you spot another improvement. Stay on the single path
   described in the objective below.

2. **Allowlisted scope.** Only modify files inside the allowed paths stated in the
   current-trial section appended below. Those paths must mirror the harness configuration;
   changes outside the harness allowlist will be rejected and reverted automatically.

3. **No `git commit` or `git push`.** Leave your changes as uncommitted working-tree edits.
   Do not stage, commit, merge, rebase, or push anything. The evaluator reviews diffs
   directly from the filesystem — it does not need a local commit.

4. **Leave changes for the evaluator.** When you are finished editing files, exit with
   status 0. The harness captures your diff and passes it to the evaluation step. Do not
   attempt to self-evaluate or self-accept.

5. **Nonzero exit when blocked.** If you cannot proceed — missing context, ambiguous
   objective, tool failure that prevents editing — exit with a nonzero code (e.g., `exit 1`).
   The harness records the failure and may revert before the next trial.

## Trial metadata

The following environment variables are set for this trial:

- `AR_TRIAL` — current trial number (starts at 1)
- `AR_REPO_PATH` — absolute path to the working repository root
- `AR_PREVIOUS_SCORE` — best score so far, or empty string if no prior accepted trial

## Objective

The user's objective for this trial is provided below. Focus your changes on that single
hypothesis only.
