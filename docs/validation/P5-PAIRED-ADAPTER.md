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
