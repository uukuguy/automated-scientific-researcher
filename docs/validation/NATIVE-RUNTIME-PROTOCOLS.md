# Native runtime protocol checks

Date: 2026-11-03. No model inference in these checks. Existing local Codex and
Grok login and coding use is separately confirmed by the user. These checks do
not establish ASR tool integration, subscription quota, scientific acceptance or
OS isolation.

## Grok Build ACP discovery

Installed version: 1.0.70 (`f50904eaee6c`), stable. The actual isolated initialize
request returned ACP protocol version 1 with:

- loadSession: true; session list/resume/close advertised.
- Prompt image and embeddedContext: true; audio: false.
- MCP HTTP/SSE: true.
- x.ai/hooks blocking events: pre_tool_use, stop, subagent_stop;
  decisions deny/block; stop signals continue/stopReason/additionalContext.

Tested launch (private temporary directory placeholders):

```sh
grok --no-auto-update --no-subagents --disable-web-search \
  --permission-mode dontAsk --deny '*' \
  --leader-socket <private>/leader.sock agent --no-leader stdio
```

The installed agent help exposes --no-leader. HOME/GROK_HOME, cwd and socket were
private; environment allowlist excluded API keys. No global configuration was
changed and the user's pre-existing Grok process was preserved.

An empty private home advertised only grok.com authentication. A temporary mode
0600 copy of existing cached authentication advertised cached_token as default;
authenticate(cached_token, headless=true) succeeded. Credentials and response
payloads were not printed; temporary files were removed. No session/new,
session/load or session/prompt was sent. This verifies cached authentication
acceptance, not inferred billing, quota or resumed-session effects.

Own probe children were cleaned: first required SIGKILL after bounded SIGTERM;
second exited after stdin EOF and SIGTERM. This is a cleanup observation for
no-inference probes, not proof that all tasks spawned by an active agent stop.
Actual permission enforcement, session loading, cancellation and tool execution
remain untested. Retain these gates before research acceptance.

Sources:
- https://docs.x.ai/build/cli/headless-scripting
- https://github.com/xai-org/grok-build/blob/main/crates/codegen/xai-grok-pager/docs/user-guide/15-agent-mode.md
- https://github.com/xai-org/grok-build/blob/main/crates/codegen/xai-grok-pager/docs/user-guide/18-sandbox.md

## Codex App Server

Installed codex-cli 0.166.0 exposes stdio app-server and local schema generation.
The bounded client in integrations/runtimes/codex_app_server.py passed 12 fake
process tests, including immediate child exit during reader startup. Actual
initialize/initialized/close completed with exit code 0 without inference.
Context7 /openai/codex was consulted; exec-server signatures were excluded.

User then explicitly requested actual model conversations. One Codex App Server
prompt returned ASR_CODEX_OK with turn status completed in 25.409 seconds under
45 seconds. Actual returned model gpt-6.1-sol, high reasoning, provider openai;
account/read confirmed chatgpt type without retaining raw account data. Private
HOME/CODEX_HOME/workspace excluded global configuration, plugins and MCP; shell
was disabled. No tool attempt or API fallback occurred. Direct child exited 0.
See CODEX-APP-SERVER-CONVERSATION.json. This is actual native dialogue acceptance,
not ASR tool/admission integration or whole descendant execution containment.

The corresponding Grok real prompt created a session with default grok-4.6 but
timed out without assistant text. No tool/permission events; owned process group
cleanup was verified, existing user process unchanged. Preserve this failure in
GROK-ACP-CONVERSATION.json. Network/config investigation continues; never turn a
successful cached-auth handshake into a claimed successful conversation.

## Grok inference route correction and successful dialogue

Anonymous connectivity to cli-chat-proxy.grok.com timed out directly; the
operator's existing local HTTP proxy reached the endpoint (HTTP404 at root,
which proves reachability, not model success). Explicit HTTP(S)_PROXY was absent
from the first isolated child. Codex's successful smoke had already supplied
this proxy explicitly; it does not establish automatic system-proxy discovery.

The first proxy-enabled Grok session advertised grok-4.7 instead of the earlier
grok-4.6 default. The model guard stopped before any prompt. Preserve that
observation in GROK-ACP-CONVERSATION-PROXY.json. The user did not pin 4.6; the
subsequent check explicitly accepted and verified the actual 4.7 default.

GROK-ACP-CONVERSATION-VERIFIED.json records the successful single prompt:
ASR_GROK_OK, end_turn, 10.065 seconds, zero tool/permission events, cached_token
subscription authentication with no API fallback, owned process-group exit
verified. No actual charge or remaining subscription quota is inferred.
`integrations/runtimes/grok_smoke.py` preserves a repeatable explicitly invoked
single-prompt diagnostic; it is not a Grok/AAR runtime adapter. No further model
calls are needed to establish this dialogue check.
