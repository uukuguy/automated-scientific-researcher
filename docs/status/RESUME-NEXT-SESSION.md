# Live Session Checkpoint

> Updated: 2026-11-03. Active checkpoint; no final handoff or P4 closure.

## User intent

Simulate the human researcher's actual project and have ASR solve it (D026).
A target trainable method performs poorly on some OOD regimes; determine whether
similar-distribution augmentation helps and how to generate useful data (D025).
Do not ask the human to design samplers or wait for unavailable real-client data.
Developer supplies the client project and infrastructure; AAR owns the research.

## Actual state

- P3 complete; P4 active. New simulated client package is implemented under
  research_projects/ood_augmentation. Real labels: 320/320 equation-valid;
  fixed synthetic case118/PV-PQ, operating violations and missing thermal ratings
  explicit. No operational-feasibility or real-client benefit claim.
- Public train/ID-dev/OOD-diagnostic: 128/32/32; private test:64/64. Fixed quadratic
  surrogate ID voltage RMSE6.678335356298293e-7 pu versus OOD9.20150915545494e-5 pu.
  Actual preparation root: artifacts/p4-simulated-client-001. Preserve unchanged.
- Actual AAR/pi intake root: artifacts/p4-intake-001; project ood-client-ef6293124853;
  run research_bb9205963bd144b898d1bc46c4dbf1ad. Pinned prepared checkout:
  artifacts/p2-aar-private-20261102-final-preflight.
- First intake failed with fetch failed; direct network timed out. Resumed SAME
  run via configured HTTP/HTTPS proxy http://127.0.0.1:7897. No API keys/fallback.
  Final total216397/300000ms,11/40turns,21/100tools; both sessions exited;
  all reservations zero. Numerical budgets zero. Control and actual AAR paused.
- ASR authored two prospective exploratory hypotheses and RESEARCH-INTAKE.md,
  snapshot b73de0118a6f906ae26e3348cc5de04ca5dda489eac837f5e0054e1ce7c81082.
  Its mixed-regime/bridge/global augmentation design is UNTESTED, not developer
  advice. Its request for704solves is not authorized budget or completed work.
- Original client preparation root is denied to pi by actual macOS sandbox;
  denial probes retained. This is targeted filesystem isolation, not a claim of
  unrestricted runtime containment. Private seeds/data never copied to workspace.
- ASR found native read's50KB single-line issue. Lossless<=40000-byte JSONL pages
  now exist in workspace/client-data with source hashes. CLIENT-ADDENDUM.md gives
  exact mapping/distributions and original ID acceptance predicate; original files
  unchanged. Human guidance recorded, NOT yet acknowledged; Control revision5.
  AAR projection synchronized. No further model session has read the addendum.

## Current implementation checkpoint

Development profile `ood-study-development/1` is implemented through the existing
Control/asr_dispatch/Supervisor ledger. Tools: isolated author Python analysis,
1..64 fresh-coordinate labels with immutable augmentation/probe role, unchanged
trainer consuming only verified augmentation trial evidence. sample_proposals is
a separate conservative compute permit count; actual completed rows stay explicit.
No final-test capability. Image manifest artifacts/p4-worker-image-002/manifest.json;
image sha256:091c3ae6729e2afe32f9ff6aeea5becff172858659911be21986e20f5933cc92.
Original client project.py and all320 raw preparation hashes are unchanged.

## Next concrete work

Connect same-run continuation to the new bridge profile and record a finite
successor resource contract before actual AAR execution. Do not reset prior
216397ms,11turns,21tools. User continues to authorize advancing the simulated
project on subscriptions/local compute; finite limits must be recorded explicitly,
with their measured purpose and recovery rather than inferred unlimited scope.
The same actual AAR run is NOW RUNNING under contract revision2. Process tool session29412; log artifacts/p4-intake-001/study-launch-001.log; per-session events under study-*/native-events.jsonl. Do not start another owner. Baseline fit trial_6e19bad026b94c24b339eb7525ba18f1 succeeded. Recorded limits file integrations/runtimes/ood-study-limits.json: model total1500000ms/140turns/300tools,40 jobs/2400000ms,768 proposal permits; prior consumption retained. The current session caps at1200s/100turns/200tools; no automatic extension.
Then implement frozen final-test release/independent performance evaluation;
P4 requires actual researcher experiments and supported findings, not these tests.
Keep the client private root and all controller/evidence material denied to pi.

## Verification and commit

304 core tests pass (19 explicit environment skips);13 scientific tests pass;
four real Docker tests pass:64 labels plus baseline/augmentation fit, isolated
analysis, timeout, output overflow. No leftover owned study containers. Bridge
profile preflight and original client integrity verified. Details are in
`docs/validation/P4-DEVELOPMENT-TOOLS.json`. Development slice committed as809bdf7;
prior simulated client/intake is commit76b8c98. A new same-run model session is active as described above. Continuation launcher and its two tests are not yet committed.

## Newest live checkpoint (supersedes earlier session pointers)

Development slice is809bdf7. Current uncommitted work adds same-run continuation,
backpressure recovery, request-limit deferral, independent final evaluator and
final/synthesis launchers. Do not revert these files. Actual continuation1 failed
at256 pending records, baseline fit retained. Continuation2 completed704 labels
and nine augmented fits, then22-input analysis exceeded12 and paused. Both costs
retained; no model/compute cap increased. Fixed queue backpressure plus small stop
poll; fixed request-size errors to defer only the request. Recovery guidance is
recorded. Continuation3 is NOW ACTIVE via exec session14782; log study-launch-003.log.
At last check31 succeeded trials,704 proposal permits consumed, all ten original
fits retained. Native producer output contains encrypted provider reasoning;
inspect event types/public text only, never print full native message objects.

Overall model total remains1500000ms,40jobs,768proposals; before current active
session historical model consumption772986ms. Current session reserves727014ms.
No automatic budget extension. Track remaining time before synthesis.

Independent final code is implemented and tested (tests/test_ood_final*,
asr_evaluation/ood_{metrics,worker,backend}.py, asr_service/ood_final.py).
Image artifacts/p4-final-image-002/manifest.json:
sha256:cd5dc68c73d6c397c838dff732111ee72d90bb5161243690ca3d12ea06a90012.
Real final Docker engineering test used PUBLIC training rows as artificial test
samples; actual private test remains unopened by research/evaluation. Final CLI
requires BOTH FINAL-TEST-PROPOSAL.md/json in one actual matching AAR snapshot,
replays the selected fixed training in a new container first, then publishes a
controller-only confirmation contract and admits one immutable final protocol.
Run integrations.runtimes.ood_finalize dry first, then --execute-frozen-evaluation
when AAR is paused/exited and proposals exist. No new budget needed; use remaining
compute. After independent result, run ood_study --synthesis-only using the same
root/client/image002 development manifest/checkout/proxy; it exposes no experiments,
uses remaining model balance, and preserves an evidence-linked final report/finding.
Then inspect claims, finish Control and sync actual AAR lifecycle, publish sanitized
evidence and update P4 status honestly. Private rows stay in denied controller paths.

Most recent full suite before final frontend additions:311 passed/skipped19;
focused final math/admission3, final snapshot1, real final Docker1 passed. Re-run
combined suite and changed Docker profiles before final completion claims.
