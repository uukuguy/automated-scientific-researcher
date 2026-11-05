# Limit and recovery audit

Status: reviewed for the current managed P3 and P4 profiles, 2026-11-03. Required by the user and AGENTS.md. Confirmed material gaps are corrected and verified; explicit legacy and observability limits remain listed below.

Every inventory row records scope/unit, purpose, default adequacy, exceedance
record/action, recovery and evidence. Acceptance budgets are not production
research recommendations. A forced stop of an unsafe/unresponsive owned process
must preserve the research and its evidence. Unknown execution must stay reserved.

## Verified findings and corrections

- The original P3 acceptance budget of 180 seconds was enough for the scientific
  chain but insufficient for graceful final response/cleanup. The 37ms overshoot
  remains in the original ledger and report. It is not a recommended operational
  research default. A separate recorded closeout revision completed successfully.
- A queued numerical attempt could start after an earlier overrun created debt.
  Commit 58a288b now reuses Control's gate both before claim and before start;
  tests cover both paths. Consumed costs and reservations remain unchanged.
- Runtime recovery may clear a gate while evaluator execution is still unknown.
  Reproduction confirmed and fixed in 4aa7db7 with a shared cross-component recovery check.

## Inventory

The inventory below was checked against source, boundary tests and actual managed execution evidence. Adequacy statements apply to the stated workload and scope.

| Scope / setting | Value and purpose | Default adequacy / handling |
|---|---|---|
| Project model ledger | Explicit research_walltime_ms, turns, tool_executions | No infinite fallback or operational research default; reserve before use, retain consumption. Original 180s/20/32 was an acceptance choice and inadequate for clean closeout. |
| Project compute ledger | Explicit attempts, execution_ms, evaluation_attempts, evaluation_ms | Separate units and reservations. Failed/unknown work is not refunded speculatively. |
| Budget integer representation | Nonnegative integers up to 2^63−1 | Storage-domain guard, not a recommended resource allowance. |
| Numerical/evaluator concurrency | One owned execution per run | Single-researcher P3 calibration; queued work must recheck gate before start. Scale changes require policy and acceptance. |
| Execution lease | 30s default, bounded at 3600s | Ownership/fencing interval, not an execution allowance or retry trigger. Expiry never releases uncertain work. |
| Candidate method revisions | Optional explicit 1..1000 per run | Counts distinct admitted frozen references, including failures. Unused artifact registration does not consume or bypass execution rights. |
| Candidate/evaluation timeout | Requested finite ms; profile max 60s; applicable contract may be narrower | Bounds runaway case118 execution, not all future scientific workloads. Reject incompatible request rather than rewrite frozen experiment. |
| Candidate source | 64KiB UTF-8 single candidate.m | Adequate for bounded P3 method/configuration; larger/multifile methods need a separately admitted profile. |
| Candidate process isolation | CPU1, memory/swap1GiB, PIDs64, /tmp128MiB | Fixed case118 profile. Actual network, write and scratch probes exercised. Captured configuration/exit evidence distinguishes confirmed OOMKilled from unknown internal resource denial. |
| Candidate captured output | 1MiB combined stream | Prevent host-memory/disk flood. External collector stops owned execution; structured configured/observed-at-least byte diagnostics preserve the task and attempt. |
| Independent evaluator isolation | CPU1, memory/swap256MiB, PIDs32, /tmp16MiB | Trusted fixed numerical checker, separately mounted materials. Not a general researcher environment. |
| Evaluator material inventory | 4MiB per material, 16MiB total, 100 artifacts; trusted code cap64KiB | Reject oversized/unexpected material before evaluation; preserve source and explicit failure. Typed size/count diagnostics retain material and the explicit reason. |
| Reference CLI, separate debug interface | 120s default, max3600s; iterations20 default, allowed0..1000 | Historical standalone runner, not P3 managed candidate policy. Iteration termination is a solver outcome, not proof of infeasibility. |
| Reference cleanup / inspect | 20s / 10s | Attempts process cleanup and exit proof; unknown outcome remains unresolved. These are not whole-operation deadlines. |
| Raw evidence publication | 100MiB | Host publication bound, not a live disk quota. Current trusted reference output is small; untrusted candidate uses stronger live capture bound. |
| Numerical tolerance and power limits | Frozen evaluator tolerance1e-7 pu and original grid constraints | Scientific rules, not execution budget knobs. Never relax them to turn a failed method into success. |

