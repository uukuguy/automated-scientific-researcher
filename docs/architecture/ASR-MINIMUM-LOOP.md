# ASR 最小研究闭环详细设计

版本：0.3，2026-11-02。状态：P1 参考实验与 P2 本机控制/监督、pi 订阅轨迹及中断恢复已有验证；实际 pinned AAR loop/ORM 和科学环境已完成受限验收；P3 独立验证仍在实现。跨项目协议待 Capstone 对齐，正式科学参数待校准。

实现入口：`asr_service/README.md`、`asr_supervisor/README.md`、`integrations/runtimes/README.md`。本文目标协议与当前本机路由并不完全相同；不能以设计路径宣称端点存在。真实订阅验收见 `docs/validation/P2-SUBSCRIPTION.md`。

本文件细化 [项目主设计](../PROJECT-DESIGN.md) §4–§10，覆盖单课题、单研究员、真实实验、人类介入、独立复核和中断恢复。主设计仍是唯一总入口；本文负责实现边界和行为，不复制项目目标或维护进度。对总体原则的改变必须回到主设计和决策记录。

## 1 交付边界与技术选择

首个闭环：发布完整研究契约 → 启动 AAR → 提出假设并提交真实 trial → 人在运行中指导或控制 → 发布候选发现 → 独立重跑 → 读取复核结果继续研究。工作台断线、Agent 重启、执行器异常均不丢失已承认的请求、证据和预算。

采用模块化服务加容器执行。直接在 AAR 后端扩展控制入口，比另建一套研究调度平台更容易保持运行身份一致；仅用目录和聊天记忆则不能保证并发预算与恢复。初版不增加消息队列，也不把每个模块拆成独立微服务。

### 1.1 组件与部署

| 组件 | 部署与职责 | 允许写入 |
|---|---|---|
| ASR API/control | 扩展 AAR 后端，提供版本化 HTTP 接口；唯一数据库写入服务 | 契约、运行、命令、预算、实验索引、事件与验证记录 |
| Supervisor | 受信任的执行管理进程，管理带身份标签的容器、租约与超时；经 API 报告 | 自身运行日志；通过受权限限制的内部接口提交执行事实 |
| AAR researcher | 受限容器，可替换 Runtime 会话与研究工具，工作区可写 | 研究工作区、候选代码、笔记和候选发现；不写权威数据库 |
| Candidate runner | 按 attempt 启动的容器，执行冻结候选及输入 | 本 attempt 的临时输出目录 |
| Validator/replicator | 独立受限进程/容器读取冻结材料，候选执行与验证再次隔离 | 独立验证产物，经可信发布流程登记 |
| Capstone | 独立应用，通过后端适配 ASR | 对话、草稿和可重建投影；不直接写 ASR 表或访问 Docker |

使用 AAR 已有 SQLite 数据库及 SQLAlchemy 模型作为本机起点，增加迁移和 ASR 表；所有业务写入经一个控制服务，SQLite 文件位于本机持久卷而非网络文件系统。多主机扩展时再迁移数据库。API 多请求仍需事务级比较版本和预算检查，单写入服务不是省略并发控制的理由。

研究运行沿用 AAR Experiment，增加 `research_run_id`、契约引用和 ASR 生命周期字段；原有 status 仅为兼容投影。禁止原 RunPod/local worker 与新 Supervisor 同时调度同一 ASR 运行。ASR 模式只启用新执行管理入口；旧运行按旧模式读取，不能自动迁移为新运行。

Supervisor 是唯一持有容器管理能力的组件，可先以本机受信任进程运行。Agent、候选代码和评价代码均不挂载 Docker socket。实验容器无外网，只有冻结输入的只读挂载、独立输出目录和必要临时空间；禁用提权并限制 CPU、内存、进程数、时间与输出体积。研究容器仅允许必要模型/API 通信，模型凭据不传入候选容器。

代码包构建在执行前完成，镜像按 digest 引用；运行时不联网安装依赖。新增依赖需经过受控构建，构建费用和时间另行记录。恢复与备份必须包含数据库及其引用的全部产物；导出时先停止新提交并取得一致快照。

### 1.2 拟实施目录与责任

- `asr_service/`：契约、命令、预算、事件、权限与数据库迁移；提供公共 API 和内部执行报告入口。
- `integrations/aar/`：固定来源、补丁、依赖裁剪、SDK 会话钩子与身份适配；生成的上游运行副本不作为唯一改动来源。
- `asr_supervisor/`：容器管理、租约、停止、回收与事实对账。
- `powerflow_lab/`：已有计划中的数值适配、输入结构、独立验证和证据 manifest。
- `contracts/`：实施时交付 JSON Schema、版本清单及成功/失败样例；当前协议以本文为设计依据。
- `tests/`：契约、状态转换、恢复故障、权限和数值负例；`scripts/`、`docker/`、`configs/` 保存可重放入口与配置。

以上是目标目录分工；已实现切片位于 powerflow_lab、tests、scripts、docker 和 configs，其余以工作清单为准。数据库只由控制服务持有；P1 可通过同一领域模块的本地入口先完成真实实验，后续接入 HTTP 时不另写一套验证语义。

