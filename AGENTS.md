# ASR Repository Working Rules

## Purpose and current maturity

Automated Scientific Researcher (ASR) is a durable autonomous research system.
Its first scientific application explores power-grid sampling and power-flow
solver methods, including new methods and combinations. The user controls the
research question, permitted changes, evaluation rules and resource budget.

The repository has a verified local MATPOWER/Octave reference runner, independent
Python electrical checks and immutable trial evidence. Local authenticated control
and a fenced execution supervisor support the pinned reference profile, durable
commands, budgets and recovery. The pinned AAR loop and Experiment/Finding ORM have actual subscription-backed
pi/Codex evidence, including a negative numerical outcome and notebook snapshot.
See docs/validation/P2-SUBSCRIPTION.md and docs/validation/P3-SYSTEM-ACCEPTANCE.md for measured scope; candidate
execution is restricted to explicit profiles: octave-candidate/1 for numerical methods and offline ood-study-worker/1 for admitted Python analysis. Candidate isolation, fresh method replication and Control-budgeted evaluator recovery have real Docker tests; the complete bounded P3 model-driven trajectory and lifecycle closeout are verified. P4 completed a simulated OOD augmentation project: actual AAR-designed sampling/training, frozen independent held-out scoring (83.23% target RMSE reduction with allowed ID degradation), exact training replay and usable data/model delivery. See docs/validation/P4-SCIENTIFIC-RESULTS.md. Final AAR report was controller-archived after a recorded model walltime limit; this is not a fully unattended lifecycle or real-industrial generalization claim. Typed evaluator artifact links are verified separately from scientific claims.
P5 has versioned organization/member/direction/task/discussion records in the same Control database, authenticated HTTP and an explicit coordination tool profile. A real bounded serial Organizer/Lead/Worker design pilot has verified autonomous direction proposals, delegation, substantive review and source revision; see docs/validation/P5-ORGANIZATION-PILOT.md. It used zero compute and does not complete P5 or prove parallel execution/scientific gains. Task-bound OOD admission and Lead/worker scientific tool binding now have engineering checks, including real successful/failed containers. Frozen paired-arm reuse and separate accounting now have real container checks; the preserved team prototype has trusted numerical/training adapters with actual 64-label,192-row task-bound container checks and model receipt binding. An opt-in contract adapter now persists and reconciles these artifacts through submit_study, with real tool interruption/corruption recovery checks. A subsequent real model-driven implementation run delivered a coordinate generator and adversarial review through two isolated analysis jobs, retaining a confirmed self-check oracle defect. This is qualified pinned-source acceptance, not OOD utility or full P5 science; see docs/validation/P5-IMPLEMENTATION-PILOT.md. Independent project-level conversion now binds that actual source/evidence to the native paired protocol, rejects the real wrong-order counterexample and prepares32 arms/2048 inputs; no new labels or fits follow from this preparation (P5-GENERATOR-ADMISSION.md).
A subsequent project-directed Organizer/two-Lead run autonomously delivered512 labels,9 models and24 experiments with full visible communication archived; public utility gains remain exploratory, independent hidden evaluation/replay and parallel organization acceptance remain open. See docs/validation/P5-PROJECT-PILOT.md.
Research-context preparation, independent-session review, one-use host installation and native pi post-write verification have actual subscription evidence, including continuation and owner-only source retrieval. See docs/validation/RESEARCH-CONTEXT-INSTALLATION.md. This is explicit-trigger engineering acceptance, not arbitrary long-run auto-compaction or scientific validation. Organization and summary/installation entry points now record communication asynchronously with explicit finalization receipts and archive gaps; source registration parses outside the database write transaction. Control cursor registration remains synchronous; stalled-writer memory growth and finalization recovery remain open. Never continue a provider request after requested compaction without the Control verification receipt; preserve original journals, failures and uncertain writes. Historical source retrieval grants no current permissions.
Keep subscription account authentication separate from role conversations: stage canonical OAuth and reconcile refreshed credentials after process exit, preserving concurrent logins and recording conflicts. Never interpret transport errors as a reason for automatic browser login.
Researcher runtimes are replaceable and subscription-first; pi is the lightweight
baseline. Subscription runtime children must not receive any *_API_KEY; only pi explicitly using a non-openai-codex provider may allow such settings. That exception does not authorize paid API usage or fallback. Use `uv sync --locked` and `uv run python -m
unittest discover -s tests -v` for the base suite. Add `--extra aar` to `uv run`
for the actual upstream integration tests. The fixed-PV/PQ baseline is a calibration
profile, not a restriction on candidate-method research. See
`docs/validation/P1-NUMERICAL-LAB.md` for evidence and limits. Check the worklist
and code before reporting implementation status; update this paragraph when it changes.

