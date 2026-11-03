# P4: realistic OOD sample generation

Status: active, research framing and contract preparation. P3 is complete.
No new model or experiment budget has been admitted. This document is a planning
boundary, not an executable contract or a claim of scientific novelty.

## Current priority and proposed first experiment

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
  is not broad OOD coverage. Validate downstream utility only if a downstream
  task and frozen external test set are available.

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
