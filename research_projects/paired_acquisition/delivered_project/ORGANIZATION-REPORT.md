# Organization report — bounded exploratory delivery

Run `research_2fdee65a1c2f4bd5b107bfc388469d8d`; project `organization-97ad1aee4ff4`; upstream Experiment 1.

## Conclusion

**Target-only augmentation was useful on the researcher-visible development panels; formal independent client success remains unestablished.** At equal 64 new proposals per fit, target-only passed the original joint public utility rule in 4/4 sampling replicates versus 1/4 mixed replicates. Diagnostic PQ-voltage RMSE medians were9.61156224304887e-6 and2.0307460741472068e-5 pu, respectively. These are four unpaired replicates on the same known-regime public32-ID/32-diagnostic panels, not a population reliability estimate, component-causal result or fresh hidden evaluation.

Frozen selected target4104 reduced diagnostic RMSE **90.2345%**, from9.201509155430224e-5 to8.98572253292635e-6 pu. ID RMSE **worsened 11.4468×**, from6.678335356296072e-7 to7.644552142635415e-6 pu: absolute increase6.976718607005808e-6. It passes the absolute ID allowance, not unchanged-ID-accuracy retention. ID angle error also worsens. All negative outcomes remain reported below.

Organizer accepted the independent-role review and closed `target-versus-mixed` r3 at organization seq29. Both tasks are completedr3. This closes the bounded direction, **not** independent acceptance, full artifact export or research-run lifecycle. No further numerical work is requested merely because global quota remains.

## Fixed client and scientific ownership

The unchanged synthetic IEEE118 client uses three contiguous bus-index Pd/Qd multipliers in[.7,1.6], prescribed nonreference Pg scaling, fixed topology/PV-PQ, original128 rows, ten quadratic regional-load features, equal-row ridge1e-10 with unpenalized intercept. Only scenario allocation changed; equations, controls, trainer and acceptance did not.

Joint primary rule: target PQ-voltage RMSE<=.8*baseline AND ID RMSE<=max(1.1*baseline,baseline+1e-5 pu). Angles are secondary. Current same-panel thresholds: diagnostic7.36120732434418e-5; ID1.0667833535629609e-5 pu. Baseline is the current original-only fit, not historical final metrics. Original public baseline-file equality is unavailable and not claimed.

No scientific topic/design was assigned by the host. Organizer invited Lead-owned scoping and independent source audit (seq7–9). Lead_1 proposed this direction (seq10), prospective exploratory hypothesis `organization-97ad1aee4ff4/target-versus-mixed/r1`, and plan/source snapshot `bf39df6f2e7f0e29dd8aead01583c6dc17297455ff93818388999ff3c6a35594` before results. Organizer activatedr2 seq13; Lead_2 audited rather than creating an unnecessary second topic; Workers were not needed. Capacity policyr1 permits two Leads/two Workers; role sessions were serial.

Lead deliberately replaced the optional historical paired four-arm design with two independent packages: target-only64 LHS points seeds4101–4104; mixed32 target/16 bridge/16 global points seeds5101–5104. Target law is documented rectangle[1.2,1.45]x[.85,1]x[1.05,1.25]; global is[.7,1.6]^3. Bridge interpolates from original-train coordinate median to independently generated target anchors. Fixed streams/order, six-decimal rounding and no resampling/replacement. All512 coordinates froze before labels and were screened against exact/rounded public coordinates and each other. No public evaluation labels entered training/generation, no cross-arm pooling. Known public laws and historical outcomes informed design, so evaluation is exploratory.

Hypothesis predicted target-only>=3/4 public joint passes and median diagnostic RMSE no worse than mixed. Both observations hold within that scope. Four seeds do not establish equivalence, universal dominance or isolated bridge/global necessity. No mechanistic or novelty claim is advanced. Supplied P4 success remains attributed historical development knowledge, never fresh evidence in this run.

## Complete public outcome table

