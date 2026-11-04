# Replaceable researcher runtime

`pi.py` runs one pi 1.5.0 coding-agent session through documented JSONL RPC.
`session.py` claims one exclusive ASR runtime identity, obtains a finite walltime
reservation, binds every turn/tool permit to its session/epoch/owner and settles
after the process group exits. It does not schedule research sessions. Native pi
session IDs remain stable across reopen; control execution-session IDs are distinct.
The acceptance harness reads the user's validated pi default Codex model and
thinking level; it does not silently substitute another provider or model.
A successful prompt receipt or `agent_end` is insufficient: wait for `agent_settled`
and inspect provider errors. Subscription quota errors close admission without
switching provider or using an API key.

`asr-extension.mjs` asks the trusted bridge for permits before every provider
request and tool execution. Pi swallows provider-hook exceptions; the extension
therefore exits on denial or loss of the bridge. The parent enforces walltime,
checks stopping state during generation, and terminates/reaps the process group.
An unconfirmed exit retains the runtime reservation for reconciliation. The durable process identity includes host, boot identity, PID/group and OS birth
time; reconciliation rejects reused identities and verifies the registered group
is gone before settlement. The extension has an unconditional deadline watchdog
that kills its own group even if the Python parent disappears. This proof covers
the restricted file-tool profile. It does not cover arbitrary detached children
from unrestricted code; arbitrary coding execution remains unavailable.

`prepare_oauth` copies only `openai-codex` OAuth into a private config directory,
keeps refreshed tokens there across reopen, and does not modify the user's auth
store. Ambient API keys, skills, extensions, project context, provider switching
and shell tools are disabled. Five versioned skills are loaded explicitly: scientific-reasoning, systematic-debugging, code-review, verification-before-completion and deep-research. They contain method guidance and no hidden model calls. Native pi
read/edit/write/grep/find/ls tools are reused with path guards rooted in the
research workspace, excluding symlinks, host paths and Git/pi metadata. Exact
read-only exceptions permit the frozen declared skill files. `find` is deterministic glob
search, not OMP semantic model search. Do not publish that private directory or session
transcript: both may contain sensitive data. The runtime returns model-reported
usage; dollar cost metadata is an estimate, not a subscription invoice.

`capabilities.json` is the versioned capability-pack seam. This acceptance pack
exposes ASR tools and guarded native workspace file tools. A separate sandbox
execution capability is advertised as unavailable until its OS boundary exists.
Curated skills, reasoning helpers, MCP tools, runtime-specific translations and
coding sandbox dependencies can be added explicitly under the same finite budget.
A runtime with Bash must not receive host credentials, evaluation assets or the
Docker socket. This host adapter does not claim OS sandboxing for arbitrary code.

Run the explicit authorized subscription acceptance:

```sh
uv run python -m integrations.runtimes.acceptance --output artifacts/p2-pi-UNIQUE
```

The tracked finite limits allow 120 seconds total, 12 provider turns, 20 ASR tool
calls and two numerical attempts. The first session has at most 100 seconds;
recovery uses the same native session and remaining total budget. The model
chooses its own hypothesis/iteration setting and writes its finding from actual
supervised numerical evidence. Reopen must preserve trial IDs and findings.
The workspace has its own Git root and Git ancestor discovery is bounded.
If the provider reports an expired token despite a future local expiry field,
`--refresh-oauth` refreshes an isolated credential using pi's `auth check`
and reconciles it to the canonical source. Each role stages current source OAuth,
then returns refreshed Codex credentials after process exit under a short lock
and compare-before-write guard. Other providers are preserved. A newer login,
busy store or I/O error pauses with an explicit receipt; it does not trigger
automatic browser login. Credentials are never printed. Role conversations and
tool permissions remain separate from the shared account authentication.
An unavailable proxy can produce `fetch failed`: explicitly configure the
operator's existing HTTP(S)_PROXY and NO_PROXY for the local bridge.
Failed acceptance artifacts are retained and are not scientific success evidence.

Tests use fake RPC subprocesses and an extension hook probe; they validate
protocol/budget plumbing, not autonomous research. Local docs inspected:
`docs/rpc.md`, `rpc-commands.md`, `extensions.md`, `cli.md`, `providers.md`,
`session-format.md` in the installed pi package. Pi is MIT; no pi code is vendored.

Installed-version drift is rejected before launch. Earlier acceptance03 used pi
1.0.0; acceptance04 verified pi1.5.0 with skill/file tools, forced interruption
after numerical completion, and same-session finding recovery. Run
`python -m integrations.runtimes.recover_acceptance --root PATH` only on an
existing interrupted acceptance. It cannot dispatch new numerical work. The04
model omitted snapshot paths; that failed call is retained and argument help now
explains the required paths. Domain toolkit availability is explicit in
`domain-powergrid.json`; unavailable sampling/novel solver/comparison capabilities
return unsupported rather than silently using the reference.

Before any pi invocation, preflight enforces the capability schema, runtime
version, explicit skill ID/path/content hash and native tool inventory. The
verified skill bytes are frozen under the private runtime directory, and session
results record `capability_pack_sha256` and `capability_pack_id`. A changed skill,
manifest version or path fails before spawning pi. Historical acceptance04
artifacts predate this enforcement and are preserved unchanged.


## Simulated OOD project lifecycle

`ood_intake` delegates the frozen public client package; `ood_study` continues the
same AAR run under explicit model/compute totals; `ood_finalize` requires a real
frozen proposal plus prospective hypothesis and performs selected-training replay
before controller-only hidden evaluation. It exports only verified aggregate final
results to the workspace. `ood_study --synthesis-only` removes experiment tools and
uses remaining model budget to interpret final results and training reproduction.
See `docs/validation/P4-SCIENTIFIC-RESULTS.md` for the actual completed trajectory,
limits and controller-assisted archival. Never relaunch the completed P4 run.

Native context can exhaust before ASR's time budget. P4 preserved the original
session directory, recorded context-recovery.json and opened a fresh conversation
with the same research identity and remaining allowance, restoring from durable
files. This was an explicit operator recovery, not implemented automatic
compaction/rotation. A runtime's final timeout is not erased by scientific success.

### pi 订阅连接方式

ASR 的私有 `settings.json` 明确使用 `transport: sse`。本机 pi 1.5.0 的设置定义和 SDK 传递路径已核查，并用 Context7 核对上游文档。此设置用于避开真实研究中出现的 WebSocket 连接错误和 300 秒空闲超时；仍使用同一 openai-codex OAuth 订阅，不写入 API key、不切换计费、不自动重试或增加额度。网络中断仍须保留记录并核查进程后恢复，SSE 不代表永不断线。

### 组织角色的上下文恢复

明确遇到模型上下文容量不足时，可在核查进程退出、预算预留归零后，用 `organization_pilot --resume --fresh-context-for lead_1 --recovery-reason ...` 为指定角色开启下一代原生会话。恢复记录保存角色名单，后续启动从记录推导会话代数；旧 `sessions` 目录原样保留，新会话使用 `sessions-generation-N`。研究身份、角色权限、工作区、组织消息和累计预算均保持不变，完整交流归档同时读取各代原生日志。

这不是自动压缩或自动重试；新会话必须从持久研究材料恢复，不能靠清空会话重跑已完成实验。参数仅允许在显式恢复时使用。
