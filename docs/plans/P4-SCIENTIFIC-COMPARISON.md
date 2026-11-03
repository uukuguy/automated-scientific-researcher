# P4: targeted OOD augmentation for solver generalization

Status: active, simulated client project prepared and actual AAR intake verified.
P3 is complete. A separate 300-second subscription-only intake contract was
admitted with zero compute allowance. Development analysis, labeling and fixed training now use the owning Control
ledger and isolated Supervisor. Final evaluation and resumed model-driven study
remain outstanding; P4 is not complete.

## Actual simulated project and next implementation boundary (D026)

The development agent acts as client: prepares artifacts and criteria, delegates
the problem and supplies experiment capabilities. AAR owns scientific diagnosis,
hypotheses and augmentation design. Do not implement the researcher's proposed
scientific solution on its behalf or label developer preparation an ASR result.

- Prepared 320 real reference-labelled scenarios; all pass independent original-
  equation checks. Public train/ID-development/diagnostic counts are 128/32/32;
  private ID/target-regime counts are 64/64. Operating limits remain partially
  assessed. See `P4-CLIENT-PREPARATION.json` and project README.
- Actual AAR/pi received the public package and generated two hypotheses plus
  a frozen intake note. Its proposed mixed-regime augmentation and controls are
  researcher-authored and untested, not client-prescribed instructions.
- Intake used 216397/300000 ms including a retained 21486-ms network failure,
  11/40 turns and 21/100 tools. Same run resumed via the existing local proxy;
  both sessions exited and reservations are zero. Control and AAR are paused,
  not completed. Public evidence: `P4-ASR-INTAKE.json`, `P4-RESEARCHER-INTAKE.md`.
- The researcher exposed a real delivery issue: native reads reject the large
  compact single-line data arrays. Lossless 40,000-byte pages and a precise client
  addendum now exist without overwriting sources. Guidance is recorded but not
  yet acknowledged.
- Next implement only the needed admitted scenario-labeling, unchanged-trainer
  and independent-evaluation capabilities, with frozen material identities and
  Control accounting. Then resume this researcher's run/hypotheses. Do not use
  the old fixed-case profile or a developer-run augmentation experiment as proof
  that ASR completed the client task. Its proposed 704 solve attempts are a
  request to assess, not an automatically approved compute budget.

## Task meaning and human/researcher boundary (D025)

User clarification: a particular trainable solving method performs poorly on
some OOD samples. The research question is whether additional usable training
samples from similar distributions can improve that method's generalization,
and how to generate those samples. This supersedes generic OOD coverage as the
primary goal. More similar data helping is a hypothesis to test, not a guarantee.

The human supplies this problem-level intent and available target artifacts,
permissions and resources. The Research Lead must translate it into diagnoses,
measurable hypotheses, a definition of relevant similarity, generation methods,
training experiments and independent comparisons. Do not require the human to
choose a sampler, similarity metric, perturbation range or detailed experiment
sequence. Clarify missing external facts rather than delegating research design
back to the human. The real client's exact model/data remain unknown. The user subsequently directed
us to simulate the human client's project (D026), so waiting for external materials
is not the current task. `research_projects/ood_augmentation/` now supplies a
measured synthetic target, checkpoint, training/diagnostic data and criteria.
This demonstrates ASR on a simulated project, not the unknown industrial case.

Three linked research questions:

1. Which OOD regimes expose the target method's weaknesses, and what failure or
   error mechanisms do they share? Use a designated diagnostic set; repeated
   inspection makes it development data, not the final unseen test set.
2. Does training with additional data from those regimes improve performance on
   fresh examples from the target distribution? Separate sample scarcity from
   architecture/optimization/label or numerical problems. Also measure ID retention.
3. Which generator produces usable, diverse training examples in those relevant
   regimes most effectively for the combined generation/labeling/training cost?
   Similarity must preserve the relevant regime, not merely produce near-duplicates.

Keep the target method being improved separate from the trusted label/reference
pipeline. The latter need not be the poorly performing method. Reference outputs
need independent checks; target predictions are not automatically ground truth.
A learned warm start, hybrid method or end-to-end solver may need different
training targets. Do not select labels before inspecting the actual interface.

