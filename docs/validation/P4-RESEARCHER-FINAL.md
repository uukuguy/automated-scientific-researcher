# Final research report — upstream Experiment 1

Run: `research_bb9205963bd144b898d1bc46c4dbf1ad`  
Project: `ood-client-ef6293124853`  
Status: research-owner interpretation of completed independent evidence; any published finding remains **candidate**, not an author-issued validation verdict.

## Conclusion

**Objective met on the one frozen synthetic ID/target-regime test.** The prospectively selected mixed-202 model passes both the original client ID-retention allowance and the required >=20% target PQ-voltage RMSE reduction. Target RMSE falls approximately **83.23%**, from 1.0760772778696295e-4 to 1.8048463257316755e-5 pu. ID RMSE increases substantially, from 7.300125027977869e-7 to 8.042635962016063e-6 pu (about 11.02 times baseline), but remains below the allowed 1.0730012502797789e-5 pu. “Retention” means passing that tolerance, **not unchanged ID accuracy**.

This establishes held-out utility for this fixed surrogate and declared target distribution. It does not establish unseen-family transfer, operating feasibility, real-grid benefit, optimality or scientific novelty. A separate training replay establishes exact reproduction only on the frozen selected inputs.

## Evidence and frozen decision

Read sources: `FINAL-TEST-PROPOSAL.md`, `INDEPENDENT-TRAINING-REPLAY.json`, `INDEPENDENT-FINAL-RESULT.json`, effective contract revision 7, delivered guidance, budgets, original hypothesis revisions and versioned `shared_findings/1_r1_ood-client-ef6293124853.json` through `3_r1_ood-client-ef6293124853.json`. The final result declares schema `asr-ood-independent-validation/1`; the replay is a separate receipt, not a final-performance evaluation.

- Frozen proposal snapshot: `919e3cf608e5d3e0daacc97bdda2d1093e7f6379bd0c723fc150386fa6205a7b`.
- **Primary original fitted trial:** `trial_b1bcc4832d704263b948b1865ef1ea8f`; manifest `981f29d98837fafb5de253483e8d75bed65ba41e83420cf51c1856a1c40e3352`.
- **Original-only fitted reference:** `trial_6e19bad026b94c24b339eb7525ba18f1`; manifest `f773d8b40657ca65c62537216591775606c387e807d993a863ed59bbcfd2014e`.
- **Final evaluator:** `trial_8435ec64fb3644778ece38ddaa574620`, attempt `attempt_a34789b5bbb14c5bbc4a5d2cc41da25f`; succeeded and exited; manifest `049e9079e722febf49d9f50cef5e31e06918c82ee35ef3dd18345a6387ce6c13`; protocol SHA-256 `896ab41e376f9f50feb353dff42abb276ccc57a0ffe951285fd4b1849921fe94`. Its assessment is `objective_met_on_frozen_test`.
- **Development synthesis:** `trial_7be0db47db1743f9befcdc9964f4d2d2`; author analysis, not independent validation.

The unchanged quadratic surrogate (ridge 1e-10) was fitted to the original 128 rows plus 64 newly solved rows from `trial_22035fdaffb24d1aadc54502b5e696f0`: 32 target-neighborhood, 16 bridge and 16 global. No diagnostic, ID-development or probe labels entered training. Equal-row fitting, physical case, topology, PV/PQ and dispatch policy were fixed.

Before augmentation results, selection required the exact ID guardrail on both development ID panels and >=20% reduction on fresh target probes, then minimum target-probe RMSE, lexical trial-ID tie break and baseline fallback. Mixed 202 and 303 qualified; 202 won. All ten original fits were frozen for scoring; auxiliary results cannot replace the primary. No new experiment, model switch or refitting was performed for this report.

## Independent final performance and absolute errors

There were 64 labelled final ID scenarios and 64 labelled final target scenarios. Metrics use the original 64 PQ-voltage outputs (pu) and 117 non-reference angle outputs (degrees).

| Metric | Pinned client baseline | Frozen primary |
|---|---:|---:|
| ID PQ-voltage RMSE, pu | 7.300125027977869e-7 | 8.042635962016063e-6 |
| Target PQ-voltage RMSE, pu | 1.0760772778696295e-4 | 1.8048463257316755e-5 |
| ID angle RMSE, degrees | 0.0006512417889280194 | 0.005803101878583946 |
| Target angle RMSE, degrees | 0.09052819051064813 | 0.014963475351853713 |

