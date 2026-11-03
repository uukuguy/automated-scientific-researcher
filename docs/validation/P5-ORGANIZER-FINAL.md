# Organization report — final design handoff

Run `research_ea8d744abd5e4a31bc913d1564f12528`; project `organization-0518e6ccecc2`; upstream Experiment 1.

## Outcome

Produced a source-grounded diagnosis, a precise prospective experiment, an **UNTESTED** static-acquisition/provenance prototype, Worker audit, Organizer cross-review, and Lead corrections/disposition. Organizer inspected the revised artifacts and closed direction `utility-first-acquisition` at revision 3, organization seq19. This closes design work, not the numerical research question or the run lifecycle. No code was executed, no labels generated, no model trained, and no numerical improvement or reproduction established here.

Recommendation: test whether target-only allocation suffices before adding iterative acquisition or solver-recovery machinery. Revise the human's suggested two-layer architecture to **proposal allocation -> independently checked labelling -> unchanged fitting -> joint ID/OOD utility evaluation**, with provenance throughout. Operational-feasible-region discovery is a separate objective; it must not silently exclude this client's equation-valid but operating-violating samples.

## Contract, evidence and organization

Read CLIENT-BRIEF.md, CLIENT-TASK.json, TARGET-METHOD.py, P4-SAMPLER.py and both P4 reports. Recovered state/history on each wakeup; complete organization history inspected incrementally through seq18 before closure, with has_more=false. Contract r1 permits organization/design only, no hidden assets, new labels, execution or training. No additional guidance was returned; directed review instructions were incorporated. Human capacity r1 permits two Leads and two Workers; only lead_1 and worker_1 were needed. No department/topic was assigned by the host.

Trajectory: organizer invited independent direction formation (seq7); lead_1 proposed utility-first acquisition (seq8–9); organizer inspected its actual proposal and activated it (seq10). Lead assigned bounded source-contract audit to worker_1 (seq12). Worker started and completed its own task (seq15–16), preserving actual audit evidence. Organizer independently reviewed actual drafts plus audit and returned substantive corrections (seq17). Lead inspected both reviews, revised source/docs and returned a final disposition (seq18). No acknowledgement loop or slot-filling second direction was needed. Worker task completion is an author claim; inspection of its artifact establishes useful review text, not test execution.

At final session entry, state reported 75479 ms walltime available, 240000 reserved, 210 tools and 97 turns available; attempts/execution remained zero. These are a receipt at entry, not final consumption or permission to experiment. No lifecycle/process-exit or final budget-release claim is made.

## Source-grounded diagnosis

- TARGET-METHOD.make_scenario applies three synthetic bus-index group Pd/Qd scalings and fixed synthetic nonreference Pg dispatch. This is not a feasibility certificate.
- features/fit use ten quadratic columns, equal-row ridge 1e-10 and an unpenalized intercept. Data selection changes the fitting distribution while the hypothesis class stays fixed; utility need not improve monotonically with more OOD rows.
- P4-SAMPLER.main allocates 32 target-neighborhood/16 bridge/16 global coordinates per mixed batch. Acquisition reads diagnostic coordinates, not labels; its separate audit does read labels. It is not demonstrated active learning or operating-feasible-region discovery.
- Historical reports describe about 83.23% target RMSE reduction with about 11.02-fold ID RMSE increase, still within the original absolute allowance. They preserve mixed101's failed development ID guardrail and global/ID control failures. This pilot read those reports; it did not inspect the underlying numerical JSON/replay/raw evidence or reproduce their numbers. No component ablation or difficult-solve bottleneck is established by supplied evidence.
- Reports describe equation-valid labels with operating violations and unassessed thermal limits. Solver convergence, equation residual, preserved input, operating feasibility and training utility must remain distinct. Failed solve does not prove infeasibility.

`shared_findings/` was initially empty and later received snapshot indices. Inspected `8_r1_organization-0518e6ccecc2.json`: finding_type=snapshot, empty asr_evidence, explicitly not a numerical result, pointing to the revised Lead snapshot below. Snapshot publication is not scientific validation. No historical trial ID is passed off as current evidence; organization evidence_trial_ids remain empty.

## Deliverables and review trail

All paths below are relative to `shared-artifacts/`:

1. **Final Lead package:** `29c1fa7302d7ded1492ce5b7b9b17457f8ad3fe3401c7be2a3587b1354dac262/`
   - `NEXT-EXPERIMENT.md` — prospective protocol v2; SHA256 `e86753380cd077d0fee3e77c201a367b083e1cc9a5275d4e603ccd5f45e529b9`.
   - `acquisition_ledger.py` — untested source; SHA256 `7587e7161c26863df3be96c3376331d44234b37c7da98e391a168aea179fe2fb`.
   - `PROTOTYPE-NOTES.md` — interface/trust boundaries, lossless native receipt adapter specification, unexecuted adversarial specifications.
   - `REVIEW-RESPONSE.md` — Lead's explicit acceptance and limitations for each review finding.
