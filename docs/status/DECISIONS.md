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

## D012 — Replaceable subscription-first researcher runtimes

- Date: 2026-11-02. Status: accepted by user.
- Decision: use replaceable coding-agent runtimes, primarily subscription authentication; add pi as lightweight baseline with Codex subscription support to verify locally.
- Rationale: long-running API research costs are unsuitable as the default; user has GPT/Grok subscriptions and expects Claude subscription shortly.
- Boundary: preserve AAR research organization and ASR authoritative contracts/evidence; runtime session IDs remain separate. No silent paid API fallback. Subscription support must be verified per runtime/provider; unknown quota is not unlimited.
- Supersedes: main design fixed-Claude-SDK initial implementation recommendation.

## D013 — ASR capability base from omp and AAR

- Date: 2026-11-02. Status: accepted by user.
- Decision: combine omp tool-configuration guidance and pi native tools with AAR research methods, memory, shared findings and snapshots.
- Rationale: a bare runtime lacks the configured coding/research environment needed for autonomous scientific work.
- Boundary: curated versioned packs; no inherited global tools, hidden paid model consultation, or skill-based permission escalation. Tool-only smoke acceptance remains distinct from isolated coding capability.

## D014 — Explicit power-grid scientific computing capability pack

- Date: 2026-11-02. Status: accepted by user.
- Decision: add a distinct executable scientific-computing domain pack alongside general coding/research and ASR system tools.
- Coverage: cases/scenarios, sampling, reference and candidate solvers, diagnostics, independent electrical checks, comparisons and visualization.
- Boundary: start from verified MATPOWER/Octave and Python checks; pending capabilities must remain explicit. A skill or tool name does not establish numerical correctness or isolation.

## D015 — Preselected locked scientific environment

- Date: 2026-11-02. Status: accepted by user.
- Decision: keep MATPOWER/Octave reference and preselect pandapower with NumPy/SciPy, pandas/PyArrow, NetworkX, Matplotlib, Jupyter/ipykernel and pytest in a separate locked environment.
- Rationale: a common executable scientific base reduces repeated setup and supports reproducible development.
- Boundary: installed, numerically calibrated and formal-evaluation-approved are distinct states. Optional optimization/learning/dynamic toolchains remain task-specific.

## D016 — Scientific outcomes, hypothesis lineage, evaluator independence and resource ledgers

- Date: 2026-11-02. Status: accepted by user after the four-point assessment.
- Decision: preserve analyzable failure evidence; separate execution, experiment validity, hypothesis assessment and finding validation. Unsupported is not refuted; invalid experiments cannot establish refutation. Scientific negative results are not infrastructure retries.
- Decision: immutable Hypothesis revisions bind frozen trials to predictions, scope and criteria. Changed hypotheses/methods retain lineage; findings link supporting, opposing and inconclusive evidence with independent Validation. Post-hoc interpretation is explicit. Runtime sessions are not research identity.
- Decision: verify execution, frozen-data and mathematical independence separately. Existing independent electrical checks do not establish evaluator isolation.
- Decision: two logical ledgers for model/subscription use and experimental compute, with one Control authority and atomic admission under project policy. Unknown quota stays unknown; local limits still apply. No automatic paid API fallback; no implicit GPU enforcement or per-step approvals.
- Rationale: prevent retry-driven success narratives, self-grading, loss of scientific history across runtimes and hidden cost transfers.
- Supersedes: the proposed status of main design former §13.1. Current requirements live in §§6.1,8,9; detailed mechanisms and tests belong to P3. P2's historical measured acceptance is unchanged.

## D017 — Scientific director and Capstone (superseded role split)