| Runtime engine deadline | Explicit per-session allowance minus min(5s, 25%) cleanup reserve | Counts setup/version checks against the claim-derived deadline. Headroom covers cooperative abort, group exit, reader drain and bridge shutdown; actual overrun remains charged, never hidden. |
| Native abort escalation | 1500ms default, configurable up to 3s | A short local flush/abort grace within cleanup reserve, not a research budget. Escalation is recorded, and local exit does not prove remote provider work stopped. |
| Pi RPC transport | 4MiB/record, 16MiB queued bytes, 256 queued records, 100000 total records | Configurable transport protection, ample for this bounded trace; not model context or scientific output quality limits. Overflow yields a structured limit observation and recoverable pause. |
| ASR tool transport | 10s ordinary, 40s scientific call, each bounded by remaining engine time | Bounds waiting, not proof of service cancellation. Accepted request key and uncertain outcome survive; read authoritative state before retry. |
| Context7 | Default8 calls/client (configurable1..100), name120/query2000/ID256 characters, response100000 bytes, socket10s | Bounded documentation slice, not a deep-research allowance. Reports remaining calls, actual/lower-bound size and correction/recovery. No automatic client reset or retry. |
| Crossref metadata | Query512 chars, 1..5 results, response256KiB, title512 chars, 20 authors, name256/given-family128 chars, DOI256 chars; socket5s | Explicit small metadata search. Every omitted/truncated field is labelled; oversized/invalid DOI is omitted rather than changed into another identifier. Not full-text research. |
| Network timeout scope | Socket timeouts and checks between reads | DNS and a single blocking read may exceed nominal client time. Outer runtime observes transport timeout separately; no claim of a hard total network deadline. |
| Codex App Server transport | 30s connection / 5s request defaults; 1MiB/line, 8MiB buffered, 256 queued events, 4096 messages, 32 pending requests | Protocol diagnostic defaults; configurable. Overflow raises with limit details and close receipt; queued prefix stays readable. Raw stderr intentionally discarded for credential safety, byte count retained. |
| Grok diagnostic | 45s total / 42s engine, 8s stages / 30s prompt, 1MiB line, 4096 frames, 4KiB captured reply, 500-char preview | One-prompt connection check, not a research runtime default. Capture overflow and preview omission are explicit; no silent truncation or inferred successful task completion. |

## Verification evidence

- 291 tests in the combined optional-AAR suite; 15 explicit Docker opt-ins skipped.
- 59 combined real Docker checks passed: `ASR_REAL_DOCKER=1 uv run python -m unittest tests.test_execution_limits tests.test_candidate_execution tests.test_evaluation_replay tests.test_managed_evaluation tests.test_supervisor_evaluation tests.test_supervisor -v`.
- Cap, credential and projection regressions include `test_control_limits`, `test_runtime_deadline`, `test_subscription_environment`, `test_p3_finalize`, native protocol, Context7/Crossref and actual upstream ORM tests.
- Fixes are in 58a288b, 4aa7db7, c3ff486, ffa207a, 68f48c2, ddb0509 and ae2d808; source history preserves red/green review findings.
- Actual [P3 reports](P3-SYSTEM-ACCEPTANCE.md) retain the first authentication failure and timeout; a separate read-only 30s closeout settled without forced termination. All original reports and scientific counts remained unchanged, with zero final reservations/debt.
- Independent root checks reverified both original evaluator artifacts after the diagnostic changes. Evaluation tolerance and numerical source pins were not changed.


## Scope and limits of the audit

- Quota remaining at a subscription provider is unknown unless a sourced
  observation exists; finite local budgets are not a claim about provider quotas.
- P3 resource defaults apply to the frozen case118 calibration workload only.
  They are not defaults for arbitrary models, multi-file solvers, large networks,
  GPUs or long-running research. Larger workloads need explicit policy/profile
  changes and evidence, not silent cap increases.
