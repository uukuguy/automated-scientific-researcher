# Research intake — upstream Experiment 1

## Identity, authority and status

- Research run: `research_bb9205963bd144b898d1bc46c4dbf1ad`; upstream `aar-experiment:1`.
- ASR project: `ood-client-ef6293124853`; supplied task project: `simulated-ood-voltage-001`. These are different identifiers; do not silently substitute them.
- Effective contract: `client-intake`, revision 1, SHA-256 `aae25e1bede57d8689e563a81271ac14d6ed9a5ff65b946fd2a4936d961913cf`; control revision 3 at intake. Pause and resume commands were already applied; no outstanding guidance was returned.
- Intake-only scope governs. Legacy `case118`/Newton–Raphson variable fields and candidate-interface references do not authorize numerical work. Numerical, training and final evaluation are explicitly not exposed.
- Initial state reported no trials, hypotheses, findings or snapshots; `shared_findings/` was also inspected and empty. No accepted experiment was repeated.
- Budget at initial state read: attempts 0/0, execution_ms 0/0; tools 99 remaining, turns 38 remaining. Research walltime limit 300,000 ms, previously spent 21,486 ms and active-session reservation 278,514 ms. Displayed unreserved availability 0 is not additional compute permission. Provider quota is unknown.

**Outcome of this session: an evidence-grounded design and preserved hypotheses only. No new scenarios or labels were generated, no numerical checks or training were executed, and no improvement or independent validation is claimed.**

## Client objective and fixed boundaries

`CLIENT-BRIEF.md` asks whether additional useful data from related regimes can improve a trained voltage predictor's OOD generalization. The client did not prescribe a sampler. I select the research approach below independently.

`task.json` fixes the original data, model/trainer, equations and evaluation rules. Research may change augmentation scenarios and selection, not feature order, model class, loss/fit policy, topology, or acceptance criteria. Inputs are three synthetic contiguous bus-index groups, not geographic regions; each group's Pd/Qd scales together and non-reference Pg scales with total Pd. Allowed proposal domain is [0.7,1.6] per coordinate. Exact group boundaries and dispatch implementation still need executable confirmation.

Primary metric: PQ-voltage RMSE (pu). Secondary: non-reference angle RMSE (degrees). Task acceptance parameters are 20% relative OOD RMSE reduction, ID maximum ratio 1.1 and absolute allowance 1e-5 pu. The JSON does not specify precisely how the two ID allowances combine; obtain the client's fixed executable predicate rather than invent a favorable interpretation. Diagnostic samples are for diagnosis/design, not a fresh final test. Never train on their labels or disguise them as generated data.

## Materials actually inspected and evidence limits

Read `CLIENT-BRIEF.md`, `task.json`, `manifest.json`, `baseline-report.json`, `baseline.json`, `target-method.py` and `case.json`. Attempted reads of `train.json`, `id_dev.json` and `diagnostic.json` were blocked by the read tool's 50-KB single-line limit (approximately 673, 168 and 167 KB respectively). A subsequent content search exposed each first-row metadata prefix, but not the complete records or coordinate/label arrays. There is no shell, Python runtime, JSON projection or byte-range reader available here. I therefore **have not audited all dataset rows, empirical coordinate ranges, duplication, output order or label residuals**. A smaller/projection-friendly data view is an immediate prerequisite; this is not evidence that the data are malformed.

The first-row prefixes show, as supplied metadata:

| Split / first sample | Solver iterations | Equation valid / inputs preserved | Maximum mismatch (pu) | Operating status |
|---|---:|---|---:|---|
| train-0000 | 4 | true / true | 9.09408909509232e-13 | violated |
| id_dev-0000 | 4 | true / true | 1.6116895305169418e-13 | violated |
| diagnostic-0000 | 4 | true / true | 3.121513792545394e-10 | violated |

These prefixes and their input/solution hashes are provenance metadata, not checks rerun by me. `case.json` exposes baseMVA 100, buses numbered through 118, reference bus 69, PV/PQ bus types, generator setpoints and branch data including zero thermal-rating entries. Missing ratings must remain unassessed, not be treated as proof of thermal safety.

`manifest.json` provides package hashes (not recomputed here), including:
- baseline report: `4b3382ee4b843c55acc5aef3720d127b28dd258c7f9ddaf8a7a5e3bc545994e8`
- original train: `e40355188f87fce3fea509e2f5e70e195168991690a3a1e1aa2cf3b6b91e8638`
- diagnostic: `7f31c6a9ee0ceeb5a5c0810b868488f1e16005a8410c91e66d205046827e1eb8`
- ID development: `9f6985ca843a7bf11b002e906b957d271cf437686b789898554b0b990ded8d74`