## Read before work

1. `docs/PROJECT-DESIGN.md`: canonical current goals, architecture and boundaries.
2. `docs/architecture/ASR-MINIMUM-LOOP.md`: subordinate technical design for the
   minimal loop; proposed wire protocol and implementation behavior.
3. `docs/status/INDEX.md`, then relevant state, recovery and recent journal entries.
4. `docs/plans/WORKLIST.md`: package scope, dependencies and acceptance evidence.
5. For integration work, `docs/handoffs/CAPSTONE-SCIENTIFIC-RESEARCH-MODE.md`.

User instructions take precedence. Keep confirmed principles, technical design,
calibration choices and verified behavior distinct. The original task book and
dated redirect are background, not the current implementation authority.

## Component ownership

- Capstone owns the human workbench, conversation and presentation projections.
- ASR control owns effective contracts, admission, commands and budget records.
- AAR is the first autonomous researcher; one executor advances each research run.
- The experiment service owns actual execution and immutable raw evidence.
- Independent evaluation owns validation and replication reports. An agent's
  claimed score or a UI label cannot replace those reports.

Do not create a second research scheduler or authoritative ledger in Capstone.
Keep cross-system IDs explicit: a conversation turn is not a research run or
numerical attempt. Read a sibling repository's rules before modifying it and
preserve its unrelated work. Preparing a handoff is not proof it was delivered,
accepted or implemented by the other project.

## Research and execution invariants

- Sampling and solver methods are research variables from the start. A fixed
  reference baseline does not restrict candidate methods.
- Variable modes are fixed/bounded/open. Open grants method exploration within
  the contract, not unlimited budget, arbitrary permissions or evaluation access.
- Distinguish scenario changes, algorithm changes and problem-definition changes.
  Validate the original problem with explicit fixed and allowed control variables.
- Separate execution completion, solver claims, equation validity, operating
  constraints, reproducibility and generalization. Solver failure is not proof
  of infeasibility; missing constraints remain unassessed.
- Preserve failed trials, negative findings, code/input/environment provenance
  and every execution attempt. Published evidence is immutable.
- New contract versions govern subsequent submissions. Accepted experiments keep
  their starting versions. Controls require actual receipts and effective scope.
- Reserve budget before execution, retain consumed costs after failure, and
  reconcile live processes before releasing reservations or retrying.
- Candidate code cannot modify evaluation code or read hidden evaluation assets.
  Claims of isolation require actual OS/container enforcement and verification.

## Limits, exceedance and recovery

Every limit must name the risk or resource it controls, its unit and scope,
where it is configured, and why its default is sufficient for the intended
workload. Distinguish acceptance-test limits from operational defaults. Do not
add arbitrary short limits merely to make a test finish. Recheck current limits
when workload, runtime, tools or execution profiles change.

Exceedance must produce durable, inspectable records: limit name, configured
value, measured or requested amount, affected research/session/trial/attempt IDs,
action taken, retained evidence and the recovery or escalation path. Distinguish
budget exhaustion, provider rate limits, transport timeout, invalid output and
scientific negative outcomes. Never suppress an error, report success after an
unverified operation, discard consumed cost or silently retry/fall back.

Ordinary budget/session limits must pause or defer the research at a recoverable
boundary with an explicit receipt. They must not silently discard or terminate
the research task. Reserve cleanup/checkpoint time before deadlines. If safety,
resource isolation or an unresponsive process requires forced termination, stop
only the owned execution, preserve evidence and state, record the reason and
actual exit proof, and leave the research recoverable. Unknown execution retains
its reservations and blocks duplicate work until reconciled. Raising a limit
requires an explicit recorded policy/budget change; it must not erase prior
exceedance or reset usage. No paid API fallback follows from a limit change.

For each changed or newly reviewed limit, verify its boundary and exceedance
behavior with appropriate tests or actual execution evidence. Keep an up-to-date
inventory in `docs/validation/LIMITS-AUDIT.md`; unresolved limits must be stated
explicitly rather than hidden behind a successful test count.

## Local development and upstream adaptation