- Date: 2026-11-02. Status: superseded by D018 after the user separated the human-facing Super Agent from multiple scientific direction leads. Earlier interpretation combined those responsibilities.
- Decision: Research Director reasons about scientific direction, hypotheses, complementary tasks, evidence conflicts and synthesis; typically delegates candidate implementation and experiments. Reuse AAR research loops and collaboration rather than build a separate competing scheduler.
- Decision: Capstone owns human interaction/projections. ASR Control retains authoritative contracts, budget, permissions and receipts; direct human stop remains available. The director cannot self-approve evaluation or increase authorized resources.
- Rationale: single-researcher acceptance establishes a foundation, not the long-term ceiling. Multi-researcher coordination should improve science, not merely route messages.
- Boundary: future capability, not deployed. Preserve current P3 scope; assess DeepSeek's Super-agent design for useful patterns without committing to its runtime or replacing AAR.

## D018 — Research Orchestrator, multiple Research Leads and Research Workers

- Date: 2026-11-02. Status: user-confirmed three-layer responsibility split. Role terminology uses Research Orchestrator (研究统筹), Research Lead (方向负责人) and Research Worker (研究执行者); Super Agent remains the architectural name.
- Decision: Super Agent communicates with humans through Capstone and coordinates the AAR research organization across directions. It is not the sole scientific mentor.
- Decision: multiple Research Leads belong inside AAR, guiding direction-level science, critiquing hypotheses/designs and synthesizing evidence. Workers perform concrete retrieval, implementation, experiments, debugging and review. Preserve unique task/run ownership and use AAR collaboration primitives.
- Boundary: one ASR Control authority for authorization, budgets and receipts; independent evaluator owns formal validation. Capstone and every agent hold projections or author interpretations, not duplicate ledgers or self-approved scientific claims.
- Supersedes: D017's merged mentor/human-facing coordinator. Current single-researcher implementation and P3 acceptance are unchanged; P5 carries the future three-layer organization.

## D019 — Research Organizer and role/runtime separation

- Date: 2026-11-03. Status: accepted in user discussion.
- Research Organizer (研究组织者) replaces D018's Research Orchestrator role name; Super Agent remains the architectural name.
- Research Leads retain former autonomous researchers' scientific reasoning and may delegate concrete tasks. Leads can directly discuss and cross-review; the organizer is not a mandatory message relay.
- Separate role capability contracts (responsibility, tools, skills, actions, outputs, budget, communication) from runtime bindings (implementation, provider/model, authentication/billing and recovery). Same runtime may serve multiple isolated roles. Reject missing required capabilities; no silent fallback.
- Bound global concurrency and discussion costs before scaling. Initial 1 organizer/2 leads/2 shared concurrent workers/1 experiment remains a proposed calibration configuration, not deployed behavior. Preserve P3 single-researcher scope.

## D020 — Native Codex App Server followed by Grok Build ACP

- Date: 2026-11-03. Status: accepted; user confirms both local agents are logged in and have performed coding.
- Preserve verified pi/Codex baseline; implement Codex App Server first and Grok ACP next, through their native programmatic protocols. Keep native reasoning/tool loops instead of rebuilding them around raw model APIs.
- Existing login/coding use is user-confirmed availability, not ASR tool/lifecycle acceptance. Reuse login without reauthentication; inspect no secret payloads. Subscription mode must exclude API fallback.
- Acceptance proceeds through bounded protocol, session, tool/approval, interruption/recovery and finally model-driven research evidence. Native session identity stays separate from ASR research and execution identities. Cancellation receipt alone does not prove process/remote work exit.
- Supersedes generic 'Native Codex/Grok' candidate wording with concrete adapter choices; does not close P3 or deploy P5.

## D021 — No API-key environment for subscription runtimes

- Date: 2026-11-03. Status: explicit user instruction during P3 completion.
- Decision: subscription LLM runtimes must not set or pass any `*_API_KEY`. Only pi explicitly using a non-`openai-codex`/`openai_codex` provider may allow these variables.
- Rationale: make subscription authentication explicit and prevent accidental API billing or cross-provider credentials.
- Boundary: enforce in launcher code and tests; OAuth login remains allowed. The pi exception does not authorize paid API usage or change finite budget requirements. Supplements D020 and the subscription-first runtime policy.