## 2 课题契约与版本

### 2.1 最小结构

接口采用 UTF-8 JSON，时间使用 UTC RFC3339，数值禁止 NaN/Infinity；浮点测量与用于身份的规范化输入分别保存。ID 为不透明字符串，revision 为单调递增整数。

| 字段 | 类型与规则 |
|---|---|
| `schema_version` | `asr-contract/1`；不支持的主版本拒绝 |
| `project_id`, `contract_id`, `revision` | 服务分配；契约版本不可覆盖 |
| `objective` | 目标、研究方向、成功标准和结论适用范围 |
| `variables` | 按变量 ID 索引；每项含 type、unit、default、value、mode、allowed、modifiable_by、scope |
| `problem_ref` | 原始 case hash、场景 schema、单位及索引约定、运行政策版本 |
| `reference_ref` | 参考采样/求解/初值实现与镜像 digest；独立于候选方法许可 |
| `evaluation_ref` | 开发/正式评价身份、验证器版本、固定阈值、比较和去重协议 |
| `budget` | 时长、计算资源、尝试数、模型调用等有限额度；开发和独立评价分账 |
| `execution_policy` | 允许的实现类型/镜像、单次超时、输出限额、并发、失败重试政策 |
| `intervention_policy` | 通知事件、可选人工节点、范围修改权限、指导生效边界 |
| `provenance` | 作者、来源模板版本、创建时间、规范化配置 hash |

`allowed` 对 bounded 变量必须给出合法区间或有限集合；open 必须指定实现接口及可执行权限，不能成为任意权限通行证。`scope` 区分课题、运行、trial 和正式评价协议；单位与数据类型不可依靠自然语言猜测。

### 2.2 发布与生效

1. 从有版本的课题模板取得默认值，合并用户显式字段。只对声明过的字段合并；未知字段、类型错误、单位冲突或必要缺项返回字段级错误。
2. 校验变量模式、权限、引用存在性、依赖约束、预算与执行支持。合法但尚未支持的配置返回 `capability_unavailable`，不静默降级。例如首版单研究员不能接受数量 2 后仅运行 1 个。
3. 发布生成不可变 revision/hash。草稿可保存而不能执行；缺少数值阈值等项目不阻止一般讨论，但阻止对应实验或评价。
4. 发布不自动切换运行。`apply_contract` 使用运行的 control revision，将选定契约作用于后续提交；切换与实验受理在同一事务序列中线性化。
5. 受理成功的 trial，包括尚未启动的队列项，保持原契约。欲撤回旧条件应明确取消；新约束若要求立即停止，必须同时提交针对旧工作的控制动作。
6. 预算降低不得小于已消耗加已预留额度。实际结算超过预留时允许账本如实记账并阻止新工作，不能截断实际费用；后续额度调整必须覆盖真实负债。

候选参数在 fixed/bounded/open 授权内变化，只形成 trial 参数与代码快照，不为每次搜索创建新契约。改变权限、评价规则或问题语义才生成新的契约/协议版本。

## 3 身份、持久化与事件

| 记录 | 唯一性和用途 |
|---|---|
| Project / ContractRevision | 一个课题多个不可变契约版本 |
| Experiment ASR extension | 一个研究运行；上游 Experiment ID 与 research_run_id 唯一映射 |
| ResearchSession | 每次 SDK 会话独立身份，归属同一研究运行；不是 trial attempt |
| HypothesisRevision | 不可覆盖的假说版本、父版本、预测/适用范围/反驳条件、探索或验证属性、修改理由 |
| Trial / ExecutionAttempt | trial 冻结配置与输入；重试新建 attempt，不改历史 |
| Command / Guidance | 原请求、认证作者、规范化摘要、目标版本、回执、生效点、指导采纳记录 |
| Reservation / Usage | 预算预留与不可覆盖的实际消耗记录；按 attempt/session/replication 关联 |
| Artifact / Validation / Replication | 原始产物索引、不同验证报告、独立复核关系 |
| FindingRevision | 复用 AAR Finding，加修订和证据引用；论坛文本不能覆盖验证结果 |
| Event / DispatchIntent | 同事务事件与待执行动作；提供恢复重放，不作为第二个研究计划 |

所有变更事务同时写入对象版本、事件和必要的执行意图。Supervisor 领取意图后调用幂等内部接口；数据库提交成功而响应丢失时可按 command ID 查询。容器创建与数据库无法原子提交，因此用确定的 attempt 标签查找和对账，不能承诺跨外部系统“恰好一次执行”。

命令幂等键作用域为调用主体、课题与动作，保留到课题归档；规范化负载 hash 不同则拒绝。对象采用独立 control revision，日志追加不改变控制版本。事件序号按项目持久化单调增加，不使用时间戳作为唯一游标。

快照在一致读事务内返回对象状态与事件水位。客户端从水位之后续读；重复事件去重，过期/非法游标要求重取快照。首版保留课题全量事件直至归档，分页读取并限制响应体积；归档提供快照加产物清单，活动运行不删除恢复所需事件。

