# Capstone 科学研究模式准备工作交接

版本：0.4。日期：2026-11-02。交出方：Automated Scientific Researcher（下称 ASR）。接收方：Capstone 项目。

**请 Capstone 同步准备专属“科学研究”模式：先完成接入设计、可替换的服务适配器、模拟服务和最小工作台交互，再与 ASR 的真实研究及实验服务联调。** 当前不需要等待潮流环境完成，也不需要重建一套自主研究执行器。

ASR 已补充 [最小闭环详细设计](../architecture/ASR-MINIMUM-LOOP.md)。接入时以其中 §2–§6 的对象/控制语义及 §8.2 的接口候选进行对齐；这些不是已可调用端点，仍需共同固定 schema 和样例。

用户已同意 Capstone 工作台、研究运行服务、AAR 执行器、实验服务与独立评价器的职责划分，并授权双方同步开展准备。本文给出接收方可执行的工作范围与验收要求；字段、动作名和协议版本是双方对齐的草案，尚非可调用 API。

## 1 背景与当前状态

ASR 建设可持续运行、可恢复、可复核的自动化科研系统。首个课题研究电网运行样本与潮流求解方法，可能产生采样方法、求解方法或联合方法。不能把产品固定成样本扩充工具，也不能把求解器锁定为永久不可研究的基础设施。

人类确定目标、研究变量、边界、评价规则与预算；智能体自主提出假设、修改代码、执行实验和解释结果。人类可随时观察、提问、指导、暂停或请求复核。关键节点提供介入入口，不强制每个实验等待人工审批。

ASR 已完成本机 IEEE-118 参考实验、独立验证和证据重放，参见 [P1 数值验收](../validation/P1-NUMERICAL-LAB.md)。本机认证控制、实际AAR闭环和P4合成OOD项目已有验收，见 [P4结果](../validation/P4-SCIENTIFIC-RESULTS.md)。这些验收不证明Capstone已接入；本交接协议仍须双方对齐。Capstone 第一阶段应使用明确标记的模拟数据，并将“交互验收”和“真实科研联调验收”分开。

本机研发采用 OrbStack + Docker Compose，无额外虚拟机要求。Capstone 延续自己的开发、发布、权限与数据管理规则。

## 2 双方职责与状态归属

| 责任方 | 负责内容 | 事实与状态归属 |
|---|---|---|
| Capstone 科学研究模式 | 课题对话、材料、契约编辑、指导与控制入口、实验与发现视图 | 对话、用户草稿、界面偏好、外部对象映射和展示缓存 |
| ASR 研究运行服务 | 契约校验与版本、控制受理、预算、运行身份、指导送达与回执 | 已生效契约、运行控制及预算记录；实际执行状态与执行器对账 |
| AAR 执行器，由 ASR 适配 | 假设、方法实现、实验安排、分析、共享发现 | 研究轨迹和候选结论；执行循环由该执行器负责 |
| ASR 实验服务 | 数值执行、冻结输入、候选代码快照、失败记录、产物 | trial、执行 attempt、原始测量和不可覆盖的证据清单 |
| ASR 独立评价器 | 干净环境重跑及独立场景检查 | 复核报告与正式验证结果 |

Capstone 可以帮助用户解释结果、整理假设、建议下一步；正式执行通过 ASR 接口。不要同时让 Capstone 的研究图调度器与 AAR 各自管理同一运行的自主实验循环。

ASR 的运行适配层应复用 AAR 的编排记录并映射其身份，不再引入相互竞争的研究员调度账本。Capstone 保存可重建的展示投影，不另行判断实验是否真正停止或验证通过。

沿用 Capstone 的 Application / Domain Pack / Kernel / Authority 分工。科研接口通过应用选择的绑定与明确的语义工具接入，领域结果由注册 Authority 返回。具体包位置由 Capstone 按当前架构确定；不要把电网或 AAR 特例写入通用 Kernel。

AAR 的候选代码编写和实验执行位于 ASR 管理的隔离环境。Capstone 专业会话只获得约定的科研动作；不因此获得任意宿主机命令、Docker 管理权或评价器内部数据。

## 3 Capstone 首批准备任务

以下任务属于 Capstone 的独立交付线。ASR 的数值环境和执行器接入同时推进。

