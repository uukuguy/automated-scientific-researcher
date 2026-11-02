# Isolated frozen-material recheck

`Replay(root).run(key, source_path, manifest_hash, trial_id=..., execution_attempt_id=...,
research_run_id=..., timeout_seconds=60, mode='check')` checks an existing terminal
`asr-managed-attempt/1` manifest and every listed artifact. Source paths are a
trusted host interface; this package does not authenticate callers or resolve
Control project permissions. Keys bind the full request; repeated completed
requests verify and return their original receipt. Pending work blocks reruns.
`reconcile(key)` inspects and, if necessary, stops the exact labelled container
before publishing an interrupted receipt. A missing/unreachable container remains
unresolved. No automatic retry or process-state guessing occurs.

Only `matpower-case118-flat/1` with `fixed-pv-pq-single-slack/1` is supported.
The original JSON input must equal the tracked scientific calibration fixture
and its hardcoded SHA-256 `bc436a7e82eb7a4d0d571942189795a5ac9aee29672804e603b56b5400b9ca14`.
This is different from the MATPOWER `.m` case hash. Candidate-provided input cannot
redefine the equations. Sources with missing or different frozen tolerance
(`1e-7` pu) or validator source hash are rejected. The pinned validator hash is
`090499c1c180e63215dd444a7f3a0cb10da02a724904e3a684c74ae5beb562d3`.
The image is the already available MATPOWER environment by its immutable ID,
`sha256:d40dc592523126c64abb42a730c4cc9652083efa5593d01e56238202200d9831`;
its entrypoint is overridden with isolated Python, without running MATPOWER.

Only verified private copies of original input, frozen solution, source manifest,
source request and evaluator code are mounted. Inputs and evaluator code are
read-only; output has its own mount. Actual Docker inspection is checked before
start: image, identity, entrypoint, environment, mounts, user, network, privileges
and resource restrictions. The container has no external network, Docker socket,
candidate workspace or native login mount. It runs as UID/GID 65532 with a
read-only root filesystem, dropped capabilities, no-new-privileges, 256 MiB
memory/swap ceiling, one CPU, 32 PIDs and 16 MiB temporary storage. Input is capped
at 4 MiB per file, 16 MiB total and 100 artifacts. Docker operations have five-second
timeouts. `timeout_seconds` bounds the running polling stage, at most 60 seconds;
Docker setup, inspection and cleanup operations can each add five seconds.
This is not a hard 60-second whole-operation deadline. Docker stdout size is
checked after subprocess capture, rather than imposing a hard capture-memory
limit; only fixed trusted metadata commands are used and container logging is
disabled. Stopped labelled containers are retained for audit.

The original attempt remains untouched. Output includes its own manifest and
hash inventory, copied material, frozen evaluator source, launch/exit inspections,
terminal outcome and result. Publication metadata must match those hashed raw
artifacts, including negative results and exact source identity. This detects
inconsistent evidence; it does not make files tamper-proof against the trusted
host owner. A completed container does not imply valid equations or operating
limits. Missing ratings remain unassessed. This replays numerical **material**;
it does not rerun a candidate method, establish held-out generalization, publish
an authoritative Validation or reserve/settle Control budgets. Those integrations
remain separate. It does not isolate a researcher running on the host or prove
arbitrary candidate-code isolation.

Run unit checks with:

```sh
uv run python -m unittest tests.test_evaluation_replay -v
ASR_REAL_DOCKER=1 uv run python -m unittest tests.test_evaluation_replay -v
uv run python -m scripts.evaluation_probe --root data/isolated-evaluation-acceptance
```

The probe script uses actual retained P2 evidence plus explicitly synthetic
corrupted copies for negative tests. These copies are not admitted executions.
Its receipt contains sanitized inspection facts and preserves the distinction.
