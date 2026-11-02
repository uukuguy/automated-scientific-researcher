# Actual AAR organization and replaceable researcher

`upstream.json` pins source revision, file hashes and source URL. No upstream
source is vendored. The pinned repository has no license files; redistribution
terms remain unconfirmed. These scripts prepare a private local checkout and
apply tracked minimal adaptations without editing the ignored original.

The numerical/control environment stays small. Actual upstream integration uses
an optional CPU-only dependency set, locked in the root lockfile:

```sh
uv sync --locked --extra aar
uv run --extra aar python -m integrations.aar.prepare_upstream --destination artifacts/aar-private-UNIQUE
uv run --extra aar python -m integrations.aar.loop_patch artifacts/aar-private-UNIQUE
uv run --extra aar python -m unittest discover -s tests -v
```

Without the optional dependencies the upstream integration tests explicitly
skip. Full upstream W2S training/CUDA dependencies are not installed. Importing
the real Claude Agent SDK is required by pinned upstream source, but this ASR
profile invokes pi subscription authentication; no Claude/API call or paid
fallback follows from installing that import dependency.

`upstream_adapter.py` loads the **actual pinned** Experiment, Idea, Finding and
related Flask-SQLAlchemy model classes. ASR adds explicit identity/evidence
columns to those mappings. Actual upstream ORM queries read the stored rows;
owner writes use those mapped column definitions/defaults inside the same
SQLite transaction as ASR control. A real Experiment row and its
`aar-experiment:{numeric-id}` ASR binding are created atomically and replay
returns the original row. This ID is no longer a fabricated runtime marker.
The underlying integer is an upstream identity, not a numerical trial or native
agent session ID. Existing legacy rows retain their execution mode.

ASR remains the authoritative owner for contracts, budgets, trial admission,
commands, immutable findings and scientific evidence. AAR Finding/Forum is a
rebuildable organization projection: each ASR finding revision has its own
actual Finding row, explicit run/project/revision and immutable evidence refs.
Author claims populate content and candidate context; legacy PGR/accuracy fields
remain null. Project-scoped forum reads include prior runs and revisions.
The bridge exposes these shared records to researchers. The actual upstream
FindingsSync is reused with local fetching and version-aware filenames.

Successful local snapshots also use actual upstream Finding snapshot fields
(`commit_id`, `files_snapshot`) plus an explicit local path, rather than S3.
Registration checks scope and file hashes; restoration rechecks content and
refuses an existing destination. The bridge retains its bounded atomic snapshot
publisher. A failed model snapshot request is retained as failure; it cannot be
reported as a snapshot just because this adapter supports one.

`upstream_worker.patch` explicitly disables the actual legacy worker in ASR mode
and rejects direct legacy execution of an ASR Experiment before deployment
imports or credentials. The patch is validated before application and its
receipt/hash checked by the adapter. No legacy RunPod/local queue competes for
an ASR research run. The ASR supervisor still owns numerical attempts.

`loop_patch.py` adds bounded-session/control hooks to the actual pinned
AutonomousAgentLoop. `researcher.py` keeps that upstream `run()` as the single
outer research-loop owner and injects the selected pi session implementation.
It requires the real Experiment mapping before execution. Domain prompts,
ASR tools, shared findings and local snapshots replace W2S-specific tools and S3
behavior. Runtime session IDs and fenced ASR sessions remain separate.

The previous acceptance03/04 evidence used the standalone ASR organization
bridge. It cannot retroactively establish that the original upstream loop/ORM
was active. The new optional integration tests prove actual ORM mappings,
shared revision roundtrips, local snapshot restoration and disabled legacy
execution. A model-backed acceptance through `--aar-checkout` is separately
required to establish that assembled autonomous trajectory.
