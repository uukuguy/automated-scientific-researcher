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