## D022 — Purposeful limits and recoverable exceedance

- Date: 2026-11-03. Status: explicit user requirement, added to AGENTS.md.
- Decision: audit every implemented limit for purpose, unit/scope, configurable value and default adequacy. Keep acceptance-test budgets distinct from operational defaults.
- Decision: exceedance requires detailed inspectable records and explicit recovery. Ordinary exhaustion pauses/defer research rather than dropping the task; forced execution termination requires a safety/resource reason, preserved evidence and exit proof. No silent failure or implicit fallback.
- Boundary: raising limits is a recorded policy change, never usage reset. Unknown execution stays reserved. Current P3 closure includes re-auditing existing code, not only documenting future rules.

## D023 — Research toward new methods, not rediscovery of known algorithms

- Date: 2026-11-03. Status: user clarification of the scientific objective.
- Decision: literature search and trying an existing solver are preparation, not sufficient delivery of “find new methods.” The researcher must formulate an unresolved problem, propose a substantive mechanism/method and test its contribution against relevant prior work and controlled evidence.
- Rationale: do not confuse autonomous tool use or algorithm reproduction with autonomous scientific contribution. Agent-generated code and simple recombination do not establish novelty.
- Boundary: do not preselect solver research from engineering convenience. Exploration can refine questions; confirmatory claims require frozen protocols and independent validation. Negative outcomes remain valuable and retained, but cannot be relabelled as achieving the new-method objective.
- Supersession: withdraws this session's suggested solver-first direction; preserves P3 engineering acceptance and P4 planning status. No new run budget or claim of novelty is granted.

## D024 — Prioritize realistic OOD sample generation

- Date: 2026-11-03. Status: explicit user priority.
- Decision: retain D023's new-method objective, but first address realistic OOD sample generation. Do not require inventing a solver before building a useful generation loop.
- Boundary: OOD needs an explicit reference distribution and shift definition. Synthetic correlated public-case scenarios are not measured real operations. Equation validity, operating feasibility and downstream utility remain separate.
- Supersession: P4 now prioritizes sampling rather than leaving sampling/solver/joint research equally unselected. The concrete sampling design remains proposed; no model/compute budget is admitted.

## D025 — Targeted augmentation for a specified method's OOD weakness

- Date: 2026-11-03. Status: explicit user problem decomposition and human-role clarification.
- Decision: identify the OOD regimes where a target trainable method performs poorly; test whether more similar-distribution training data helps; research generation of those usable examples. Improvement is a hypothesis, not an assumed consequence of data volume.
- Roles: human problem decomposition can stop at this level. Research Lead owns diagnosis, similarity, sampling and experiment design; request only genuinely missing external facts/materials/authority.
- Evidence: independent target-regime evaluation after augmentation, original-distribution retention and controlled training comparisons are central. Separate target model from label generation; separate diagnostic/augmentation data from final tests and retain original-distribution provenance.
- Supersession: narrows D024 from generic OOD generation to targeted training benefit. Generation/coverage alone cannot close the scientific task. Exact model/data/interface and budgets remain unspecified; no execution is authorized by this record.

## D026 — Simulate the human client's project and delegate to ASR

- Date: 2026-11-03. Status: explicit user task.
- Decision: the development agent prepares a concrete simulated client project, with a trainable target, original data, measured OOD weakness and criteria, then delegates scientific work to ASR. Do not keep asking the human to supply a detailed project or conduct the research as the developer.
- Boundary: client preparation and infrastructure are developer work; scientific diagnosis, hypotheses and augmentation choices belong to the AAR researcher. A synthetic project is not evidence of real-client benefit. Intake is not completion.
- Implementation: real numerical client materials and actual subscription AAR intake are verified; two hypotheses and a snapshot exist. Zero-compute intake is paused pending supported training/labeling/evaluation capabilities. All initial connection failure costs remain charged.


