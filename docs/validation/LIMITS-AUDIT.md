# Limit and recovery audit

Status: reviewed for the current managed P3 and P4 profiles, 2026-11-03. Required by the user and AGENTS.md. Confirmed material gaps are corrected and verified; explicit legacy and observability limits remain listed below.

Every inventory row records scope/unit, purpose, default adequacy, exceedance
record/action, recovery and evidence. Acceptance budgets are not production
research recommendations. A forced stop of an unsafe/unresponsive owned process
must preserve the research and its evidence. Unknown execution must stay reserved.

## Verified findings and corrections

- The original P3 acceptance budget of 180 seconds was enough for the scientific
  chain but insufficient for graceful final response/cleanup. The 37ms overshoot
  remains in the original ledger and report. It is not a recommended operational
  research default. A separate recorded closeout revision completed successfully.
- A queued numerical attempt could start after an earlier overrun created debt.
  Commit 58a288b now reuses Control's gate both before claim and before start;
  tests cover both paths. Consumed costs and reservations remain unchanged.
- Runtime recovery may clear a gate while evaluator execution is still unknown.
  Reproduction confirmed and fixed in 4aa7db7 with a shared cross-component recovery check.

## Inventory

The inventory below was checked against source, boundary tests and actual managed execution evidence. Adequacy statements apply to the stated workload and scope.

| Scope / setting | Value and purpose | Default adequacy / handling |
|---|---|---|
| Project model ledger | Explicit research_walltime_ms, turns, tool_executions | No infinite fallback or operational research default; reserve before use, retain consumption. Original 180s/20/32 was an acceptance choice and inadequate for clean closeout. |
| Project compute ledger | Explicit attempts, execution_ms, evaluation_attempts, evaluation_ms | Separate units and reservations. Failed/unknown work is not refunded speculatively. |
| Budget integer representation | Nonnegative integers up to 2^63−1 | Storage-domain guard, not a recommended resource allowance. |
| Numerical/evaluator concurrency | One owned execution per run | Single-researcher P3 calibration; queued work must recheck gate before start. Scale changes require policy and acceptance. |
| Execution lease | 30s default, bounded at 3600s | Ownership/fencing interval, not an execution allowance or retry trigger. Expiry never releases uncertain work. |
| Candidate method revisions | Optional explicit 1..1000 per run | Counts distinct admitted frozen references, including failures. Unused artifact registration does not consume or bypass execution rights. |
| Candidate/evaluation timeout | Requested finite ms; profile max 60s; applicable contract may be narrower | Bounds runaway case118 execution, not all future scientific workloads. Reject incompatible request rather than rewrite frozen experiment. |
| Candidate source | 64KiB UTF-8 single candidate.m | Adequate for bounded P3 method/configuration; larger/multifile methods need a separately admitted profile. |
| Candidate process isolation | CPU1, memory/swap1GiB, PIDs64, /tmp128MiB | Fixed case118 profile. Actual network, write and scratch probes exercised. Captured configuration/exit evidence distinguishes confirmed OOMKilled from unknown internal resource denial. |
| Candidate captured output | 1MiB combined stream | Prevent host-memory/disk flood. External collector stops owned execution; structured configured/observed-at-least byte diagnostics preserve the task and attempt. |
| Independent evaluator isolation | CPU1, memory/swap256MiB, PIDs32, /tmp16MiB | Trusted fixed numerical checker, separately mounted materials. Not a general researcher environment. |
| Evaluator material inventory | 4MiB per material, 16MiB total, 100 artifacts; trusted code cap64KiB | Reject oversized/unexpected material before evaluation; preserve source and explicit failure. Typed size/count diagnostics retain material and the explicit reason. |
| Reference CLI, separate debug interface | 120s default, max3600s; iterations20 default, allowed0..1000 | Historical standalone runner, not P3 managed candidate policy. Iteration termination is a solver outcome, not proof of infeasibility. |
| Reference cleanup / inspect | 20s / 10s | Attempts process cleanup and exit proof; unknown outcome remains unresolved. These are not whole-operation deadlines. |
| Raw evidence publication | 100MiB | Host publication bound, not a live disk quota. Current trusted reference output is small; untrusted candidate uses stronger live capture bound. |
| Numerical tolerance and power limits | Frozen evaluator tolerance1e-7 pu and original grid constraints | Scientific rules, not execution budget knobs. Never relax them to turn a failed method into success. |

