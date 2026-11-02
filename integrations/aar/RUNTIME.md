# Pinned AAR research owner with pi sessions

Prepare a **new private checkout**, then apply the tracked ASR adaptations:

```sh
uv run --extra aar python -m integrations.aar.prepare_upstream --destination artifacts/aar-private-UNIQUE
uv run --extra aar python -m integrations.aar.loop_patch artifacts/aar-private-UNIQUE
```

Preparation verifies the original clean pinned checkout and refuses an existing
destination. `loop_patch.py` refuses the original ignored checkout and modified
agent/sync sources. It records original/patched hashes without vendoring upstream
code. The original repository's missing license remains an explicit limitation.
The separate worker patch prevents the original backend worker from claiming ASR
runs; there is one research owner.

`researcher.py` imports the actual pinned `AutonomousAgentLoop` and real optional
Claude Agent SDK dependencies. It does not emulate upstream modules. The original
`run()` is the sole outer session loop; a small reproducible source adaptation
adds finite session/error counts and an external control gate. Its original
`_run_session()` still manages session naming, logging and `AgentResult` handling.
The subclass injects the effective ASR prompt and pi session implementation.
Pi owns model reasoning and tool use within a session; the existing ASR control
service owns admission, budgets and runtime identity. No Claude API call is made.

AAR mode requires an actual upstream `Experiment` row mapped atomically into the
ASR run through `UpstreamAdapter`. A fabricated external ID is insufficient. The
actual `Finding` ORM and forum query retain candidate findings and local snapshots;
independent validation stays in ASR evidence. The original `FindingsSync` thread
runs locally against that project-wide forum, including other research runs.
A revision-aware filename patch preserves every finding revision rather than
silently skipping updates. It neither contacts the legacy remote server nor S3.
The original paid research-thinking skill and ambient hooks are not loaded.

The explicitly authorized bounded real acceptance is:

```sh
HTTPS_PROXY=http://127.0.0.1:7897 HTTP_PROXY=http://127.0.0.1:7897 NO_PROXY=127.0.0.1,localhost \
  uv run --extra aar python -m integrations.runtimes.acceptance \
  --aar-checkout artifacts/aar-private-UNIQUE \
  --oauth-source PRIVATE_OAUTH_FILE \
  --output artifacts/aar-acceptance-UNIQUE
```

Use the operator's actual configured proxy when needed. The source auth path is
never logged and only the Codex OAuth provider is copied into private runtime
storage. Limits remain 120 seconds total, 12 provider turns, 20 tool calls and two
numerical attempts. The model chooses a testable hypothesis and numerical trial,
reads independent evidence, writes and snapshots a note, and publishes its own
candidate finding. Reopening both the actual ORM adapter and native pi session
must preserve trial IDs. A successful actual ORM snapshot is required.

Protocol verification uses both Context7's `/earendil-works/pi` documentation and
the installed pi1.5 source. `tool_call` mutates `event.input` in place; returning
an `input` object does not rewrite tool arguments. A regression invokes the actual
installed `ExtensionRunner` and native write tool. Agent retries, provider retries
(`retry.provider.maxRetries=0`) and cache warming are explicitly disabled to avoid
unmetered automatic requests. Historical pre-adaptation artifacts are unchanged.

Acceptance05 is immutable. Its frozen contract retained an earlier provenance
organization string saying that the upstream SDK loop was not launched; this
metadata is stale for05. The actual loop summaries, patched-source hashes,
Experiment row, original FindingsSync files, successful snapshot and model
trajectory establish the path that ran. Future contracts now select accurate
provenance for actual AAR mode versus the standalone pi bridge.

Runtime import checks derive exact patch output from pinned Git blobs and compare
all imported-package physical bytes with the pinned tree, independently of index
flags or mutable receipt hashes. Disposable private-checkout bytecode caches are
purged before imports; generated cache files are not source authority. Reprepare
older private checkouts that lack current patch receipts rather than rewriting
historical experiment evidence.
