# Project Working Rules

## Current design and durable state

- Read `docs/PROJECT-DESIGN.md` before design changes or implementation. It is the canonical current design.
- Read `docs/status/INDEX.md` before other status files; use `CURRENT-STATE.md`, `RESUME-NEXT-SESSION.md`, and recent `JOURNAL.md` entries for recovery.
- Track delivery in `docs/plans/WORKLIST.md`. The original task specification and dated design redirects are historical context.
- User instructions take precedence. When the user settles a design change, update the relevant main-design section in the same work cycle, record rationale/supersession in `docs/status/DECISIONS.md`, and align affected plans.
- Keep confirmed decisions, proposed defaults, unresolved choices and actual implementation evidence distinct. Do not create a new full dated design for each discussion.
- Journal durable decisions and verification immediately. Keep JOURNAL append-only; maintain active-session checkpoints at recovery boundaries.

## Research boundaries

- Users control research direction, variable defaults, fixed/bounded/open modes, evaluation rules and budget.
- Sampling and solver methods are research variables from the start, including custom methods within the contract.
- A fixed reference baseline does not restrict candidate solvers. Separate scenario changes, algorithm changes and problem-definition changes.
- Validate against the original problem. Solver failure does not prove infeasibility. Preserve failed trials and negative findings.
- Local development uses OrbStack Docker and Compose without an additional VM.
- Reuse AAR from `3th-party/automated-w2s-research`; preserve reproducible integration changes outside the ignored upstream copy.