| Runtime engine deadline | Explicit per-session allowance minus min(5s, 25%) cleanup reserve | Counts setup/version checks against the claim-derived deadline. Headroom covers cooperative abort, group exit, reader drain and bridge shutdown; actual overrun remains charged, never hidden. |
| Native abort escalation | 1500ms default, configurable up to 3s | A short local flush/abort grace within cleanup reserve, not a research budget. Escalation is recorded, and local exit does not prove remote provider work stopped. |
| Pi RPC transport | 4MiB/record, 16MiB queued bytes, 256 queued records, 100000 total records | Configurable transport protection, ample for this bounded trace; not model context or scientific output quality limits. Overflow yields a structured limit observation and recoverable pause. |
| ASR tool transport | 10s ordinary, 40s scientific call, each bounded by remaining engine time | Bounds waiting, not proof of service cancellation. Accepted request key and uncertain outcome survive; read authoritative state before retry. |
| Context7 | Default8 calls/client (configurable1..100), name120/query2000/ID256 characters, response100000 bytes, socket10s | Bounded documentation slice, not a deep-research allowance. Reports remaining calls, actual/lower-bound size and correction/recovery. No automatic client reset or retry. |
| Crossref metadata | Query512 chars, 1..5 results, response256KiB, title512 chars, 20 authors, name256/given-family128 chars, DOI256 chars; socket5s | Explicit small metadata search. Every omitted/truncated field is labelled; oversized/invalid DOI is omitted rather than changed into another identifier. Not full-text research. |
| Network timeout scope | Socket timeouts and checks between reads | DNS and a single blocking read may exceed nominal client time. Outer runtime observes transport timeout separately; no claim of a hard total network deadline. |
| Codex App Server transport | 30s connection / 5s request defaults; 1MiB/line, 8MiB buffered, 256 queued events, 4096 messages, 32 pending requests | Protocol diagnostic defaults; configurable. Overflow raises with limit details and close receipt; queued prefix stays readable. Raw stderr intentionally discarded for credential safety, byte count retained. |
| Grok diagnostic | 45s total / 42s engine, 8s stages / 30s prompt, 1MiB line, 4096 frames, 4KiB captured reply, 500-char preview | One-prompt connection check, not a research runtime default. Capture overflow and preview omission are explicit; no silent truncation or inferred successful task completion. |

## Verification evidence

- 291 tests in the combined optional-AAR suite; 15 explicit Docker opt-ins skipped.
- 59 combined real Docker checks passed: `ASR_REAL_DOCKER=1 uv run python -m unittest tests.test_execution_limits tests.test_candidate_execution tests.test_evaluation_replay tests.test_managed_evaluation tests.test_supervisor_evaluation tests.test_supervisor -v`.
- Cap, credential and projection regressions include `test_control_limits`, `test_runtime_deadline`, `test_subscription_environment`, `test_p3_finalize`, native protocol, Context7/Crossref and actual upstream ORM tests.
- Fixes are in 58a288b, 4aa7db7, c3ff486, ffa207a, 68f48c2, ddb0509 and ae2d808; source history preserves red/green review findings.
- Actual [P3 reports](P3-SYSTEM-ACCEPTANCE.md) retain the first authentication failure and timeout; a separate read-only 30s closeout settled without forced termination. All original reports and scientific counts remained unchanged, with zero final reservations/debt.
- Independent root checks reverified both original evaluator artifacts after the diagnostic changes. Evaluation tolerance and numerical source pins were not changed.


## Scope and limits of the audit

