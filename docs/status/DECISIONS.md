# Project Decisions

## D001 — Bounded autonomous research as the initial operating model

- Date: 2026-11-02.
- Status: accepted; initial task details and provisional planning notes below are superseded by D002–D006.
- Objective: build a durable automated research system; power-grid OOD research is its first delivered scientific result.
- Decision: humans set the initial research direction and evaluation rules. AAR chooses methods, experiments and iterations within that boundary.
- Scope expansion: humans decide when to extend the initial research direction. Autonomous project-wide decomposition and allocation are outside the initial model.
- Rationale: establish reliable experiment execution, recovery, evidence and review while testing autonomy on a tractable research direction.
- Source hierarchy: user decisions govern scope. Task specification v2.2 is a reference that may be revised, not a mandatory implementation sequence.
- Planning impact: the initialization worklist is provisional; align it with early single-researcher integration before implementation.
- Still proposed: fixed-topology IEEE-118 as the first bounded task. Exact OOD ranges, operating rules, metrics, budget and runtime design remain open.

## D002 — Initial research contract and system acceptance

- Date: 2026-11-02.
- Status: loop and acceptance principles remain active; sampling-only scope and fixed candidate solver are superseded by D004/D005.
- Initial task: fixed-topology IEEE-118 OOD sample production and coverage under equal computational budgets.
- Attribution: initially fix solver configuration; open solver research separately when supported by bottleneck evidence.
- Required loop: task/workspace, unified experiment execution, evidence-backed memory and recovery, independent evaluation and replay.
- Acceptance: a valid negative result may pass system acceptance; scientific improvement requires separate evidence.
- Implementation design: `docs/superpowers/specs/2026-11-02-bounded-aar-design.md` documents proposed technical details; numerical configuration still requires baseline calibration.
- Supersedes: D001's proposed status for the initial fixed-topology task and the initialization worklist's algorithm-first sequence.

## D003 — OrbStack Docker for local development

- Date: 2026-11-02. Status: accepted.
- Decision: use the existing OrbStack Docker Engine and Compose; do not add a separate VM during development.
- Rationale: the existing Linux container runtime is available; another machine and daemon add no required capability for this stage.
- Platform default: native linux/arm64; record architecture and separate emulated performance measurements.

## D004 — Solver methods are research variables from the start

- Date: 2026-11-02. Status: accepted; corrects D002's attribution restriction.
- Evidence: the user clarified that the external request may include discovering new methods, then explicitly stated solver methods should be agent research variables.
- Decision: open sampling and solver research from the start, including new implementations and combinations within the user-defined contract.
- Rationale: fixing the reference baseline or evaluation standard does not require fixing candidate methods.
- Boundary: retain original-input validation and crossed comparisons for attribution. Changed inputs or model semantics must be identified.
- Uncertainty: the external request's precise business meaning remains unresolved; do not assume a specific new algorithm is required.

## D005 — User-controlled research variables and defaults

- Date: 2026-11-02. Status: accepted.
- Decision: variables have defaults, effective values, fixed/bounded/open modes, allowed ranges, modification authority and scope.
- Coverage: research direction, problem scenarios, sampling/solver methods, learning aids, data/evaluation protocols, budget and researcher organization.
- Rationale: users steer research without prescribing the agent's experimental workflow.
- Evaluation changes create new protocol versions; active trials retain their starting contract. Internal stopping criteria differ from external validity thresholds.

## D006 — One continuously maintained project design

- Date: 2026-11-02. Status: accepted.
- Decision: `docs/PROJECT-DESIGN.md` is the canonical current design. Update it when discussions settle changes.
- Rationale: rapid evolution must not leave conflicting design versions controlling implementation.
- Other files: DECISIONS records rationale and supersession; WORKLIST records delivery; JOURNAL records events; RESUME records live intent.
- Former dated design is a redirect. The original task specification remains background, not the current scope authority.
