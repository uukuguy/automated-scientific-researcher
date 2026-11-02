# AAR organization bridge

`upstream.json` pins the inspected AAR tree. `python -m integrations.aar.prepare`
checks its revision, clean status and file hashes; `--destination PATH` creates a
new private detached checkout and refuses existing targets. No upstream source
is vendored. The pinned tree has no license files, so redistribution terms remain
unconfirmed.

`bridge.py` retains the research-organization concepts needed by ASR: shared
revisioned findings, immutable local code/note snapshots, research-run recovery
state and evidence references. `ControlService` owns contracts, trial admission,
budgets and guidance. `Supervisor` owns real numerical execution. The model cannot
publish independent validation status. Snapshot creation is bounded, rejects
symlinks/path traversal, publishes atomically and verifies existing content.
Accepted trial replay returns the same identity and does not re-execute terminal
work.

The present pi acceptance runs the ASR bridge, **not** the pinned AAR
`AutonomousAgentLoop` or its `Experiment` ORM. The external Experiment ID is an
explicit runtime-adapter identity, not proof of an upstream database record.
No upstream research loop patch or actual AAR backend deployment is claimed.
The chosen runtime replaces the original Claude SDK session implementation;
future upstream/backend integration must preserve explicit identity mappings.
Guidance is readable in state; reading alone does not prove delivery, adoption
or an authoritative acknowledgement receipt.