- OS enforcement can prove configured memory/PID/tmpfs restrictions. Docker's
  OOMKilled field can prove an OOM termination. An untrusted candidate may handle
  a PID or scratch-allocation failure internally; a host observer cannot infer
  that event merely from a generic failure. Preserve stream/exit facts and report
  the cause as unknown instead of inventing measured resource usage.
- The historical direct `python -m powerflow_lab.reference` debug entry point
  retains a generic EvidenceError for its post-execution publication cap. Pending
  raw files and identity remain available, but it does not emit the new detailed
  diagnostic schema. It is not the arbitrary-candidate or managed research path.
  Its pinned numerical sources remain unchanged to preserve prior provenance.
  The managed Supervisor wrapper supplies detailed publication-cap diagnostics.
- A Docker metadata CLI timeout does not establish container exit. The owned CLI
  group is cleaned up; the admitted container intent and reservation remain until
  separately reconciled. No lease or subprocess timeout grants retry permission.
- Native Codex App Server/Grok smoke transport limits are diagnostic connection
  limits. Those adapters have not become full AAR research executors; they must
  not be presented as long-research defaults or complete task recovery support.

## P4 simulated-client preparation and intake (2026-11-03)

- Client preparation: fixed320 proposals (128/32/32 public,64/64 private), not an
  open-ended rejection sampler. Every failure counts and is retained. Between-
  sample600s per-invocation deadline pauses resumably; this is not a hard timeout
  on an individual trusted numerical solve. The pinned reference has20iterations.
  This trusted development CLI is not an ASR experiment admission service.
- Intake model ledger:300s total,40turns,100tools, zero numerical allowance. Purpose
  is one actual project reading/diagnosis session, not long research. Failure cost
  retained; same-run recovery used remaining278514ms. Final total216397ms and no
  unresolved reservations. No cap was raised or provider/billing mode changed.
- Actual pi read refused compact data lines above50KB. Researcher reported the
  limitation explicitly; no data were silently treated as read. Lossless public
  JSONL pages now cap each page at40000bytes, below that observed boundary. A row
  above the page cap is rejected with an explicit remedy; no field truncation.
  Source hashes/row counts preserved; final/private data excluded.
- Data-domain multipliers[0.7,1.6] and utility thresholds are explicit simulated
  client task rules, not numerical stability guarantees or global ASR defaults.

## P4 development worker profile (2026-11-03)

These caps authorize no model run. The actual intake contract still has zero
compute allowance. New jobs require a separately admitted successor contract.

| Limit | Purpose and sufficiency | Exceedance and recovery |
|---|---|---|
| 64 proposals per label batch | Bound raw evidence, solve latency and cancellation loss; real full-batch test passes within 60s | Structured admission block before any solve; retain task and continue with smaller requests |
| 300s maximum worker walltime, further reduced by contract | Stop stalled author code/solver; tested at 60s for 64 labels and 1s for timeout | Stop owned container, retain stream/events, publish timeout receipt and actual elapsed cost; no automatic retry |
| 64KiB analysis source, 12 input trial references | Bound request size/dependency fan-in; sufficient for one generator and baseline plus nine fits plus two probe batches | Detailed deferred-request receipt; source and original trials retained, research remains active |
| 16MiB frozen input and 16MiB combined stdout/stderr | Bound trusted collector memory and evidence size; 64 raw labels fit comfortably | Input admission block or externally stopped output overflow; retain bounded raw prefix and diagnostic, never report success |
| 1GiB RAM, one CPU, 64 PIDs, 128MiB temporary storage | Offline single-worker resource isolation; actual labeling/fitting/analysis pass | Docker resource limits remain enforced; OOM flag becomes explicit diagnostic. PID/temp exhaustion surfaces process/worker error, not an inferred scientific failure |
| `sample_proposals` ledger | Prevent a batched job from hiding dozens of solve permissions behind one attempt | Reserve whole batch before dispatch; charge whole admitted count conservatively after launch even on timeout; retain completed/failed rows separately. Unstarted cancellation releases all |
| 335s bridge transport wait for study jobs | Accommodate up to 300s execution plus launch/publication, bounded further by runtime deadline | Existing runtime timeout observation and native recovery apply; retry same key only after reading state, never duplicate admitted work |
| 40,000-byte inline result threshold | Keep routine model responses readable without dropping full author output | Larger output is exported completely to a workspace file and can be consumed by later analysis dependency; native single-line limits may still require analysis-based extraction for a very long scalar |
| 600s image build CLI timeout | Bound developer build wait; measured locked dependency build succeeds | Retain context/log/failure record; timeout does not prove Docker daemon build ended. Reconcile before a new invocation |

