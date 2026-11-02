# Replaceable researcher runtime

`pi.py` runs one pi 1.0.0 coding-agent session through documented JSONL RPC.
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
An unconfirmed exit retains the runtime reservation for reconciliation. Persisted
process identity and recovery after supervisor death require further work; native
conversation reopen alone does not prove process reconciliation.

`prepare_oauth` copies only `openai-codex` OAuth into a private config directory,
keeps refreshed tokens there across reopen, and does not modify the user's auth
store. Ambient API keys, skills, extensions, project context, provider switching
and shell tools are disabled. Do not publish that private directory or session
transcript: both may contain sensitive data. The runtime returns model-reported
usage; dollar cost metadata is an estimate, not a subscription invoice.

`capabilities.json` is the versioned capability-pack seam. This acceptance pack
exposes only the ASR tool. It is not the final coding/reasoning capability pack.
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
`--refresh-oauth` refreshes only the isolated runtime credential using pi's
`auth check`; it never prints credentials or rewrites the user's auth store.
An unavailable proxy can produce `fetch failed`: explicitly configure the
operator's existing HTTP(S)_PROXY and NO_PROXY for the local bridge.
Failed acceptance artifacts are retained and are not scientific success evidence.

Tests use fake RPC subprocesses and an extension hook probe; they validate
protocol/budget plumbing, not autonomous research. Local docs inspected:
`docs/rpc.md`, `rpc-commands.md`, `extensions.md`, `cli.md`, `providers.md`,
`session-format.md` in the installed pi package. Pi is MIT; no pi code is vendored.