### 3.1 假说与证据关联（D016，部分实现）

版本以课题和假说 ID 为作用域；修订采用并发版本检查、幂等键和同事务事件。Trial 受理时检查假说版本属于本课题，并冻结该版本与评价协议。后续修订不改变旧 trial；历史无假说版本的 P2 数据保持 legacy/unlinked，不虚构实验前声明。

FindingRevision 引用具体 hypothesis revision、trial/attempt/manifest 和 Validation ID；每项关系记录支持、反对或不确定及适用范围。反对证据不能被后续成功版本覆盖，缺失证据和实验无效不能转为假说被否定。Validation 的正式状态仅由 evaluator 身份写入；作者只能提交候选解释。后见解释明确记录观察发生在声明之前。

执行状态、实验有效性、假说判断、发现复核状态是不同字段/记录，不能合成单一 outcome 枚举。当前实现 `asr_service/hypotheses.py` 的严格文档 schema、追加修订表、HTTP 发布/查询、trial 可选冻结绑定、作者证据关系与 pi 工具接入。旧请求幂等负载和原回执保持不变；旧 trial 的 legacy_unlinked 仅为读取投影。正式 Validation 记录已新增 evaluator 专用发布/读取接口：精确绑定 terminal trial/attempt、manifest hash 和评价引用，验证原始产物 inventory，保存独立结果轴、报告 hash 及不可覆盖 supersedes 关系。身份、引用与字节校验不等于服务已证明 OS 隔离或结论为真；independence_basis 为 evaluator_attestation，isolation_verified_by_service 为 false。作者关系不能当作评价器判定；发现晋升、真实隔离和完整科学轨迹另行验收。

## 4 运行、控制与指导状态

运行分别记录 `lifecycle`、`admission`、`health` 和 `control_revision`，避免一个状态字段同时表达暂停、心跳和科学结果。

- lifecycle：`queued → starting → active → stopping → completed/stopped/failed`；任意非终态在执行身份不明时进入 `interrupted`，对账后可恢复 active 或结束。
- admission：`open` 或 `paused`，附原因（用户、预算、权限、基础设施）；只有 active/open 且 health 正常才可受理新实验。
- health：`ok`、`stale`、`reconciling`；失联本身不等于进程退出。
- 终态不可恢复为 active。继续已经终止的工作创建新运行并引用前序；中断运行则可在证明旧执行权失效后原身份恢复。

| 动作 | 前提与生效行为 | 完成条件 |
|---|---|---|
| start_run | 已发布完整契约和有限预算；创建运行及启动意图 | 容器与会话报告身份后 active，失败有明确原因 |
| pause_submissions | 任意非终态；事务关闭新 trial 入口和待启动 trial 派发 | 门控已关闭即 applied；在途实验继续，显示数量 |
| resume_run | paused 或 interrupted；剩余预算足够，旧租约已对账 | 门控开启；新会话持有效执行代次 |
| cancel_trial | 指定 trial/attempt；排队项直接终结，在途请求停止 | 执行端退出且产物处理完成；竞争完成时返回实际终态 |
| stop_run | 立即关闭门控，取消未启动项，终止活动 Agent 与候选容器 | 所有受管执行已退出、证据及预算对账后 stopped |
| finish_run | 研究员/用户声明阶段结束；关闭门控，不再启动排队工作，在途完成 | 无在途工作且完成汇总；未启动项取消并记录原因后 completed |
| apply_contract | 非终态、匹配 control revision、权限与预算校验 | 后续提交使用新版本；不会改写已受理 trial |

默认暂停除禁止新提交，也暂缓已经排队但未启动的试验；活动 SDK 会话可在剩余会话额度内完成分析，但不启动下一会话。需要立即停止模型消耗时使用 stop_run，不能把暂停声称为所有资源已停止。

回执状态：`accepted → pending → applied/failed`，拒绝为 `rejected`。取消失败不能伪造 applied；终态已完成时可 applied 并标注 `already_terminal` 与实际结果。命令回执、执行状态及科学验证均分开。

研究指导有独立收件箱，不占用研究执行会话锁。状态为 received、delivered，再追加 adopted/deferred/declined 及理由；已送达不等于模型采纳。每次会话启动和工具调用前读取新指导，当前模型生成中不承诺立即注入；控制门控由服务端立即生效，不等待模型理解。明确范围/预算变更走契约动作，指导文本不能修改权限。

通知默认包括候选发现、复核完成、预算阻塞、基础设施中断和需要授权的范围扩展；普通实验失败仅进事件流。相同原因合并通知，进度节奏由用户配置；没有回复不表示批准。科学停滞只是基于进展证据的建议，不默认自动提高资源。

## 5 实验执行与发布

trial 固定原始问题、候选快照、具体参数、输入清单、随机种子、验证协议和请求额度。相同科学请求因显式重试产生新 attempt；真正复现实验建立新 trial 并用 `replay_of` 关联，保留独立费用与证据。

