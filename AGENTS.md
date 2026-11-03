# ASR Repository Working Rules

## Purpose and current maturity

Automated Scientific Researcher (ASR) is a durable autonomous research system.
Its first scientific application explores power-grid sampling and power-flow
solver methods, including new methods and combinations. The user controls the
research question, permitted changes, evaluation rules and resource budget.

The repository has a verified local MATPOWER/Octave reference runner, independent
Python electrical checks and immutable trial evidence. Local authenticated control
and a fenced execution supervisor support the pinned reference profile, durable
commands, budgets and recovery. The pinned AAR loop and Experiment/Finding ORM have actual subscription-backed
pi/Codex evidence, including a negative numerical outcome and notebook snapshot.
See docs/validation/P2-SUBSCRIPTION.md for measured scope; arbitrary candidate
execution is restricted to the explicit octave-candidate/1 profile. Candidate isolation, fresh method replication and Control-budgeted evaluator recovery have real Docker tests; the complete P3 model-driven trajectory remains under acceptance. Typed evaluator artifact links are verified separately from scientific claims.
Researcher runtimes are replaceable and subscription-first; pi is the lightweight
baseline. Subscription runtime children must not receive any *_API_KEY; only pi explicitly using a non-openai-codex provider may allow such settings. That exception does not authorize paid API usage or fallback. Use `uv sync --locked` and `uv run python -m
unittest discover -s tests -v` for the base suite. Add `--extra aar` to `uv run`
for the actual upstream integration tests. The fixed-PV/PQ baseline is a calibration
profile, not a restriction on candidate-method research. See
`docs/validation/P1-NUMERICAL-LAB.md` for evidence and limits. Check the worklist
and code before reporting implementation status; update this paragraph when it changes.

## Read before work

1. `docs/PROJECT-DESIGN.md`: canonical current goals, architecture and boundaries.
2. `docs/architecture/ASR-MINIMUM-LOOP.md`: subordinate technical design for the
   minimal loop; proposed wire protocol and implementation behavior.
3. `docs/status/INDEX.md`, then relevant state, recovery and recent journal entries.
4. `docs/plans/WORKLIST.md`: package scope, dependencies and acceptance evidence.
5. For integration work, `docs/handoffs/CAPSTONE-SCIENTIFIC-RESEARCH-MODE.md`.

User instructions take precedence. Keep confirmed principles, technical design,
calibration choices and verified behavior distinct. The original task book and
dated redirect are background, not the current implementation authority.

## Component ownership

- Capstone owns the human workbench, conversation and presentation projections.
- ASR control owns effective contracts, admission, commands and budget records.
- AAR is the first autonomous researcher; one executor advances each research run.
- The experiment service owns actual execution and immutable raw evidence.
- Independent evaluation owns validation and replication reports. An agent's
  claimed score or a UI label cannot replace those reports.

Do not create a second research scheduler or authoritative ledger in Capstone.
Keep cross-system IDs explicit: a conversation turn is not a research run or
numerical attempt. Read a sibling repository's rules before modifying it and
preserve its unrelated work. Preparing a handoff is not proof it was delivered,
accepted or implemented by the other project.

## Research and execution invariants

- Sampling and solver methods are research variables from the start. A fixed
  reference baseline does not restrict candidate methods.
- Variable modes are fixed/bounded/open. Open grants method exploration within
  the contract, not unlimited budget, arbitrary permissions or evaluation access.
- Distinguish scenario changes, algorithm changes and problem-definition changes.
  Validate the original problem with explicit fixed and allowed control variables.
- Separate execution completion, solver claims, equation validity, operating
  constraints, reproducibility and generalization. Solver failure is not proof
  of infeasibility; missing constraints remain unassessed.
- Preserve failed trials, negative findings, code/input/environment provenance
  and every execution attempt. Published evidence is immutable.
- New contract versions govern subsequent submissions. Accepted experiments keep
  their starting versions. Controls require actual receipts and effective scope.
- Reserve budget before execution, retain consumed costs after failure, and
  reconcile live processes before releasing reservations or retrying.
- Candidate code cannot modify evaluation code or read hidden evaluation assets.
  Claims of isolation require actual OS/container enforcement and verification.

## Local development and upstream adaptation

Use the existing OrbStack Docker Engine and Compose; no additional VM is needed.
Researchers and candidates do not receive the Docker socket or host credentials.
Keep persistent evidence outside disposable containers. Do not launch paid model
runs without an explicitly configured authorized budget.

The ignored upstream checkout is `3th-party/automated-w2s-research/`; Python
sources are under its `w2s_research/` directory. Pin the upstream revision and
license. Store reproducible patches and preparation scripts in tracked
`integrations/aar/`; do not leave the only implementation in the ignored copy.

Verify changes with focused checks. Numerical claims need real numerical tests;
autonomous-research claims need actual model-driven execution. Mock tests only
prove the interface and orchestration behavior they exercise. Preserve the
existing tests unless explicitly changing their contract as part of the task.

## Durable alignment

Update the relevant main-design section in the same work cycle when the user
settles a design change. Record rationale and supersession in DECISIONS; align
affected detailed designs, handoffs, worklists, schemas and tests. Maintain
stable document paths instead of cloning full designs for each discussion.

JOURNAL is append-only. Record durable decisions, checks and commits promptly;
refresh RESUME as an active-session checkpoint at recovery boundaries. Keep
CURRENT-STATE structural. Register status files in INDEX. Stage only task-owned
changes and preserve unrelated tracked, untracked and runtime data.