Limits combine: 12 dependencies do not guarantee that their raw rows fit within
16MiB. A large combined analysis must request fewer inputs or a reviewed profile
revision. Conservative proposal charges are permits, not a claim that every
reserved solve completed. Actual attempts and partial raw events remain distinct.

### Actual P4 recovery findings

The first development continuation hit the native256-record pending queue after
1,971 consumed events, despite only about1MiB of recorded traffic. This was a
producer/consumer burst, not exhausted research budget. The adapter now applies
bounded backpressure within the existing256-record/16MiB capacities, records peak
occupancy/wait counts, and polls only authenticated run state instead of loading
all trial evidence for every token delta. A full-queue EOF is delivered rather
than silently lost. Individual oversize records, total event count and walltime
still produce explicit limit receipts. Regression tests cover burst preservation,
EOF and hard caps. The actual recovery completed all704 requested labels and nine
augmentation fits without another transport-cap event; original failure cost is
retained.

A subsequent22-input analysis exceeded the12-reference request cap. The previous
policy paused the whole run, closing its next provider permit. This was too broad:
request-shape limits now record `action=request_deferred` without closing research
admission, so the researcher can split the analysis. Project budget exhaustion
still pauses with a receipt. No numerical allowance, queue capacity or dependency
cap was raised, and no accepted label/training job was rerun during recovery.

Independent final scoring allows at most10 fitted-model references and one frozen
protocol. Raw payload retains the16MiB cap; final execution is at most60seconds
within remaining compute balance. A distinct controller-only capability locks
all subsequent study submissions, even if an old development contract is reapplied.
Failed final execution can only retry its identical frozen protocol after exit is
reconciled; completed release cannot be repeated with new models. Synthesis exposes
no experiment tools and caps its session at180seconds/25turns/50tools, bounded by
remaining historical balances rather than a new model allowance.


### P4 context and final reporting limits

The first final synthesis received explicit provider context-window exhaustion,
after accumulated development history; this is not a compute failure. Its7,525ms
charge and transcript remain. Existing per-response40KB projection limits do not
bound accumulated conversation size. No automatic context-rotation guarantee is
made. The original native sessions directory was archived intact with an explicit
recovery receipt, then a fresh conversation recovered from frozen proposal,
aggregate final report, training replay and authoritative state under the SAME
research identity and remaining107,680ms. No model or experiment budget increased. After completion, archived transcripts were also restored to their original paths so historical evidence references continue to resolve.

The recovered session wrote and read back the complete report, then hit its
102,485ms engine cap (102,487ms observed; cleanup headroom retained). Final ledger
is1,495,509/1,500,000ms,79/140turns,107/300tools, with all reservations zero.
The controller verified the successful write-event bytes, archived that exact
report and explicitly published its conclusion as controller archival. This is
not a clean model termination or agent-issued publication. Science was preserved;
the report's lifecycle limitation is public.4,491ms remained and was not used for
another unlikely-to-complete model call. The bounded25-minute allowance was
sufficient for this science result, but insufficient for fully autonomous report
publication with these recoveries; it is not a production default. Future long
runs need measured context monitoring and an explicit publication/cleanup reserve,
not silent retries, truncation, allowance increases or paid fallback.

### P5 organization record limits (foundation only)