Freeze the original training-distribution definition. Augmentation samples are
OOD relative to that original set; after inclusion they are training data. The
claim must concern fresh, independent target-regime test samples, with grouping
by shared parent/time episode/scenario lineage to avoid near-duplicate leakage.
Any claim about transfer to additional unseen regimes needs a separate test.

Suggested causal comparison, to be refined by the Lead: original checkpoint;
equal-budget continuation without new data; untargeted augmentation; targeted
augmentation. Match starting checkpoint, training policy and relevant resource
budgets; report both training and generation/labeling costs and repeat uncertainty
checks as appropriate. Do not let extra training steps masquerade as a data benefit.
Final test labels and feedback must not steer the generator or method selection.

Primary outcome: target-method performance on the independent target-regime test
set after training, plus regressions on the original distribution. Sample yield,
physical validity, diversity and coverage are supporting measures. A dataset-only
engineering milestone cannot establish improved generalization or close the full
scientific task. Negative transfer or no gain must be retained and investigated.

## Earlier generation proposal: supporting options, not a selected protocol

The following D024 options remain useful only if they address the observed target
weaknesses. Fixed topology, regional features and local expansion are not imposed
on the research question before seeing its data and method.

### D024 generation options

User steering, 2026-11-03 (D024): record the new-method objective for later;
prioritize realistic OOD sample generation now. The design below is a proposal,
not an admitted experiment. It supersedes the unselected-direction framing below
for immediate work. A useful initial data-generation deliverable need not claim
algorithmic novelty; later scientific contributions still need D023 evidence.

- Define one sample as original grid/scenario inputs, control policy, solved
  state if available, and independent equation/operating assessments. Keep the
  proposal before any dispatch adjustment and record all transformations.
- Establish the reference distribution from existing successful samples and the
  generator that produced them, if supplied. With public case118 only, construct
  an explicitly synthetic reference distribution; never call it a measured
  operational distribution. Fit scaling, feature normalization and OOD thresholds
  on reference/development data only.
- Begin with a fixed topology and a small interpretable scenario space: regional
  load levels/shapes, P/Q relationships and generation mix. Preserve correlations
  and explicit balancing/dispatch constraints. Do not perturb every bus field
  independently or use an unlimited slack generator to hide power imbalance.
- Separate magnitude shifts, spatial-pattern shifts and new combinations of
  familiar factors into named OOD groups. A random train/test split alone does
  not define OOD. Topology/outage shifts are a later profile after input and
  validation semantics are supported. Disconnected cases require explicit policy.
- Compare random/LHS proposals and correlated-profile sampling under the same
  variable envelope, dispatch policy, solver policy and total compute budget.
  A candidate adaptive sampler can propose around verified points toward coverage
  gaps, adjust step sizes from feedback, and restart in separate regions. This
  is a testable engineering starting point, not an asserted novel algorithm.
- Preserve original proposals, repaired/redispatched inputs, all solver attempts
  and outcomes. Recompute OOD labels for final inputs; repairs may move a proposal
  back into the reference distribution. Solver failures remain unresolved rather
  than automatically infeasible. Charge diagnostic restarts and continuation.
- Keep equation-valid/operationally-satisfied, equation-valid/violating,
  equation-valid/partially-assessed and unresolved outcomes separate. Dataset
  inclusion depends on its declared purpose; never discard failure denominators.
- Report unique independently validated OOD yield per compute budget, per-group
  coverage proxies, duplicates, rejection/failure rates and constraint assessment
  completeness. Freeze features, normalization and duplicate tolerances first.
  Retain coverage and yield separately; a high success rate in one easy region
  is not broad OOD coverage. Under D025, target-method training/evaluation is
  required for the generalization claim; without it only generation readiness
  can be reported.

Existing gaps in the table below must be addressed for this experiment: scenario
input profiles, original-input binding, an admitted control/Q-limit policy and
independent checks, plus unseen-data access protection. The present case118
fixture has unassessed thermal limits; do not invent branch ratings or call its
samples fully operationally feasible. Before full feasibility claims, obtain
traceable ratings or explicitly select a documented, separately pinned test case.