attempt 状态：queued → running → succeeded/failed/timed_out/cancelled/interrupted。取消意图为单独字段；终态由实际事实决定。queued 项取消无需启动容器；running 项不能仅凭取消请求成为 cancelled。trial 展示全部 attempts 和显式选定的结果 attempt，不只展示“最近成功”并隐藏失败。

### 5.1 候选进程协议

固定命令入口由已注册镜像配置提供，服务传入参数数组而非拼接 shell。输入为只读 `/input/request.json` 及被引用材料；候选写 `/output/response.json` 和有界产物，stdout/stderr 是日志而非权威协议。

| kind | 输入 | 输出 |
|---|---|---|
| sampler | 变量定义、场景预算、种子、原 case 引用 | 有稳定 scenario ID 的参数/场景清单、生成成本与诊断 |
| solver | 冻结场景、初值及来源、方法参数、时限 | scenario ID 对应的电压/必要控制变量、求解声明、迭代诊断与原因 |
| joint | 采样条件与同一预算下的候选策略 | 场景、对应候选解、逐项成本；由服务另行核验 |

schema 使用 `asr-candidate/1`。每个场景须带输入 hash；结果缺失、重复 ID、未知 ID、非有限数值、错误维度、越界产物路径均标为协议错误并保留原输出。部分场景有合法结果时可单独验证，但统计分母含全量已提交场景，不能丢弃失败。

退出码 0 只表示程序正常退出；监督进程仍校验格式和产物发布。失败时保留已产生输出，按逐场景结果报告未知或未完成。候选自报迭代次数等标记来源，未采集不能补造。

### 5.2 证据提交顺序

1. API 事务创建 trial/attempt、预留额度与派发意图。
2. Supervisor 带 attempt ID、执行代次和容器标签启动；派发前再次检查门控及租约。单个 attempt 不允许两个活动容器。
3. 候选结束后确认进程已退出；可信发布器读取输出、拒绝符号链接/越界路径，限制文件数和大小，复制到服务拥有的暂存区。
4. 固定快照、日志和结果的 hash，写 manifest 并同步文件；在同一持久卷原子发布不可变目录。
5. API 事务登记 manifest hash、终态、消耗和事件。重复报告必须匹配相同内容；不同内容返回冲突，不能覆盖。
6. 验证器读取已发布材料，追加独立 Validation 记录。验证失败不改变执行 succeeded；报告是新的不可变产物。

若在 4 与 5 之间崩溃，对账验证完整 manifest 后补登记；无完整 manifest 的目录只作未完成材料，不能当成功。数据库已记录而产物丢失/损坏时显示 `evidence_unavailable` 并阻止引用为已核验证据；原执行历史仍保留。

## 6 预算与恢复

预算以项目为上限，运行/独立评价分配子额度，防止新建运行绕过项目上限。每一计量维度满足 `available = limit - spent - reserved`；所有预留和变更在同一数据库事务内检查。并发槽、内存峰值是准入约束，不与累积 CPU 时间相加。

受理前预留该操作声明的最大额度，执行后结算实际值并释放未用部分。失败、超时和取消已消耗的费用不返还。未知消耗保留预留或保守结算并标记估计，不能因心跳失联释放预算。每笔用量按执行身份和计量序号去重。

可硬限制项为外部可测的执行时长、CPU/内存/进程限制、调度次数及受控工具调用。自定义程序内部“求解次数”可能不可可靠拦截，记录为自报或仪表化测量，不能宣称它是所有自定义算法的硬公平预算；正式比较优先使用受监督的时间/资源额度，并另报内部操作次数。

模型调用经有限调用数、输出限制、会话时限和费用估计门控；账单延迟或 SDK 内部重试须计入未结算风险，不承诺精确硬金额封顶。开发与独立评价分别结算，总成本均报告；预算耗尽时先关入口，已有预留允许在上限内完成，超时仍停止。

模型与计算使用两个逻辑账本（D016），共享同一控制写入方。跨账本操作必须原子预留或全部拒绝；各计量维度独立，不把 token、秒与费用直接相加。订阅配额观测有来源、观测时间及 unknown/limited/exhausted 等语义，供应商观测与本地预算分开，不能因一次刷新覆盖已消耗记录。账本归属、结算幂等和恢复后保守预留须迁移验证。GPU 等未接入资源在准入中明确不支持，不能仅接受配置字段就宣称限额有效。

已实现首个双逻辑账本切片：BudgetStore 对原权威 reservation 行提供 model（research_walltime_ms、turns、tool_executions）及 compute（attempts、execution_ms）一致快照，并支持跨组原子预留。历史消耗和在途预留不搬迁、不重置或重复计数；未知旧维度单列 unclassified，不自动授予新执行能力。provider_quota 保持 unknown，不能从本地剩余预算推断供应商订阅额度。此切片不等于供应商额度观测、GPU 计量或完整 A14 验收。

### 6.1 单执行权与恢复过程

Supervisor 使用 lease、递增 epoch 与容器不可复用身份；API 只接受当前 epoch 的结果写入。工程起始建议：5 秒心跳，30 秒过期，10 秒优雅终止后强制终止。这些为配置默认值，可按环境调整，不是数值科学参数。

