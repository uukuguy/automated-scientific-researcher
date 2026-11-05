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

研究组织支持显式角色会话换代和受管上下文维护；各代原生日志、身份、工作区及累计预算保留。D034/D035设计见`docs/architecture/RESEARCH-CONTEXT.md`，真实正常/恢复两条接续的范围见`docs/validation/RESEARCH-CONTEXT-AUTOMATIC.md`。

- 独立`asr_context`提供不可变笔记、摘要/复核协议、完整交互分组、结构覆盖和安装内容编译。结构匹配或模型复核不授予权限，也不证明科学正确性。
- Control现有数据库持有笔记采用指针、来源登记、准备/准入、一次安装票据及写后核验。成员可分页回查本人冻结原文；历史材料不授予当前权限。typed快照/实验原件按来源登记解析，不提供隐藏评价或任意宿主文件访问。笔记/附件文件读取、校验及草稿持久化在写事务外；提交同步重查采纳指针、现行来源、权限及执行绑定，竞争失败保留草稿与未采纳记录。准入摘要/复核、安装stage/授权编译和授权复核计算在事务外，提交重查冻结输入、当前状态和成员/会话资格；准入与一次票据仍各自同步登记。
- `context_maintenance`是现有AAR唯一执行者的串行子程序。显式成员复核映射下，异步预警可在下一请求或下一角色会话触发；摘要/复核分开会话且禁用执行工具。原任务保持同一原生会话身份，额度沿用Control总账。
- 普通安装使用pi同步压缩钩子、一次票据和写后读回；已压缩叶子的恢复使用受管无模型SDK子进程。均需实际核验成功才能继续模型请求。系统配置按固定SDK增量合并语义核对，原始记录不改写。
- 失败写入阻止同一原生会话普通启动；退出后历史核验不授予当前使用资格，必须重新准备当前安装。监督者只能通过专用接口延期，不获得人类resume权限；过期科研笔记由所有者明确修订。
- 正式会话绑定成员、原生日志目录、所有权和OS进程出生身份。游标与文件/分支联合核对，异步观测本身不锁定会话，安装边界另行排空与同步核验。
- 统一容量入口`configs/capacity-policy.json`登记目的、单位、范围、默认充分性与恢复说明，覆盖当前传输、握手、投影、摘要/复核、异步记录和附件正文读取块配置。其余旧容量调用迁移仍未全部关闭。
- 普通交流及Control游标按序异步；收尾持久化回执和缺口随不可变归档导出。安装边界检查排空及原生序号，原生日志的登记、准备/准入、安装/确认/恢复解析及SDK投影均在写事务外，登记来源的会话材料重建随本次事务外核验完成，提交前重查文件版本和Control身份/状态。显式resume可冻结已写出前缀并核验补记，不声称恢复从未写出的队列。
- 积压在下一turn准入处留回执并延期，保留旧许可、额度和在途试验；128MiB软水位有已测日志规模依据，不是硬内存隔离。
- 请求容量使用公开SDK估算，未知与精度留痕；预警不证明可靠准入。提供方完整载荷/窗口、任意长程语义与代码引用保真、持久队列/断电恢复、跨文件系统/数据库原子恢复及状态指纹/数据库大对象占锁仍开放。P5总体保持active。

Control提供显式成员笔记核对，比较不可变文件、原保存/采纳回执及当前指针；只生成历史检查报告，不补造成功、不采纳或删除。文件读取在写事务外，提交核对账本与文件版本；报告沿原请求/事件账本保存和导出。

笔记附件正文按统一读取块流式校验/分页，缓存仅保留摘要与文件版本，取页仍核验全文。清单JSON和引用/文件数量的内存仍需单独处理。