The manifest lists the physical case, baseline model and task too, but does not list `target-method.py`. Pin that source and the actual reference/checker/evaluator implementations before execution.

### Supplied baseline, not a reproduced result

From `baseline-report.json`:

| Split | Labelled / proposed | PQ-voltage RMSE (pu) | Non-reference angle RMSE (degrees) |
|---|---:|---:|---:|
| Original training | 128 / 128 | 5.954164271518141e-7 | 0.0005289538307780596 |
| ID development | 32 / 32 | 6.678335356298293e-7 | 0.0005757682326768478 |
| Diagnostic | 32 / 32 | 9.20150915545494e-5 | 0.07760824195082572 |

The supplied diagnostic/ID voltage-error ratio is 137.78147793637015. Absolute voltage error is small in pu despite that large ratio; practical benefit is not established by the ratio alone. The report marks every labelled row operationally violating and incompletely assessed in all three splits. Thus violation presence alone does not distinguish ID from diagnostic; violation severity could still differ and has not been inspected. The report explicitly says it is a measured simulated-client deficiency, not an ASR augmentation result.

## Target method and provisional diagnosis

`target-method.py` uses NumPy and exactly ten features: intercept, three centered linear terms z=x-1, three squared terms, and three pairwise products. `fit` requires at least ten finite paired rows and solves normal equations with ridge 1e-10, leaving the intercept unpenalized. `predict` enforces the feature schema and ten weight rows. `baseline.json` records schema `regional-load-quadratic/1`, ridge 1e-10, training_count 128 and fitted weights.

This is a deterministic global quadratic fit, not a flexible neural surrogate. More data can relocate approximation error but cannot add cubic terms or represent arbitrary nonlinear power-flow behavior. Changing sample count/location changes the effective equal-row fitting distribution. Heavy OOD emphasis can therefore improve the target regime while damaging an exceptionally accurate ID baseline. Broad-domain fitting could also dilute local accuracy. Normal-equation conditioning and feature rank merit checking; they are risks, not observed faults.

Working explanations, not established causes:
1. Covariate/feature extrapolation beyond training support could amplify quadratic approximation error.
2. Smooth higher-order physical response could impose a model-class tradeoff even with good coverage.
3. Feature ill-conditioning, output ordering, reference-angle convention or scenario-construction inconsistencies could mimic a shift and must be ruled out first.

No full coordinate audit is available to choose conclusively among these explanations. No solver failure or operational infeasibility is inferred from surrogate error.

## Hypotheses preserved prospectively

Both predictions follow inspection of existing baseline evidence, but precede any new experiment; they are exploratory, not retrospective claims of success.

1. `h1-coverage-versus-quadratic-bias`, revision 1, SHA-256 `27c79e50c789593d9d7ff669615bcc46e97b1c107029c68acce02f12a939381b`.
   - Predict higher diagnostic feature leverage/distance than ID and higher baseline error on independently solved bridge/target probes; targeted augmentation should beat equal-size ID-only additions.
   - Comparable support opposes the mechanism; no matched-control advantage opposes its actionable implication. Invalid experiments are inconclusive.
2. `h2-mixed-regime-augmentation`, revision 1, SHA-256 `50de7a9c42bbbb33e0d39dac2c3bdf238303a5f0e969761f78199b5856651145`.
   - Predict a 64-label mixture (32 target-neighborhood, 16 bridge, 16 global) achieves at least 20% lower fresh diagnostic-regime development RMSE with the fixed ID guardrail, and lower median RMSE than matched global-only and ID-only controls across three sampling seeds.
   - Median reduction below 20%, an ID guardrail failure, or no comparative advantage opposes the corresponding prediction. Seed disagreement remains visible. Final acceptance needs separate fixed evaluation.

ASR accepted both hypothesis revisions. They are candidate scientific predictions, not validated findings. Any material change to these predictions requires a new revision before associated trials.

## Proposed bounded experiment — NOT executed or currently authorized

### Gate 0: integrity and reproduction

Obtain complete machine-readable split views. Verify hashes; dimensions; bus/group and output mappings; fixed-input preservation; finite values; row IDs; input duplicates across splits; original train provenance; exact sampling distributions; equation/check tolerances and solution-branch convention. Reproduce the supplied baseline with unchanged source, report all metric masks/denominators and diagnose discrepancies before augmentation. Compute per-coordinate ranges, training-support distances, quadratic-feature rank/conditioning and diagnostic versus ID feature leverage. Report error stratification without optimizing against individual diagnostic labels.

### Design selected by researcher

Freeze seeds 101, 202 and 303 and the sampler specification before label generation. For each seed compare original-only baseline with three equal-budget augmentation arms:

