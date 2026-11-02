# Container PowerFlow Lab Implementation Plan

Current design: [Project design](../../PROJECT-DESIGN.md), especially research-variable controls and comparison semantics.

Goal: run a real, reproducible IEEE-118 reference trial in OrbStack Docker, independently validate it, and replay it.
Architecture: a CPU-only MATPOWER/Octave image, Python standard-library runner and independent electrical checks. Candidate solvers remain research variables; this slice supplies a reference implementation only.
Constraints: no extra VM, no paid model calls, no AAR runtime launch; preserve failures and changed-input detection.

Technical behavior: [Minimum-loop design](../../architecture/ASR-MINIMUM-LOOP.md), especially §5–§7. The local runner must preserve the same admission, manifest and attempt semantics later exposed by the service. A reference tolerance is a calibration input, not an accepted scientific threshold.

## Deliverables and verification

- [x] Pin base-image digest and MATPOWER archive checksum; build native arm64 image. Record installed package versions.
- [x] `tests/test_validation.py`: analytic two-bus reference, deliberately perturbed voltage, changed load, non-finite values, tap/shunt physics and missing thermal limits.
- [x] `powerflow_lab/validation.py`: construct admittance independently from branch data; verify full nodal balance, fixed input settings and operating constraints.
- [x] `scripts/reference_pf.m`: export effective input, output, iteration count and solver version; keep verbose solver logs.
- [x] `powerflow_lab/runner.py`: immutable attempt directories, request identity, process timeout, code/input hashes, atomic terminal manifests and replay.
- [x] `tests/test_runner.py`: duplicate requests, changed requests, retained failure, artifact tampering and replay behavior.
- [x] `compose.yaml`: read-only root, dropped capabilities, offline runtime, CPU/memory limits, explicit result mount.
- [x] Run real case118; verify sizes, solver convergence and independently computed residual. Reject modified voltage and modified input fixtures.
- [x] Repeat completed request without new attempt; replay into a fresh trial and compare electrical outputs.
- [x] Run a deliberately truncated Newton solve; retain failure and logs.
- [x] Document commands, measured results, limitations and accepted solver-research scope.

## Test contract

```python
report = validate(input_case, solved_case, tolerance_pu=1e-7)
assert report['equation_valid']
assert report['input_preserved']
```

A changed load must be rejected even if the returned voltage solves the changed problem. Unknown limits must stay unassessed.
A terminal execution status is separate from scientific validation. A failed reference solve does not establish infeasibility.

## Execution order

Write and run validator tests before implementation. Build the numerical image while developing the runner. Run runner failure-path tests before real integration. Finish with actual reference, failed-solve and replay evidence. No unit test substitutes for a numerical smoke test.

## Verified scope and limits

Evidence: [P1 numerical lab](../../validation/P1-NUMERICAL-LAB.md). All listed reference-slice deliverables have been exercised. The executor is local and trusted; generalized candidate execution, runtime disk quotas, database budget admission and active-process reconciliation remain P2/P3 work. Dependency package inventory and final image ID are recorded; APT rebuild sources are not snapshot-pinned.
