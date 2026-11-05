# Automated Research System Worklist

Scope authority: [Accepted decisions](../status/DECISIONS.md).
Current design: [Project design](../PROJECT-DESIGN.md).
Research reference: [Task specification v2.2](../IEEE118_OOD_Sample_Expansion_Task_v2_2.md).

This ledger replaces the initialization WP1–WP7 breakdown after the user confirmed the system-first foundation and bounded initial task.
At most one package is active. P4 is complete; P5 organization implementation is active. Status records evidence, not elapsed time.

## P5验收准备实查（2026-11-05）

[独立验收准备](../validation/P5-ACCEPTANCE-READINESS.md)：478份档案及14份交付指纹通过，候选固定；当前paused/准入关闭，开发profile无最终评价授权，现有最终评价器绑定P4旧面板。待确定独立评价方、前瞻协议、新面板保管与评价预算后执行，不重复训练或恢复旧面板。

## 当前收尾边界（2026-11-05）

用户已同意停止扩展基础设施优化。本轮只迁移当前P5路径的9项旧容量参数；目录审计分页、大JSON标量/嵌套、持久队列与断电恢复、精确提供方请求计量均留作待办，不自动阻塞P5验收。D034/D035已有的限定工程实现不再标为未实现；任意长期无人干预与语义保真仍未验收。下文旧进展按历史证据阅读，以此段及[容量收尾报告](../validation/CAPACITY-CLOSEOUT.md)为当前范围。

P5下一步为外部独立验收准备：锁定团队最终候选及原始材料，核对独立评价协议、隔离、预算与复现入口，再把评价结果经Control反馈给同一组织。不能把团队内部复现或工程测试当作独立科学验收。并行组织验收及Capstone接入仍未完成。

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

D035异步记录首批实现：组织/摘要/安装入口按序异步写盘、收尾回执与不完整导出缺口；source登记解析移出写事务并复查状态。Control游标登记异步化、队列崩溃恢复与其它重型读取仍未关闭。

D035后续：普通Control游标登记已按序异步；安装边界排空及原生单调序号拒绝晚到旧观测；日志收尾超限返回draining，保留后台写入和最终回执。软队列内存/崩溃恢复及容量自动接续仍未关闭。

D035观测恢复：组织显式resume已接已退出旧会话的落盘前缀冻结/逐条核验/幂等补记；保存新恢复报告并导出，保留旧原件和缺口。真实记录器SIGKILL后前缀核对通过，不代表未写出队列或断电恢复；活动积压内存和完整自动容量接续仍open。

D035积压控制：普通队列当前计数接既有turn准入，事务性延期、不扣本轮额度、不撤销旧许可；原生等待/检查点/宿主明确状态及退出证据有工程检查。128MiB默认水位有历史日志规模依据，仍不关闭硬内存边界/持久溢写或完整自动容量接续。

D035容量观测首接：pi请求边界采集SDK估算/未知状态/耗时，宿主异步计算统一预留比例并留痕；不增加工具或模型请求，不将估算作为准入证明。完整自动摘要/复核/安装与提供方载荷/窗口可靠计量仍未验收。

D035自动维护已接入现有AAR/组织入口，显式复核成员配置下从请求边界或上一角色会话预警串行生成/独立复核/安装/同一会话接续。第五轮受管SDK恢复安装与第六轮正常pi钩子路径均有真实订阅证据，七事实保留，零新科研、原预算不变；六轮全部失败及开发干预保留。35历史会话全部退出，零预留/待核验安装，归档一个旧结果未finalize缺口明确保留。详见[自动接续验收](../validation/RESEARCH-CONTEXT-AUTOMATIC.md)。可靠完整请求计量、任意长程保真及P5总体仍未关闭。

D035事务拆分：原生日志准备/准入、安装stage/授权/确认和历史恢复的SDK投影与解析已移出写事务；文件版本与当前Control状态在提交时重查，原件哈希/覆盖/系统配置核验保留。真实SQLite并发与SDK安装恢复检查覆盖竞争拒绝。后续笔记及代码/实验附件读取、解析、草稿持久化也已移出写事务；提交重查当前采纳/来源/权限及执行绑定，失败保留草稿与未采纳回执。编译、大对象处理、孤立草稿崩溃对账仍开放。两轮均未调用模型或运行科研；见NOTE-IO-TRANSACTIONS.json。

D035安装编译拆分：stage与授权的安装编译、授权阶段摘要/复核校验移出写事务；提交重读原记录、当前状态/进程/游标与一次使用状态，拒绝计算期间变化。实际SDK安装及7项专项检查覆盖。准入复核计算、状态指纹、大对象序列化和崩溃对账仍开放；无模型/科研请求。

D035准入复核拆分：摘要/复核计算移出写事务，提交重新核对冻结输入、当前状态、成员与会话；竞争延期/拒绝并保留原幂等语义。9项专项检查覆盖并发写入及状态/权限/会话竞争；见CONTEXT-ADMISSION-COMPUTATION.json。状态指纹、大对象序列化、崩溃对账及全量附件内存仍开放。

D035测量驱动拆分：本机临时库/合成消息测量定位到重复会话材料重建，已移到事务外来源核验；提交仍核对冻结记录及原件版本。1MiB包围区间中位数约24ms→12ms（每组3次，含关闭，非生产保证）；3项并发/竞争检查及证据见CONTEXT-TRANSACTION-PROFILE.md/.json。剩余序列化/指纹/数据库提交不因该测量宣称已解决。

D035笔记恢复核对：控制端显式核对文件与保存/采纳回执，未登记完整草稿可发现并由本人历史读取；无自动采纳/删除/回执补造。真实子进程在写盘后退出及10项专项检查覆盖；报告随交流导出。跨系统原子性、断电恢复、超大清单内存及附件全量内存仍开放，见NOTE-RECONCILIATION.md/.json。

D035附件正文流式化：完整哈希与Unicode分页按块读取，缓存仅保留元数据/文件版本；统一策略第7版默认1MiB块，可显式调整，不是文件总量上限。10项流式+2项策略新增检查及1/12/48MiB内存测量完成，清单JSON/目录数量内存和每页全文IO仍开放，见NOTE-ARTIFACT-STREAMING.md/.json。

D035附件清单流式化：固定ijson版本，完整解析/哈希至EOF，仅保留身份和目标条目；重复关键字段或目标拒绝。8项专项及大清单内存对比完成，依赖锁定。单标量/嵌套、原生内存和目录核对清单仍开放，见MANIFEST-STREAMING.md/.json。