Reference implementations to inspect, not blindly adopt:
[GridFM DataKit](https://github.com/gridfm/gridfm-datakit) and
[PFDelta](https://github.com/MOSSLab-MIT/pfdelta).
GridFM's [PF/OPF mode documentation](https://gridfm.github.io/gridfm-datakit/manual/getting_started/)
explicitly distinguishes PF data that may violate operating limits from OPF data.
Pin and verify an implementation before reuse; neither a library label nor its
own validation replaces ASR's independently bound evidence.

## Scientific objective

The user clarified that “find new methods” means substantive research beyond
searching for an existing method and trying it. The longer-term new-method objective therefore targets an original,
evidence-supported contribution in power-grid sampling, power-flow solution, or
their interaction. It does not preselect solver improvement as the right direction.
Novelty is an aspiration to investigate, not a result that the system may fabricate
or a success condition that forces every research attempt to produce a discovery.

The autonomous AAR researcher, the future Research Lead, owns problem formulation,
hypotheses, methodological choices and interpretation. Engineering provides the
experiment and evidence boundaries. A prescribed list of algorithms to try is not
the research plan. Familiar methods, literature search and reproductions establish
prior knowledge and controls; they do not by themselves satisfy the intended
contribution. A useful negative finding remains a valid research outcome, with its
scope and evidence explicit, even when the new-method objective remains unmet.

## Candidate research scopes, not selected directions

| Scope | Possible contribution to investigate | Main comparison requirement |
|---|---|---|
| Sampling | A new sampling principle or mechanism that improves a defined coverage/utility objective | Same solver policy, acquisition cost and sample budget; retain unsuccessful proposals |
| Solver | A new algorithmic mechanism or justified adaptation that addresses a demonstrated failure mode | Same frozen input scenarios, original equations and resource accounting |
| Joint | A justified interaction between sampling and solving | Crossed controls and ablations that separate each component and its interaction |

Do not choose among these only because the existing backend makes one easy.
No particular new algorithm, failure explanation or scientific benefit is yet
established. Public prototype evidence does not establish benefit on unavailable
business cases.

## Research formation before confirmatory evaluation

1. Establish what is already known. Produce a sourced account of the closest
   methods, their assumptions, reported limits and reproducibility. Explain how
   any proposed mechanism differs. “Not found in a search” is not proof of novelty.
2. Diagnose a concrete unresolved problem using available development evidence.
   Separate implementation defects, numerical failure, invalid problem setup and
   physical constraints. P3's six Q violations do not prove solver failure or
   physical infeasibility. A small residual alone is not operating feasibility.
3. Record a hypothesis, proposed mechanism, expected advantage, counterexamples
   and falsification criteria before testing that prediction. Subsequent changes
   append hypothesis revisions; retrospective explanations remain post-hoc.
4. Develop and test methods autonomously within a finite exploratory contract.
   Keep all failed trials and consumed costs. Existing-method controls and code
   generated by an agent do not establish originality. Combinations need a
   substantive rationale and evidence, not merely a new label.
5. Freeze a confirmatory comparison after development: method versions, closest
   relevant baselines, input families, unseen split, selection rule, metrics,
   failure denominators and compute policy. Use ablations to test the claimed
   mechanism where applicable. Fresh unseen instances from a familiar family and
   genuinely held-out families support different claims and must be distinguished.
6. Independently evaluate and replicate selected claims, retaining contrary
   evidence. Report effect sizes and uncertainty appropriate to the design;
   do not infer broad superiority from one success or reuse development feedback
   as held-out evidence. If validation informs further development, retire that
   set from its unseen role and record the next protocol version.

Exploratory scope, data access, immutable evidence and resource limits are set
before exploration. Confirmatory hypotheses and rules are frozen before their
unseen tests. This allows genuine question formation without retroactively
presenting exploratory choices as preregistered discoveries.

## Verified implementation gaps (2026-11-03)

| Current code | Observed boundary | Required before broader scientific runs |
|---|---|---|
| `asr_service/control.py`, `_validate_contract` and `submit_trial` | Exact case118 reference metadata and fixed flat input only | Explicit scenario/problem profiles; frozen input identities checked at admission |
| `asr_supervisor/candidate_wrapper.m` | Loads case118 directly; does not consume arbitrary scenario inputs | Trusted scenario loading and original-input evidence, with a versioned profile |
| `asr_evaluation/replay.py`, `freeze_source` | Requires exact calibration input bytes and validator hash | Verify against the admitted scenario's original bytes, preserving old-profile replay |
| `asr_service/control.py`, `get_reference` and `get_run` | Project-authorized reads; no formal held-out release policy | Keep hidden materials and pre-release results out of researcher-visible references/state |
| `integrations/runtimes/asr-extension.mjs` | File-tool path checks; host researcher process | Verify an OS access boundary for hidden assets; prompt/path restrictions alone do not establish isolation |
| P3 reports | Same-case method replication and material validation | Separate comparative evidence, contribution analysis, ablations and held-out claims |

Do not remove existing hashes or loosen current profiles to make new inputs pass.
Keep old P3 evidence reproducible. Add only the capabilities required by the
selected scientific experiment; do not build a generic platform first.

Read-only verification: `uv run python -m unittest tests.test_control_service
 tests.test_evaluation_replay -v` ran 35 tests, with three explicit Docker skips.
These checks confirm existing admission/material guards, not P4 scenario support.
No new research model, numerical candidate or Docker experiment was launched.

## Contract and resource admission

Once an actionable question and required workload are identified, record:

- Original equations, scenario/control variables and allowed algorithm changes.
  Fixed PV/PQ is the current calibration profile, not a permanent research rule.
  Changing Q-limit policy or controls requires a distinct admitted problem profile.
- Development access, private validation material, exposure policy, frozen input
  generation and manifests. A hash is an integrity commitment, not access control.
- Relevant baseline and comparison rules, including all internal solver attempts,
  warm-start acquisition, training, tuning and failed proposals. Report equation
  validity and operating constraints separately; missing ratings remain unassessed.
- Subscription provider/model, finite model walltime/turn/tool allowances, and a
  separate compute allowance with justified per-attempt resources and concurrency.
  Calibrate limits for the workload; the P3 180-second cap is not a research default.
- Recoverable pause and extension rules under D022. Unknown execution remains
  reserved; no automatic paid fallback or budget reset is permitted.

Do not manufacture a ready-to-run contract with placeholder hashes, presume that
“continue” supplies a quantified execution budget, or spend P3 closeout allowance.
Budget proposals follow the actual research workload, rather than an arbitrary
number of algorithms or experiments chosen in advance.

## Deliverable and completion boundary

Deliver the research question and prior-work comparison, hypothesis history,
reproducible methods, complete experiment ledger, controlled comparisons,
independent validation and a contribution/limitations report. Explicitly classify
outcomes as reproduction, empirical characterization, supported new contribution,
unsupported candidate contribution or negative finding. The report must state
whether the new-method objective was achieved, remains open or was refuted in the
studied scope. Engineering readiness and a polished report alone do not close P4.

Multi-Lead coordination remains P5. Capstone's separate acceptance lane remains
independent. The current researcher must first demonstrate substantive research;
adding agents is not a substitute for that evidence.

## Implemented development slice

`asr_service/study.py` admits versioned analysis/label/fit payloads into the existing
Control ledger and `asr_dispatch`; `asr_supervisor/study.py` uses the existing
fenced Supervisor with an immutable scientific image. No additional scheduler.
Each job binds hypothesis revision and dependencies. Raw labels are streamed and
checked against reconstructed original equations before training. Probe and
author-analysis outputs cannot become augmentation labels. Final-test material
is never loaded by this development profile.

Real Docker tests cover64 labels, unchanged baseline training, one-second timeout,
16MiB overflow and offline/non-root/read-only isolation. See
`../validation/P4-DEVELOPMENT-TOOLS.json`. These are developer tests, not experiments
performed by AAR. The actual intake run remains paused with its original budget.
Next connect same-run continuation and a recorded successor contract, then let
AAR select and execute experiments. Final-test freezing/release and independent
performance evaluation remain required before P4 can close.
