# Automated Research System Worklist

Scope authority: [Accepted decisions](../status/DECISIONS.md).
Current design: [Project design](../PROJECT-DESIGN.md).
Research reference: [Task specification v2.2](../IEEE118_OOD_Sample_Expansion_Task_v2_2.md).

This ledger replaces the initialization WP1–WP7 breakdown after the user confirmed the system-first foundation and bounded initial task.
At most one package is active. P4 is complete; P5 organization implementation is active. Status records evidence, not elapsed time.

| ID | Outcome and scope | Status | Dependencies | Acceptance |
|---|---|---|---|---|
| P0 | Research contract, upstream code mapping and initial system design. | complete | none | Accepted D001–D006; written design with observed source anchors, data boundaries and acceptance steps. |
| P1 | Reproducible real numerical trials and evidence. Pin AAR source and numerical environment; implement case/config provenance, validation, trial manifests and idempotent execution. The reference solver is a baseline, not a candidate-method restriction. | complete | P0 | One real IEEE-118 baseline trial, independent residual validation, retained failure evidence, replay from frozen inputs, tests for duplicate requests and interrupted publication. |
| P2 | AAR single-researcher loop. Apply user-controlled variable contracts to domain prompt/tools, findings and snapshots; enforce external stopping and recovery. | complete | P1 | Real research session calls numerical tools, submits evidence-linked findings, survives interruption without losing completed trial identities or budget. |
| P3 | Independent verification and system acceptance, including D016 hypothesis lineage, scientific outcome semantics and model/compute ledgers. Isolate evaluation and replay frozen evidence. | complete | P2 | Separate replay report, failed validation cases, process-recovery checks and one complete research trajectory. A supported negative result is acceptable; A12–A14 verify hypothesis history, outcome separation and resource accounting. |
| P4 | First scientific deliverable targets a specified trainable method’s OOD weakness (D025): diagnose regimes, generate usable similar-distribution training samples and test generalization gains. Research Lead owns detailed design. | complete (actual AAR study, frozen independent test, exact training replay; controller-assisted report archival) | P3 | Controlled augmentation/training comparisons on fresh target-regime test samples, ID retention, separate equation/operational validity and label checks, complete costs and reproducible evidence. Generation alone does not establish generalization; report null or adverse outcomes. |
| P5 | Three-layer organization: Capstone-facing Research Organizer (Super Agent), multiple AAR Research Leads and task Workers (D018). | active (serial design and model-driven generator/review delivered; retained oracle defect; paired training/tool recovery and independent generator admission checked; team-owned512-label/9-fit public comparison delivered; follow-up verification requirements return to the same organization under D032; independent validation, sustained feedback and parallel acceptance remain open) | P3, P4 | Organizer forms and revises directions from evidence (D027), without fixed topic slots; team designs project methods. See [P5 plan](P5-RESEARCH-ORGANIZATION.md). Unique task ownership, same-budget comparison, independent validation and authoritative Control ledger preserved. |


## Design and parallel preparation

The accepted architecture is detailed in [Minimum-loop design](../architecture/ASR-MINIMUM-LOOP.md). P1/P2 reference controls remain verified. P3 adds the explicit octave-candidate/1 profile, managed isolated evaluation, actual frozen-method replication, hypothesis revisions and system recovery. See [P3 acceptance](../validation/P3-SYSTEM-ACCEPTANCE.md) and [limit audit](../validation/LIMITS-AUDIT.md). Acceptance IDs A1–A14 map to P1–P4. Capstone owns C0–C4 separately; no Capstone completion is inferred here.

## Current evidence