租约过期：先置 stale/reconciling 并关门控，再查容器标签、启动时间和运行状态。旧执行仍活着时确认接管或终止后才允许重启；即便旧 epoch 写入被拒绝，旧进程仍可能消耗资源，不能仅靠 fencing 就释放预留。

对账顺序：读取未结命令/派发意图 → 核对容器 → 恢复已发布 manifest → 核对实际预算 → 标记无法完成的 attempt interrupted → 恢复待送达指导 → 决定启动下一会话。不能从模型笔记推导运行终态。

默认不自动重跑有副作用的实验。AAR 或用户显式重试创建新 attempt，经过新预算预留；Supervisor 的幂等派发恢复不视为新研究试验。基础设施连续失败达到 3 次时关闭受影响入口并通知；科学不收敛不计入该阈值。该阈值可配置，不允许无限自动重启。

## 7 科学评价与独立性

三层独立性分别出具证据：执行层验证 OS/容器身份及读写权限；数据层验证冻结原材料和内容哈希；逻辑层验证原问题数学重建与故意错误结果拒绝。不同进程或不同库名称不能替代这些测试。

验证依赖冻结原输入、声明的可变控制量和原始数学问题。不可把求解后允许变化的 Slack 出力、无功或受政策约束的状态一概当作“输入被篡改”；也不能接受候选任意改负荷后求解。由运行政策明确固定量、未知量和允许的控制转换，独立检查全部约束。

| 层次 | 独立输出 |
|---|---|
| 输入有效性 | schema、单位、索引、拓扑、固定量与允许变更；失败不进入有效样本计数 |
| 求解声明 | 候选 converged/nonconverged/unknown，仅为作者声明 |
| 原方程验证 | 按冻结政策重算残差及必需控制约束；pass/fail/not_assessed |
| 运行约束 | 各约束通过/违反/未评估；缺失限额不能算完全可行 |
| 科学比较 | 协议版本、场景/种子、资源成本、有效性、覆盖代理、失败与不确定性 |

验证器从原始 branch/bus/gen 数据独立构造检查，不能只读取候选声称的 mismatch。用解析小算例、改变输入、非有限数、索引/单位错误、tap/shunt 与故意越限作为负例；参考工具差异由人工可审查报告解释。具体电气实现遵循经核对的参考文档，本文不替代该校准工作。

独立复核分两类：同一输入与冻结策略的 replication；未用于开发的场景族上的 generalization。报告分别给执行是否完整、可重复性是否一致、科学断言是否得到支持。候选作者不能写正式判定。

正式评价代码、种子和数据由 evaluator 身份管理；候选执行所需输入按次提供，无权读整套评价资产或控制验证器。评价场景的明细反馈若已用于开发，该集合必须降级为开发集；不能反复修改策略后继续把同一反馈集合称独立测试。新策略正式评价使用另一个未暴露批次并记录评价次数与消耗。

比较采样器时固定参考求解协议；比较求解器使用相同输入和资源规则；联合策略至少包含基线采样+基线求解、候选采样+基线求解、基线采样+候选求解、联合候选四组。热启动、参考标签、训练、筛选、多次尝试与预处理成本均计入对应口径。

正式比较预先冻结主要指标、随机种子安排、预算、容差、失败分母、去重与覆盖定义；报告重复试验波动及效应，不仅报告挑出的最优运行。新增发现可以来自可靠的负面结果或失败机制，不要求每轮“赢过基线”。

### 7.1 校准与启动门槛

| 项目 | 当前状态 | 未完成时禁止什么 |
|---|---|---|
| MATPOWER/Octave 版本、镜像 digest、case hash | 当前镜像与参考 case 已核验，换镜像需重验 | 禁止声称参考环境可复现 |
| Slack、Q 限值、PV/PQ、负荷与控制模型 | 从基线明确并固定后写入契约 | 禁止无定义地比较不同问题的解 |
| 残差、输入保持、运行约束及复现容差 | 解析用例及真实试验校准；现有 1e-7 只为计划中的测试起点 | 禁止未经协议的正式有效性判定 |
| 扰动范围、OOD 家族、去重与覆盖分区 | 小规模开发试验后冻结 | 禁止宣称正式 OOD 泛化或全可行域覆盖 |
| 用户资源额度、模型调用及复核额度 | 启动前明确有限值 | 禁止有费用的自主循环；不由本设计代用户授权金额 |

可先完成不涉及上述未定值的契约/控制模拟验证，再以明确标记的 calibration profile 做真实小实验。校准数据记录为开发用途，不能之后悄悄变成独立测试。

## 8 AAR 接入与人机协议

### 8.1 AAR 改造点

本地上游的实际 Python 包根为 `3th-party/automated-w2s-research/w2s_research/`。固定来源与原始 revision；适配补丁放在 `integrations/aar/`。

