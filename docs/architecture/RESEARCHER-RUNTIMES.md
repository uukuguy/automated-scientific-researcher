# Researcher runtimes

Status: accepted architectural direction, 2026-11-02. Main authority:
[PROJECT-DESIGN](../PROJECT-DESIGN.md), decision D012.

ASR owns research contracts, run/trial identity, budgets, controls and evidence.
The researcher runtime owns model reasoning, tool calls and native conversation
state. AAR research organization and collaboration are separate from the SDK.
Replacing a runtime does not replace experiment evidence or reset project budgets.

## Subscription-first execution

The user currently has GPT and Grok subscriptions; Claude subscription is pending. Prefer coding-agent subscription
sign-in. Record runtime, provider, model, authentication mode and billing mode
separately. A subscription account alone does not verify a particular SDK's access.
Never silently fall back to a paid API, another account or another provider.
Paid API execution needs explicit separate authorization.

Subscription usage still has finite limits: active session walltime, model turns,
tool calls and numerical attempts. Unknown provider quota is recorded as unknown;
rate limits/exhaustion pause new work and preserve recovery. Local limits are not
an exact provider billing meter. Do not label subscription token estimates as API
charges actually incurred.

## Adapter contract

An adapter accepts the effective research contract, durable recovery references,
a curated tool surface, a native session identity and finite limits. It emits
model/tool events, actual completion/error/limit outcomes and native session
references. The trusted coordinator verifies process exit before releasing the
session reservation. A stale session must be reconciled before another starts.

Tools read effective state, submit trials, observe immutable evidence, publish
candidate findings and receive guidance. Research steps are model-selected.
Pause stops new admission; immediate stop must reach an active runtime externally.
The runtime receives no Docker socket, authoritative database or evaluator keys.
Credentials stay in private runtime configuration and out of evidence/log payloads.

Native conversation resume is an optimization. Portable recovery uses contract,
notebook, code snapshots, completed/in-flight trial identities, guidance and
findings. It must not rerun experiments merely to rebuild conversation context.

## Runtime candidates and evidence

| Runtime | Role | Verified basis | Remaining verification |
|---|---|---|---|
| pi + openai-codex OAuth | Lightweight baseline | Local pi 1.0.0 installed; selected provider credential type is OAuth | Actual bounded ASR model trajectory and durable recovery |
| Native Codex | Alternative coding runtime | Official Codex authentication documents subscription sign-in | ASR adapter, tool integration and acceptance |
| Claude Code / Agent SDK | AAR upstream runtime family | Upstream uses Claude Agent SDK; official SDK has tool/session/hooks capabilities | Supported subscription use for the selected deployment; ASR adapter |
| Grok Build | Alternative coding runtime | Official docs expose browser authentication, headless JSON and ACP | Account entitlement/billing mode and ASR adapter |

These are distinct verification states, not claims of equal feature support.
Primary sources checked 2026-11-02:

