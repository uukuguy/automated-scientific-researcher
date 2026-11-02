# Research variable policy

`variable-policy.schema.json` describes `asr-variable-policy/1`, a component of the future `asr-contract/1`. It is not the full executable contract. The example contains network, iteration and solver variables; it does not authorize a numerical or model run.

Run checks with `uv sync --locked` and `uv run python -m unittest discover -s tests -v`.

`asr_service.contracts.resolve_policy(template, overrides)` copies defaults into effective values, rejects undeclared fields/types/units, and checks bounds. User overrides can change value, mode, allowed range, modification roles and implementation description; changing declared types or units requires a new template. A default can lie outside a newly narrowed range only when an explicit effective value is valid. `check_change` checks a candidate value, role and scope without mutating policy. Fixed values require a new policy revision to change. Open values still need service-level capability and budget admission.

`PolicyStore(path)` owns only `asr_policy_*` tables. `publish` requires an expected revision (0 for creation), a project-scoped idempotency key and a resolved policy. Repeating the same request returns the original revision; changed content or stale expected revision is rejected. Publications and events commit in the same SQLite transaction. `get` returns a detached document.

`apply` explicitly switches a binding for an external run ID using the binding's control revision (0 for initial binding). Publication does not change that binding. It does not create a research run, validate a real upstream run, reserve budget or start a process. Apply currently uses compare-and-swap, not the future idempotent HTTP command envelope; callers must read the binding after uncertain responses. These local bindings will be incorporated into the owning runtime's transaction before real trial admission is added.

The actor argument is a trusted in-process role assertion, **not authentication**. Public callers must not directly invoke these methods or supply their own trusted actor. Project grants, registered problem/evaluation references, complete budgets, capability checks, migrations and HTTP envelopes remain P2 work. An empty database may be initialized for local tests; no AAR production database was modified.

The example is an editable template, not a newly imposed limit on all research. Capstone may consume the schema and examples to prepare forms; semantic checks remain authoritative on the server side. Do not advertise this sub-schema as the complete cross-project contract.


### P2 local budget primitive (2026-11-02)

本地预算原语 `asr_service/budgets.py` 已实现项目级整数计量、事务预留、幂等结算及超额记账。执行退出由可信调用方声明，尚未连接进程核验、运行子额度、完整准入或 AAR；不能作为执行授权。

预算原语新增 `reserve_many` 与 `reserve_many_in_transaction`：多维额度原子预留、完整请求重放校验，可加入拥有者事务；尚未实现完整 trial 准入。事务调用方必须使用同一数据库，并负责 trial/事件/派发意图及认证。

本地 `asr_service/references.py` 提供按项目和类型隔离的不可变 JSON 元数据引用，读取时复核内容 hash，并支持在拥有者事务中查询。注册是可信内部操作，不验证外部产物可用性、科学协议完整性或身份权限；完整 trial 准入仍未实现。

`asr_service/admission.py` 已提供本地准入准备事务：核对显式 policy ID/revision 和项目引用，原子保存 trial/attempt 身份、预算束和事件；重复请求复用身份。必填可信 owner_gate 承担认证、外部运行门控、完整契约和产物/能力检查，当前没有真实适配。queued 记录仅为准备意图，无领取/派发/租约；不得用于真实执行授权。

本地准入准备接口将必填 `authorize` 与 `owner_gate` 分开：每次请求先校验访问权限；已受理的相同请求直接返回原回执，新请求才检查运行门控。暂停后恢复丢失响应不会创建新试验或再次预留预算。两种回调仍需真实服务适配。
