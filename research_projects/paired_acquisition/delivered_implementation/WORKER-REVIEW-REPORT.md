# Worker 2 — executed adversarial implementation review

## Scope and provenance
Reviewed actual PREVIOUS-PROTOCOL.md, PREVIOUS-PROTOTYPE.py, P4-SAMPLER.py, Lead plan snapshot 09808c6a9549445702f73e4fbc7db34b5ee8181ea829396495478e8662b2baf1 and full paired_generator.py from snapshot 044870fa16118d9a8942ebd193ff2c8483b89c59c42eb1596bfe7bd7c67e79b9. Read original trial output head/check summary and regenerated full candidate matching its recorded SHA; did not manually inspect every coordinate line. Original execution trial_ec62b369aab54cb5932462a0e2b037fa exited succeeded; its reported deterministic rerun and poison/delete-label checks are true.

Source inspection: constants, stream seeds, 32/16/16/16/16 counts, clipped ten-percent diagnostic envelope, original median interpolation, anchor-then-fraction order, six-decimal rounding and fixed arm order match protocol. Only x is accessed by generate. Historical sampler is different and was not substituted. Fixed loops have no resampling path. Candidate is descriptive, not an admitted adapter manifest.

## Actual executed reviewer evidence
Task adversarial-generator-review r2; hypothesis organization-dd58b2d04033/paired-generator-conformance r1. Source review_generator.py was snapshotted before submission at dd752cda09fafa51f2e02f43eb89b256b21f862614c3c0cd438c779b25b71853 (file SHA 05aadf2fdf6d1a6490258a1842e757b26a3fe164ff435767c64c395343f2eb93). It copies original imports/constants/digest/generate literally, replacing main with reviewer tests. QMC monkeypatch is confined to one instrumentation check and restored afterward; no original generator fix is claimed.

Trial trial_7e01fb758353401cb051b8b59690d68d exited succeeded, 1526ms, execution attempt attempt_f36ba22b112a49d1ac89712bd80a3918, manifest fae0a4de615a411940aabc917bef578d45a0b46da5ea65c68df0b8088abe06f1. NumPy 2.4.6 / SciPy 1.18.1. Complete output study-result-trial_7e01fb758353401cb051b8b59690d68d.json: 545769 bytes, SHA 4c640caea14bf6bf95486ec5652cccc5a59ede9b1a33fc0a5531cd026d2ecc4d. All 12 expected observations true (tail lines 19152..19191):

- Regenerated baseline accepted and exactly matches original full candidate hash f28262870d046f46d3c22c61e06df639b789966ee459c9d4723348bd3bad0176.
- Coordinate-only rows with a trap on non-x item access leave full result unchanged.
- NaN, infinity, out-of-domain, empty, malformed and degenerate inputs rejected with structured failure results.
- Injected exact generated G coordinate into id_dev: rejected with public_exact and public_rounded6 collisions; complete generated blocks unchanged, preserved in output rather than resampled.
- Instrumented collision case made exactly 32 public QMC random calls, fixed seeds/counts for four LHS streams per seed; instrumented/uninstrumented complete results identical. Bridge RNG internal calls were not instrumented; its fixed two draws are source-inspection evidence only.
- Independent literal frozen arm-order check passes baseline.
- Deliberately reversed TT order is accepted by built-in self-checks: useful negative-control failure of the oracle, not an accepted alternative manifest.

## Concrete finding: medium test-oracle gap, not an observed baseline-generation error
Location: paired_generator.py ARMS constant and arms construction/check loop (approximately lines 83–98). Trigger: set ARMS['TT']=('TB','TA','T0'). The implementation generates that incorrect frozen order and still returns accepted=true with every built-in check true. The checker derives both expected order and constructed arms from the same mutable mapping. Negative-control hash 897d3f9c02dae30ab88acce56b6d0f551a10b903eebec3269af5da21750fd1d4; first_order=['TB','TA','T0'] in complete reviewer output. Consequence: the built-in acceptance flag alone cannot establish frozen protocol conformity after a mapping regression. Baseline source is correct and passes a separate literal check. Remedy: keep independent literal contract assertions on seed/name/order/counts and coordinate/input pins in an external acceptance checker, rather than treating generator self-consistency as protocol validation. No patch or retest is claimed here.

## Recommendation and limits
Lead may accept the exact pinned baseline artifact for bounded implementation acceptance, explicitly conditioned on the external literal contract check and retaining the oracle gap. Do not present built-in accepted as a generic validator. Freeze source, environment, input-coordinate digests and candidate hash before any separately authorized labels. All deliberate failures are retained. One reviewer job of <=2 used; no failed jobs/retries, labels, fit, hidden evaluation or host numerical work. Cross-seed/cross-block collision injection, rounded-only collision injection and bridge draw instrumentation were not executed. Original collision checks were inspected and original full candidate reproduced. No independent physics, scientific utility, held-out overlap, full paired-comparison or P5-completion claim.