- `research_loop/agent.py`：每次会话绑定 run/session/epoch；启动及工具前同步指导和契约；SDK 活动会话由外部监督时限约束。
- `research_loop/prompt.jinja2`：替换 W2S 训练预设，注入有效契约、证据要求、可用工具、预算及已知状态；不规定固定科研步骤。
- `research_loop/tools/server_api_tools.py`：增加试验/检查/发现/复核的有类型工具；只把实际受理身份和回执返回模型。
- `research_loop/tools/findings_sync.py`：使用 finding ID 加 revision 同步；本地模式也要接收共享发现和复核报告。
- `web_ui/backend/models.py`、`worker.py`、`app.py`：扩展身份与记录，接入新控制和 Supervisor，隔离旧评分写入与旧调度路径。

本地恢复不以 SDK session 可续接为必要条件：新会话读取有效契约、已完成/在途实验、未结指导、预算、代码快照与简洁研究笔记。实际试验不因新会话自动重做。候选发现必须附证据引用；记忆摘要保留引用而非复制不可靠数值。

### 8.2 面向 Capstone 的接口候选 v0.1

公共协议标识 `asr-control/1`。以下是待实现并与 Capstone 对齐的路径设计，当前不存在可调用端点。浏览器经 Capstone 后端访问；ASR 校验受信任调用凭据、授权主体和课题范围。即使本机单用户，也不以任意浏览器提交的 author 字段授权。

| 方法与路径（前缀 `/api/asr/v1`） | 作用 |
|---|---|
| GET `/capabilities` | 支持的协议、动作、变量 schema 与限制 |
| POST `/commands` | 所有业务变更统一入口；按 kind 校验负载与权限 |
| GET `/commands/{id}` | 按 ID 查询回执及生效结果 |
| GET `/projects`、`/projects/{id}` | 有权限的课题分页与详情 |
| GET `/contracts/{id}/revisions/{revision}` | 读取不可变契约 |
| GET `/runs/{id}`、`/runs/{id}/trials`、`/runs/{id}/findings` | 运行快照与分页对象 |
| GET `/runs/{id}/guidance?after=...` | 独立指导收件箱；读取不自动表示模型已采纳 |
| GET `/trials/{id}`、`/findings/{id}`、`/replications/{id}` | 详情与证据引用 |
| GET `/artifacts/{id}`、`/artifacts/{id}/content` | 产物元数据及授权流式下载 |
| GET `/projects/{id}/snapshot`、`/projects/{id}/events?after=...` | 一致快照和有界增量轮询；SSE 可后加 |

command envelope 必含 schema_version、command_id（客户端生成）、idempotency_key、kind、target、expected_revision、payload。创建新对象时 expected_revision 为 null；修改现有对象必须给相应 control revision，读取不需要。响应含 command_id、status、target、accepted_revision、effective_boundary、result_ref 或结构化 error。

kind 集合：`create_project`、`validate_contract`、`publish_contract`、`apply_contract`、`start_run`、`add_guidance`、`ack_guidance`、`pause_submissions`、`resume_run`、`cancel_trial`、`stop_run`、`finish_run`、`submit_trial`、`retry_trial`、`publish_finding`、`request_replication`。只读契约校验通过统一命令入口不发布新版本。

语义拒绝记录可查询回执：400 格式/未知字段，401/403 身份或权限，404 不存在或不可见对象，409 版本/幂等/状态冲突，422 契约/预算/能力不满足，503 服务不可用。异步受理为 202；同步完成及重复已完成命令为 200，创建回执不代表后台完成。格式或认证失败可以没有持久回执；带幂等请求超时后按原 command ID 查询，不能自动换 ID 重试。

分页默认 50、最多 200 条；单个命令负载最多 256 KiB（工程建议默认，可通过 capabilities 公布变更）。产物通过独立流式上传/下载机制处理，首版候选快照由研究工作区的可信快照工具登记，公共 commands 不接收任意宿主路径或大文件 base64。

角色：human 可发布/切换契约和控制运行；researcher 仅在已授权契约下提交实验、候选发现、指导答复与复核请求；supervisor 仅报告执行事实；evaluator 独占验证结果写入。内部接口与公共 kind 分离。初版使用分别配置的服务凭据与课题授权，认证密钥不进入事件及日志。

内部协议至少包含 claim_dispatch（领取执行意图与 lease/epoch）、heartbeat、report_attempt（容器身份、退出事实、manifest hash、用量）、report_validation 和 report_replication。每次写入校验角色、目标归属、当前执行代次与报告幂等键。终态后收到完全一致的旧报告返回原回执，冲突报告保留审计并拒绝，不能复活运行。

事件类型按对象事实发布：contract_published/applied、run_state_changed、command_updated、guidance_updated、attempt_state_changed、artifact_published、validation_recorded、finding_published、replication_completed、budget_updated。事件只携带摘要、对象修订和引用，不携带完整实验数据或模型秘密。详情始终能通过授权查询重建。

### 8.3 命令负载与回执样例

以下字段是各 kind 的最低负载，未声明的字段拒绝。引用必须验证存在性、权限、所属课题和不可变修订；ID/hash 不能仅由模型口头保证。公共 envelope 的 target 表示被修改对象，payload 中的关联对象不改变其版本。