| 顺序 | 工作包 | Capstone 应交付什么 | 依赖与验收 |
|---|---|---|---|
| C0 | 接入设计与对象映射 | 科学研究模式接入方案、当前组件复用表、对象映射、双方协议差异清单 | 可立即开始。确认研究运行独立于单轮对话，明确状态写入责任，不创建第二个实验调度器 |
| C1 | 服务适配器与模拟服务 | 可注入的科研服务接口、协议样例、确定性模拟实现、错误与恢复场景 | 基于 C0。真实与模拟实现共享接口；模拟模式显著标记；服务端地址来自受控配置 |
| C2 | 最小科研工作台 | 课题入口、变量与预算编辑、运行概览、实验列表、发现与复核详情 | 基于 C1。能完成第 7 节操作链；复用现有对话、材料、证据及产物组件 |
| C3 | 异步介入与恢复 | 独立指导/控制通道、执行回执、断线恢复、冲突处理 | 与 C2 协同推进。运行中仍可交流；刷新后恢复外部运行；重复请求和旧版本操作不导致重复执行或覆盖 |
| C4 | 真实服务联调准备 | 连接配置说明、契约检查、联调清单和当前验收记录 | C1–C3 完成即可交付准备成果。真实执行验收须等待 ASR 提供可用服务与实验材料 |

**Capstone 应首先交回 C0 的设计与接口差异，同时开始 C1 的模拟适配。** C2/C3 可基于双方认同的草案推进。未确定的字段用版本化适配处理，不在界面各处硬编码假定的 AAR 数据库或内部接口。

本交接不要求立即建设多研究员调度、完整假设关系图、插件市场、复杂报告编辑或跨课题资源优化。这些不应阻塞上述首批交付。

## 4 工作台首版信息结构

保持 Capstone 现有对话与工作区交互习惯，增加以下科研对象视图。它们可以是面板、标签页或详情抽屉，不要求分别创建页面。

| 入口 | 最低内容 |
|---|---|
| 课题与对话 | 目标、材料、关联运行、交流记录；人类与智能体内容有来源，交流与控制回执可区分 |
| 研究配置 | 每个变量的默认值、有效值、fixed/bounded/open 模式、允许范围、修改权限与生效范围；契约版本、评价协议和预算 |
| 运行概览 | 实际状态、数据更新时间、当前研究重点、已用/预留/剩余额度、待处理指导与需要人介入的事项 |
| 实验详情 | trial 与 attempt、契约和代码版本、输入、状态、测量、终止原因、日志与产物；保留失败和中断 |
| 发现与复核 | 结论、适用条件、支持及反对实验、局限、作者判断、复核请求与独立报告 |

研究变量目录由服务契约提供，界面不硬编码为某几个求解算法。初版示例至少覆盖研究目标、网络/拓扑、运行条件、采样方法、求解方法、初值、学习辅助、数据与评价分布、预算及研究员数量。

`open` 允许在授权范围内提出新实现，仍受预算、问题语义和执行权限约束。未设置的必要预算显示“未配置”，不能默认为无限额度；展示哪些缺项阻止启动。候选求解方法与固定参考基线分别显示。

## 5 接口协作草案

### 5.1 身份与版本

下表是最小对象语义，最终 schema 由双方对齐后形成带版本的单一协议。字段使用外部 opaque ID，不截取或重构，不将两个系统碰巧同名的 ID 当作同一对象。

| 对象 | 建议标识及关联 | 必要语义 |
|---|---|---|
| 课题 | `project_id` | 目标、材料引用、关联对话与运行 |
| 研究契约 | `contract_id`、`revision`、`project_id` | 有效变量、权限、预算、评价协议版本；已发布版本不可原地修改 |
| 研究运行 | `research_run_id`、`project_id`、契约引用 | 跨会话持续存在；AAR 原始身份由适配层映射 |
| 实验及尝试 | `trial_id`、`execution_attempt_id`、`research_run_id` | 冻结输入和配置；重试产生新 attempt；契约版本明确 |
| 指导或控制 | `command_id`、目标类型/ID、`idempotency_key`、预期版本 | 原始请求、系统解读、处理回执、生效边界 |
| 发现及复核 | `finding_id`/修订、`replication_id` | 支持/反对证据、冻结策略引用、独立报告 |
| 证据引用 | `artifact_id`、来源对象、类型、hash、大小 | 有界预览、授权下载；大文件不塞入对话或事件正文 |

`execution_attempt_id` 是跨系统接口的建议名称，本项目内部称 `attempt_id`；需显式映射，避免与 Capstone 自身对话 attempt 混淆。Capstone thread/turn/attempt 与科研运行/trial/attempt 不是一一对应关系。

### 5.2 需要支持的动作

以下为接口能力名，不规定 HTTP 路径或 MCP 工具名；Capstone 不应据此调用尚不存在的服务。