## D027 — Autonomous direction formation and research architecture (2026-11-03)

- Decision: The Research Organizer proposes directions from the client question and evidence; Leads discuss and may propose creation, splitting, merging or closure. Developers do not prescribe scientific departments. Changes within the effective authorization proceed autonomously; scope/budget/permission changes require the corresponding human authorization.
- Capacity is separate from scientific structure: an initial suggestion of at most two active Leads is not two required topics. One initial diagnostic direction and additional queued directions are valid. Record rationale, evidence, ownership and resource effects of organizational changes.
- The supplied two-layer sample-generation diagram is a human-provided candidate architecture, not ASR core infrastructure or a verified P4 autonomous invention. The team may adopt, change or reject it. Two method layers need not map to two Leads.
- P5 must assess autonomous problem decomposition and project-code construction as well as coordination and scientific utility. Keep governing execution/evidence/evaluation boundaries fixed. Do not declare a difficult-solver layer necessary merely because it is drawn; P4 did not establish that need.
- Rationale: Predetermined directions would prevent testing the Organizer's scientific decomposition capability and could force an unnecessary architecture.
- Clarifies D018 role responsibilities and concurrency suggestions; preserves D019/D020 role/runtime separation and D025/D026 client-task boundaries. No implementation or new model budget is claimed by this decision.

## D028 — Canonical subscription authentication, isolated role conversations

- Date: 2026-11-03. Status: implementation correction prompted by the user's repeated-login report; preserves D019/D021.
- Diagnosis: role-local auth took precedence over source updates, and refreshes remained in private copies. New runs could reuse an old canonical credential; different roles could retain divergent credentials. Provider WebSocket failure is a separate transport condition.
- Decision: stage Codex OAuth from the explicit canonical source; after confirmed process exit, reconcile refreshes under a short compatible file lock and compare-before-write check. Preserve other providers and newer logins. Store conflicts pause and retain results/costs; do not open login automatically.
- Roles retain separate conversations/tool configuration. No API keys, paid fallback or credential values in receipts. A successful isolated browser login was explicitly consolidated to the same-account canonical source after the pilot.
- Boundary: tested serial reconciliation and conflict detection, not yet a fully validated concurrent refresh broker. This supersedes the implementation convention of never returning a private refresh to the user's source, not historical P2 evidence.


## D029 — Subscription completion takes priority over short acceptance windows (2026-11-04)

User explicitly corrected limits after normal Organizer finalization was cut off.
The previous20-minute aggregate/four-minute role limits were developer-selected
pilot envelopes, not user scientific constraints. Adopt generous configurable
failsafes (current4h aggregate/30min role), stop upon complete useful delivery,
and retain separate compute/scientific admission. Current user direction permits
an explicit model-only extension of implementation001, preserving spent costs,
old contracts and failed sessions. No hidden budget reset or automatic paid
fallback. The existing Control publication/application path owns revisions;
local policy intent/receipt is recovery evidence, not another ledger. True
progress-aware anomaly detection remains unimplemented and separately tracked.


## D030 — Researchers own the scientific process; development observes externally (2026-11-04)

User corrected the tendency to encode a team's intermediate products and research
sequence in ASR. Organizer/Leads/Workers must produce and evolve research plans,
project implementations and intermediate artifacts themselves. ASR supplies
execution/evidence/permission/budget/contract infrastructure and independent
validation boundaries. Developers externally monitor/evaluate behavior and repair
infrastructure; they must not act as an invisible scientist or scheduler.

