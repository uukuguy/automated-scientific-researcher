# P4 scientific deliverable: simulated OOD augmentation project

Date: 2026-11-03. **P4 complete within the simulated client's scope.** Actual AAR
proposed hypotheses, wrote its sampler/analysis, conducted controlled experiments,
froze its selected model, and interpreted independent final evidence. Developer
work supplied the client, governed tools and independent evaluator. No developer
selected the scientific augmentation recipe for the researcher.

Machine-readable evidence: [P4-RESULTS.json](P4-RESULTS.json). Author's unchanged
report: [P4-RESEARCHER-FINAL.md](P4-RESEARCHER-FINAL.md). Local usable delivery:
[README](../../artifacts/p4-delivery-001/README.md),
[manifest](../../artifacts/p4-delivery-001/manifest.json).

## Outcome and tradeoff

The fixed quadratic surrogate was trained on original128 plus64 new labels,
without changing features, ridge1e-10, equal-row fit policy or acceptance criteria.
Independent scoring used64 fresh ID and64 fresh target-regime cases, inaccessible
to the researcher before model selection was frozen.

| PQ-voltage RMSE (pu) | Original baseline | Frozen selected model |
|---|---:|---:|
| ID | 7.300125027977869e-7 | 8.042635962016063e-6 |
| Target OOD regime | 1.0760772778696295e-4 | 1.8048463257316755e-5 |

Target RMSE decreased **83.23%**. ID RMSE increased **11.02 times** relative to the
baseline, but its absolute increase7.312623459e-6 remained below the predeclared
allowance. Both original predicates passed: target<=0.8×baseline and
ID<=max(1.1×baseline,baseline+1e-5). This is tolerance-based ID retention, not
unchanged ID accuracy. Secondary angle errors show the same tradeoff.
Paired2,000-resample intervals support target-MSE decrease and ID-MSE increase
conditional on these fixed models; they do not measure training-seed uncertainty
or transfer to new shift families.

The exact primary model and frozen training payload were reproduced in a fresh
container before final scoring. This is training reproduction, separate from the
held-out generalization result and not a full reproduction of research discovery.

## Research performed and failures retained

- AAR generated704 fresh labels:576 augmentation samples across mixed/global/ID
  arms and seeds101/202/303;128 probes reserved for development evaluation.
- Nine equal-count augmented fits were compared with the original-only fit.
  Selection was written before augmentation results and frozen before final test.
- Selected mixed202 used32 target-neighborhood,16 bridge and16 global samples.
  Of64 selected rows,60 are outside the original[.9,1.1]^3 box and4 inside; the
  delivery does not mislabel every mixed sample as OOD. Combined training has192
  distinct coordinates and no diagnostic, probe or final rows.
- Mixed101 failed the development ID rule and stayed excluded even though it
  later passed the descriptive final comparison. All six global/ID controls
  failed joint final utility. No post-test model switch or adaptive retraining.
- h1 coverage explanation remains partial evidence, not isolated causation.
  h2 has seed-dependent ID failure; prospective h3 passed its frozen joint rule.
  No mixture-component ablation, optimality or scientific novelty is claimed.

## Trust boundary and physical scope

The independent scorer uses its own standard-library feature/mask/RMSE logic,
not the author's metric implementation. It reconstructs original cases from
frozen raw inputs and checks equations independently. All128 final labels and
704 generated labels passed equation checks. All nevertheless have operating
violations;186 branch thermal ratings per scenario remain unassessed. Fixed
PV/PQ, dispatch and topology restrict applicability. Neither safe operation nor
unknown real-client/industrial benefit follows from this result.

Final ID draws follow Uniform([.9,1.1]^3); target draws follow independent
Uniform([1.2,1.45]×[.85,1]×[1.05,1.25]). This validates fresh examples from the
known target regime, not unseen topologies, contingencies or shift families.
Private final raw rows/seeds were not exported to the researcher or delivery.
Final admission permanently closes further study submissions for this run.

## Actual identities and lifecycle

Run: `research_bb9205963bd144b898d1bc46c4dbf1ad`; actual AAR Experiment1.
Primary: `trial_b1bcc4832d704263b948b1865ef1ea8f`.
Independent final: `trial_8435ec64fb3644778ece38ddaa574620`.
Training replay: `trial_9a8088b82a234aeea6fffdb558b260e6`.
Full hashes, snapshot/prospective-hypothesis binding and report receipts are in
P4-RESULTS.json. All33 immutable execution inventories were rechecked.

Model consumption:1,495,509/1,500,000ms,79/140turns,107/300tools.
Compute:33/40jobs,129,098/2,400,000ms,704/768proposal permits.
All reservations zero; all native sessions exited. Control and actual AAR ORM
both read `completed` after the authenticated finish/projection receipts.
Subscription usage is not a measured monetary charge or an inferred remaining
provider quota. No API-key runtime or paid API fallback was used.

The final native session was **not a clean autonomous closeout**. The first
synthesis hit provider context exhaustion; its transcript and charges remain.
A fresh conversation recovered from durable files within the same research run
and unchanged budget. It wrote and read back the complete report, then hit the
walltime cap before snapshot/finding publication. The controller verified exact
bytes against the actual successful write event, archived the unchanged report,
and published its verbatim conclusion with explicit controller authorship. The
candidate finding does not replace the independent evaluator's artifact.
Context rotation and report-first recovery are currently operator-managed; a
fully unattended long-research lifecycle remains future work.

## Verification and delivery

Combined core/AAR suite and focused final-export tests pass; exact counts are in
P4-RESULTS.json. Separate real Docker checks cover development labels/training,
container isolation, timeout/overflow evidence and final scoring with public-only
engineering fixtures. Actual scientific final evaluation is separately recorded.

The delivery includes selected64 full raw labels, combined192 training rows,
frozen model, exact replay payload, researcher sampler/analysis sources and plan,
independent aggregate results, image manifests and33-trial evidence index.
The original320 client raw files and original fixed trainer remain unchanged.
Large/runtime artifacts stay local under artifacts/; tracked reports contain
hashes and acceptance evidence. P5 organization and Capstone C0–C4 remain pending;
this repository's completion does not prove cross-project delivery or acceptance.