- Human-published `policy/capacity` sets positive max_active_leads and
  max_active_workers. There is no implicit default/compute grant. The suggested
  initial2/2 is a small organization experiment, not proven production capacity.
  Count distinct owners of active directions and worker assignees of in-progress
  tasks; limits constrain these declarations, not unimplemented runtime launch.
  Same-transaction checks prevent simultaneous requests exceeding capacity.
- A member cannot hold two in-progress tasks. This prevents ambiguous execution
  ownership in the first serial-per-member model; contention returns
  member_already_working. Ownership/revision conflicts retain original work.
- Each document is at most65,536 UTF-8 JSON bytes: enough for an assignment,
  explanation and evidence identities, not bulk code/data. Oversize requests
  create an organization_request_deferred event with requested/limit, record/key,
  content hash and artifact-based recovery; nothing is silently truncated.
- History pages default100, maximum500 records, bounding database/response work.
  At the document cap a maximum page can still approach32MiB plus envelopes; this
  is not a recommended model-context size. Callers may choose smaller pages.
  next_after/has_more explicitly expose remaining records. Overlarge page requests
  record a recoverable rejection and leave all history intact.
- No new timing/retry limit or model budget is introduced. Existing transport and
  runtime limits still apply. Actual long-session context behavior remains a P5
  runtime-binding concern; paginated records alone do not solve context exhaustion.

Tests cover concurrent direction activation, duplicate task claims, capacity
rejection/restart, document and page boundaries, role spoofing, terminal history,
HTTP authentication and explicit bridge capability gates. No actual multi-role
model execution is claimed by these checks.

Organization role binding preserves the existing single-active-runtime-per-run
limit. First role integration is serial: active-direction/worker declarations are
not evidence of model concurrency. A new role claim cannot escape an unresolved
prior process or obtain a new budget ledger. Failed setup costs remain charged
when a different member subsequently reserves time. No new session timeout or
automatic retry is added; old membership revisions and tool profiles are rejected
before admission. Parallel model execution needs a separate reviewed integration.

### P5 paired research adapter (2026-11-04)

The optional paired-acquisition/1 adapter keeps the team's64-slot arm and
1101–1108 seed set as explicit scientific-protocol constraints. These are not
new default ASR capacity limits. Its fixed original128 and IEEE118 checks bind
the proposed training comparison; other methods remain possible without this
project-specific adapter. Violations reject preparation before execution and do
not resize, truncate or resample. Ordinary study batch/payload/budget limits
continue to use their existing detailed diagnostics and owning ledger.

No new runtime timeout or automatic execution retry was introduced. Failed
processes keep their consumption; blocked verification records code/message and
recovery in the same Control event history and state projection. Replaying the
original request only retries verification of completed evidence. Artifacts stay
outside model output; state returns hashes/counts/diagnostics. Full raw evidence
and immutable adapter JSON remain in the authoritative local stores.


## Completion-first subscription correction (2026-11-04, D029)

Actual implementation001 disproved adequacy of the old20-minute aggregate and
four-minute role windows: a reviewer delivered computation but timed out during
reporting, and Organizer had only38.515seconds after normal review/handoff.
Organization direction closed, but report refresh and four deliveries remained.
These are operational interruptions, not scientific failures. User explicitly
requested complete execution rather than strict controls except clear anomalies.

| Setting | Old → current | Purpose and evidence |
| --- | --- | --- |
| Aggregate model walltime | 20min → 4h | Broad unattended-run failsafe; not an expected duration. Stop on complete delivery. |
| Role model walltime | 4min → 30min | Allows inspection, reasoning, tool work and report publication in one session. |
| Aggregate turns/tools | 160/320 → 1600/3200 | Generous runaway-volume ceiling; counts alone do not establish no progress. |
| Role turns/tools | 40/80 → 200/400 | Allows substantial coding/review; detailed runtime records remain. |
| Analysis compute | 12 attempts,60s/job,720s total | Unchanged case-specific verification allowance; actual2jobs/3.407s, no exhaustion. |
| Labels/fits | zero labels; contract analysis-only | Scientific scope, not runtime economy; model extension cannot change it. |
| Capacity | two Lead/two Worker slots,serial execution | Unchanged ownership/concurrency boundary. |

