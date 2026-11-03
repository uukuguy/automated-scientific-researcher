# P3 closure implementation and evidence plan

Updated 2026-11-03. Implements the already accepted main design and A8/A9/A12–A14;
this does not change scientific evaluation rules or expand P4/P5 scope.

## Remaining implementation

1. Control owns candidate registration and evaluator admission. Store bounded
   UTF-8 candidate.m content in immutable service artifacts, not agent-selected
   host paths. A contract explicitly enables octave-candidate/1. Existing
   reference-only contracts and replay payloads keep their old semantics.
2. Candidate execution reuses Supervisor fencing. The trusted wrapper invokes
   candidate(mpc) using fixed original case118 data. Mount code read-only, provide
   no host-writable bind, evaluator, credentials, network or Docker socket. Bound
   temporary storage, processes, memory, CPU, time and collected output. Capture
   claims separately from independent equation and operating checks.
3. Control reserves evaluation_attempts/evaluation_ms before evaluator launch.
   Separate evaluation job identities refer to the original trial and frozen
   evaluation reference. Recovery retains reservations until the exact execution
   is reconciled. Settle failed work without refunding consumed cost. Bind the
   actual verified evaluation artifact to Validation; author tool requests cannot
   choose the verdict or publish evaluator reports.
4. Replicate a frozen candidate method in a fresh admitted trial/attempt and
   separate container. Preserve code/input hashes and compare evidence explicitly.
   Material rechecking, method replication and generalization remain different.
5. Keep quota observations sourced and timestamped, including unknown. Local
   finite limits remain authoritative when provider quota cannot be observed.
   Never infer monetary charges from subscription token estimates or switch APIs.
6. Extend pi/AAR tools through a separate declared P3 capability pack. The old P2
   pack must not silently receive candidate/evaluation actions. The model writes
   candidate code, publishes and revises hypotheses from observed evidence, submits
   trials and findings, and reads independently published reports. AAR retains
   the only outer research loop; no task-specific scripted research scheduler.

## Verification gates

- Unit/integration tests: immutable registration, cross-project/role rejection,
  stale execution epochs, duplicate submission, source/code tampering, concurrent
  budgets, unknown quota, retained failure costs and recovery after interruption.
- Real Docker tests: candidate cannot alter original input or evaluator, cannot
  read host credentials/hidden assets, cannot write host directories, and cannot
  exceed configured output/time/storage boundaries without termination. Validate
  actual configuration and negative behavior, not merely requested flags.
- Actual independent replay: run frozen method again under a new identity; retain
  both executions, independent residual checks, operating violations and missing
  constraints. Distinct reports must not turn a negative result into success.
- Real subscription trajectory: use verified pi/openai-codex defaults. Track at
  most 180 seconds model sessions, 20 provider turns, 32 tool calls, 4 numerical
  attempts and 3 evaluations, with finite per-execution limits. These are local
  acceptance limits, not provider quota estimates. No paid API authorization.
- Preserve actual source/evidence hashes, model-selected code and hypotheses,
  version lineage, unsuccessful attempts, tool receipts and budget balances.
  Exercise session replacement/recovery without repeating completed trials.

## Closure rule

Close P3 only when the source changes, focused failures/recovery tests, real
container checks and model-driven research evidence jointly satisfy A8/A9/A12–A14.
A supported negative result is acceptable. A native greeting, mocked execution,
standalone numerical recheck or code installation alone cannot close the package.
Report fixed-profile limits and keep comparative scientific findings/generalization
in P4. Preserve Capstone's separate acceptance lane and P5's pending status.