- Quota remaining at a subscription provider is unknown unless a sourced
  observation exists; finite local budgets are not a claim about provider quotas.
- P3 resource defaults apply to the frozen case118 calibration workload only.
  They are not defaults for arbitrary models, multi-file solvers, large networks,
  GPUs or long-running research. Larger workloads need explicit policy/profile
  changes and evidence, not silent cap increases.
- OS enforcement can prove configured memory/PID/tmpfs restrictions. Docker's
  OOMKilled field can prove an OOM termination. An untrusted candidate may handle
  a PID or scratch-allocation failure internally; a host observer cannot infer
  that event merely from a generic failure. Preserve stream/exit facts and report
  the cause as unknown instead of inventing measured resource usage.
- The historical direct `python -m powerflow_lab.reference` debug entry point
  retains a generic EvidenceError for its post-execution publication cap. Pending
  raw files and identity remain available, but it does not emit the new detailed
  diagnostic schema. It is not the arbitrary-candidate or managed research path.
  Its pinned numerical sources remain unchanged to preserve prior provenance.
  The managed Supervisor wrapper supplies detailed publication-cap diagnostics.
- A Docker metadata CLI timeout does not establish container exit. The owned CLI
  group is cleaned up; the admitted container intent and reservation remain until
  separately reconciled. No lease or subprocess timeout grants retry permission.
- Native Codex App Server/Grok smoke transport limits are diagnostic connection
  limits. Those adapters have not become full AAR research executors; they must
  not be presented as long-research defaults or complete task recovery support.

## P4 simulated-client preparation and intake (2026-11-03)

- Client preparation: fixed320 proposals (128/32/32 public,64/64 private), not an
  open-ended rejection sampler. Every failure counts and is retained. Between-
  sample600s per-invocation deadline pauses resumably; this is not a hard timeout
  on an individual trusted numerical solve. The pinned reference has20iterations.
  This trusted development CLI is not an ASR experiment admission service.
- Intake model ledger:300s total,40turns,100tools, zero numerical allowance. Purpose
  is one actual project reading/diagnosis session, not long research. Failure cost
  retained; same-run recovery used remaining278514ms. Final total216397ms and no
  unresolved reservations. No cap was raised or provider/billing mode changed.
- Actual pi read refused compact data lines above50KB. Researcher reported the
  limitation explicitly; no data were silently treated as read. Lossless public
  JSONL pages now cap each page at40000bytes, below that observed boundary. A row
  above the page cap is rejected with an explicit remedy; no field truncation.
  Source hashes/row counts preserved; final/private data excluded.
- Data-domain multipliers[0.7,1.6] and utility thresholds are explicit simulated
  client task rules, not numerical stability guarantees or global ASR defaults.

## P4 development worker profile (2026-11-03)

These caps authorize no model run. The actual intake contract still has zero
compute allowance. New jobs require a separately admitted successor contract.

| Limit | Purpose and sufficiency | Exceedance and recovery |
|---|---|---|
| 64 proposals per label batch | Bound raw evidence, solve latency and cancellation loss; real full-batch test passes within 60s | Structured admission block before any solve; retain task and continue with smaller requests |
| 300s maximum worker walltime, further reduced by contract | Stop stalled author code/solver; tested at 60s for 64 labels and 1s for timeout | Stop owned container, retain stream/events, publish timeout receipt and actual elapsed cost; no automatic retry |
| 64KiB analysis source, 12 input trial references | Bound request size/dependency fan-in; sufficient for one generator and baseline plus nine fits plus two probe batches | Detailed deferred-request receipt; source and original trials retained, research remains active |
| 16MiB frozen input and 16MiB combined stdout/stderr | Bound trusted collector memory and evidence size; 64 raw labels fit comfortably | Input admission block or externally stopped output overflow; retain bounded raw prefix and diagnostic, never report success |
| 1GiB RAM, one CPU, 64 PIDs, 128MiB temporary storage | Offline single-worker resource isolation; actual labeling/fitting/analysis pass | Docker resource limits remain enforced; OOM flag becomes explicit diagnostic. PID/temp exhaustion surfaces process/worker error, not an inferred scientific failure |
| `sample_proposals` ledger | Prevent a batched job from hiding dozens of solve permissions behind one attempt | Reserve whole batch before dispatch; charge whole admitted count conservatively after launch even on timeout; retain completed/failed rows separately. Unstarted cancellation releases all |
| 335s bridge transport wait for study jobs | Accommodate up to 300s execution plus launch/publication, bounded further by runtime deadline | Existing runtime timeout observation and native recovery apply; retry same key only after reading state, never duplicate admitted work |
| 40,000-byte inline result threshold | Keep routine model responses readable without dropping full author output | Larger output is exported completely to a workspace file and can be consumed by later analysis dependency; native single-line limits may still require analysis-based extraction for a very long scalar |
| 600s image build CLI timeout | Bound developer build wait; measured locked dependency build succeeds | Retain context/log/failure record; timeout does not prove Docker daemon build ended. Reconcile before a new invocation |

