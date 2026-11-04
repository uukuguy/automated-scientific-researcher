# P5 paired sampling and prototype adapter

Date: 2026-11-04. Engineering verification; P5 remains active.

## Governed execution

An optional `provenance.paired_sampling` contract freezes named groups, unique
coordinate blocks and arms. Each arm lists the blocks it will solve. Only
explicit shared blocks within the same group may reuse coordinates across arms.
Public data and previous ordinary label/probe coordinates remain excluded.
Every arm is submitted once, using `paired_batch: {group_id, arm_id}`; exact
coordinate order and augmentation purpose must match the contract. Replaying
the same request returns its original receipt. A different request key cannot
replace a failed or cancelled arm. No automatic resampling or retries occur.

Each actual arm reserves and consumes its own attempts/time/sample budget.
Contract publication rejects insufficient proposed sample/attempt allowances
with configured and requested amounts, recovery guidance and a durable event;
it does not interrupt the current run. Existing per-batch 64-sample limits
still apply. No live 3584-slot scientific budget was authorized by these tests.
Once a paired dispatch exists, subsequent submissions reject a changed or
removed paired protocol. Existing accepted jobs retain their frozen protocol.

The dispatch, compact researcher projection and Supervisor manifest retain the
protocol hash, group, arm and slot IDs. Manifest substitution is rejected.
Training may use one paired arm, or no augmentation for the baseline. Pooling
arms is rejected. This controls data membership, not scientific efficacy.

## Actual checks

- Seven admission tests cover shared reuse, independent reservations, idempotency,
  cancelled-slot preservation, protocol changes, wrong coordinates/purpose,
  collisions, rejected-budget diagnostics, legacy overlap and mixed-arm training.
- One explicit real Docker test passed: two identical coordinates were solved
  independently, consuming two sample slots and two attempts. Both labelled
  successfully. Mixed-arm training was rejected; a single-arm fit used 129 rows.
  Tampering with a manifest's arm identity was rejected.
- Image: `sha256:cd5dc68c73d6c397c838dff732111ee72d90bb5161243690ca3d12ea06a90012`.
  The final fixture, Control database, raw evidence and adapter ledger are archived
  under `artifacts/p5-paired-execution-checks-002` with an inventory. They are
  engineering evidence, not a published scientific comparison.
- Five prototype/adapter tests passed. The exact team source hash was checked;
  its static plan produced 256 slots from 96 distinct supplied coordinates.
  A previously archived real numerical row was revalidated and ingested.
  Archive inventory hashes were checked before use. The row remained equation
  valid, operationally violating, with 186 thermal limits unassessed.
- Altered targets, inputs, claimed validation and validator source were rejected.
  Constructed exception and equation-invalid fixtures retained slots and costs;
  extra attempts and missing terminal receipts were rejected. These negative
  fixtures are mechanical tests, not newly observed solver failures.

## Remaining boundary

The trusted adapter reconstructs expected inputs without reading solver outputs.
The archived-row test reconstructs an input retrospectively. The real paired
container test additionally writes the expected-input hash map before either
solver starts, then ingests both native rows through the adapter and prototype. Each reconstructed input
matched the archived native input exactly, and AC checks were recomputed from
raw matrices rather than trusting reported residuals.

Evidence authentication and externally frozen pins remain the caller's job.
Model-driven dispatch through this adapter, complete paired training/model
binding, fresh held-out evaluation and scientific comparison remain outstanding.
No sampler novelty, active learning, OOD benefit or P5 completion follows from
these checks. Original P4 results and the completed P5 design pilot are unchanged.

## Preserved adapter failure and correction

The first adapter/container fixture (`p5-paired-execution-checks-001`) failed
after one successful numerical solve. Container Python reported residual
3.9470765451502593e-13; host uv Python independently computed
3.948332333872848e-13 from identical matrices. System Python reproduced the
container value. Requiring bit-identical full validation dictionaries was an
incorrect cross-environment assumption. Both verdicts satisfied the unchanged
1e-7 equation tolerance. The adapter now recomputes acceptance, checks matching
discrete verdicts, and preserves both complete reports. It does not loosen the
physics tolerance or trust the reported residual. A regression test covers
nonidentical residuals; input/target/verdict contradictions still reject.

The failed fixture, consumed attempt and raw evidence remain intact. A separate
explicit engineering fixture (`002`) passed the full two-arm/fit/adapter path.
Logs: `/tmp/asr-paired-docker-tests.log` and
`/tmp/asr-paired-docker-recovered.log`. No automatic retry was added to ASR.

Full regression: `uv run --extra aar python -m unittest discover -s tests -v`
ran367 tests,344 passed,23 environment skips; `/tmp/asr-paired-final-tests.log`.
Runtime extension syntax passed `node --check`. These checks supplement the
explicit real Docker run; skipped tests are not counted as passed.

## Full-arm training correspondence (2026-11-04)

`training_adapter.py` now derives all prototype contract pins from frozen public
materials, an externally pinned scientific build manifest, matching local source
files, fixed fit policy and explicit measurement masks. The protocol hash uses
Control's canonicalization, including Unicode group names. Build/source mismatch,
public-coordinate overlap, incomplete arm and altered original-row status reject
before preparation. Build-manifest authentication remains the caller's duty.

The explicit real task-bound fixture `artifacts/p5-training-binding-002` saved
64 expected inputs before dispatch. ResearchBridge submitted an assigned worker's
label task, all64 native slots were independently checked, and a pinned bundle
and training manifest were saved before fit. After closing the label task, the
same worker claimed an assigned fit task. The unchanged pinned worker trained
original128 plus this arm's64 labels. Two attempts consumed10,173ms and64 sample
permits; no reservations remained. The actual model's training_count was192.

The adapter reads completed evidence through authenticated Control access,
checks manifest/request/arm/image bindings, matches the exact label dependency,
and compares every native augmentation row with the checked ledger hash. It
then verifies ordered x/y agreement between native and prototype representations,
original128, label counts and fixed model shape/policy. The receipt binds the
actual model, training hash, native payload, worker source and both trial
manifests. Different native/proposal sample IDs remain in their original evidence.
Changing a training target is rejected even if the caller recalculates its hash.

A constructed negative fixture kept one failed slot and its cost while yielding
63 augmentation labels and191 training rows; no replacement was generated.
This is a mechanical negative test, not a new observed solver failure.

First full-path fixture001 stopped after64 successful labels because the test
script used an unsupported pending task state. Control rejected it; no fit was
launched. Its database, labels and attempted-path log are preserved. The test
script was corrected to close the first task and assign/claim the second. No
production task transition rules changed. An earlier red test intentionally
reached the then-missing ingestion function; its disposable fixture generated64
labels and did not fit. It is not included in the archived002 budget totals.

Full regression:374 tests,350 passed,24 environment skips. Explicit real Docker
full-arm test1/1passed. See [machine-readable receipt](P5-TRAINING-BINDING.json).
Both archived fixtures include raw evidence, source records, preparation,
produced bindings as applicable, logs, relocation maps and file inventories.
Historical absolute DB paths are preserved; archive copying is not recovery of a
live run. Tests used explicit local compute fixtures and made no model calls.

This proves the full-arm execution correspondence, not independent training
replay, OOD improvement or autonomous team science. Research-runtime integration
must persist externally pinned artifacts at each boundary and supply genuinely
admitted new runtime/compute budgets. New panels and the team's full eight-seed
comparison remain unexecuted; P5 stays active.