- **Mixed-regime (64 new labels):** 32 stratified points in the diagnostic covariate bounding box expanded by 10% of each axis width and clipped to [0.7,1.6]^3; 16 bridge points between original-training coordinate median and diagnostic covariates, with interpolation fractions strictly between zero and one; 16 globally stratified points over [0.7,1.6]^3.
- **Global-only control (64):** stratified space-filling points in the full allowed cube.
- **ID-only control (64):** new points from the confirmed original input-generating distribution. If that distribution is not recoverable, this arm is blocked until an explicitly named approximation is preregistered; it must not be called the original distribution.

Use reproducible randomized Latin-hypercube stratification for nondegenerate boxes and seeded interpolation for bridges. Degenerate coordinate dimensions remain fixed. Deduplicate against every supplied split and generated probe set before solving; do not reproduce diagnostic inputs for training. Diagnostic inputs may inform the neighborhood, but diagnostic labels do not enter sampling scores, fitting, pseudo-labels or reference-label creation. Bounding-box designs can include unsupported combinations and are only a first proposal, not a claim to recover the diagnostic distribution.

Keep all 128 original rows unchanged and append each arm's new labels. Retrain weights with exactly the supplied fit function and equal row contribution; no reweighting, changed ridge, feature expansion, topology change or solver-policy change. This changes the scenario/training distribution only. Reference-solve each new input using fixed physical/dispatch/PV-PQ conventions, then separately equation-check the returned solution and preserved inputs. Retain equation-valid operating violations with flags as the client specifies; never sanitize the task into an easier feasible-only benchmark.

### Probes, comparisons and evaluation discipline

Before fitting, freeze a shared independent development panel of 64 fresh ID-regime and 64 fresh diagnostic-regime inputs, drawn from the confirmed split-generating laws, disjoint from training and all additions. If the diagnostic law is unavailable, probes from the proposed neighborhood only test that declared neighborhood; they cannot establish diagnostic-distribution generalization. Resolve this scope before testing the hypothesis.

Use original ID development as an additional regression check, but do not tune repeatedly on it. Supplied diagnostic errors remain diagnostic evidence. Compare models on identical fresh probes: primary PQ-voltage RMSE, absolute and relative differences, ID guardrail, secondary angle RMSE, per-bus and coordinate-stratified errors. Show each seed, median and range; paired scenario-level uncertainty should resample whole scenarios rather than treating correlated buses as independent. Three seeds and small panels yield limited uncertainty resolution. Freeze the chosen proposal before a separate client-controlled final evaluation; do not redefine final rules or seek hidden labels.

### Cost, stopping and negative outcomes

Proposed initial design requires up to 576 augmentation reference solves (3 arms x 64 x 3 seeds), 128 development-probe solves, nine augmented fits and one original-only reproduction fit. These are requested planning counts, **not approved budget or actual work**. Set a future hard ceiling of 704 solve attempts, counting nonconvergence and checker rejection; no automatic replacement/retry beyond that ceiling. Shared input caching may reduce execution, but log reuse transparently and preserve equal arm budgets. If failures prevent complete comparable arms, report incomplete results rather than silently replacing difficult cases. Record attempted, converged, equation-valid, operationally violating and incompletely assessed counts, label costs, training costs and all unsuccessful proposals.

Stop on unreconciled baseline/mapping discrepancies, data leakage, exhausted budget or invalid comparisons. Failure of the fixed quadratic model to meet the OOD target without ID damage is an acceptable negative outcome, not permission to change the trainer. Coverage evidence without performance improvement suggests, but does not by itself prove, an approximation-bias tradeoff. Failure to converge does not prove physical infeasibility.

## Minimum capabilities and unresolved execution gates

1. Read-only JSON parsing/projection (or pretty-printed/chunked supplied records) and hash verification; exact data schema, coordinate boundaries, output order and split-generation laws.
2. Explicit future contract and compute authorization. Current attempts and numerical time are zero. Available ASR operations here are state, hypothesis publication, snapshot and guidance acknowledgment; no trial submission, training or evaluator execution is exposed.
3. Bounded scenario generation and a pinned reference AC power-flow solver with the client's dispatch, slack, PV/PQ and solution-branch policy; preserved-input and independent equation checks with documented tolerances. Operating-limit reports must retain missing thermal assessments.
4. A NumPy-compatible environment running the immutable target source and original model/data; fixed metric/evaluation implementation including exact ID acceptance predicate and angle convention.
5. Immutable trial/artifact receipts, hypothesis binding, per-attempt costs/failures, deterministic seeds and a client-controlled untouched final evaluation. Read/acknowledge any new guidance before future submissions.

No external execution or literature service was used. The present evidence supports receiving the project and designing a controlled study; it does not establish a causal diagnosis, augmentation efficacy, operational feasibility or a successful final evaluation.
