# Current State

## Project Snapshot

- Project: Automated Scientific Researcher — durable research system with power-grid sampling and solver-method research as its first scientific deliverable.
- Current branch: main
- Theme-level focus: User-controlled research variables, reproducible experiments and independent evaluation.
- Project route: managed
- Canonical worklist: docs/plans/WORKLIST.md
- Active work package: P1 — reproducible numerical trials and evidence

## Current Architecture

- Project shell: Python >=3.12, with no declared dependencies or application code.
- Current design: `docs/PROJECT-DESIGN.md`; sampling and solver methods are both configurable research variables.
- Deployment: local OrbStack Docker Engine and Compose; no additional VM.
- Research reference: `docs/IEEE118_OOD_Sample_Expansion_Task_v2_2.md`; accepted user decisions in `docs/status/DECISIONS.md` govern scope.
- Planned numerical layer: canonical MATPOWER case, scenario generation, AC power flow, independent residual validation.
- Planned research layer: adapt AAR for early single-researcher experiments; humans set direction and evaluation rules, researchers choose methods within scope.
- Local upstream: `3th-party/automated-w2s-research/`, ignored by the parent repository; not yet integrated.

## Open Problems (theme-level)

- Uncalibrated numerical research contract and unverified AAR runtime adaptation.
- Missing canonical case, solver environment, and verified baseline.
- Unconfirmed real-world input distribution, OOD definition, failure cases, and downstream task.
- Unfixed operating conventions and independent validation contract.

## Key Files

### Repository instructions

- `AGENTS.md` — empty instruction file; `CLAUDE.md` is a symlink to it.
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
- `pyproject.toml` — Python package metadata.
- `.python-version` — Python 3.12 selection.
- `docs/IEEE118_OOD_Sample_Expansion_Task_v2_2.md` — research scope, architecture, acceptance gates, and proposed scripts.
- `3th-party/automated-w2s-research/README.md` — local upstream setup and research workflow.

## Resume Instructions

1. Read INDEX, this snapshot, the session checkpoint, and recent journal entries.
2. Read the canonical worklist for package scope and acceptance.
3. Run `git status --short` and `git log --oneline -5`.
4. Read AGENTS.md if its contents change; do not assume memory files auto-load.