| kind | payload 必需内容 |
|---|---|
| create_project | title、objective；新课题 target 为 `{type: project, id: null}` |
| validate_contract | draft、template_ref；只返回错误/有效配置，不发布 |
| publish_contract | draft、template_ref；已有契约附 base_revision，创建契约附 project_id |
| apply_contract | contract_id、contract_revision、effective_boundary=`future_submissions` |
| start_run | project_id、contract_id、contract_revision；新运行 target ID 为 null |
| add_guidance | text、scope_refs、effective_boundary（next_decision/future_submissions） |
| ack_guidance | guidance_id、disposition（delivered/adopted/deferred/declined）、reason、evidence_refs；研究员只能回执本运行指导 |
| pause_submissions / resume_run / finish_run | reason；恢复时重新检查预算和进程状态 |
| cancel_trial | execution_attempt_id、reason；不能用“最新 attempt”替代明确身份 |
| stop_run | reason；始终取消本运行的活动与排队工作 |
| submit_trial | contract_ref、candidate_ref、input_manifest_ref、parameters、seed、requested_budget |
| retry_trial | source_attempt_id、reason、requested_budget；仍执行同一冻结 trial，重试前按运行当前授权再检查，不能借重试回避新的范围限制 |
| publish_finding | statement、scope、supporting_refs、opposing_refs、limitations；修订时附 base_revision |
| request_replication | finding_ref、kind（replication/generalization）、frozen_strategy_ref、evaluation_ref、requested_budget |

追加指导和发现不会递增运行 control revision；其自身记录独立递增版本。Trial 有独立 control revision 以处理取消/重试竞争。如果新的授权不允许旧 trial 重试，返回范围冲突；用户需显式调整授权或建立符合新契约的 trial。已运行实验是否取消由显式控制决定。

示例仅用于模拟协议，不是实际已受理的操作：

```json
{
  "schema_version": "asr-control/1",
  "command_id": "cmd_example_pause",
  "idempotency_key": "pause-example-1",
  "kind": "pause_submissions",
  "target": {"type": "run", "id": "run_example"},
  "expected_revision": 4,
  "payload": {"reason": "检查高负荷失败案例"}
}
```

```json
{
  "schema_version": "asr-control/1",
  "command_id": "cmd_example_pause",
  "status": "applied",
  "target": {"type": "run", "id": "run_example"},
  "accepted_revision": 5,
  "effective_boundary": "admission_and_dispatch",
  "result_ref": {"research_run_id": "run_example", "control_revision": 5},
  "result": {"admission": "paused", "in_flight_attempts": 1},
  "error": null
}
```

错误对象含 code、message、field_errors、current_revision、retryable；非冲突可将 current_revision 置 null。能力目录公布受支持的 action 和 profile，不支持的正式评价或执行类型返回 capability_unavailable，不能用 mock 结果代替。

## 9 验收与实施映射

| 验收编号 | 可观察条件 | 所属交付 |
|---|---|---|
| A1 | 缺项/未知字段/越权契约被拒绝；发布与运行切换分离；旧 trial 不变 | P1/P2 契约 |
| A2 | 并发重复请求只产生一个试验；同键异负载冲突；预算预留不超额 | P1 受理 |
| A3 | 真实 IEEE-118 基线及故意错误结果独立核验，保留原输入 | P1 数值 |
| A4 | 原子发布前后各注入中断，可恢复；损坏产物不能用于验证 | P1/P3 证据 |
| A5 | AAR 实际模型自主提出并执行至少一个试验，提交证据关联发现 | P2 自主研究 |
| A6 | 活动会话中指导可受理；暂停阻止新提交/派发；在途状态真实 | P2 控制 |
| A7 | 取消/完成竞争、过期控制、失联旧进程与新 epoch 不产生重复执行权 | P2/P3 恢复 |
| A8 | 候选无权修改输入/评价器或读取正式评价资产；作者不能自证通过 | P3 隔离 |
| A9 | 独立环境重跑冻结材料，分别报告执行、数值一致性及结论支持 | P3 复核 |
| A10 | Capstone 刷新/失联/重复事件后恢复同一运行；mock 与真实证据明确 | Capstone C1–C4 与 P2/P3 |
| A12 | 假说修订不可覆盖；旧 trial 绑定不变；跨课题引用拒绝；会话替换仍保留支持/反对证据 | P3 假说演进 |
| A13 | 执行完成但数值无效、无效实验、证据不足及负面结果分别保留；科学失败不触发基础设施重试 | P3 科研语义 |
| A14 | 模型/计算分账；并发跨账本预留不超额；失败不退已消耗；额度未知仍受本地门控且不触发 API 回退 | P3 预算 |
| A11 | 正式同预算比较包含失败分母、交叉对照、数据隔离和成本口径 | P4 科学成果 |

先完成 P1 数值及证据，随后 P2 契约/API/AAR/控制，P3 隔离与恢复故障验收，最后 P4 正式比较。关键契约和控制模型可提前用模拟对象验证；不得以模拟完成替代 A3/A5/A9。每一切片的依赖版本、可执行命令和测量证据在实施计划与日志中记录。

## 10 设计完成度与后续对齐