Limits combine: 12 dependencies do not guarantee that their raw rows fit within
16MiB. A large combined analysis must request fewer inputs or a reviewed profile
revision. Conservative proposal charges are permits, not a claim that every
reserved solve completed. Actual attempts and partial raw events remain distinct.

### Actual P4 recovery findings

The first development continuation hit the native256-record pending queue after
1,971 consumed events, despite only about1MiB of recorded traffic. This was a
producer/consumer burst, not exhausted research budget. The adapter now applies
bounded backpressure within the existing256-record/16MiB capacities, records peak
occupancy/wait counts, and polls only authenticated run state instead of loading
all trial evidence for every token delta. A full-queue EOF is delivered rather
than silently lost. Individual oversize records, total event count and walltime
still produce explicit limit receipts. Regression tests cover burst preservation,
EOF and hard caps. The actual recovery completed all704 requested labels and nine
augmentation fits without another transport-cap event; original failure cost is
retained.

A subsequent22-input analysis exceeded the12-reference request cap. The previous
policy paused the whole run, closing its next provider permit. This was too broad:
request-shape limits now record `action=request_deferred` without closing research
admission, so the researcher can split the analysis. Project budget exhaustion
still pauses with a receipt. No numerical allowance, queue capacity or dependency
cap was raised, and no accepted label/training job was rerun during recovery.

Independent final scoring allows at most10 fitted-model references and one frozen
protocol. Raw payload retains the16MiB cap; final execution is at most60seconds
within remaining compute balance. A distinct controller-only capability locks
all subsequent study submissions, even if an old development contract is reapplied.
Failed final execution can only retry its identical frozen protocol after exit is
reconciled; completed release cannot be repeated with new models. Synthesis exposes
no experiment tools and caps its session at180seconds/25turns/50tools, bounded by
remaining historical balances rather than a new model allowance.


### P4 context and final reporting limits

The first final synthesis received explicit provider context-window exhaustion,
after accumulated development history; this is not a compute failure. Its7,525ms
charge and transcript remain. Existing per-response40KB projection limits do not
bound accumulated conversation size. No automatic context-rotation guarantee is
made. The original native sessions directory was archived intact with an explicit
recovery receipt, then a fresh conversation recovered from frozen proposal,
aggregate final report, training replay and authoritative state under the SAME
research identity and remaining107,680ms. No model or experiment budget increased. After completion, archived transcripts were also restored to their original paths so historical evidence references continue to resolve.

The recovered session wrote and read back the complete report, then hit its
102,485ms engine cap (102,487ms observed; cleanup headroom retained). Final ledger
is1,495,509/1,500,000ms,79/140turns,107/300tools, with all reservations zero.
The controller verified the successful write-event bytes, archived that exact
report and explicitly published its conclusion as controller archival. This is
not a clean model termination or agent-issued publication. Science was preserved;
the report's lifecycle limitation is public.4,491ms remained and was not used for
another unlikely-to-complete model call. The bounded25-minute allowance was
sufficient for this science result, but insufficient for fully autonomous report
publication with these recoveries; it is not a production default. Future long
runs need measured context monitoring and an explicit publication/cleanup reserve,
not silent retries, truncation, allowance increases or paid fallback.