The evaluator's fitted original-only reference agrees with the pinned baseline to numerical rounding; the client baseline above defines acceptance.

**Prospective joint rule:** target RMSE <=0.8 times baseline; ID RMSE <=max(1.1 times baseline, baseline+1e-5 pu).

- Target threshold: 8.608618222957037e-5 pu. Primary passes; absolute RMSE reduction is approximately 8.955926453e-5 pu (83.23%).
- ID threshold: 1.0730012502797789e-5 pu. Primary passes; absolute RMSE increase is approximately 7.312623459e-6 pu, leaving approximately 2.687376541e-6 pu below the threshold.
- Angle accuracy improves on target but worsens on ID. Angles were secondary, not an added acceptance criterion.

Evaluator paired candidate-minus-baseline scenario-MSE estimates and 95% bootstrap intervals (pu²):

| Panel | Mean difference | 95% interval |
|---|---:|---:|
| ID | +6.415107496327296e-11 | [5.1903550301237566e-11, 7.686977529300802e-11] |
| Target | -1.1253676053522408e-8 | [-1.457586671210631e-8, -8.077490549107295e-9] |

These 2,000 paired test-instance resamples, seed 20261103, are conditional on a fixed trained model. They document target improvement **and ID degradation**; they are not training-seed uncertainty, unseen-family uncertainty, an ID-threshold confidence test or an RMSE-reduction interval. The original point-estimate utility predicates determine acceptance. No worst-case absolute-error or tail guarantee is available from these aggregate RMSEs.

## Controls and preserved failures

All rows below are descriptive final comparisons on the same frozen panels; they did not determine a replacement primary. Values are rounded; complete precision remains in `INDEPENDENT-FINAL-RESULT.json`.

| Fit | Original fitted trial | ID RMSE pu | Target RMSE pu | ID / >=20% target / joint pass |
|---|---|---:|---:|---|
| Mixed 101 | `trial_f67211c4158f424b8bc2bb8d34f50fec` | 9.51210e-6 | 1.97330e-5 | yes / yes / yes |
| **Mixed 202** | `trial_b1bcc4832d704263b948b1865ef1ea8f` | 8.04264e-6 | 1.80485e-5 | yes / yes / yes |
| Mixed 303 | `trial_dd8793bcfc8146bdbf91f921bb392312` | 9.08831e-6 | 1.99124e-5 | yes / yes / yes |
| Global 101 | `trial_812ef849dde24f7196b6c3d1413bf0f9` | 1.85972e-5 | 8.88492e-5 | no / no / no |
| Global 202 | `trial_a1c1bd36e5724050bf0d5ab8b89adc0b` | 1.93676e-5 | 7.99574e-5 | no / yes / no |
| Global 303 | `trial_4077930704074c99998cc049e40f40e6` | 1.90094e-5 | 7.35296e-5 | no / yes / no |
| ID-only 101 | `trial_26a6c2f606a8412eadfb8fe7fee8c4af` | 6.67677e-7 | 1.08779e-4 | yes / no / no |
| ID-only 202 | `trial_1a84f42d9c8c4b94a76f19f294130e16` | 6.98895e-7 | 1.08373e-4 | yes / no / no |
| ID-only 303 | `trial_c0e6cb3d9fe34802b2cc6a1c52e49df6` | 7.06773e-7 | 1.07578e-4 | yes / no / no |

All six matched global/ID controls fail joint final utility. Two global fits improve target error sufficiently but sacrifice too much ID accuracy; additional ID labels alone do not produce useful target improvement. Mixed 101's final pass **does not erase its failed original development ID guardrail** (1.083760225450407e-5 >1.0667833535629609e-5 pu). Only two mixed seeds qualified in development. Global controls failed development joint criteria; ID controls retained ID but failed target criteria. Three final mixed passes are encouraging descriptive seed consistency, not a population guarantee.

## Original hypotheses versus observations

