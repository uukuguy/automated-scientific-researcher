# SDK call prototype verification

Checked 2026-11-02 using Context7 resolver/query tools, then installed source and
Python signatures. This checks interface compatibility, not subscription rights.

| Library | Context7 ID / indexed version | Installed version |
|---|---|---|
| pi | `/earendil-works/pi`, explicit `/earendil-works/pi/v1.4.0` | 1.5.0 |
| Claude Agent SDK Python | `/anthropics/claude-agent-sdk-python` (indexed0.2.159) | 0.2.176 |
| pandapower | `/e2niee/pandapower` (indexed3.5.4) | scientific environment3.5.6 |

No exact indexed version match is assumed. Main/develop snippets may describe
newer behavior; installed signatures and real tests control implementation.

## pi RPC and extension

- `prompt` JSONL: `{id,type:"prompt",message}`. A successful response is acceptance,
  not completion. `disposition:"handled"` means no model run starts.
- `agent_end` is one low-level run; `agent_settled` is the session-level terminal
  event after automatic follow-up/recovery. Adapter waits for settled.
- `tool_call` exposes mutable `event.input`. Mutate it in place for normalization;
  `{input:...}` return is not the documented replacement interface. Blocking uses
  `{block:true,reason}`. This review found and triggered correction of the adapter.
- `before_provider_request` is wired to provider `onPayload`; installed runner
  error handling does not constitute a denial boundary. Permit failures terminate
  the owned runtime, with an independent deadline timer.
- Session retries and provider retries are distinct. Installed configuration reads
  `retry.provider.maxRetries`; disable it as well as session retry. Disable cache
  warming explicitly for finite-count acceptance.
- OAuth provider interface exposes login/refresh/toAuth. Credential validity is
  tested through supported OAuth, never by printing or embedding tokens.

Sources:
[Extensions](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/extensions.md),
[RPC1.4](https://github.com/earendil-works/pi/blob/v1.4.0/packages/coding-agent/docs/rpc.md).
Local proof: installed `dist/core/extensions/runner.js:emitToolCall` and
`dist/core/settings-manager.js:getProviderRetrySettings`.

## Claude SDK compatibility

Actual installed `ClaudeSDKClient.query(self,prompt,session_id='default')` and
`receive_response(self)` signatures were inspected. Options include model, cwd,
mcp_servers, setting_sources and allowed_tools, satisfying pinned AAR imports.
`allowed_tools` controls approvals; it must not be mistaken for an exclusive
availability list. This optional dependency is used to import actual upstream
AAR; the selected researcher runtime remains pi/Codex subscription.

Source: [Python SDK configuration](https://github.com/anthropics/claude-agent-sdk-python/blob/main/_autodocs/configuration.md).
No Claude model call or subscription compatibility claim is made.

## pandapower

Context7 documents `from_ppc(ppc,f_hz=50,validate_conversion=False,**kwargs)`.
`runpp` initialization, transformer model, reactive-limit behavior and optional
engines must be explicit. `init_va_degree` accepts a float/vector; the local
integer-vs-float discrepancy is preserved in numerical calibration evidence.
Internal `_ppc` matrices are audited implementation details, not immutable public
problem representation. Installed signature/source checks and numerical results
are recorded in the pandapower calibration report.

Source: [PPC converter](https://github.com/e2niee/pandapower/blob/develop/doc/converter/pypower.rst).

## 2026-11-04：pi 订阅连接方式复核

Context7 的 `/earendil-works/pi` 文档确认，`transport` 可为 `sse` 或 WebSocket 系列；文档跨版本，实际以本机 1.5.0 为准。本机 `docs/settings.md` 列出默认 `auto`，`dist/core/settings-manager.js:getTransport` 读取该项，`dist/core/sdk.js` 将其传给智能体。ASR 私有配置明确改为 `sse`，保留同一 openai-codex OAuth 订阅、模型和禁重试设置。

真实运行已出现 WebSocket 错误和 300 秒空闲超时。SSE 随后成功完成 6 轮对话、16 次工具调用，但也发生一次 `terminated`，因此不能宣称已解决所有网络中断。失败和累计消耗保留，进程退出与预留核清后才显式恢复。没有重新登录、写入 API key 或切换付费服务。419 项回归检查通过，其中 25 项环境相关跳过。

## pi会话投影复核

2026-11-04核查本机1.5.0公开导出的buildSessionProjection(entries, leafId, byId?)，并通过Context7核对：它处理当前分支、已有compaction及context_edit，返回消息与来源条目。ASR只读适配器使用此接口，实际安装SDK的压缩/编辑投影测试通过。getLeafId必须来自活动sessionManager才能成为活动游标见证；离线文件最后节点不等价。核心覆盖算法不导入该SDK。

pi 1.5.0本机types.d.ts与session-manager.d.ts再次核对：ExtensionContext.sessionManager公开getSessionId/getSessionFile/getLeafId/getBranch。游标采集使用这些只读方法，在before_provider_request许可之后读取当前叶节点、指定分支ID并复查游标。Node宿主回调检查通过；尚无真实模型会话使用新事件的验收，不等于提供方最终载荷或Control身份绑定已验证。

同步边界再次核查pi 1.5.0已安装types.d.ts及agent-session.js：session_before_compact支持cancel/compaction，手动及自动压缩均await该钩子；没有明确结果时进入默认生成器。现有扩展明确取消所有尚未联合授权的压缩，不用异常逃离（SDK可能吞掉钩子异常）。SDK代码检查证明调用语义；新增Node/HTTP测试使用模拟会话管理器，不代表真实模型安装验收。