Values rounded for display; full precision/ratios/margins/scenario errors are in the existing synthesis artifact. Primary voltage RMSE is pu; angles are degrees.

| Fit | ID voltage | Diagnostic voltage | ID angle | Diagnostic angle | Joint rule |
|---|---:|---:|---:|---:|---|
|original-only|6.6783353563e-7|9.2015091554e-5|.000575768233|.077608241951|no target gain|
|target4101|7.1070376505e-6|9.8266076964e-6|.005993095361|.008242365958|pass|
|target4102|7.4165356190e-6|9.3965167897e-6|.006241036070|.007925474621|pass|
|target4103|6.9088125927e-6|1.0007156455e-5|.005839337141|.008427709143|pass|
|**target4104**|**7.6445521426e-6**|**8.9857225329e-6**|**.006445882132**|**.007595248568**|**pass**|
|mixed5101|1.1206468094e-5|1.9725433281e-5|.010592214607|.015786941631|fail ID|
|mixed5102|1.4106280753e-5|1.6474354913e-5|.010389824880|.013497388431|fail ID|
|mixed5103|1.5376334271e-5|2.3944899048e-5|.014379296905|.020577752726|fail ID|
|mixed5104|1.0148215273e-5|2.0889488202e-5|.007122140939|.017457078339|pass|

Every augmented fit meets the diagnostic improvement predicate; three mixed ID failures separate joint outcomes. Target-only ID median7.261786634760989e-6 versus mixed1.265637442342959e-5 pu. Selection was fixed prospectively: arm>=3/4 passes eligible, lowest median diagnostic error (target tie-break), then minimum-diagnostic passing seed (numeric tie-break). Only target eligible;4104 selected. Its ID margin is3.0232813929941937e-6 pu. Best-public-seed selection is optimistic; no confidence interval, significance/noninferiority/equivalence test or pseudo-independent bus/seed analysis was performed.

## Execution, negative controls and retained failures

1. **Coordinate oracle:** Lead_2 found r1 self-hash checks did not reconstruct actual draws. No baseline coordinate defect was observed. Revised source independently redraws full rounded arrays from literal seeds/laws/counts and original train median, checking metadata/bounds/order/hashes/collisions. Actual preflight `trial_14ac543babbf48e8904161e0999c20b3` passed12 baseline checks and9 metamorphic observations, including consistent-hash point tampering, changed draw with unchanged metadata, stale hash, wrong order/seed, repeat/delete/poison tests. Candidate `0b421c2571c97183c628cd495bbb684cbaf01f3f97d1f42cbca38e7d4522e3a7`; Python3.12.12/NumPy2.4.6/SciPy1.18.1. Scoped author tests are not generic hostile-input validation or cross-version reproduction.
2. **Labels:** all8 frozen batches solved exactly once,64/64 labelled each;512 proposals charged, no solve failure/invalid label/replacement or operational filtering. Transfer/schema analysis reused frozen arrays without generation/solving.
3. **Failed author audit:** `trial_9242c815b4cb41ec8e0cdcaac67fd60b` exited successfully but returned subset_pass=false:128 controlled-voltage assertions failed. Initial source confused initial busVm1 with online-generator Vg controls. Actual bus1 generatorVg.955 and solvedVm.9550000000000001 support the root cause. The corrected checker uses every active generator's Vg, retaining1e-12 tolerance/reference-angle check. Original/repair row hashes and residuals match; no label/control/threshold changes or exclusions. Old source/output and directed repair seq25 remain. This is a failed assertion repaired and regression-tested, not a failed solve erased by a pass.
4. **Admission recovery:** four-batch audit input17047576 bytes exceeded16777216 limit (`block_3ae45b1bbd8e4034a1113edda4e6f4fd`); rejected before numerical execution. Corrected audits regrouped3/3/2, covering indices{0,1,2},{3,4,5},{6,7} with no missing/duplicate batch. All subset_pass=true/issues empty BEFORE any fit; no new labels. Group-size metadata changed, scientific checks did not.
5. **Integrity:** all512 attempted inputs equal intended fixed-case/x scenarios and hashes; ordered events/coordinates match manifest;236 finite targets equal canonical solution voltage-then-angle outputs; fixed network/dispatch/controls preserved. Host checker evidence and separate AUTHOR nodal residual audits pass<=1e-7. Max author residual9.285355397797318e-9 pu, host9.285352148933798e-9. Author audit is not an independent physics verdict.
6. **Fitting/scoring:** one baseline and8 augmented fixed-trainer fits executed once. Author synthesis uses all9 native models and independently written feature/mask/RMSE calculations; reported scores agree with native public metrics within1e-12 pu/1e-10 degrees, analysis_issues=[]. Masks64PQ/117nonreference angles. This is author cross-check, not external validation or replay.
7. **Other retained limitations/failures:** direct public-path access denial; invalid finding metadata corrected without computation; oversized snapshots; three mixed ID failures; ID deterioration even on pass. All remain in versioned records/artifacts.

