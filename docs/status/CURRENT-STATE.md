# Current State

## Project Snapshot

- Project: Automated Scientific Researcher — durable research system with power-grid sampling and solver-method research as its first scientific deliverable.
- Current branch: main
- Theme-level focus: Formal scientific comparison contracts over a verified bounded single-researcher foundation.
- Project route: managed
- Canonical worklist: docs/plans/WORKLIST.md
- Active work package: P4 — targeted OOD augmentation for solver generalization; task and contract framing (no new run budget admitted)

## Current Architecture

- Local numerical implementation: Python >=3.12 standard-library validator/runner; MATPOWER/Octave in a pinned arm64 Docker image.
- Current design: `docs/PROJECT-DESIGN.md`; detailed behavior: `docs/architecture/ASR-MINIMUM-LOOP.md`. Sampling and solver methods are configurable research variables.
- Deployment: local OrbStack Docker Engine and Compose; no additional VM.
- Research reference: `docs/IEEE118_OOD_Sample_Expansion_Task_v2_2.md`; accepted user decisions in `docs/status/DECISIONS.md` govern scope.
- Implemented numerical slice: fixed case118 reference, independent residual/operating checks, immutable local trial evidence; explicit octave-candidate/1 source execution and replication are verified; generalized scenarios and broader profiles remain planned.
- Research layer: actual pinned AAR AutonomousAgentLoop with replaceable subscription runtime; original Experiment/Finding ORM shares the ASR SQLite database. The measured profile supports model-authored frozen candidates, hypothesis revisions, isolated evaluation, method replication, curated skills, findings, snapshots and interruption recovery. This researcher is the future Research Lead prototype; the multi-Lead organization is not deployed.
- Human interaction: asynchronous guidance and versioned controls; Capstone scientific-research mode is the accepted workbench architecture; preparation is defined in `docs/handoffs/CAPSTONE-SCIENTIFIC-RESEARCH-MODE.md`.
- Local upstream: `3th-party/automated-w2s-research/`, ignored by the parent repository; tracked deterministic preparation/patches live in integrations/aar/.

- Supervisor: fenced attempts, frozen request dispatch, external timeout and conservative process reconciliation.

- Control: authenticated local HTTP, reference-profile executable contracts, atomic admission, project budgets, command receipts, candidate findings and evaluator-only immutable Validation attestations. Shared budget rows expose model/compute balances and evaluator dimensions; sourced quota observations preserve unknown values. Managed evaluator artifacts and lifecycle projections have verified receipts.

## Open Problems (theme-level)

- P4 targets substantive new-method research beyond retrieving known algorithms: prior knowledge and problem formation precede frozen confirmatory comparisons. Scenario support, hidden-material isolation and independent contribution evidence remain gaps.
- Explicit octave-candidate/1 supports bounded single-file methods; broader workloads/profiles require separate capability and limit review.
- Unconfirmed real-world input distribution, OOD definition, failure cases, and downstream task.
- Formal evaluation policy and expanded operating conventions remain uncalibrated; the implemented reference uses fixed PV/PQ and one Slack.
- Verified managed isolation does not establish universal researcher-runtime isolation; raw evaluator artifacts, attested scientific judgments and formal claim validation remain distinct.
- Numerical image execution is pinned; APT rebuild sources and cross-machine image distribution remain unresolved.

## Key Files

### Repository instructions

- `AGENTS.md` — living-design, research-boundary and durable-state rules; `CLAUDE.md` is a symlink to it.
- No repository `MEMORY.md` exists.

### State / recovery

- `docs/status/INDEX.md` — file catalog.
- `docs/status/CURRENT-STATE.md` — structural snapshot.
- `docs/status/JOURNAL.md` — append-only event log.
- `docs/status/DECISIONS.md` — accepted scope and architecture decisions.
- `docs/status/RESUME-NEXT-SESSION.md` — session recovery point.

### Implementation and specification anchors

- `docs/plans/WORKLIST.md` — canonical package ledger and acceptance gates.
- `docs/PROJECT-DESIGN.md` — canonical current design, research variables and source mapping.
- `docs/superpowers/plans/2026-11-02-container-lab.md` — current numerical-environment implementation slice.
- `docs/architecture/ASR-MINIMUM-LOOP.md` — subordinate detailed design and control protocol candidate.
- `docs/handoffs/CAPSTONE-SCIENTIFIC-RESEARCH-MODE.md` — workbench preparation contract.
- `powerflow_lab/reference.py` — constrained Docker reference CLI.
- `powerflow_lab/validation.py` — independent equation and operating checks.
- `powerflow_lab/runner.py` — local idempotency and immutable attempt publication.
- `tests/` — reference configuration, validator and evidence-runner checks.
- `scripts/reference_pf.m` and `docker/` — numerical entrypoint and image recipes.
- `compose.yaml` — direct reference debugging service.
- `integrations/aar/upstream.json` — pinned upstream identity; tracked preparation and runtime adapter alongside it.
- `pyproject.toml` — Python package metadata.
- `.python-version` — Python 3.12 selection.
- `docs/IEEE118_OOD_Sample_Expansion_Task_v2_2.md` — research scope, architecture, acceptance gates, and proposed scripts.
- `3th-party/automated-w2s-research/README.md` — local upstream setup and research workflow.

## Resume Instructions

1. Read INDEX, this snapshot, the session checkpoint, and recent journal entries.
2. Read the canonical worklist for package scope and acceptance.
3. Run `git status --short` and `git log --oneline -5`.
4. Read AGENTS.md if its contents change; do not assume memory files auto-load.

## Verification entry

- `docs/validation/P1-NUMERICAL-LAB.md` — commands, fixed environment and measured limits.
- `configs/numerical-environment.json` — executed image identity and source hashes.
- `powerflow_lab/` — local reference runner, validator and evidence publication.

- `asr_service/contracts.py` and `contracts/README.md` — variable validation and local revision repository.

- `asr_service/references.py` — immutable scoped metadata registry and content-addressed bundles.
- `asr_service/validations.py` — evaluator-only immutable reports with orthogonal scientific assessment axes.
- `asr_evaluation/` — standalone and Control-managed isolated checks, identity-bound artifacts and conservative recovery.

- `asr_service/admission.py` — local transactional preparation; control.py owns authenticated run admission.

- Research runtime: subscription-first replaceable adapters; pi/Codex baseline. omp/AAR capability base and separate power-grid scientific pack.
- `docs/architecture/RESEARCHER-RUNTIMES.md` — runtime and capability boundaries.
- `docs/validation/P2-SUBSCRIPTION.md` — bounded real model trajectory evidence and remaining limits.

- `docs/validation/P3-SYSTEM-ACCEPTANCE.md` — bounded scientific lifecycle, retained failures and actual final receipts.
- `docs/validation/LIMITS-AUDIT.md` — purpose/default/exceedance/recovery inventory and explicit limits.
- `docs/plans/P4-SCIENTIFIC-COMPARISON.md` — governed successor contract-planning boundary.