Use the existing OrbStack Docker Engine and Compose; no additional VM is needed.
Researchers and candidates do not receive the Docker socket or host credentials.
Keep persistent evidence outside disposable containers. Do not launch paid model
runs without an explicitly configured authorized budget.

The ignored upstream checkout is `3th-party/automated-w2s-research/`; Python
sources are under its `w2s_research/` directory. Pin the upstream revision and
license. Store reproducible patches and preparation scripts in tracked
`integrations/aar/`; do not leave the only implementation in the ignored copy.

Verify changes with focused checks. Numerical claims need real numerical tests;
autonomous-research claims need actual model-driven execution. Mock tests only
prove the interface and orchestration behavior they exercise. Preserve the
existing tests unless explicitly changing their contract as part of the task.

## Durable alignment

Update the relevant main-design section in the same work cycle when the user
settles a design change. Record rationale and supersession in DECISIONS; align
affected detailed designs, handoffs, worklists, schemas and tests. Maintain
stable document paths instead of cloning full designs for each discussion.

JOURNAL is append-only. Record durable decisions, checks and commits promptly;
refresh RESUME as an active-session checkpoint at recovery boundaries. Keep
CURRENT-STATE structural. Register status files in INDEX. Stage only task-owned
changes and preserve unrelated tracked, untracked and runtime data.


## Completion-first subscription limits

Subscription runtime limits must leave enough room for complete research and
report delivery. The former20-minute run/4-minute role windows interrupted
normal work and must not be reused as production defaults. Normal elapsed time
alone is not evidence of abnormal behavior. Finish useful work and stop promptly;
do not consume a budget merely because it remains available. Separate model
allowances from scientific permissions, compute quotas and data/evaluation scope.
Use generous explicit failsafes, record their purpose, and preserve checkpoints,
failures, pending deliveries and all costs if reached. Never silently drop work,
claim completion from a timeout, or silently switch to paid API billing.
User-authorized extensions use versioned Control contracts and replayable receipts;
existing consumption never resets. Current implementation policy is4 aggregate
model hours/30-minute role sessions,1600/3200 total turns/tools and200/400 per
session. These are current configurable failsafes, not permanent scientific limits.
Progress-aware no-progress/repetition detection is not yet implemented; do not
claim that these duration ceilings detect anomalies.


## Research autonomy and external development oversight

Under the research organization, the Organizer/Leads/Workers own scientific
problem decomposition, direction formation, project algorithms, intermediate
artifacts, experiment planning and iteration. ASR must not turn one team's
proposal into a hard-coded research workflow or require its particular artifact
sequence as a universal process. Core controls own permissions, explicit resource
policies, immutable evidence, effective contract versions and independent
validation boundaries. Enforcing an explicitly frozen evaluation rule is distinct
from prescribing how researchers reach a result.
Development work observes and evaluates real team behavior from outside; repair
generic infrastructure defects without silently supplying scientific decisions,
project code or next-step orchestration. Record any lifecycle intervention and
any developer-authored project adapter/reference separately from team outcomes.
Project-specific validators remain opt-in to that contract, never universal ASR
rules. No hard-coded four-arm/eight-seed/33-model sequence in the core. Scientific
changes require explicit prospective protocol revision, not hidden evaluator edits.


## Complete research communication records

Retain the full recorded research conversation, not only final reports or curated
summaries: project/human instructions, role inputs and visible outputs, directed
messages, tool requests/results/errors, revisions, delivery receipts and lifecycle
interventions. Associate records with actors, sessions, tasks and trials, retaining
native timestamps where available and explicit source hashes. Never silently
truncate or replace missing originals with a retrospective summary. Export immutable
indexed archives; active prefixes, absent records and redactions must be explicit.
Keep raw native originals in the restricted run store. Credentials and private
model reasoning are not public communication artifacts; mark export redactions.
Raw provider stderr is currently not retained, and external developer-chat history
is not automatically exported: disclose those limits instead of claiming complete
historical coverage. Do not mutate frozen project materials to add new guidance;
record new human requirements via the existing Control guidance path.


## 面向人阅读的文档

所有交给人类阅读的报告、说明、评价请求和进展总结使用中文、说人话。先说明
做了什么、结果、限制和下一步；少用缩写及内部术语，必要术语解释含义。代码、
稳定标识符和机器证据保留原样。冻结英文原稿不可改写，提供标明来源的中文
阅读版本；不得为翻译或整理报告重复实验。此要求同时适用于研究组织的交付。
