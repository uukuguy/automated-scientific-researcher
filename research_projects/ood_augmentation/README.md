# Simulated client: OOD training augmentation

This is a client-side test project for ASR. It supplies the problem, baseline and
acceptance criteria, not a sampling solution. The user explicitly requested that
we simulate a human researcher's actual project and have ASR address it.

The target is a small trainable voltage surrogate on IEEE-118. Its fixed model
uses quadratic features of three synthetic regional demand multipliers. All
voltages and angles are predicted; primary error is PQ-bus voltage RMSE, secondary
error is non-reference angle RMSE. It is a deliberately modest surrogate, not a
claim about the user's unknown production solver or a complete physical solver.

Scenario groups are contiguous bus-index groups, not inferred geographical zones.
Within each group P and Q scale together. Non-reference active generation follows
total demand; the reference generator supplies remaining balance/losses. Labels
come from the calibrated pandapower conversion and pass the independent original-
problem Python equation checker. Operating violations and missing thermal ratings
remain explicit; these labels are for PF-state learning, not a feasible-dispatch
training set. No deliberate label corruption creates the OOD gap.

## Material preparation

Use the existing locked scientific environment:

```sh
environments/scientific/.venv/bin/python -m research_projects.ood_augmentation.project \
  --root artifacts/p4-simulated-client-001
```

The prepared specification has 128 training, 32 ID development, 32 OOD diagnostic,
64 private ID and 64 private target-regime samples. Counts are modest enough for
CPU preparation and to expose a controlled regression problem; they do not imply
statistical power for a real industrial claim. Independent split seeds and exact
coordinates are retained by the client; no final-test seed is in the public pack.
The original training box is [0.9,1.1]^3. The diagnostic regime shifts the three
factors to [1.2,1.45], [0.85,1.0], [1.05,1.25]. A run's distribution/model choices
are frozen before error measurement; no outcome-dependent tuning occurs.

Every proposal, input, solution, independent assessment and failure is saved under
`raw/`. The public pack includes original training/development/diagnostic material,
model weights, case, task and baseline report. `private/` is for the evaluator.
The generator uses a 600-second between-sample preparation limit, recording a
pause and resuming existing samples without re-solving. It is not a hard timeout
on an individual trusted solve; the reference solver has its fixed 20-iteration
limit. A new source version requires a new root. This CLI is trusted developer
preparation, not a service that runs agent-authored code or admits ASR experiments.

The first prepared instance contains 320/320 independently equation-valid labels.
The measured public ID voltage RMSE is 6.678335356298293e-7 pu; diagnostic OOD RMSE
is 9.20150915545494e-5 pu (137.78 times larger). Absolute errors remain small, so
this is a measurable toy generalization gap, not evidence of a severe real-grid
failure. These measurements do not establish that augmentation will help.

## Client request and acceptance

The ASR researcher receives the existing method, data, errors and the request:
produce useful additional training examples that improve performance on fresh
samples from related regimes, without unacceptable ID regression. It chooses its
own diagnosis, hypotheses and augmentation method. The original model architecture,
trainer and formal evaluation rules are fixed, so algorithm replacement cannot
masquerade as data benefit. A future run may explicitly revise that scope.

The first simulated client criterion is at least 20% lower target-regime PQ voltage
RMSE, with ID RMSE no greater than max(1.1 * original ID RMSE, original ID RMSE +
1e-5 pu). The absolute allowance avoids claiming practical harm from microscopic
ID baseline differences. This is an explicit synthetic-client utility threshold,
not an engineering standard or a retrospectively fitted criterion. Report angle
error, training/generation costs and controlled comparisons as well. Diagnostic
labels are for diagnosis, not additional training. Final test feedback must not
steer method selection. Failure to meet the criterion is a valid negative result,
not project success.

## Actual ASR handoff

`integrations.runtimes.ood_intake` invokes the actual pinned AAR owner with pi/Codex
subscription authentication. Its separate `ood-project-intake/1` capability pack
allows state, hypotheses, notes and snapshots, but no numerical submission,
training, final evaluation or evidence-backed finding publication. The effective
Control contract has zero compute allowance. One intake session has 300 seconds,
40 turns and 100 tool activities; this is a reading/diagnosis allowance, not a
long-research default. Standard cleanup headroom and recoverable cap receipts apply.

The launcher copies only public materials to the researcher workspace and checks
an actual macOS sandbox denial of the entire original client preparation root.
This protects private materials for this local intake; it does not claim general
process/network containment. Raw transcripts and OAuth stay in ignored artifacts.

Current missing capability is an admitted scenario-labeling/training experiment
profile. Giving the researcher a brief or receiving its plan does not complete
this scientific project. Keep the run paused with its actual hypotheses/native
history until that capability and its compute contract are ready. Do not reuse
P3's fixed-case numerical tools to produce misleading training evidence.

## First actual intake and delivery corrections

Actual AAR intake completed after a retained network failure and same-run proxy
recovery. It published two hypotheses and snapshotted RESEARCH-INTAKE.md; no
experiment or training took place. Public evidence is in
`docs/validation/P4-ASR-INTAKE.json` and `P4-RESEARCHER-INTAKE.md`.

The researcher found the compact public arrays exceeded the native read tool's
50-KB single-line boundary. `delivery.py` now creates lossless JSONL pages below
40,000 bytes, with source hashes and row counts. The original arrays are unchanged.
`CLIENT-ADDENDUM.md` supplies exact mappings and clarifies the existing acceptance
predicate. Its guidance receipt is stored but not yet acknowledged by the paused
researcher; preparing an addendum is not proof it was read.
