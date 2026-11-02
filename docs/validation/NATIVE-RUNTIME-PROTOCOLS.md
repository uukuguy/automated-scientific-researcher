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

Installed help exposes stdio app-server and local schema generation. Protocol
foundation implementation/tests are in progress; live initialization results
will be recorded after actual execution. Context7 /openai/codex was consulted;
its exec-server results are excluded from app-server signatures. Local generated
schema and official App Server docs govern implementation.