**Physical scope:** ALL512 new scenarios are operationally violating, with186 thermal limits unassessed each; public metrics likewise report violated/incomplete cases. Convergence/equation validity/input integrity are not operating feasibility. No safe-operation, real-grid, unseen topology/contingency/family or practical deployment claim follows.

## Frozen artifacts and evidence custody

Primary `trial_c1597a2d68b445c4b770d7daecf764b2`, attempt `attempt_cf8f115b92f04df49ca2decd0c0ad5cc`, manifest `3f4e35002aefc2886aadbd9ab5cacbc52b519441c783e5d36c8fab08f675d968`; own augmentation `trial_bd40876f4c5540f7a40fe7f73a762706` plus original128. Native model schema regional-load-quadratic/1, training_count192, ridge1e-10; model canonical SHA:

`cf81c81f7208ff452f7be06595ff0afdcf7f4e4c8072aad1eed234ae46b4f589`.

Baseline `trial_a2989bb71afe49508465861b51f65902`, attempt `attempt_427fc8efbf694fed8a6070142be308b0`, manifest `927acff12a85621fb5056c05ac3f37a2dd1763ac81bf6e7bcec7d1ac4bc593a7`; model SHA `b4479736d4a777048b09193f423670f3ba7e550928f910e3b521cc710b41670b`.

Synthesis `trial_13fa49dde9024b41921d1ba0cbbbca29`, attempt `attempt_e032596239db408da27d71aa6ba634f3`, manifest `ce6061a0d992c44f92b5529064b424b54dc2f14b0030bddb5b4f830e6f9b8d4f`. Native path in scientific-role workspaces: `study-result-trial_13fa49dde9024b41921d1ba0cbbbca29.json`;2281626 bytes, SHA `1e8d5300400cfe042902373e6fffcb56359add858a8cf3d07a17e0c9e17a0223`. Actual models are at `author_output.native_fit_trials[trial_id].events[0].result.model`. All9 models and AUTHOR reconstructed selected192-row x/y payload are preserved there. Author payload SHA `b94ad271ee83e10a05443ece530a1b3ceb88fdfcc7a04a85a7f6612d57c64101` is NOT native ingestion attestation or independent replay.

Large native audits use `study-result-<trial_id>.json` in scientific-role workspaces and immutable service dependencies:

| Audit | Bytes | SHA256 |
|---|---:|---|
|trial_9242c815b4cb41ec8e0cdcaac67fd60b (failed assertion)|41727429|90be7ad81d55446686fba633485e787855a859f16396e930bb46a89ae0eeb35e|
|trial_a36ecb60b2d74d76a173b5aceb62d5e3|62544932|9d04dd120bef3c6e20c5ff6292cd2b48dd983c9b136fdfcd4035847ac6e54e92|
|trial_e8f5d87b4d5345d8a1011592872af906|62573561|a15f16a2ce6986f3ea1225edd20656fab7756ce6cbe5e733a1360cb3aefd6668|
|trial_636accfed9ea46eda25a0c733331d1e8|41715113|083de4f1d6f518365ae353f4a88012eaf48d56312ea9eb85a2af42293b681eeb|