Policy: integrations/runtimes/organization-implementation-limits.json.
Explicit revision: integrations.runtimes.organization_resources publishes and
applies a new Control contract only while paused, healthy, exited and unreserved.
Old policy/contract/balances and reason persist before change; interrupted receipt
publication replays the original API commands. Budget consumed does not reset.
Compute, capacity, billing, source and evaluation scope cannot change through
this model-only path. Recovery is explicit, never automatically granted.
Exact original source bytes are required when local JSON was reformatted.

Emergency ceilings still pause and reconcile; no claim of adaptive/progress-aware
anomaly detection is made. Genuine no-progress/repetition detection and proactive
durable handoff before emergency deadlines remain implementation work. Existing
unknown-process fencing, isolation/resource limits, provider failures and raw
failure retention continue. Default adequacy beyond this observed workload still
requires real evidence, not just larger numbers.


## Project-directed run policy (D030)

organization-project-limits.json declares4h aggregate/30min role model failsafes,
1600/3200 total turns/tools and200/400 per session;256 scientific tasks,4096
label slots and7200000ms cumulative local compute. Per-job60s is the observed
small case118 batch envelope, not a universal researcher deadline. Counts are
capacity, not a mandated experiment schedule. Existing Control reserves and
retains all failed consumption; profile payload/batch restrictions still apply.
The project brief reads current state instead of repeating stale20min/4min values.
No paid fallback, automatic retry or hidden-evaluation grant. User continuation
under D030 authorizes the configured new project run, not old-budget reopening.


## Communication retention (D031)

The organization event writer adds sequence and UTC collection time, writes the
complete event payload and flushes/fsyncs every event. It adds no truncation or
retention-size cap. Existing native transport ceilings still apply and preserve
explicit limit/recovery records. An I/O failure propagates; it cannot silently
turn into a successful archived session. The archive retains explicit incomplete
JSONL/session/source gaps. Export failure is reported in the run receipt and
requires archival recovery only, never a repeat of scientific computation.

Archives are distinct non-overwriting checkpoints, with source hashes and an
inventory. The current exporter reads each source into memory; it has no tested
unbounded-size guarantee or automatic retention/deletion policy. Original native
journals remain in the restricted run directory; raw provider stderr was already
omitted for credential protection and cannot be reconstructed retrospectively.

## Workspace snapshot correction (observed during project001)

The old1MiB ceiling rejected the actual2,281,626-byte utility synthesis, and its
plain snapshot_too_large error omitted size/purpose/recovery details. This was an
inadequate general sharing default. The new16MiB ceiling bounds in-memory snapshot
publication and copies to role workspaces while allowing observed model/report
bundles. It is not a scientific computation allowance or a retention limit.
41–62MB raw analysis evidence remains in the immutable experiment store; use exact
references or an explicit external export instead of repeating computation.

Oversize requests now include limit, observed-at-least requested size, source
relative path, purpose and recovery instructions. Control records a recoverable
request_deferred event without pausing the run or changing its budget. Originals
remain untouched. Two tests reproduce the prior2.3MiB rejection and verify detailed
oversize recording/preservation. An actual byte-identical2,281,626-byte export is
at artifacts/p5-snapshot-capacity-001, snapshot6eaa428654e3b2de9a03635b8ef3a27f79c8ae970085fea052b6816e4629c001.
This external capacity check was not injected into the live team; its process
loaded the old ceiling, whose actual failures remain in the research record.

## 2026-11-04：订阅连接的上游超时

本次真实研究遇到 pi 上游 WebSocket 的 300 秒空闲超时。这是连接层限制，不是 ASR 的研究总时长或单角色额度；不能靠提高研究预算解决。ASR 私有 pi 设置改为支持的 SSE 连接，原订阅和累计额度保持不变。SSE 仍可能断线，已保留一次 `terminated` 失败，因此没有把改连接方式当成可靠性验收完成。每次恢复先核查全部旧进程退出、预算预留为零及已完成任务；不重新训练已完成的任务、不抹除消耗、不自动登录或计费回退。

### 模型上下文容量