The four-arm/eight-seed/33-model comparison is one historical team proposal, not
ASR architecture. Explicitly admitted evaluation criteria can be frozen and
verified, without making the research path universal. Preserve previous project
adapters as transparently developer-authored, opt-in integration evidence, not
proof that the team autonomously performed those steps. Supersedes the immediate
plan for developer-built fixed P5 comparison orchestration. Uncommitted selection
math moved out of asr_evaluation into tests/paired_selection_reference.py as an
external test reference only; no runtime path may import or invoke it. Next step
is to expose adequate generic capabilities and let the team determine its own
continuation, while retaining independent evaluation and hidden-data boundaries.


## D031 — Preserve complete recorded research communication (2026-11-04)

User requires the whole research communication process to be recorded. Keep raw
native role journals/events plus authoritative Control messages, task revisions,
human guidance and receipts; produce indexed immutable communication exports.
Visible conversation/tool content is retained rather than summarized. Source hashes,
role/session links, active/missing-record gaps and redactions are explicit.
Credentials/private reasoning are excluded from the communication export; native
originals remain restricted. Existing runtime stderr omission and unavailable full
external developer-chat export remain disclosed limitations. Do not manufacture
historical messages/timestamps. New human requirement is recorded as Control
guidance in project001; no scientific direction, experiment or budget is altered.


## D032 — 把后续验证工作交回研究组织，检验持续研究能力（2026-11-04）

用户要求将训练材料核对、重复训练和新样本独立评价作为后续项目要求，交回
原研究组织；获得外部结果后，再交给组织解释并继续研究。这取代了开发侧
直接包办后续科学判断的安排。同一项目、组织、历史和已用预算继续保留；
上一轮任务完成后，可以因明确的新委托继续工作，不能为了消耗剩余额度重开。

团队自己拆解问题、分工、选择检查方法和提出证据请求。开发侧提供通用能力，
从外部核查实际行为，不代写团队的科学回应。研究员可以组织和请求独立评价，
但不能因此获得修改正式评价程序或读取隐藏数据的权限。提出请求不代表服务
已存在、已获准或已执行。接续验收要看是否恢复真实历史、产生新的实质工作、
说明能力缺口，并根据实际返回结果继续判断；只恢复聊天或重复旧报告不够。

用户还提出人类提供黑箱评价器。接口设计区分可反复获得的研究反馈与使用
另一些未见数据的最终验收。每次请求、结果、错误和版本均须保留；看不到
评价器内部并不能防止反复试分造成偏差。目前未接入人类提供的黑箱服务。


## D033 — 给人看的文档用中文、说人话（2026-11-04）

用户要求所有交付给人阅读的文档使用中文，避免内部黑话。研究报告、说明、
评价请求、摘要和进展均适用；必要术语应解释，代码/标识符/原始证据可保留。
原英文冻结记录不可事后改写；提供有来源的中文阅读版本。要求已通过Control
指导及组织消息送达，当前研究继续，科学条件和资源不变。

## D034 — 研究上下文管理需要专项设计（2026-11-04）

用户指出研究会话极长，不能按普通聊天自动压缩处理。ASR需要面向研究过程的上下文管理与压缩专项。其目标是保留科学语义、证据关系、失败历史和任务连续性，而不是仅让聊天长度变短。

原始交流与原始证据保持完整、不可被摘要替代。压缩得到的是有版本、有来源、可核查的工作材料，不是新的权威记录或科学事实。研究身份和状态独立于模型会话。当前显式会话换代只是应急恢复，不代表专项已经实现。后续设计与验收应特别覆盖遗漏反证、混淆假说版本、把未完成写成完成、跨角色泄露、遗失未决问题和重复执行等风险。

这补充D016的研究对象分离与D031的完整交流保留，不撤销原记录要求；不把固定的科学研究步骤写进ASR。

### D034补充：压缩算法与Runtime解耦

用户明确压缩算法本身不依赖pi机制。核心使用ASR规范化研究材料和来源引用；pi原生钩子仅为适配方案。核心生成成功与实际应用成功分别记录，运行时不支持安全接入时明确保留未应用状态。先完成离线核心及保真验收，再做pi首接入，后续支持其它Runtime。

