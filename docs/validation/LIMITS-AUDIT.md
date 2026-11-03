# Limit and recovery audit

Status: active review, 2026-11-03. Required by the user and AGENTS.md.
P3 remains open until current limit behavior is reviewed and material gaps fixed.

Every inventory row records scope/unit, purpose, default adequacy, exceedance
record/action, recovery and evidence. Acceptance budgets are not production
research recommendations. A forced stop of an unsafe/unresponsive owned process
must preserve the research and its evidence. Unknown execution must stay reserved.

## Verified findings and corrections

- The original P3 acceptance budget of 180 seconds was enough for the scientific
  chain but insufficient for graceful final response/cleanup. The 37ms overshoot
  remains in the original ledger and report. It is not a recommended operational
  research default. A separate recorded closeout revision is being prepared.
- A queued numerical attempt could start after an earlier overrun created debt.
  Commit 58a288b now reuses Control's gate both before claim and before start;
  tests cover both paths. Consumed costs and reservations remain unchanged.
- Runtime recovery may clear a gate while evaluator execution is still unknown.
  Reproduction confirmed; correction is in progress.

## Inventory

Control/budget, runtime/tool and candidate/evaluator inventory reviews are in
progress. No claim of complete coverage is made at this checkpoint.