### P5 organization record limits (foundation only)

- Human-published `policy/capacity` sets positive max_active_leads and
  max_active_workers. There is no implicit default/compute grant. The suggested
  initial2/2 is a small organization experiment, not proven production capacity.
  Count distinct owners of active directions and worker assignees of in-progress
  tasks; limits constrain these declarations, not unimplemented runtime launch.
  Same-transaction checks prevent simultaneous requests exceeding capacity.
- A member cannot hold two in-progress tasks. This prevents ambiguous execution
  ownership in the first serial-per-member model; contention returns
  member_already_working. Ownership/revision conflicts retain original work.
- Each document is at most65,536 UTF-8 JSON bytes: enough for an assignment,
  explanation and evidence identities, not bulk code/data. Oversize requests
  create an organization_request_deferred event with requested/limit, record/key,
  content hash and artifact-based recovery; nothing is silently truncated.
- History pages default100, maximum500 records, bounding database/response work.
  At the document cap a maximum page can still approach32MiB plus envelopes; this
  is not a recommended model-context size. Callers may choose smaller pages.
  next_after/has_more explicitly expose remaining records. Overlarge page requests
  record a recoverable rejection and leave all history intact.
- No new timing/retry limit or model budget is introduced. Existing transport and
  runtime limits still apply. Actual long-session context behavior remains a P5
  runtime-binding concern; paginated records alone do not solve context exhaustion.

Tests cover concurrent direction activation, duplicate task claims, capacity
rejection/restart, document and page boundaries, role spoofing, terminal history,
HTTP authentication and explicit bridge capability gates. No actual multi-role
model execution is claimed by these checks.

Organization role binding preserves the existing single-active-runtime-per-run
limit. First role integration is serial: active-direction/worker declarations are
not evidence of model concurrency. A new role claim cannot escape an unresolved
prior process or obtain a new budget ledger. Failed setup costs remain charged
when a different member subsequently reserves time. No new session timeout or
automatic retry is added; old membership revisions and tool profiles are rejected
before admission. Parallel model execution needs a separate reviewed integration.

### P5 paired research adapter (2026-11-04)

The optional paired-acquisition/1 adapter keeps the team's64-slot arm and
1101–1108 seed set as explicit scientific-protocol constraints. These are not
new default ASR capacity limits. Its fixed original128 and IEEE118 checks bind
the proposed training comparison; other methods remain possible without this
project-specific adapter. Violations reject preparation before execution and do
not resize, truncate or resample. Ordinary study batch/payload/budget limits
continue to use their existing detailed diagnostics and owning ledger.

No new runtime timeout or automatic execution retry was introduced. Failed
processes keep their consumption; blocked verification records code/message and
recovery in the same Control event history and state projection. Replaying the
original request only retries verification of completed evidence. Artifacts stay
outside model output; state returns hashes/counts/diagnostics. Full raw evidence
and immutable adapter JSON remain in the authoritative local stores.


## Completion-first subscription correction (2026-11-04, D029)

Actual implementation001 disproved adequacy of the old20-minute aggregate and
four-minute role windows: a reviewer delivered computation but timed out during
reporting, and Organizer had only38.515seconds after normal review/handoff.
Organization direction closed, but report refresh and four deliveries remained.
These are operational interruptions, not scientific failures. User explicitly
requested complete execution rather than strict controls except clear anomalies.

