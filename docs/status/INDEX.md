# docs/status INDEX

Catalog of repository state files.

Status legend: 🟢 active; 🟡 decision history; 🔴 superseded; ⚫ scratch.
Read active files on resume. Historical recommendations may no longer apply.
Register each new status file here. Register archive buckets as one row per bucket.

## Active

| File | Status | Purpose |
|---|---|---|
| `CURRENT-STATE.md` | 🟢 active | Structural snapshot. |
| `JOURNAL.md` | 🟢 active | Append-only event log. |
| `RESUME-NEXT-SESSION.md` | 🟢 active | Session recovery point. |
| `INDEX.md` | 🟢 active | File catalog. |
| `DECISIONS.md` | 🟢 active | Accepted scope and architecture decisions. |
| `BOOTSTRAP-PREFLIGHT.md` | 🟢 active | Dated WP1 environment evidence; recheck before setup. |

## Decision history

| File | Status | What it recorded | Outcome / supersession |
|---|---|---|---|

## Archived

| Bucket | Files | Notes |
|---|---|---|

## Knowledge routing

Technical invariants belong in CLAUDE.md; architectural choices belong in DECISIONS.md.
Collaboration preferences belong in MEMORY.md. Complete evidence stays in indexed topic files.

## External anchors

- `docs/plans/WORKLIST.md` — canonical packages and acceptance gates.
- `docs/IEEE118_OOD_Sample_Expansion_Task_v2_2.md` — research objective and requirements.

- `docs/superpowers/specs/2026-11-02-bounded-aar-design.md` — bounded research system design and implementation boundaries.