- P2 implemented: authenticated local control API, complete pinned-reference contract validation, immutable revisions, atomic trial/budget/dispatch, commands, candidate findings, fenced numerical execution and conservative recovery.
- P2 real subscription evidence: pi/Codex default gpt-6.1-sol/high produced one actual numerical trial and evidence-linked candidate finding; native-session reopen retained trial identity. See `docs/validation/P2-SUBSCRIPTION.md` and sanitized results. Clean reopen is not crash recovery.
- P2 accepted (bounded reference profile): actual pinned AAR loop/Experiment/Finding ORM, pi1.5 subscription trajectory05 with snapshot and candidate finding; process interruption/reopen04 retains native session and numerical IDs. Curated pack hashes, external stopping and source-integrity checks are enforced. Combined suite109 tests and scientific environment5 tests pass; evidence manifests independently checked. Tool-only calibration does not prove arbitrary candidate coding isolation.
- P3 accepted within its fixed-case scope: actual model-authored method, two trials, two isolated evaluations, three Validation reports, two hypothesis revisions and one candidate finding; interruption/recovery and read-only final closeout preserve all evidence. Authentication failure, timeout and original 37ms overrun remain retained. No novelty, operating feasibility or held-out generalization claim. D021/D022 credential and limit requirements are implemented/audited.
- Runtime direction accepted: subscription-first replaceable coding agents, pi baseline. GPT/Grok available; Claude pending. Other runtime subscription support is verified before activation.

- P0: `docs/status/DECISIONS.md` and the linked design.
- P1: `docs/validation/P1-NUMERICAL-LAB.md` and `P1-REFERENCE-RESULTS.json`; 28 focused tests, real baseline/replay/truncated/timeout trials. Original preflight is historical discovery evidence.
- Implementation slice: `docs/superpowers/plans/2026-11-02-container-lab.md`. The planned local reference slice is implemented and verified. Runtime database admission/budgets are implemented for the reference profile; octave-candidate/1 is now verified; broader execution profiles remain future admitted work.
- Real reference power-flow trials have been demonstrated. A pi subscription-backed calibration trajectory is verified; the pinned upstream AAR loop/ORM is demonstrated in trajectory05; scientific improvement has not been demonstrated. Paid API research requires separate explicit authorization.

## Execution constraints

- Human intervention follows main design §9.1 (accepted basic model). Capstone scientific-research architecture is accepted in §9.2/D009. Its parallel preparation follows `docs/handoffs/CAPSTONE-SCIENTIFIC-RESEARCH-MODE.md`; protocol details remain to be aligned. Capstone owns C0–C4 in its ledger; P2 bounded single-researcher acceptance is complete; P3 is complete; P4 simulated-project work is complete within its declared scope; see [scientific results](../validation/P4-SCIENTIFIC-RESULTS.md).
- Solver methods and sampling are research variables from the start. Variable defaults and permitted changes come from the user-controlled contract.
- Preserve the user's bounded-autonomy model. Research workflow is autonomous; scope and evaluation remain governed.
- Preserve AAR collaboration capabilities while separating W2S dependencies. Ignored local changes alone are not reproducible integration.
- Freeze scenario and operating semantics before formal comparisons; baseline calibration is recorded separately.
- Distinguish research runs, numerical trials and execution attempts. Retries retain prior evidence and consume budget.
- A solver failure is unresolved, not proof of physical infeasibility.
- Never treat author-supplied scores as independently verified results.
- Real-case materials and downstream requirements remain open. Public prototype results do not establish business benefit.

## P3 closure and P4 transition

- A8/A9: real restricted candidate containers, fresh method replication, independent material checks and typed evaluator artifact references.
- A12/A13: immutable prospective/post-hoc hypothesis history, retained operating counterevidence, separate scientific axes and candidate findings.
- A14/D021/D022: subscription-only credential environment, two ledgers, explicit cap receipts, preserved failure costs, conservative unknown-state recovery, reviewed limits and finite policy revisions.
- Actual Control finish receipt closes the research; AAR lifecycle projection is synchronized separately from scientific evidence. See the acceptance report chain.
- P4 delivered the [simulated scientific comparison](../validation/P4-SCIENTIFIC-RESULTS.md) under D026:704 generated labels,9 augmented fits, one frozen independent test, exact selected-training replay and usable artifacts. The final report required explicit controller archival after native walltime exhaustion. P5 remains active; fully unattended context recovery is an implementation gap, not hidden by scientific acceptance.

## Continuing risk checks