本版已给出最小闭环的组件、状态、身份、契约、执行协议、预算、恢复、科学验证、AAR 改造及接口候选。P1 本机数值与证据代码及测试已交付；P2 参考 profile 的控制协议、预算、AAR 接入及真实订阅闭环已验收。D016 假说/评价生命周期与双账本完整实现、独立评价隔离仍属 P3。

仍需外部反馈的项目只有：Capstone 对接口/对象映射的反馈；真实基线对科学参数的校准；用户实际运行的资源额度与业务成功标准。这些有明确的责任方和启动门槛，不妨碍无费用的工程设计与本地接口准备，但会阻止相应真实执行或正式成果验收。

新技术选择是本轮的实现设计，不冒充已运行验证或用户逐项确认。实施反馈如改变职责或研究边界，先更新主设计；仅修正字段/错误码等细节时同步本文件、Schema、Capstone 交接和契约样例。


### Runtime and capability alignment

已确认可替换、订阅优先研究员运行时，以 pi/Codex 为默认；omp+AAR 工具基座与独立电网科学工具包按版本装配。当前原生文件工具和科研 skill 有路径边界与 hash 校验，任意 shell/候选代码执行仍需 OS 隔离能力验收。具体支持状态见 [研究员运行时](RESEARCHER-RUNTIMES.md)，不能以工具清单代替数值或隔离验证。

### Native runtime protocol adapters (D019/D020)

Codex App Server and Grok ACP retain distinct wire protocols behind ASR lifecycle semantics. Role requirements and capability negotiation precede launch. Persist ASR run/session/epoch separately from native thread/session/turn IDs; preserve raw typed events as well as normalized projections. A prompt receipt, completed turn, cancellation receipt and verified execution exit are separate facts. Reconcile ambiguous in-flight work before retry or reservation release. The protocol foundation does not itself implement ASR tool permits or prove candidate/evaluator isolation. See RESEARCHER-RUNTIMES.md for staged acceptance.

### 已验证的独立材料复核切片

`asr_evaluation.Replay` 只接受固定 case118 原始 JSON hash、固定 validator hash
和 1e-7 阈值的 terminal managed evidence。逐文件校验后只读复制数据和可信代码，
独立输出目录；启动和恢复发布前核对真实 Docker inspect。只读/无网络/非 root
探针、负例、超时及中断发布恢复已有真实 Docker 测试。最终摘要必须由已冻结
job/request/output/exit/outcome 派生一致，不能单改摘要将负结果标为成功。

实际 AAR trajectory05 的冻结解已重算：原输入保持，残差0.8253756289466181，
方程无效，9处无功越限、186热限额未评估。通过真实 evaluator HTTP POST/GET
追加到原数据库，幂等和服务重开已验证；不修改旧试验与候选发现。完整记录见
ISOLATED-EVALUATION.json 和 P3-ACTUAL05-VALIDATION.json。

这是材料复核而非候选代码重跑；研究设计、假说、复现与泛化判定仍未评估。
Standalone 执行尚未接入 Control 预算预留/结算；报告发布不追补历史执行成本，
也不把服务的 isolation_verified_by_service 改成 true。完整 P3 仍需候选代码
隔离、评价执行准入与实际模型驱动的新科研轨迹。


## P3 verified boundary and next package (2026-11-03)

A8/A9/A12–A14 have bounded acceptance in [P3 system acceptance](../validation/P3-SYSTEM-ACCEPTANCE.md): explicit octave-candidate/1 source registration and restricted execution, fresh method replication, Control-owned evaluator jobs and typed artifacts, immutable hypotheses, distinct scientific axes and two resource ledgers. Authentication failure, interruption, timeout and original budget overrun remain retained. Explicit finite read-only closeout and lifecycle projection receipts complete the run without changing scientific evidence.

D021 forbids subscription runtime *_API_KEY settings except the explicitly permitted non-Codex pi case (which grants no billing authority). D022 requires purposeful limits, adequate defaults, detailed exceedance receipts and recoverable research. [Limit audit](../validation/LIMITS-AUDIT.md) records implemented boundaries and limitations, including legacy direct-debug diagnostics and non-hard-total DNS timeouts.

The single researcher is the Research Lead prototype: AAR owns its outer scientific loop and runtime owns inner reasoning/tools. Organizer/Lead/Worker deployment remains P5. P4 now plans formal comparison and held-out evaluation; P3's fixed-case replication is not a substitute. No new P4 model/experiment allowance follows from P3 closeout.

The `ood-study-development/1` capability now admits analysis, label and fit jobs
through the same `asr_dispatch` table, budget reservations and fenced Supervisor.
Frozen payload hashes, dependencies and hypothesis revisions bind each job. An
additional compute dimension, `sample_proposals`, charges all admitted proposals
conservatively once execution starts; unstarted cancellation releases them.
Private test material is absent from this profile. Analysis outputs remain author
claims and cannot satisfy fixed-trainer label dependencies. Probe and training
roles cannot be reassigned by resubmitting the same coordinates. A real batch of
64 labels and fixed-trainer reproduction are engineering acceptance evidence,
not a model-driven P4 result. Final-test release and continuation of the actual
intake run still require their integration and a recorded successor contract.