P5 的第028次角色会话被提供方明确拒绝：输入超过模型上下文容量。此限制独立于研究时长，不能增加预算解决。新增显式的指定角色会话换代恢复：旧日志原路径保留，新目录承接对话；同一研究、权限、材料和累计预算继续。恢复名单与原因写入不可覆盖的恢复记录，归档保留各代日志。仍未实现自动容量预警或自动压缩，不能宣称无人工介入的上下文恢复已完成。

## 研究笔记原文分页上限

source_read默认8000、最多16000个Unicode字符/页，用于约束单次工具返回和上下文重新增长；不是原件大小、研究工作量或总检索额度。按UTF-8最坏每字符4字节，正文最多64000字节，仍须服从既有工具传输限制。原件不截断，offset/next_offset/has_more/partial明确；越限记录实际参数、上限、目的及恢复方式，不暂停研究或自动重复实验。每页重新验证文件及笔记绑定，源文件本身仍受既有发布/快照政策约束。

## 摘要订阅工程试验额度

summary-validation-limits.json显式设置总30分钟、单会话10分钟、总100轮/100工具、单会话20轮/20工具。输入内联，实际6轮/0工具，保留首轮格式拒绝，模型累计108652ms。时限用于处理无响应或异常循环，不是科研结论门槛；不自动重试或增加预算。原件字节准备/复核容量分别由调用方给定，超出则保留材料并返回deferred。

只读finalization profile现允许新建零attempt/零execution_ms的验证契约，模型会话仍按原Control预留和结算；已有研究预算不改变。独立工程试验没有数值调度工具。恢复前核查全部旧进程与预留；收尾命令按控制版本取唯一键，避免恢复后幂等冲突。

## 上下文容量预留

capacity.decide没有生产默认窗口或硬编码百分比；调用方必须提供回复/工具结果/检查点token预留及测量来源。未知/估算不能当作精确准入，上次usage与目录窗口不是下一请求完整用量。容量风险给出检查点/恢复建议，保护在途实验，不自动取消任务或扩大额度。当前尚未接Runtime拦截，不能宣称已避免真实超限。

## 原生日志只读解析

pi_context.observe要求调用方显式提供max_journal_bytes；本次离线演练128MiB，仅保护解析器内存，不截断或限制历史保存。超出返回deferred及实际至少大小、目的与恢复说明。只读SDK辅助进程30秒检测卡住，TimeoutExpired保留配置时限及恢复方式，不修改日志或取消实验。生产默认预算尚未选择。

会话来源登记要求宿主显式给定max_journal_bytes和keep_recent_groups，服务不偷偷选择或提高容量。SDK只读辅助进程维持30秒超时；超限登记为deferred并保存原因、限制与恢复建议。登记与准入重读目前在Control事务内执行，最坏会占用写锁至辅助进程超时；当前为宿主离线流程，接自动安装前需评估读取频率与锁竞争。pi请求前的游标采集失败仅生成deferred事件，不触发实验终止或模型重试。

游标绑定沿用运行原预算和epoch，不新增模型/科研额度。每次模型请求的游标回执只做本机身份与路径元数据核验，不启动SDK辅助进程；完整文件投影仅在宿主显式登记/准备/准入时重读。核验失效生成deferred并保留事件及运行回执，不取消实验、不自动重试或重新登录。异步收据无时间窗口默许，不将“刚收到”当作会话锁。

同步压缩握手上限：ASR_CONTEXT_BOUNDARY_TIMEOUT_MS由宿主明确设置30000ms，目的为防止本机Control请求挂起。压缩算法或模型摘要生成不在该握手中运行。取消、超时或失败均返回cancel:true，保留原上下文，不采用pi内置摘要、不主动终止科研实验。记录limit_ms/elapsed_ms、原因、恢复说明；现有研究运行总时限仍有效，不因压缩握手扩大预算。测试显式设15ms检验超时，生产宿主值仍为30秒。

安装闭环新增限制核查：