| Setting | Old → current | Purpose and evidence |
| --- | --- | --- |
| Aggregate model walltime | 20min → 4h | Broad unattended-run failsafe; not an expected duration. Stop on complete delivery. |
| Role model walltime | 4min → 30min | Allows inspection, reasoning, tool work and report publication in one session. |
| Aggregate turns/tools | 160/320 → 1600/3200 | Generous runaway-volume ceiling; counts alone do not establish no progress. |
| Role turns/tools | 40/80 → 200/400 | Allows substantial coding/review; detailed runtime records remain. |
| Analysis compute | 12 attempts,60s/job,720s total | Unchanged case-specific verification allowance; actual2jobs/3.407s, no exhaustion. |
| Labels/fits | zero labels; contract analysis-only | Scientific scope, not runtime economy; model extension cannot change it. |
| Capacity | two Lead/two Worker slots,serial execution | Unchanged ownership/concurrency boundary. |

Policy: integrations/runtimes/organization-implementation-limits.json.
Explicit revision: integrations.runtimes.organization_resources publishes and
applies a new Control contract only while paused, healthy, exited and unreserved.
Old policy/contract/balances and reason persist before change; interrupted receipt
publication replays the original API commands. Budget consumed does not reset.
Compute, capacity, billing, source and evaluation scope cannot change through
this model-only path. Recovery is explicit, never automatically granted.
Exact original source bytes are required when local JSON was reformatted.

Emergency ceilings still pause and reconcile; no claim of adaptive/progress-aware
anomaly detection is made. Genuine no-progress/repetition detection and proactive
durable handoff before emergency deadlines remain implementation work. Existing
unknown-process fencing, isolation/resource limits, provider failures and raw
failure retention continue. Default adequacy beyond this observed workload still
requires real evidence, not just larger numbers.


## Project-directed run policy (D030)

organization-project-limits.json declares4h aggregate/30min role model failsafes,
1600/3200 total turns/tools and200/400 per session;256 scientific tasks,4096
label slots and7200000ms cumulative local compute. Per-job60s is the observed
small case118 batch envelope, not a universal researcher deadline. Counts are
capacity, not a mandated experiment schedule. Existing Control reserves and
retains all failed consumption; profile payload/batch restrictions still apply.
The project brief reads current state instead of repeating stale20min/4min values.
No paid fallback, automatic retry or hidden-evaluation grant. User continuation
under D030 authorizes the configured new project run, not old-budget reopening.


## Communication retention (D031)

The organization event writer adds sequence and UTC collection time, writes the
complete event payload and flushes/fsyncs every event. It adds no truncation or
retention-size cap. Existing native transport ceilings still apply and preserve
explicit limit/recovery records. An I/O failure propagates; it cannot silently
turn into a successful archived session. The archive retains explicit incomplete
JSONL/session/source gaps. Export failure is reported in the run receipt and
requires archival recovery only, never a repeat of scientific computation.

Archives are distinct non-overwriting checkpoints, with source hashes and an
inventory. The current exporter reads each source into memory; it has no tested
unbounded-size guarantee or automatic retention/deletion policy. Original native
journals remain in the restricted run directory; raw provider stderr was already
omitted for credential protection and cannot be reconstructed retrospectively.

## Workspace snapshot correction (observed during project001)

The old1MiB ceiling rejected the actual2,281,626-byte utility synthesis, and its
plain snapshot_too_large error omitted size/purpose/recovery details. This was an
inadequate general sharing default. The new16MiB ceiling bounds in-memory snapshot
publication and copies to role workspaces while allowing observed model/report
bundles. It is not a scientific computation allowance or a retention limit.
41–62MB raw analysis evidence remains in the immutable experiment store; use exact
references or an explicit external export instead of repeating computation.

Oversize requests now include limit, observed-at-least requested size, source
relative path, purpose and recovery instructions. Control records a recoverable
request_deferred event without pausing the run or changing its budget. Originals
remain untouched. Two tests reproduce the prior2.3MiB rejection and verify detailed
oversize recording/preservation. An actual byte-identical2,281,626-byte export is
at artifacts/p5-snapshot-capacity-001, snapshot6eaa428654e3b2de9a03635b8ef3a27f79c8ae970085fea052b6816e4629c001.
This external capacity check was not injected into the live team; its process
loaded the old ceiling, whose actual failures remain in the research record.