- [Codex authentication](https://learn.chatgpt.com/docs/auth)
- [Claude Agent SDK](https://code.claude.com/docs/en/agent-sdk/overview)
- [Grok Build](https://docs.x.ai/build/overview)
- [pi provider documentation](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/providers.md)

The local pi package is `@earendil-works/pi-coding-agent`; use its installed docs
for the pinned runtime protocol. The initial acceptance tool surface is curated
ASR tools. Full arbitrary coding workspace isolation is a separate capability;
passing a tool-only research trajectory does not prove that isolation.

Current selection: use the existing pi + Codex default configuration immediately. Verify other subscription runtime authentication, headless operation and billing before enabling them. Claude readiness is pending, not an implementation prerequisite. Preserve required local network/proxy configuration while excluding paid API credential fallback.

## Capability packs (accepted direction; implementation staged)

A runtime alone does not supply the whole research environment. Package curated
skills, semantic tools (MCP or native extensions), hooks and dependencies in a
versioned capability manifest. Separate generic research/coding, power-grid domain
methods and ASR system integration. Load skill summaries initially and detailed
instructions when relevant; do not import all developer home configuration.

AAR upstream already supplies research-thinking skill, MCP tools and project
hooks. Its research-thinking skill calls a paid Anthropic API directly; do not
load it unchanged in subscription mode. Replace it with method guidance or an
explicitly budgeted subscription delegation capability. Skill text cannot grant
network, credentials, evaluator access or execution authority.

The current calibration manifest includes curated scientific guidance, guarded pi
native file tools and ASR service tools. It does not execute arbitrary candidate
code. A coding-research profile needs a separately verified isolated execution
environment for testing and candidate submission. Its methods and
tool effects must be assessed on scientific tasks, not by installed skill count.

### ASR base toolset: omp + AAR

User accepted this combination as the ASR base on 2026-11-02. Reuse pi native
capabilities where they fit; use omp as the tool-configuration reference, not as
an instruction to copy every tool or enable all global configuration.

| Group | Base choice | Access and evidence |
|---|---|---|
| Workspace navigation | pi read, grep, find, ls | Research workspace and explicitly mounted reference material |
| Code changes | pi edit, write; omp-style LSP diagnostics when available | Writable candidate workspace only; snapshots before experiments |
| Analysis and tests | bounded shell/Python; optional notebooks | Isolated execution with explicit resource/time/output limits |
| Research method | hypothesis, experiment design, debugging, evidence review skills | Curated version/hash; no hidden paid model calls |
| Scientific state | ASR contract, guidance, trial, validation, finding tools | Authenticated service; immutable evidence references |
| Research memory | AAR-inspired notebook, shared findings, code snapshots | Preserve failures and negative evidence; version-aware retrieval |
| Literature | web search/fetch or MCP literature tools | Explicit network/credential/cost profile; sources recorded |
| Organization | local todo; optional delegated critique | One owner per research run; all auxiliary calls share budget |

Default excludes host desktop control, broad credential access, automatic git
commits, public sharing/upload, uncontrolled background processes and automatic
extra model consultations. These exclusions describe the initial tool profile;
capabilities can be added under an explicit supported contract.

MCP is a transport adapter. Tool semantics and authorization remain the same when
pi extensions, native coding-agent tools or MCP provide the frontend. Runtime
and pack versions are recorded separately so experiments can attribute behavior
to model, runtime and tool changes rather than treating them as one opaque agent.

Two profiles remain explicit: calibration-smoke (ASR service tools, curated skill and guarded workspace file tools), and
coding-research (workspace tools, bounded execution and research skills). The
latter cannot be declared operational solely by adding names to a manifest.

### Storage and reuse across runtimes

| Material | Current location / behavior | Cross-runtime boundary |
|---|---|---|
| Canonical skill source | `integrations/runtimes/skills/scientific-reasoning/SKILL.md` | Shared versioned method guidance; executable scripts would need declared dependencies and permissions |
| Capability declaration | `integrations/runtimes/capabilities.json` and `domain-powergrid.json` | Shared capability identity and contract; current runtime/version binding is pi-specific, not a universal loader |
| Session skill copy | `<config_dir>/capabilities/<skill_sha256>/SKILL.md`, verified then frozen read-only | Each runtime gets the same verified content through its own loader; never a mutable global home installation |
| pi service-tool binding | `integrations/runtimes/asr-extension.mjs` → local authenticated `integrations/aar/bridge.py` | The extension is pi-specific; ASR operations/backend are reusable through another adapter |
| Scientific dependencies | `environments/scientific/.venv`, managed by that directory's locked uv environment | Reusable dependency specification; runtime access must go through supported controlled execution, not unrestricted host shell |
| Runtime auth and sessions | Private `<config_dir>`; acceptance example `artifacts/p2-aar-subscription-20261102-05/pi-private/` | Credentials/session formats are runtime-specific and must not be shared as tool-pack content |

Currently there is no ASR-installed general MCP server or Claude runtime binding.
MCP is an optional common interface to the same backend, not a requirement to
replace useful pi native tools. A future Claude adapter can load the shared skill
and connect supported tools through native SDK/MCP bindings, with the same
project/run authorization and resource accounting. Server implementations and
read-only assets may be shared; stdio servers normally have per-client processes,
while a network service needs explicit client/run isolation. Reusing an installation
does not imply sharing mutable sessions, credentials or permissions.

Current pi launch explicitly uses `PI_CODING_AGENT_DIR=<config_dir>`, disables
automatic skill/extension discovery, and passes only the selected frozen skill and
extension. Global `~/.pi`/`~/.claude`/developer MCP settings are not the authoritative
ASR configuration. Tools available to the development assistant (for example
Context7) are not automatically installed or authorized for the ASR researcher.
Claude loading and subscription authentication must be verified
against the selected installed SDK before claiming runtime parity.

### Context7 documentation capability (recommended; not installed in ASR yet)

Context7 is a suitable shared coding-documentation capability: resolve a library,
then query its documentation/examples. The [official API guide](https://context7.com/docs/api-guide)
exposes the same lookups through MCP and REST; the [official MCP package](https://github.com/upstash/context7/blob/master/packages/mcp/README.md)
supports remote or local connection. This makes a narrow pi native adapter and a
future Claude MCP binding possible without a general plugin platform.

Use for SDK/library syntax and version checks, including pi, Claude SDK and
scientific dependencies when indexed. Record library ID, documentation version,
query and source attribution; verify against installed source/signatures when
indexed versions lag. Documentation output is reference material, not executable
permission or scientific validation. Do not send credentials or private evaluation
assets in queries. Credentials stay in operator/runtime configuration, outside
candidate containers. Bound requests/time/response size and report rate limits;
Context7 service usage is distinct from coding-model subscription usage. Provider
outages must not cause unbounded retries or paid-model fallback.

Current developer Context7 access does not establish ASR access. Activation needs
an explicit capability declaration and adapter, authentication/availability check,
and actual tool-call test; no Context7 server or credential was installed by this
recommendation. Generic text skills remain reusable across runtimes.

### Engineering and literature skill selection

User requested systematic debugging, code review, deep search and deep research
alongside Context7. Select by behavior and provenance, not vendor-like names.
[Superpowers](https://github.com/obra/superpowers) supplies systematic-debugging,
requesting-code-review and verification guidance; these are community sources,
not automatically Anthropic official assets. Any imported material requires a
pinned source, license, content hash and runtime/dependency check before loading.

| Capability | ASR use | Required boundary / current state |
|---|---|---|
| Systematic debugging | Reproduce technical failures, distinguish root cause from scientific negative evidence, verify minimal repairs | Selected for adaptation; no blanket requirement to keep fixing a refuted hypothesis |
| Code review / receiving review | Examine candidate code, numerical conventions, leakage and unsupported claims | Selected; reviewer comments are author/development evidence, not independent validation; additional agents consume configured budget |
| Verification before completion | Check actual execution and evidence before claiming success | Selected; existing scientific-reasoning guidance already enforces claim limits |
| Deep search | Search decomposition, synonyms, citation trails, source deduplication and counterexamples | Selected; needs actual search/fetch backend, bounded queries and retained provenance |
| Deep literature research | Compare methods, assumptions and contradictions; extract testable hypotheses and research gaps | Selected; literature synthesis is not a novel experimentally verified finding |
| Context7 | Version-aware implementation documentation | Recommended backend; ASR adapter and live lookup acceptance pending |

The active pack currently contains the ASR scientific-reasoning skill and pi/ASR
tools only. The table is selection scope, not an installed-tool inventory. Do not
import a whole workflow framework that forces approval for every experiment,
automatic commits, unrestricted shell or hidden paid-model consultation. A
subscription product called Deep Research is not assumed callable by SDK/MCP or
included in another provider's coding subscription. Preserve the single researcher
and let skills guide relevant decisions rather than impose one fixed research
sequence.

### Active AAR adaptation audit (2026-11-02)

The active ASR override replaces original W2S/PGR task prompts and agent creation;
legacy training/five-seed/S3/paid research-thinking paths are not active. Remaining
limitations are explicit: reference-only execution, one-session acceptance bound,
and original ORM fields with null W2S metrics. Do not enable the original PGR
leaderboard or mislabel candidate claims as verified results. Upstream private
method/text-patch coupling and eager legacy dependencies require versioned upgrade
checks; maintain the existing loop instead of creating another scheduler.

## Power-grid scientific computing pack (accepted scope)

This is a separate domain pack, not just a prompting skill or a fixed solver.
It combines executable numerical libraries, typed tools, domain guidance and
independent validation. User confirmed inclusion on 2026-11-02.

| Capability | Required behavior | Current evidence |
|---|---|---|
| Cases and models | Read network/bus/branch/generator data; explicit units, indexing, hashes and operating policy | Fixed case118 reference only |
| Scenarios and sampling | Generate reproducible load/generation scenarios, record seeds and original problem changes | Generalized scenario/sampler adapter pending |
| Reference power flow | Run pinned MATPOWER/Octave with frozen inputs and finite budgets | Implemented and real-case verified |
| Candidate methods | Register sampler/solver/joint implementation and run isolated candidate snapshots | Interface designed; arbitrary implementations pending |
| Numerical diagnostics | Residuals, convergence traces, conditioning/Jacobian diagnostics and failure categorization | Independent residuals implemented; richer traces/conditioning pending |
| Electrical checks | Input preservation, original equations, voltage/reactive/thermal/angle constraints, explicit unassessed values | Implemented within fixed PV/PQ single-Slack profile |
| Comparisons | Equal-budget baselines, crossed sampler/solver comparisons, repeat seeds, failure denominators and uncertainty | Formal experiment/comparison harness pending |
| Visualization | Topology, operating points, convergence and coverage plots with source evidence references | Domain plotting adapter pending |

Scientific computation runs inside versioned environments. Large arrays and
matrices are artifacts, not unrestricted tool-response payloads. Return summaries,
units, diagnostics and artifact references. Every operation records provenance,
including failed attempts and costs. Separate candidate claims, equation validity,
operating constraints, reproducibility and generalization.

Expand the established MATPOWER/Octave reference plus Python validation first.
Additional Python numerical/network libraries or alternate solvers require
version pinning and cross-checks before becoming a supported execution profile.
A domain skill explains use; it does not replace executable tools or independent
validation, and never grants access to hidden evaluation assets.

### Preselected scientific environment (accepted)

The default scientific environment contains MATPOWER/Octave reference plus
pandapower, NumPy, SciPy, pandas, PyArrow, NetworkX, Matplotlib, Jupyter/ipykernel
and pytest. Python dependencies use a separate locked environment; do not inflate
the control-service dependency set. The runtime's declared tool capabilities
remain separate from which libraries are installed.

Track installed, numerically calibrated and formal-evaluation-approved states
separately. Cross-calibrate pandapower against the original MATPOWER input/model
policy before comparing results; retain independent equation checks. Additional
optimization, ML, symbolic, distribution or dynamic packages belong to explicit
optional environments, not automatic installation by a researcher.