### D034实施细化：实际安装与回查（2026-11-04）

用户要求本轮完成闭环，不能在中间步骤停下。指定触发的闭环已取得真实订阅证据，不以工程探针替代。覆盖核心与Runtime解耦；确需移出的保护项逐字重放，适配器原生系统重放另做逐字核对后去重。同步边界一次性票据、写入后原件/投影核验和继续请求前的Control回执是不同步骤，任何单一标志不能替代。历史原文查询只读本人冻结可见材料，不扩大权限。

因实际失败加入明确的JSON记忆summary解码引文视图、UTF-8流解码和正式RPC通知，不改写模型原答或接受转述。早期膨胀、引文拒绝、过期笔记及不稳定投影都保留，最终验收见RESEARCH-CONTEXT-INSTALLATION.md。该结果不宣称容量已自动调度或P5全部完成。


## D035 — 统一、宽裕且可恢复的容量策略（2026-11-05）

用户确认：所有容量上限须统一管理；逐项说明风险、单位、范围和默认值充分性，可配置调整。触限必须留记录，在可恢复边界暂停相关请求，不得静默中断整个任务；不得丢弃成本、在途执行、原始交流或未交付成果。扩大上限须保留旧策略与消耗，不能增加科学权限或自动切换付费服务。

统一入口为`configs/capacity-policy.json`，宿主加载后冻结版本与内容指纹。首批覆盖上下文握手、投影、日志/摘要/复核材料、pi传输容量；显式调用参数仍属实际有效配置，运行回执同时保存它们，不能用默认策略指纹冒充有效参数。模型窗口由模型能力与可靠测量确定，不以统一字节数替代。pi SDK当前用量为估算，只可用于预警。

这一轮先统一配置基础；自动容量采集、生成/复核调度、可恢复暂停及自动安装接续尚未完成。其余既有容量上限须逐项迁移登记，不能宣称全仓库已统一。


### D035补充 — 普通日志异步化（2026-11-05）

普通容量观测、进展与审计日志采用异步记录，不因逐条写盘/flush/fsync堵塞模型请求主链路。轻量观测与日志持久化分开；采集顺序、原生时间、归属会话和记录来源须保留。会话结束或导出归档前核对写入完成情况，未落盘前标记活动前缀，不能声称归档完整。队列拥塞、写入失败或进程崩溃导致的缺口必须显式呈现；不能静默丢记录，也不能因普通日志失败直接中止整个研究任务。队列容量及排空策略纳入统一容量配置，实施前核查超限恢复，不能引入未登记的任意小上限。

预算预留、权限变更、一次性安装授权及安装后核验属于执行控制回执，仍须在执行前取得成功确认；它们不按普通观测日志异步放行。完整日志投影应在数据库写事务外完成，随后短事务重新核对身份、版本与游标并提交结果，不能拿异步日志替代来源核验。

当前EventRecorder仍逐条同步fsync，session.record_event仍同步登记观测；异步化是下一实现项，尚未完成，不宣称主链路已解耦。


### D035实施更新：异步观测及收尾延期（2026-11-05）

普通游标登记已异步化；安装边界检查已入队任务排空，并通过原生进程单调序号防止原输出队列中晚到的旧记录覆盖新边界。普通会话结束只取非阻塞快照，未完成记录进入归档缺口。日志收尾默认等待120秒，到时返回draining，后台继续写，最终回执原子替换；不杀线程、不关闭其流、不声称已完成。观测排空同为120秒，仅安装边界等待；安装握手扩为300000毫秒，按统一策略第3版记录用途与余量。软队列内存增长、进程崩溃队列恢复及多次长日志投影充分性仍未验收。


### D035实施更新：恢复落盘前缀而非声称恢复全部队列（2026-11-05）

