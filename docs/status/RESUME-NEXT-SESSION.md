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

## Next concrete work

Implement the minimal admitted scenario-labeling, unchanged-trainer and independent
final-evaluation profile needed for this actual researcher plan, then resume its
existing run/hypotheses with a recorded compute/model contract. Do not bypass
Control or disguise a developer-run augmentation as ASR science. The old fixed-case
profile cannot serve this training task. The intake launcher currently supports
only initial launch or one pre-intake provider-failure recovery, not post-intake
research continuation; extend deliberately rather than resetting the run.

Check the researcher note before deciding tool requirements. Its unresolved data
reading and predicate ambiguities were corrected via the client addendum. Do not
rewrite its original snapshot or hypotheses. No model is currently running.

## Verification and pending commit

293 core tests,15 explicit Docker skips;9 scientific pytest tests passed. Added
public-page preservation/private-exclusion test then verified3 focused intake/
delivery tests. Numerical preparation verified all320raw artifact hashes. Final focused25 tests passed after review, and material preflight remains valid.
Implementation and evidence are ready for the task commit. Credentials
and native transcripts remain ignored. Prior P3 immutable reports unchanged.
