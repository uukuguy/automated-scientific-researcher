# Container PowerFlow Lab Implementation Plan

Current design: [Project design](../../PROJECT-DESIGN.md), especially research-variable controls and comparison semantics.

Goal: run a real, reproducible IEEE-118 reference trial in OrbStack Docker, independently validate it, and replay it.
Architecture: a CPU-only MATPOWER/Octave image, Python standard-library runner and independent electrical checks. Candidate solvers remain research variables; this slice supplies a reference implementation only.
Constraints: no extra VM, no paid model calls, no AAR runtime launch; preserve failures and changed-input detection.

## Deliverables and verification

- [ ] Pin base-image digest and MATPOWER archive checksum; build native arm64 image. Record installed package versions.
- [ ] `tests/test_validation.py`: analytic two-bus reference, deliberately perturbed voltage, changed load, non-finite values, tap/shunt physics and missing thermal limits.
- [ ] `powerflow_lab/validation.py`: construct admittance independently from branch data; verify full nodal balance, fixed input settings and operating constraints.
- [ ] `scripts/reference_pf.m`: export effective input, output, iteration count and solver version; keep verbose solver logs.
- [ ] `powerflow_lab/runner.py`: immutable attempt directories, request identity, process timeout, code/input hashes, atomic terminal manifests and replay.
- [ ] `tests/test_runner.py`: duplicate requests, changed requests, retained failure, artifact tampering and replay behavior.
- [ ] `compose.yaml`: read-only root, dropped capabilities, offline runtime, CPU/memory limits, explicit result mount.
- [ ] Run real case118; verify sizes, solver convergence and independently computed residual. Reject modified voltage and modified input fixtures.
- [ ] Repeat completed request without new attempt; replay into a fresh trial and compare electrical outputs.
- [ ] Run a deliberately truncated Newton solve; retain failure and logs.
- [ ] Document commands, measured results, limitations and accepted solver-research scope.

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