- **h1-coverage-versus-quadratic-bias, revision 1 (prospective exploratory): partially supported.** Original feature audit found diagnostic leverage median 18.2475 versus ID 0.0770, and nearest-training distance median 0.2635 versus 0.0229. Baseline bridge errors across the three batches were 2.42e-5–4.68e-5 pu versus fresh ID 6.55e-7 pu. Targeted mixtures beat equal-count ID controls across seeds in development and final testing. This supports the predicted coverage association and actionable advantage. It does not isolate extrapolation as a causal mechanism or exclude quadratic approximation bias; operating violations are present across regimes, not a unique explanation.
- **h2-mixed-regime-augmentation, revision 1 (prospective exploratory): supported with explicit seed-dependent ID failure.** Development mixed median target reduction was 81.971%; median target RMSE was lower than both matched arms. All three mixed seeds exceeded 20% target reduction, but seed 101 failed one ID panel; no universal seedwise joint success is established. The frozen primary's independent pass supports the selected approach without retroactively changing that exploratory record.
- **h3-frozen-mixed202-final-transfer, revision 1 (prospective confirmatory): supported within its declared scope.** The exact selected fit passes both final predicates. Its roughly 83.23% reduction is consistent with the proposal's approximately 80% expectation; only the >=20% plus ID allowance was the confirmatory threshold. “Transfer” here means fresh samples from the declared target regime, not a previously unseen family.

No new explanatory hypothesis is advanced. Any future claim attributing benefit to one mixture component or proposing a mechanistic explanation from these outcomes would be **post_hoc** and require a new test; the original hypotheses are not rewritten.

## Training reproduction is a separate result

`INDEPENDENT-TRAINING-REPLAY.json` records independent execution of the unchanged trainer on the frozen selected inputs: `trial_9a8088b82a234aeea6fffdb558b260e6`, attempt `attempt_bfff4bd08a414418b02243fa4eb61001`, succeeded and exited; manifest `da5f88d3d26d5372663cdef1e5e1fe2148818e671ae98eaba7c5ee93a327ea9e`. Both model and payload are identical. Original and replay model SHA-256:

`02b4db9c8b1bf4a5c27584720b4d96bfe66a9372239a857271777721942891e6`.

This supports exact training reproduction on these frozen inputs without hidden-test access. It does not independently regenerate the labels, reproduce the entire research trajectory, establish cross-platform robustness or establish generalization. The final evaluator itself makes no training-reproduction claim; that conclusion comes from the separate replay receipt. The replay was not another candidate selected using final outcomes.

## Physical validity, applicability and resource limits

- Final original-equation checks passed for all 128 final scenarios. Nevertheless, **64/64 ID and 64/64 target scenarios are operationally violating and incompletely assessed**. Equation validity and successful labelling are not operating-feasibility certificates; exact final residual magnitudes are not supplied here.
- Development audit recorded 704/704 newly proposed labels as converged, equation-valid and input-preserved, with maximum mismatch 8.70656853991246e-9 pu. All 704 had operating violations; 186 thermal limits per scenario were unassessed. Fixed PV/PQ without Q-limit switching, synthetic dispatch and missing thermal assessments limit any physical application. No safe-operation or deployment recommendation follows.
- Final laws were ID Uniform([0.9,1.1]^3) and target independent Uniform([1.2,1.45] x [0.85,1.0] x [1.05,1.25]). These are fresh held-out samples of the development-informed target regime. No new topology, dispatch policy, physical system, contingency family, real measurement distribution or other unseen shift family was tested.
- Only three sampling seeds, one final panel per regime and one selected replay were examined. There were no mixture-component ablations, sample-efficiency frontier or optimality proof. The baseline already has small absolute voltage errors; a large relative improvement does not establish practical industrial value. Novelty was not independently assessed, and no scientific-novelty claim is made.
- Existing consumption reported before synthesis: 33/40 attempts, 129,098/2,400,000 execution ms, 704/768 sample proposals, 96/300 tool executions and 74/140 turns. Walltime available was zero with 107,680 ms reserved. These are the state receipt's counters, not new measurements or permission to experiment. Development used ten original fits and 704 labels (576 augmentation, 128 probes); the separately recorded replay and final evaluator remain charged and preserved. Earlier 22-input and 45,069,132-byte analysis requests were rejected/deferred before numerical execution; bounded analyses completed without repeating accepted acquisition/training. No numerical work was repeated during synthesis.

The prior candidate development finding and its then-pending-final limitation remain historical records, not overwritten evidence. This report closes that pending comparison using the actual final evaluator while retaining negative controls and ID-regression evidence. Further experimentation is closed under the effective contract regardless of unused numerical counters.
