# P5 research tool adapter recovery

Date: 2026-11-04. Actual local engineering verification; P5 remains active.

An explicitly configured `paired_adapter` now connects the preserved research
prototype to the existing `submit_study` tool. Researchers do not call the
low-level Python adapter functions or supply validation verdicts. Control owns
artifact references in its existing database, alongside the original dispatch,
budget and task records. No new experiment scheduler or resource ledger exists.

## Contract and execution behavior

`provenance.paired_adapter` has exactly these fields:

- `profile`: `paired-acquisition/1`, the sole supported trusted adapter.
- `image_manifest` and `image_manifest_sha256`: an authorized pinned build record;
  its image ID must match the study image.
- `group_seeds`: every frozen paired group maps to one distinct seed in the
  team's proposed1101–1108 set. This is a research-profile choice, not a general
  ASR sampling or organization restriction.

The existing human-authorized contract also contains `paired_sampling`. Its
coordinates remain researcher-proposed; this adapter generates no sampler.
Changing/removing adapter configuration after paired submissions is rejected for
new work. Historical requests and accepted evidence retain their original pins.
No arbitrary module import or caller-authored validation code is accepted.

A label admission atomically stores its64-slot preparation, freezes its artifact
reference into dispatch and reserves the existing compute budget. Failed budget
admission rolls these database writes back. Fit admission requires a verified
label bundle and training manifest; a direct service caller cannot bypass it.
The original-only baseline remains supported without the paired-arm adapter.

The Supervisor also binds adapter references into the raw evidence manifest.
After execution, Bridge verifies native evidence and stores the label bundle,
training manifest or actual model binding. If the Bridge disappears after the
process exits, a later state request reconciles the original completed trial.
Queued/running work remains pending; it is not relaunched by reconciliation.

State returns compact counts, hashes and status. It rechecks saved artifacts and
native evidence integrity before returning a cached verified status. Corruption
produces a durable blocked diagnostic, keeps evidence/task/consumption and blocks
dependent training. Missing/corrupt results are not displayed as valid outputs.
Repairing material does not silently retry a blocked check. Replaying the exact
original study request/key explicitly retries verification without dispatching
an already finished experiment. Prior blocked events remain in Control history.

## Actual verification

The final fixture used ResearchBridge, task-scoped admission and the pinned real
scientific container. No manual `prepare`, `ingest` or `bind_fit` calls occurred
in the tested workflow. The test checked that preparation already existed before
the first solver launch, then simulated loss of the tool response after label
execution. A recreated Bridge recovered verification through `state`. A direct
fit submission before that recovery was rejected without reserving compute.

The worker then fitted192 rows: original128 and its64 labels. Repeated original
requests were tested with a dispatch callback that would fail if called; none
reran. Both raw-result corruption and preparation corruption were injected,
reported, restored and recovered through original-key verification replay.
Both final checks were verified. Two real attempts consumed10,007ms and64 sample
permits, with no reservations left. The corruption cases are constructed tests,
not observed scientific failures or evidence loss in a live research run.

Raw fixture: `artifacts/p5-adapter-flow-002`, with Control DB, immutable execution
evidence, check history, final Bridge state, log, archive path mapping and file
inventory. The preceding fixture001 also passed its narrower recovery check and
remains archived. See [machine-readable receipt](P5-STUDY-ADAPTER-FLOW.json).

Full regression:382 tests,357 passed,25 environment skips; explicit real Docker
recovery test1/1passed. Runtime extension syntax passed `node --check`.

Focused tests also cover durable preparation across service restart, budget
rollback, unsupported profile/digest/seed configurations, configuration drift,
failed-process diagnostics and readable state with missing raw evidence.

## Archive inventory correction found by regression

Regression detected that the earlier training-binding001/002 inventory update
had been performed while a raw SQLite read connection remained open. It listed
transient `control.db-shm` and an empty `control.db-wal` that disappeared on close.
Every durable listed file still matched its original hash. The recorded WAL hash
was the SHA256 of empty bytes; no uncheckpointed transactions were omitted.

Original inventories were retained unchanged. Each archive now has
`inventory-correction.json` and `inventory-v2.json`; the tracked training receipt
pins the corrected002 inventory while retaining the original inventory pin.
Tests validate both pins and all durable files. Archive inspection now uses a
closed immutable SQLite connection so it does not create transient files.
This correction changes the inventory description, not scientific results or
original evidence bytes.

## Acceptance boundary

This is the real researcher-tool execution/recovery path, driven by an engineering
test. No LLM selected coordinates, authored a new sampler or made a scientific
comparison in this run. A future model-driven team run still needs its proposed
coordinate generator, prospective contract/budget admission and new evaluation
panels. The completed P4 and P5 design runs remain closed. This slice does not
complete P5, demonstrate parallel execution or establish OOD scientific gains.