- compact_before_prompt缺省false；只有宿主明确指定才在下一请求前发原生compact。此时设置keepRecentTokens=1只是让SDK准备器对短工程会话也触发自定义钩子，实际切点与全部保护项由ASR覆盖计划决定，绝不是只保留1个token；自动压缩仍关闭。没有合法票据就取消压缩，不能产生内置摘要调用。
- 安装票据绑定成员、epoch/owner、进程出生信息和当前回调，限一次使用；写入后失败记录native_write_observed并阻止下一模型请求，状态为context_recovery_required，保留任务与已接纳实验，不把它们取消或重新执行。原生compact成功响应不足以解除保护。
- conversation_read缺省8000、上限16000个Unicode字符，限制单次工具结果大小；返回完整来源哈希、partial、has_more和next_offset，不偷偷截断。仅本人已登记可见记录可读，原件不可用也能读取冻结历史视图，不升级现行权限。
- 本次摘要材料上限524288、复核1048576个序列化字节，超出返回deferred，不当作模型token安全证明。来源解析仍显式128MiB，流式UTF8修复防止合法中文跨块变为替换字符。已使用固定解码器复核三次成功安装的来源，全部与冻结消息一致；被拒绝的004确实不一致。
- 本轮延用原1800000ms/100轮/100工具工程预算，未增额；累计395231ms、21轮、1工具，预留为零。每会话最多600秒/20轮/20工具仍是明确故障保护，真实接续与回查已在该预算内完成。未设置*_API_KEY，也未付费回退或自动重新登录。


## 统一容量策略首批迁移（2026-11-05）

`configs/capacity-policy.json`为统一登记入口，每项含value/unit/scope/purpose/adequacy/recovery；显式宿主配置通过`load_policy(path)`校验并生成SHA256，不接受缺项、错误单位、布尔值或无记录回退。PiRuntime通过capacity_policy_path加载，默认传输容量来自该策略；运行回执同时保留完整策略与实际protocol_caps。sdk_projection支持capacity_policy_path。摘要/复核/日志容量目前仅登记，尚未替换所有显式调用参数。

握手由30秒改为120秒，投影辅助进程由30秒改为120秒；约束本机请求挂起及解析进程，不限制研究时长。超时仍返回明确deferred或取消本次压缩并保留原文。120秒是可配置宿主保护值，扩大余量的工程选择，尚无大型长会话实测充分性结论。投影处于Control事务中可能延长占锁，这一缺口仍未关闭，自动接入重型来源核验前须解决。

其余默认值保持既有传输配置：4MiB单记录、16MiB缓冲、256条待处理、十万条单会话记录；日志128MiB，摘要8MiB、复核16MiB为宿主材料容量，不表示模型可接收这些内容。SDKgetContextUsage为估算，不能以之证明完整下一请求安全。全仓库其它容量和超限路径尚未全部迁移；不宣称已满足统一管理总体验收。


### 异步交流记录实施进展（2026-11-05）

组织运行与摘要/安装验收入口已使用AsyncEventRecorder：生产端冻结事件JSON、采集顺序与时间后入队，单个后台线程按序写入；运行中不逐条flush/fsync，收尾排空后核对持久化。events.recording.json先标记recording，收尾记录complete或incomplete、数量、具体失败序号/哈希、积压峰值与策略指纹；交流导出保存此回执，活动或失败记录列为明确缺口。旧同步EventRecorder仅保留兼容接口，不代表新入口仍逐条同步落盘。

64MiB待写入预警水位集中于capacity-policy第2版，可配置；越线只记首次值及峰值，不丢弃、不阻断生产端，不主动终止研究。这是软预警，非内存隔离；持续磁盘故障可能造成内存增长，尚无自动持久溢写/进程崩溃后队列恢复保证。收尾排空没有新设任意短时限，写入器永久卡住仍会影响收尾，须继续处理。写入失败只记录缺口，不声称所有原始事件可从原生日志完全重建。

source登记的重型SDK解析已移出数据库写事务，提交前短事务重新核对成员、运行、幂等请求与游标。prepare/admit/安装核验的既有读取链尚未全部迁移，不宣称所有重型读取都已消除占锁。session.record_event的Control游标身份登记仍同步，尚未完成异步解耦；预算/安装权限/生效核验继续同步。
