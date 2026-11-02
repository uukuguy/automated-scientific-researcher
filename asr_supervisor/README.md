# Trusted execution manager

`Supervisor` consumes one admitted `asr_dispatch` attempt and its frozen
`execution_request`. It does not choose experiments or automatically retry.
`ExecutionStore` is an internal control-service adapter over the same SQLite
file as ControlService, not a public authentication API. The local CLI requires
trusted host access:

```sh
uv run python -m asr_supervisor --db /path/control.db --evidence-root /path/evidence \
  --attempt attempt_ID --owner supervisor_ID
```

Add `--reconcile` after the prior lease expires to inspect/stop the original
container and recover publication. Reconciliation never launches another
container. A held host file lock prevents takeover while the old local executor
is still advancing. A missing/unknown container cannot release its reservation;
resolve its identity and process facts explicitly. Stopped containers are retained
for inspection and can be removed by an operator after evidence is registered.

The production backend supports the pinned MATPOWER reference profile only.
Container ID, deterministic name, attempt/trial/run labels and creation epoch
are retained. Network, mounts, user and resource settings match the existing P1
reference restrictions. Arbitrary candidate code and independent evaluator
isolation are not implemented by this module. `ProcessBackend` is for trusted
local tests/debugging only and does not recover process identities after restart.

The supervisor polls process state, heartbeats its lease, enforces an external
solver timeout and observes stop/cancel gates. Pause blocks claims and the final
pre-start gate; work already running continues. Publication records the admitted
trial and attempt unchanged. Inventory/hash checks and atomic directory rename
precede a fenced transaction settling all reserved dimensions and recording
terminal execution facts. Unknown execution retains reservations and closes
admission. Recovery with uncertain metering conservatively consumes the original
reservation and marks usage estimated. Actual wall time includes container
setup/teardown; overruns remain in the ledger. The 100 MiB/100-file limit is a
publication limit, not a runtime disk quota. Execution success and independent
numerical validity remain separate in the manifest and validation artifact.
