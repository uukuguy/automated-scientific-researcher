# Limit and recovery audit

Status: reviewed for the current managed P3 profile, 2026-11-03. Required by the user and AGENTS.md. Confirmed material gaps are corrected and verified; explicit legacy and observability limits remain listed below.

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