| 能力 | 主要输入 | 返回与处理 |
|---|---|---|
| 读取能力与变量目录 | 协议版本、课题类型 | 支持的动作、变量定义、约束及可用性；不支持的动作显示原因 |
| 创建/读取课题，校验/发布契约修订 | 草稿、预期版本 | 缺项/冲突或有效契约；运行中修改显示对后续实验的影响 |
| 启动/读取研究运行 | 已生效契约、幂等键或运行 ID | 外部运行身份和状态；启动返回不等于研究完成 |
| 追加研究指导 | 运行/方向/实验等目标、文本、版本、生效边界 | 持久化指导及送达/采纳状态；指导本身不绕过契约修改权限 |
| 暂停新提交、恢复、取消指定实验、停止运行 | 目标、预期版本、幂等键 | 控制回执及后续执行事实；不能在按钮点击时直接显示终态 |
| 读取实验、发现和产物 | 目标、游标、筛选条件 | 有界列表/详情、来源及更新时间 |
| 请求/读取独立复核 | finding 修订、冻结策略引用、幂等键 | 复核身份、状态、报告；不得由工作台自行填写验证通过 |
| 读取快照与增量事件 | 外部运行、事件游标 | 可恢复状态与后续事件；游标失效要求重读快照 |

契约修改具有独立动作与回执，不能把“优先尝试某方法”的聊天文字直接写成新的预算或执行权限。

### 5.3 命令与事件最低保证

- 命令建议包含协议版本、客户端请求身份、目标、预期对象修订、动作和负载。作者由服务认证上下文确认，不信任浏览器自行填入的身份。
- 同一幂等键与相同负载返回同一操作；同键不同负载拒绝。超时后先查询原操作，不换键重发可能产生副作用的动作。
- 预期版本针对被修改的对象，不因无关日志事件增长而使所有操作冲突。冲突时返回可解释原因与当前修订，禁止静默覆盖。
- 事件含事件 ID/游标、目标、对象修订、发生时间、关联命令和来源；允许重复投递，客户端去重并拒绝旧状态覆盖新状态。
- 断线先展示状态可能过期，再恢复事件或读取快照；不能把最后一次已知 running 当作当前存活证明。
- 服务端必须支持快照与后续事件的无缺口恢复语义，快照包含续读游标。ASR 首版选择有界增量轮询，SSE 可后加；不引入消息队列。
- 浏览器只连接 Capstone 后端；Capstone 后端适配 ASR。凭据、服务地址和访问授权由后端管理，数据按用户/课题权限取用。

双方应在真实联调前锁定协议版本、错误分类、状态枚举、版本冲突规则和事件恢复方式。ASR 维护服务协议权威文件；Capstone 维护消费侧适配与兼容检查，共用同版本样例。

## 6 人类介入的明确语义

交流、研究指导与运行控制在界面中可辨识。自然语言可作为入口；执行前展示或返回系统理解的目标与作用范围。授权已明确的操作直接处理，只有语义有歧义或缺少权限时才询问。

- **暂停研究**：停止提交新实验并暂缓排队实验派发，允许已在途实验完成并保存证据。显示“已暂停新提交，仍有 N 个实验运行”。不要暗示所有进程已停止。
- **立即停止运行/取消实验**：向实际执行端请求取消，保留已完成和部分产物。确认前显示“取消处理中”。
- **恢复研究**：依据服务端状态、有效契约及剩余预算恢复，不能通过重发旧启动请求实现。
- **追加指导**：先记录已接收，再区分已送达与已采纳/待验证/未采纳，并给出解释。指导生效点可以是下一次研究决策或后续实验，不要求修改正在执行的试验。
- **修改范围或预算**：生成新契约修订；已有实验保留原版本。无法确认安全适用的过期指令需要重新处理。
- **取消与完成竞争**：展示实际终态。已经完成的实验保留结果，取消不能删除结果或覆盖为取消成功。

建议命令回执区分 `accepted`、`pending`、`applied`、`rejected`、`failed`；查询失败时保留“状态未知”。最终枚举待双方协议固定。命令回执、研究运行状态、实验执行状态、科学验证状态分别建模。

例如实验 `succeeded` 只表示执行与产物发布完成。场景可能不收敛；方程验证可能失败；运行约束可能未评估。不得将它们合并成一个绿色“成功”。独立重跑通过也不能自动宣称已证明泛化或方法创新。

## 7 模拟验收与真实联调边界

模拟服务至少提供以下可重复场景，供 Capstone 本地验证：