Hashes/sizes above are service/publication/author fields, not Organizer-recomputed checksums. Lead_2 actually read native2.28MB synthesis and41–62MB audit sections without new computation. Cross-role scientific evidence access is established. Organizer's direct read of the synthesis basename returned workspace-path rejection; Organizer inspected full delivered sources/reports/indexes and authenticated evidence bindings, not every native coordinate/solution/weight line. Do not claim Organizer independently re-executed or inspected unavailable raw bytes.

**Full human-facing raw/model/payload shared export is incomplete:** attempts to snapshot large audits AND2.28MB synthesis returned snapshot_too_large. No successful full-package export is claimed. Retain existing native immutable artifacts; obtain authenticated lossless export/archival access, not a solve/fit rerun. Current Organizer interfaces expose no dedicated lossless byte-copy/chunk/export operation; more numerical jobs cannot fix custody. Platform archive completeness is not self-certified.

## Delivered source/report map

Paths are relative to `shared-artifacts/`:

- Prospective plan/r1 source: `bf39df6f2e7f0e29dd8aead01583c6dc17297455ff93818388999ff3c6a35594/`.
- Preflight delivery/source/full128153-byte output: `e81d9f3c732a937700d95571e6d1f45324648136ea5e94dc6ea098b3e24c2b6f/`; source SHA `f9f452bb13c2b9e3b4fde78979f708d6e499c03a031de6a7bbe35e526c892c20`.
- Main nine-file delivery: `46846f0187ff4fde0df7ee65eb303d6acf5e82c4ad67ae1da3235b9e57171772/`: LEAD-UTILITY-REPORT.md, STAGE2-LEDGER.md (all8 label identities), FIT-EVIDENCE-INDEX.md (all9 fits/attempts/manifests), PREFIT-GATE.md, AUDIT-CORRECTION.md, FROZEN-MODEL-SELECTION.md, INDEPENDENT-EVALUATION-HANDOFF.md, label_integrity_audit.py, utility_synthesis.py. This is source/reports, NOT full raw/model export.
- Audit source SHA `cb81fb5379a8beb05a65666834ac1dceddbf48871bcce1c4f8d93715a407fdde`; synthesis source SHA `bc4813926d8160cde43c79da5a02c37c287265714a424a81edcc6733d3597144`, frozen before execution. Original failed checker remains in snapshot `125431bb23dcb1d08a141f5f9c109599f9e4edfbba5b5fb1da345c70d196c600`.
- Final independent-role review: `5a6e240f12886f83b89358229be7bc8c01c6550d1bc75316b4aa702ec9f8f215/LEAD2-UTILITY-REVIEW.md`.
- Actual versioned findings: `shared_findings/7_r1_organization-97ad1aee4ff4.json` (qualified preflight) and `18_r1_organization-97ad1aee4ff4.json` (public utility,13 authenticated trial links and prospective author hypothesis assessment). Both candidate, not formal validation. Snapshot indices are publication receipts, not numerical findings.

## Authority, costs and verification boundary

Organizer read CLIENT-BRIEF, CLIENT-TASK, PROJECT-SPEC, full target/history sources and paged organization records incrementally through28 (`has_more:false`), then authored closure seq29. Scientific roles report effective contractr1, current communication-preservation guidance `command_75ea95e5f5bd48a8a5a70239b173398d` adopted with receipts; records/artifacts retain substantive requests, decisions, failures and recovery. This is not a certification of platform archive completeness. Organizer state exposes contract revision/objective/budgets/organization, not full scientific contract/guidance body or scientific trial projection; no unseen permissions or ack are inferred.

Analysis-only preflight task seq14 was claimed by Lead_1 and completedr3. Separate task seq22 explicitly permitted label/analysis/fit, claimedr2 seq24, completedr3 seq26; running specifications were not rewritten. Seq21 prospectively accepted unavailable original-file/runtime attestations ONLY as disclosed development limitations, not passed checks or changed client acceptance. Lead_2 performed independent-role source/evidence review with no numerical experiment; it supports closure but is not an external evaluator.

