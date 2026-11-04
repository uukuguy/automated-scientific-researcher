# Current State

## Project Snapshot

- Project: Automated Scientific Researcher — durable research system with power-grid sampling and solver-method research as its first scientific deliverable.
- Current branch: main
- Theme-level focus: Task-scoped scientific execution over verified single-researcher science and serial role collaboration.
- Project route: managed
- Canonical worklist: docs/plans/WORKLIST.md
- Active work package: P5 — autonomous direction formation and bounded role collaboration; P4 verified

## Current Architecture

- Local numerical implementation: Python >=3.12 standard-library validator/runner; MATPOWER/Octave in a pinned arm64 Docker image.
- Current design: `docs/PROJECT-DESIGN.md`; detailed behavior: `docs/architecture/ASR-MINIMUM-LOOP.md`. Sampling and solver methods are configurable research variables.
- Deployment: local OrbStack Docker Engine and Compose; no additional VM.
- Research reference: `docs/IEEE118_OOD_Sample_Expansion_Task_v2_2.md`; accepted user decisions in `docs/status/DECISIONS.md` govern scope.
- Implemented numerical slice: fixed case118 reference, independent residual/operating checks, immutable local trial evidence; explicit octave-candidate/1 source execution and replication are verified; generalized scenarios and broader profiles remain planned.
- Research layer: actual pinned AAR AutonomousAgentLoop with replaceable subscription runtime; original Experiment/Finding ORM shares the ASR SQLite database. The measured profile supports model-authored frozen candidates, hypothesis revisions, isolated evaluation, method replication, curated skills, findings, snapshots and interruption recovery. Serial Organizer/two-Lead research now has real project execution and communication evidence; concurrent multi-direction deployment remains unverified.
- Human interaction: asynchronous guidance and versioned controls; Capstone scientific-research mode is the accepted workbench architecture; preparation is defined in `docs/handoffs/CAPSTONE-SCIENTIFIC-RESEARCH-MODE.md`.
- Local upstream: `3th-party/automated-w2s-research/`, ignored by the parent repository; tracked deterministic preparation/patches live in integrations/aar/.

- Organization: existing Control records drive serial AAR role wakeups and durable delivery receipts; roles keep separate conversations while OAuth refreshes reconcile with the canonical account source. Verified serial roles deliver designs and executable coordinate-generation research artifacts, with task-gated isolated analysis and adversarial review. Qualified source acceptance remains distinct from scientific utility.

- Supervisor: fenced attempts, frozen request dispatch, external timeout and conservative process reconciliation.
- Subscription resource revisions: explicit model-only Control contracts preserve costs and old evidence; generous completion-first failsafes govern the current implementation profile (D029). Progress-aware anomaly detection remains separate work.

- Control: authenticated local HTTP, reference-profile executable contracts, atomic admission, project budgets, command receipts, candidate findings and evaluator-only immutable Validation attestations. Shared budget rows expose model/compute balances and evaluator dimensions; sourced quota observations preserve unknown values. Managed evaluator artifacts and lifecycle projections have verified receipts.

## Open Problems (theme-level)

- Control organization records, role binding and serial AAR design collaboration are verified; task-scoped scientific admission and real container execution are verified. Model-driven generator implementation/review is verified; concurrent roles and comparative scientific acceptance remain gaps.
- Long native conversations require explicit context recovery; final AAR report publication needed controller archival after a time cap. Automatic report-first/context recovery is not verified.

- P4 provides measured training benefit on a synthetic client project, with actual AAR experiments, independent final scoring and exact selected-training replay. Broader topology/distribution transfer, mechanistic attribution and actual client utility remain untested.
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

- `research_projects/ood_augmentation/` — concrete client fixture, fixed surrogate and lossless public-data delivery.
- `integrations/runtimes/ood_intake.py` — actual AAR intake, zero-compute contract and targeted private-material access denial.

## Organization evidence and communication storage

Project-directed role sessions use the existing Control/AAR records and generic
analysis/label/fit tools. Researchers own scientific design and source. External
scientific/communication archives preserve raw evidence, role journals, revision
history, hashes and explicit gaps/redactions. Public team-comparison evidence
is distinct from independent hidden validation and parallel organization proof.
See docs/validation/P5-PROJECT-PILOT.md and RESEARCH-COMMUNICATION.md.

研究组织支持显式角色会话换代：各代原生日志保留，身份/工作区/累计预算保持不变；交流归档涵盖各代来源。研究上下文压缩尚未实现，已作为D034专项登记，参考Asterion Prime/P7，见`docs/architecture/RESEARCH-CONTEXT.md`。

独立`asr_context`提供原文引用投影和本地不可变研究笔记。笔记不持有权威采纳指针，恢复前核对当前来源；Runtime、模型调用和Control接入仍独立待实现。接口见`asr_context/README.md`。

Control现有数据库记录组织成员私有研究笔记的采用状态；ResearchBridge的research_note工具按当前身份处理save/adopt/read，恢复检查控制/组织来源。笔记文件与采用指针进入交流归档。没有自动语义压缩或Runtime安装。

Control的研究笔记来源适配器可核对typed代码快照与已发布实验文件，原件路径由现有目录/执行登记解析，返回绑定信息，不提供隐藏评价或任意宿主文件访问。