1. 新建课题，展示默认变量，修改求解器为 open、拓扑为 fixed，发现预算缺项；补齐后发布契约并启动运行。
2. 研究运行期间继续对话与提交指导；显示其目标、生效边界和采纳记录，不重复启动运行。
3. 暂停新提交，同时保留一个在途实验；收到实际暂停回执后正确展示状态，再恢复。
4. 一个试验失败、一次中断后重试，旧 attempt 与部分产物仍可查看；另有执行完成但方程验证失败的结果。
5. 取消与完成竞争、重复点击和请求超时，均保持同一操作身份和真实终态。
6. 刷新、断线、重复事件和失效游标后恢复；能回到相同外部运行，旧事件不覆盖新状态。
7. 两次契约编辑发生版本冲突；拒绝过期写入，历史实验保留原契约。
8. 查看带反对证据的候选发现并请求独立复核；清楚显示未复核、处理中、通过/不一致，以及报告来源。
9. 无权访问的课题/产物被服务端拒绝，凭据不出现在浏览器产物与日志中。

模拟验收报告记录源码版本、具体场景、测试结果和必要截图。它只能证明消费侧协议与交互，不证明真实数值或自主科研成功。

真实联调时，ASR 必须提供可运行的服务、兼容协议、真实 trial 与产物、可执行 AAR 运行以及独立复核路径；双方按同一操作链复测。服务未就绪时，Capstone 可交付 C0–C3 和 C4 的准备部分，并明确剩余依赖。

## 8 可复用源码与阅读顺序

先阅读各自仓库的 `AGENTS.md`，遵循 Capstone 当前设计、工作区规范与变更流程。本交接不替代其已有发布与 CI 授权规则，也不要求此次直接发布服务。

Capstone 参考位置（相对 Capstone 根目录）：

- `docs/architecture/capstone-framework.md`：分层和当前研究机制边界。
- `packages/capstone-app/src/ThreadLiveEntry.tsx`、`threadClient.ts`：持续对话和传输状态。
- `packages/capstone-app/src/ResearchEvidence.tsx`：研究记录、来源及判断/核验区分。
- `packages/capstone-app/src/NativeArtifactsWorkspace.tsx`：产物浏览和下载。
- `packages/capstone-app/src/threadControlPolicy.ts`、`packages/capstone-agent/src/capstone_agent/thread_work.py`：运行中发送限制与取消处理，需要重新确认当前行为。
- `packages/capstone-agent/src/capstone_agent/native_research_bridge.py`：现有研究桥接，不能直接视为 AAR 连接器。
- `packages/capability-agent-kernel/src/capability_agent/domain/manifest.py`：领域注册契约。

这些位置在 2026-11-02、HEAD `54e33dbf` 的有改动工作树上检查过，属于导航线索。接收方先核对最新实现，保留其他正在进行的工作。

ASR 的稳定设计入口是 [PROJECT-DESIGN.md](../PROJECT-DESIGN.md)，重点阅读 §4–§9.2；交付进度见 [WORKLIST.md](../plans/WORKLIST.md)。同级 checkout 中分别对应 `../automated-scientific-researcher/docs/PROJECT-DESIGN.md` 与本交接文件。

## 9 回交成果与后续协作

Capstone 首次回交应包含：

- C0 接入方案与拟复用组件，说明科学研究模式与现有模式的关系、研究状态归属和运行中交流路径。
- 接口差异清单：认可的语义、需要调整的字段/动作、冲突点及推荐替代；不要只提供无法比较的另一套完整协议。
- C1–C3 的实施切片与本地验收计划，标明不依赖 ASR 的工作和需要 ASR 配合的事项。
- 后续每批交付的代码版本、完成范围、验证证据、尚未实现项及真实联调依赖。

ASR 同步承担：数值环境与真实试验、AAR 适配、科研服务协议和执行端语义、独立评价路径，并提供同版本真实响应样例。两边接口变更同时更新协议版本、消费侧测试与本交接的相关条目。

本文件是跨项目交付约定；研究目标与架构原则继续以 ASR 主设计为准。后续变更在本路径修订，保留 Git 历史，避免产生多份互相冲突的交接说明。

## 变量配置准备补充

ASR 已提供 `contracts/variable-policy.schema.json` 与 `contracts/examples/research-variables.json`，可用于 Capstone 表单/模拟适配。语义与限制见 [变量策略说明](../../contracts/README.md)。这是完整研究契约的子 schema，尚不具备预算、引用或执行授权；本机认证控制 API 已实现（见 asr_service/README.md），实际跨项目运行控制尚待联调。

### Subscription-first runtime alignment (2026-11-02)