- Highest: scientific trust. Inspect failure denominators, original-problem preservation, evaluator independence, exposed evaluation data and claim scope. Do not promote a metric improvement into a scientific finding.
- High: AAR coupling. Audit active prompt/tools/loop overrides and tracked patch size; keep upstream W2S/PGR task goals out of ASR contracts.
- High: infrastructure replacing research. Every P3 slice must serve the single-researcher hypothesis → candidate method → experiment → revision → finding → independent replay trajectory. P3 proves a narrow model-authored method trajectory; scientific improvement still requires P4. No speculative multi-agent/distributed/plugin-platform work.

## Accepted native-runtime integration lane (D020)

Preserve completed P3/pi acceptance. User confirmed existing local Codex
and Grok login/coding on 2026-11-03. Codex App Server precedes Grok ACP: bounded
protocol foundation → ASR tool/budget binding → actual interruption/recovery and
research acceptance. Detailed files and gates are in RESEARCHER-RUNTIMES.md.
Protocol-only tests do not close the scientific trajectory or activate P5.

研究上下文专项（D034）已纳入P5后续：研究语义的压缩、可溯源记忆、容量预警与跨会话恢复验收，见[P5计划](P5-RESEARCH-ORGANIZATION.md)。当前显式换代是应急能力，专项未实现。

P5接续实证：同组织新增3次计算，材料14项/比较33项通过，模型2360权重完全一致；35次历史会话已全部退出、无预留/待投递。已吸收外部证据并以中文交付。仍为串行同环境复现，独立隐藏评价、并行和面板未完成，见[接续报告](../validation/P5-CONTINUATION.md)。

D034已完成首个真实订阅摘要试验：两轮正常摘要获得分开会话复核接受，正文夸大反例被拒绝，失败/消耗/交流全部保留。仍未关闭专项，长期跨窗口、复杂代码引用、自动容量预警及安装待验证，见[模型验证](../validation/RESEARCH-CONTEXT-MODEL.md)。

D034容量/应用准备核心已通过11项检查并复用真实模型产物进行只读计划核查；尚无Runtime自动测量、正式安装或溢出预防验收。474项组合检查通过（25环境跳过），下一步接宿主测量与准入。

D034材料准入已接Control，服务读取当前状态并校验指定成员会话登记，准备/准入请求按运行隔离归档。当前安装许可明确false，下一步补原生会话覆盖范围及安装后生效证据；不按笔记准入宣称运行时压缩完成。

D034已实现与Runtime无关的原会话分组和结构覆盖检查，并用固定pi SDK读取指定分支；10项专项检查通过。三份真实历史日志分别覆盖345/57/328条可见记录，原件未改动，未新增模型调用。494项组合检查通过（25项环境跳过）。活动游标、Control会话来源注册与实际安装仍待接入，见[会话覆盖验证](../validation/RESEARCH-CONTEXT-COVERAGE.md)。

D034来源登记/游标采集已接：5项Control来源检查与3项Node回调检查通过；完整502项检查通过（25环境跳过）。服务冻结并重读原会话，拒绝替换；活动事件的运行身份绑定、联合核验和安装仍待完成，自动压缩尚未启用。

D034游标身份绑定及来源联合核验已接，9项新增工程检查通过，完整511项检查通过（25环境跳过）；尚无新模型验收。下一步是同步安装边界与前后核验，异步游标不能授权安装。

D034同步压缩握手已接：回调等待Control并复查游标，失败明确取消压缩而不回退默认摘要；5项Node及2项真实HTTP/进程贯通新增检查通过。完整518项检查通过（25环境跳过）。当前不安装摘要，下一步接经过联合核验的内容与原生生效回执。

D034指定触发的真实安装闭环已验收：三次pi原生写入、重新核验和订阅接续；最后一次可见字节36595→18681，七项事实及一次实际历史查询通过。20会话全部退出、零预留、零新科研实验；本轮复用原预算。完整535项检查通过（25环境跳过）。容量自动触发/任意长程保真及P5总体不据此关闭，见[实际验收](../validation/RESEARCH-CONTEXT-INSTALLATION.md)。


D035（2026-11-05）：统一容量策略首批入口已加入，配置目的/单位/范围/默认充分性/恢复说明及指纹；pi传输、握手和投影默认读取统一配置。尚待所有容量调用迁移、SDK估算预警、可靠测量与受管生成/复核/安装自动接续；P5仍active。
