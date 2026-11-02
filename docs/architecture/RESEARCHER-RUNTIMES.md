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

The current smoke manifest has no coding tools or skills. It validates tool-only
research integration. A coding-research profile needs a separately verified
isolated workspace with editing/testing/candidate submission. Its methods and
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

Two profiles remain explicit: calibration-smoke (ASR service tools only), and
coding-research (workspace tools, bounded execution and research skills). The
latter cannot be declared operational solely by adding names to a manifest.

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