Researcher runtimes are replaceable; pi with Codex subscription is the lightweight baseline. Claude SDK is no longer mandatory. AAR remains the research organization adapter, ASR owns durable run/trial/evidence IDs. Runtime credentials stay outside candidate execution and persisted event payloads. Explicit subscription mode has no automatic paid API fallback; quota limits pause new work and preserve recovery. Provider support is verified individually.

### Scientific trust alignment — D016 (2026-11-02)

Accepted ASR requirements: distinguish execution, experiment validity, hypothesis assessment and finding validation; expose immutable hypothesis revisions and supporting/opposing/inconclusive evidence; keep research identity separate from runtime sessions. Display model/subscription and experimental-compute budgets separately, including unknown quota. Never promote an author claim to formal validation or merge scientific negative results into automatic error retries.

These are P3 implementation targets, not currently available wire fields. Capstone should prepare projections and align versioned protocol changes when ASR schemas land; no duplicate authoritative hypothesis or budget ledger. This update is prepared in ASR only, not evidence of delivery, acceptance or implementation in Capstone.

### Three-layer research organization — D018 (2026-11-02)

This replaces the earlier merged mentor/interaction interpretation in D017.
Capstone connects humans to the Research Organizer (研究组织者; architecture name
Super Agent). It captures overall intent, coordinates the AAR organization across
directions and reports progress/decisions. It is not the direction-level mentor.

Inside AAR, multiple Research Leads guide hypotheses, experimental design and
evidence synthesis for their respective directions. Research Workers perform
specific search, coding, experiment, debugging and review tasks. Projections must
distinguish overall conversation, direction, task owner, research run and runtime
session; do not collapse all identities into a single chat thread or agent ID.

Human changes become explicit target/version/Control receipts. Conversation alone
does not authorize evaluation or budget changes. Direct pause/stop bypasses agent
availability. Scientific judgments remain distinct from independent Validation.
These are future P5 requirements, not deployed roles or evidence of cross-project
delivery. Reuse AAR organization; do not create another Capstone scheduler/ledger.

D019/D020 update: display role (Research Organizer/Research Lead/Worker) separately
from runtime/provider/model and tool-pack identity. Leads retain autonomous
scientific responsibility and direct cross-review. Native Codex App Server and
Grok ACP adapters follow pi; existing local login/coding is user-confirmed,
ASR runtime acceptance remains distinct. Native thread/session/turn IDs never
replace research/trial IDs. This is a prepared local handoff, not evidence of
Capstone delivery or implementation.

Implementation update: ASR now exposes immutable evaluator-only validation POST
and project-readable GET at `/v1/projects/{project}/runs/{run}/validations`.
Display separate assessment axes and evaluator-attested independence; do not
convert `isolation_verified_by_service: false` into a verified badge. Negative
superseded reports remain visible. Run reads add `resource_ledgers` alongside
legacy budget; provider quota unknown is not zero or unlimited. This local
contract update has not been delivered/accepted by Capstone.


## P3 verified handoff update (2026-11-03)

ASR's bounded P3 acceptance is complete; see `docs/validation/P3-SYSTEM-ACCEPTANCE.md` and `LIMITS-AUDIT.md`. Actual Control lifecycle and AAR Experiment projection have separate verified receipts. Display retained failures, the original timeout/overrun, subsequent explicit budget revision, scientific assessment axes and unknown values. Do not derive research completion from a stale AAR label or equation convergence.

Candidate/evaluation/replication and quota-observation local routes are documented in `asr_service/README.md`; this does not imply wire compatibility with Capstone. Typed artifact verification and evaluator attestations remain distinct. Show limit name, configured/observed values, action and recovery; do not silently discard a research task on exhaustion. Current single researcher is the Research Lead prototype, not a deployed Organizer/Lead/Worker hierarchy.

This update is prepared in ASR only. Delivery, acceptance and Capstone implementation remain unconfirmed. P4 formal scientific comparison requires its own frozen contract and finite budget.


## Planned visualization entry point (2026-11-04)

User requests a visual research dashboard at the appropriate stage. Start integration
once actual comparison data, evidence references and development/final evaluation
interfaces are stable. Initial views: organization/task progress, sample distributions,
training/evaluation comparisons and retained failures. Render authoritative ASR records;
do not create another scheduler or budget ledger. Separate human inspection views from
researcher tool access; unreleased final coordinates/labels must not flow into agent
context. This is an ASR-side plan, not delivered or accepted Capstone implementation.


D030: visualize actual team-authored plans, decisions and artifacts rather than a
fixed developer-prescribed scientific workflow. Mark human/developer lifecycle
interventions and developer-authored project adapters distinctly. The workbench
observes and communicates with the Organizer; it must not silently direct research
steps or convert one four-arm/eight-seed proposal into a universal process.
