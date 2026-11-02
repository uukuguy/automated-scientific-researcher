# Project Decisions

## D001 — Bounded autonomous research as the initial operating model

- Date: 2026-11-02.
- Status: accepted by the user in discussion.
- Objective: build a durable automated research system; power-grid OOD research is its first delivered scientific result.
- Decision: humans set the initial research direction and evaluation rules. AAR chooses methods, experiments and iterations within that boundary.
- Scope expansion: humans decide when to extend the initial research direction. Autonomous project-wide decomposition and allocation are outside the initial model.
- Rationale: establish reliable experiment execution, recovery, evidence and review while testing autonomy on a tractable research direction.
- Source hierarchy: user decisions govern scope. Task specification v2.2 is a reference that may be revised, not a mandatory implementation sequence.
- Planning impact: the initialization worklist is provisional; align it with early single-researcher integration before implementation.
- Still proposed: fixed-topology IEEE-118 as the first bounded task. Exact OOD ranges, operating rules, metrics, budget and runtime design remain open.

## D002 — Initial research contract and system acceptance

- Date: 2026-11-02.
- Status: user accepted the proposed contract and minimal loop, then requested continuation.
- Initial task: fixed-topology IEEE-118 OOD sample production and coverage under equal computational budgets.
- Attribution: initially fix solver configuration; open solver research separately when supported by bottleneck evidence.
- Required loop: task/workspace, unified experiment execution, evidence-backed memory and recovery, independent evaluation and replay.
- Acceptance: a valid negative result may pass system acceptance; scientific improvement requires separate evidence.
- Implementation design: `docs/superpowers/specs/2026-11-02-bounded-aar-design.md` documents proposed technical details; numerical configuration still requires baseline calibration.
- Supersedes: D001's proposed status for the initial fixed-topology task and the initialization worklist's algorithm-first sequence.