Observed review-entry state: **24 attempts,96833 execution ms,512 proposals spent; zero execution/proposal reservations**. Scientific-role service projections inspected by both Leads report all24 admitted jobs succeeded/exited; this includes a process-successful audit with false assertions, not24 scientific passes. Breakdown:1 preflight+1 transfer/schema+8 label+4 audit+9 fit+1 synthesis. Task23 attempts/95268 ms; overall direction24/600000-ms/512-proposal ceiling respected. Neither solves nor fits repeated. Current global limits256 attempts/7200000 execution ms/4096 proposals are larger, not permission to exceed direction ceiling. Walltime entry spent2988687/reserved1800000/available9611313 ms; tools299/3200, turns168/1600. Subscription/runtime quota unknown; no monetary-price or API-key claim. Entry counters are not final session/lifecycle totals.

## Unmet criteria and external request

1. **Fresh independent hidden utility evaluation:** unavailable to researcher tools; not performed. Public gains do not discharge formal acceptance.
2. **Independent frozen-input training replay/native ingestion proof:** unavailable/unexecuted. Author-reconstructed payload is not proof of exact native ingestion. Original baseline-file equality and independent runtime/source/image/validator loaded-byte attestations are unverified.
3. **Complete human-facing lossless model/payload/raw export:** blocked by snapshot cap; native originals remain, reviewer access exists, external custody/export support still needed.
4. Operational feasibility/real-client or unseen-family transfer remain unestablished and outside this fixed synthetic utility result.

Organizer requests the concrete external protocol in `INDEPENDENT-EVALUATION-HANDOFF.md` and `EVALUATION-REQUEST.md`: retrieve original frozen bytes/dependencies and attest custody; separately replay unchanged training; prospectively agree512 attempted fresh hidden ID+512 target cases, secret seed custody, exact/rounded overlap checks against current/public/historical data (external historical custodian needed), retained failures/no replacement and <95% valid yield stop, independent equations/features/masks/units, same-panel baseline and original joint rule. No primary switch or metric-dependent additional acquisition. Any bootstrap is fixed-model scenario uncertainty only. Counts/yield/bootstrap are proposed evidence procedures, not approved experiments or altered client utility thresholds.

This is useful delivered exploratory research with explicit incomplete requirements. Negative independent confirmation remains valid; no formal client-success, deployment, scientific-novelty or completed-run lifecycle claim is made.

## Human closing review — seq31

Reread CLIENT-BRIEF.md, current state and organization history after30 through31 (`has_more:false`), both complete final delivery files and the actual snapshot index21. Human closing-review message says no pending role deliveries remain and asks to continue only for concrete necessary work. Current authoritative records still show direction closedr3 and both tasks completedr3; execution/proposal reservations remain zero, with unchanged24 attempts/96833 execution ms/512 proposals spent. No new scientific work or result appeared.

The existing final report/external request were already preserved in snapshot `c5f7731aa7087711cf433e8f30ebc65cd3a9f39ec3ddf82e66834e01c649ecda` and handed off in organization seq30. This closing note updates the report only, not numerical evidence or scientific conclusions. Full raw/model export, external attestations, independent replay and hidden utility evaluation remain incomplete as detailed above; no new relevant capability/authorization has appeared. No concrete additional task is executable within the current closed direction and available role tools, so no direction is reopened, no experiment repeated and no acknowledgment loop requested.

Closing-entry state remains running/healthy, controlr4/contractr1; walltime spent3327601/reserved1800000/available9272399 ms, tools339/3200 and turns187/1600. The model-session reservation is distinct from zero experimental reservations. These observations do not prove research-run or session lifecycle completion. Preserve this reviewed report and EVALUATION-REQUEST.md in a final snapshot, then stop with the unmet requirements explicit.