2. **Worker audit:** `e730965b0f94811013965f93676e704119b49ea5bef23875a132cfd83b9dd021/WORKER-AUDIT.md`.
3. **Organizer cross-review:** `a123a99512b8dde7278275b46a5ca75892912796035b9098bb3ce6c941c209ce/CROSS-REVIEW.md` (also retained locally).
4. **Superseded draft:** `fc550140fed0a7a2f919127126cb1bbc70b9b7a8c9ae84306673b2634c80d3b6/`; retained so review findings remain attributable to the actual reviewed source.
5. **Lead-originated proposal:** `309dc5b4bb037e7fff24fd0fc5d3c596e80f9aeb57212362cb12466b8f375ef0/DIRECTION-PROPOSAL.md`.

Organizer read all four final Lead files, not merely the handoff summary. Source inspection confirms visible additions: expected-input hashes checked for every terminal status; available integrity contradictions checked before branching; deep copies and external ledger/manifest pins with re-ingestion/hash rechecks; invalid_label reason distinguished from a genuine solver exception; exact integer attempt count. These are source-level corrections, NOT behaviorally verified fixes. The original Worker review does not retroactively test revised code.

The high draft defect was failure-status admission of an arbitrary self-hashed input without exact scenario binding. The mutation issue was a documented immutable-store assumption, not a demonstrated deployed exploit. Native invalid_label adaptation required preserving check/solution metadata rather than inventing a solver error. All were accepted; no unresolved substantive scientific disagreement was reported. The initial proposal's snapshot/scientific-finding conflation was corrected.

## Proposed next experiment — separately authorized new run only

Freeze original128, topology/dispatch/PV-PQ, equations, features, trainer, masks and joint acceptance rule. Compare four paired replacement arms across eight seeds1101–1108, each with64 attempted slots:

| Arm | Target / bridge / global |
|---|---|
| TT |64 /0 /0|
| BT |48 /16 /0|
| TG |48 /0 /16|
| BG |32 /16 /16|

Shared coordinate streams permit conditional replacement contrasts; BG-v-TT is a package comparison, not intrinsic component causality. Eight paired seeds are not32 independent replicates. There are768 unique augmentation coordinates but2048 explicitly paid repeated arm solves: this is not an efficiency optimum, and no silent caching or cross-arm training pooling is allowed.

Proposed fresh independent panels: development ID256 +target256, final ID512 +target512. Final data remain inaccessible and primary selection freezes first; P4 final outcomes are now development knowledge. Require independent disjointness attestation if unavailable historical raw coordinates prevent local overlap checks. Retain all failures and costs, no retries or replenishment. Integrity contradictions stop the study; panel yield below95% blocks a primary acceptance verdict, and any surviving performance scope remains conditional on valid labels.

Joint rule: target RMSE <=0.8 baseline AND ID RMSE <=max(1.1 baseline,baseline+1e-5 pu), using same-panel original-only baseline. Report absolute and relative ID degradation even on pass. Eligibility requires at least7/8 development seedwise joint passes; rank eligible arms by median target error, then arm name; choose the winning arm's passing seed with lowest target error, then numeric seed. Otherwise freeze baseline fallback and report development objective unmet. No post-final model replacement.

Prospective ceilings:3584 solve slots (2048 augmentation +1536 panels),33 fits, one primary training replay,72 total jobs,2400000 execution-ms and a separately approved walltime allocation. These caps are not an authorization, runtime estimate or power proof. Preserve asymmetric budget exhaustion as incomplete, not a chance to cherry-pick finished arms. Eight seeds support exploratory replacement comparisons, not equivalence; a null result cannot justify simplification without a new powered noninferiority design.

## Remaining gates and next owner action

No imports, syntax checks, unit/integration tests, independent physics verification, numerical reproduction, generalization result, novelty or industrial value were established. The prototype composes supplied static blocks and claimed receipts; it is not a generator, active learner, solver, trainer, evaluator, authenticated database or deployable pipeline. Hashes bind content, not scientific truth or execution identity. Native receipt adapter is specified, not implemented. Authenticated external expected-input generation, immutable pins/store, actual original data, dependency/runtime pinning, canonical target ordering, trustworthy solver/checker/fit executors and an independent fresh evaluator remain mandatory.

Next owner action: obtain separate experimental authorization, implement and test adapters/provenance boundaries using the preserved adversarial specifications, verify frozen input/source manifests, then preregister and execute the locked protocol without changing trainer/thresholds. Test active acquisition only against a locked static reference with all probe/selection costs counted. Study recovery solvers only after documenting a genuine hard-solve population. A supported fixed-model negative outcome remains useful. No further delegation or current-run experiments are requested.
