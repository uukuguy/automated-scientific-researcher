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

## D007 — Human intervention throughout research

- Date: 2026-11-02. Status: basic model accepted.
- Decision: humans may observe, ask, guide and control throughout a run; event-driven intervention does not require approval for every research step.
- Distinguish conversation, research guidance and runtime controls. Changes have targets, versions, effective boundaries and execution receipts.
- Default pause stops new submissions while preserving in-flight work; explicit immediate stop requests cancellation. Exact UI, notification and protocol details remain design work.
- Source: user accepted the basic interaction setting before requesting the Capstone assessment. Main design §9.1 owns the current model.

## D008 — Capstone adaptation is available

- Date: 2026-11-02. Status: adaptation premise confirmed; architecture recommendation subsequently accepted in D009.
- User confirmed Capstone can cooperate with adaptations, including a dedicated scientific-research mode.
- Assess reusable architecture and reasonable extensions, rather than requiring existing screens to meet every research need unchanged.
- Recommendation: Capstone owns human interaction; an explicit service contract connects AAR research execution and authoritative experiment evidence. This was a recommendation when D008 was recorded; D009 accepts the responsibility split. Detailed protocol and implementation remain pending.
- Evidence and proposed boundaries: main design §9.2. Capstone was inspected read-only at HEAD 54e33dbf with a dirty working tree; no runtime acceptance is claimed.

## D009 — Capstone scientific-research workbench and parallel preparation

- Date: 2026-11-02. Status: accepted.
- User accepted the proposed workbench architecture and requested a handoff enabling Capstone preparation in parallel.
- Capstone owns human interaction; ASR owns research control, AAR integration, numerical experiments and independent evaluation. One executor advances each autonomous research run; Capstone does not create a competing experiment scheduler.
- Deliver preparation through C0–C4 in `docs/handoffs/CAPSTONE-SCIENTIFIC-RESEARCH-MODE.md`: integration design, mock adapter, minimum workspace, asynchronous intervention/recovery, and real-service integration readiness.
- Wire fields and endpoint choices remain a joint protocol draft. Mock acceptance does not prove real scientific execution.
- Supersedes D008's proposed status for the responsibility split. P1 numerical work remains active; the Capstone preparation lane is tracked in its own project.

## D010 — Complete the minimum-loop design and align repository guidance

- Date: 2026-11-02. Status: scope accepted; new technical details are the implementation design, not runtime evidence.
- User authorized completing the minimum-loop design and aligning AGENTS.md and README with actual project maturity.
- Main design delegates technical behavior to `docs/architecture/ASR-MINIMUM-LOOP.md`; it remains the canonical overall design entry.
- Technical choices: extend the AAR local database behind one control writer; separate admission, execution and verification; preserve explicit contract application, budget reservations, immutable evidence and process reconciliation.
- The detailed control protocol remains an integration candidate until Capstone alignment and executable schema validation. Scientific parameters require baseline calibration; actual resource amounts require configuration.
- Rationale: close behavioral gaps before implementation without presenting design, simulated interaction or unfinished tests as a working research system.

## D011 — Verified reference profile and P1 acceptance

- Date: 2026-11-02. Status: measured implementation boundary under the accepted P1 plan; not a formal scientific evaluation protocol.
- Reference: MATPOWER 8.1 / Octave 7.3.0, native arm64, flat initialization, fixed PV/PQ, one reference bus, no Q-limit switching.
- Evidence: 28 focused tests plus real baseline, duplicate submission, fresh replay, truncated solve and timeout cleanup in `docs/validation/P1-NUMERICAL-LAB.md`.
- Baseline is equation-valid but has six reactive-limit violations and 186 unassessed thermal limits. It is not claimed operationally feasible.
- Fixed image identity and package inventory support local execution replay; APT rebuild sources are not snapshot-pinned. Local file-lock evidence runner is not the future database admission/budget service.
- P1 reference acceptance is complete; P2 is active. Candidate methods remain open, and unsupported operating policies require explicit adapters and validation.