复用现有交流原件和Control幂等键，不增设权威观测/权限账本。宿主显式恢复时先冻结并完整校验来源，再逐条补记；只接收已退出且原身份未换代的会话。已写出前缀与从未写出的队列分开，半条尾记录保留而不猜测，恢复报告不能消除旧归档缺口。新增容量在统一策略第4版；具体边界及真实子进程证据见LIMITS-AUDIT。


### D035实施更新：积压在下一请求边界延期（2026-11-05）

复用既有turn准入和Control事务：先幂等重放，再记录当前积压与策略指纹、保存延期回执；不扣未发出轮次、不撤销旧许可、不取消在途试验。自然请求边界读取计数，不轮询日志。统一策略第5版水位128MiB，约为既有P5最大交流文件4.40倍，保留旧64MiB记录而不重解释历史。该机制抑制后续增长，不宣称硬内存边界或持久队列已完成；具体证据与局限见LIMITS-AUDIT及ASYNC-RECORDING-SIZING.json。


### D035实施更新：估算先观测，不能伪装准入（2026-11-05）

固定SDK的公开用量是投影估算，压缩后首个新回复前未知。因此先在请求边界观测、异步评估，记录精度/窗口来源/耗时，不从旧usage或字节数制造可靠计量；默认10%回复、15%工具、10%检查点预留仅用于提前建议复核。第6版统一配置支持按模型/任务调整，合计不得占满窗口，可显式关闭单项预留；不会改变实际输出上限或自行暂停研究。实际自动维护/安装仍是后续工作，见限制审计。

### D035实施更新：维护与科学执行分开，失败写入不得绕过核验（2026-11-05）

估算可在自然边界触发提前维护，但不能声称精确容量准入。复用现有AAR唯一执行者串行生成、独立复核和安装；最后一轮预警交给下一角色会话，不要求模型重复工具。维护禁用执行工具，沿用原Control总预算。默认只生成来源清单义务，不由开发侧编造科学结论；过期笔记不自动重新采纳。

真实验收发现两种基础设施边界：监督者不能调用人类pause命令，因此新增仅能延期的专用回执；pi将系统增量合并成完整快照，核验应比较完整有效配置而非最后一条增量。失败写入保留原票据与失败记录，离线历史核验不授予当前权限，必须重新准备当前安装后才能继续。不得通过新会话进程绕过旧的待核验写入。

### D035实施更新：重型核验在事务外，提交前重查权威状态（2026-11-05）

保留原件内容/哈希与SDK投影核验，移出Control写事务；提交时使用文件版本围栏，并重读成员、运行状态及票据，不用缓存替代当前权限。历史幂等回执不重跑核验；新请求遇竞争明确拒绝/延期。该方案依赖受控宿主和既有独占安装边界，不宣称跨文件系统/数据库原子性。其它笔记/typed附件I/O仍须单独处理。


### D035实施更新：笔记文件准备与权威采纳分开（2026-11-05）

笔记及代码/实验附件完整读取、校验和不可变草稿写盘不持有Control写事务；采纳指针、身份、来源和实验执行绑定仍由短事务内的当前记录决定。先写出草稿不等于保存请求已成功登记，更不等于采纳；竞争失败保留草稿并记录版本与未采纳状态，不让基础设施自动替研究员重新采纳。延续上一项的受控宿主文件版本围栏，撤销其“笔记/附件I/O尚未拆分”的当前状态描述。文件与数据库崩溃对账、全量附件内存及编译占锁仍开放。


### D035实施更新：安装计算不持有写锁，票据仍同步生效（2026-11-05）

将安装stage和授权的编译、授权阶段的摘要/复核计算移出写事务，以免纯计算阻塞其它控制写入。保留每次请求完整校验；提交重读原记录和当前状态、身份/进程、游标及一次性使用状态，任何变化拒绝旧计算。沿用既有成功回执幂等语义，不引入跨请求许可缓存。准入复核计算和大对象序列化仍未迁出。
