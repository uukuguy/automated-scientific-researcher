# Current State

## Project Snapshot

- Project: Automated Scientific Researcher — durable research system with power-grid sampling and solver-method research as its first scientific deliverable.
- Current branch: main
- Theme-level focus: Versioned research contracts, runtime control and AAR integration over verified numerical evidence.
- Project route: managed
- Canonical worklist: docs/plans/WORKLIST.md
- Active work package: P3 — independent verification and system acceptance

## Current Architecture

- Local numerical implementation: Python >=3.12 standard-library validator/runner; MATPOWER/Octave in a pinned arm64 Docker image.
- Current design: `docs/PROJECT-DESIGN.md`; detailed behavior: `docs/architecture/ASR-MINIMUM-LOOP.md`. Sampling and solver methods are configurable research variables.
- Deployment: local OrbStack Docker Engine and Compose; no additional VM.
- Research reference: `docs/IEEE118_OOD_Sample_Expansion_Task_v2_2.md`; accepted user decisions in `docs/status/DECISIONS.md` govern scope.
- Implemented numerical slice: fixed case118 reference, independent residual/operating checks, immutable local trial evidence; generalized scenarios and candidate execution remain planned.
- Research layer: actual pinned AAR AutonomousAgentLoop with replaceable subscription runtime; original Experiment/Finding ORM shares the ASR SQLite database. The measured profile supports bounded reference experiments, native file tools, curated skill, findings and snapshots.
- Human interaction: asynchronous guidance and versioned controls; Capstone scientific-research mode is the accepted workbench architecture; preparation is defined in `docs/handoffs/CAPSTONE-SCIENTIFIC-RESEARCH-MODE.md`.
- Local upstream: `3th-party/automated-w2s-research/`, ignored by the parent repository; tracked deterministic preparation/patches live in integrations/aar/.

- Supervisor: fenced attempts, frozen request dispatch, external timeout and conservative process reconciliation.

- Control: authenticated local HTTP, reference-profile executable contracts, atomic admission, project budgets, command receipts and candidate findings.

## Open Problems (theme-level)

- D016 requires immutable hypothesis evolution, separate scientific outcome semantics, three-layer evaluator independence and model/compute ledgers; local hypothesis revision/binding/author-evidence APIs exist; full scientific lifecycle, evaluator isolation and subscription quota accounting remain incomplete.
- Local authenticated control API and reference execution supervision exist; generalized candidate execution remains unavailable.
- Unconfirmed real-world input distribution, OOD definition, failure cases, and downstream task.
- Formal evaluation policy and expanded operating conventions remain uncalibrated; the implemented reference uses fixed PV/PQ and one Slack.
- Independent evaluation isolation remains unimplemented; local runtime/attempt budget accounting exists.
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

- `asr_service/admission.py` — local transactional preparation; control.py owns authenticated run admission.

- Research runtime: subscription-first replaceable adapters; pi/Codex baseline. omp/AAR capability base and separate power-grid scientific pack.
- `docs/architecture/RESEARCHER-RUNTIMES.md` — runtime and capability boundaries.
- `docs/validation/P2-SUBSCRIPTION.md` — bounded real model trajectory evidence and remaining limits.
